import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any, List

from sqlalchemy.orm import Session

from backend.benchmarks.base import BaseBenchmark, resolve_data_file
from backend.lm_studio.client import LMStudioClient

logger = logging.getLogger(__name__)

# Python runs locally via unittest; JS/Java/Go/Rust/C++ use Docker sandboxes with pre-installed deps
LANGUAGE_CONFIGS = {
    "python": {
        "runner": "local",
        "test_cmd": lambda src_name, tmpdir: [
            sys.executable, "-m", "unittest", src_name.replace(os.sep, '.').replace(".py", ""),
        ],
    },
    "javascript": {
        "runner": "docker",
        "image": "benchmax-node",
        "test_cmd": lambda src_name, tmpdir: [
            "jest", "--no-coverage", "--passWithNoTests",
        ],
    },
    "java": {
        "runner": "docker",
        "image": "benchmax-java",
        "test_cmd": lambda src_name, tmpdir: [
            "bash", "-c",
            "cd /workspace && "
            "javac -d /tmp/classes src/main/java/*.java 2>&1 && "
            "javac -d /tmp/classes -cp /tmp/classes:/opt/jars/junit.jar:/opt/jars/assertj.jar src/test/java/*.java 2>&1 && "
            "java -jar /opt/jars/junit.jar --classpath /tmp/classes:/opt/jars/assertj.jar --select-class " +
            _java_test_class(src_name) + " 2>&1",
        ],
    },
    "go": {
        "runner": "docker",
        "image": "benchmax-go",
        "test_cmd": lambda src_name, tmpdir: ["go", "test", "./..."],
    },
    "rust": {
        "runner": "docker",
        "image": "benchmax-rust",
        "test_cmd": lambda src_name, tmpdir: ["cargo", "test", "--", "--test-threads=1"],
    },
    "cpp": {
        "runner": "docker",
        "image": "benchmax-gcc",
        "test_cmd": lambda src_name, tmpdir: [
            "bash", "-c",
            "cd /workspace && "
            "g++ -std=c++20 -I/usr/local/include -DEXERCISM_RUN_ALL_TESTS -DEXERCISM_TEST_SUITE -DCATCH_CONFIG_MAIN -o /tmp/test " +
            src_name.replace('.cpp', '_test.cpp') + " 2>&1 && "
            "/tmp/test"
        ],
    },
}


def _java_test_class(src_name: str) -> str:
    stem = Path(src_name).stem
    if stem.endswith("Test"):
        return stem
    return stem.replace("Test", "") + "Test"


class AiderPolyglotBenchmark(BaseBenchmark):
    requires_docker = True

    def __init__(self, db: Session, client: LMStudioClient, quick_test: bool = False):
        super().__init__(db, client, quick_test)
        self._docker_executors = {}

    @staticmethod
    def _activate_all_tests(language: str, test_code: str) -> str:
        if language == "javascript":
            test_code = re.sub(r'\bxtest\b', 'test', test_code)
            test_code = re.sub(r'\bxit\b', 'it', test_code)
            test_code = re.sub(r'\bxdescribe\b', 'describe', test_code)
            return test_code
        elif language == "java":
            return re.sub(r'^\s*@Disabled\b.*$', '', test_code, flags=re.MULTILINE)
        elif language == "rust":
            return re.sub(r'^\s*#\[ignore\]\s*\n?', '', test_code, flags=re.MULTILINE)
        return test_code

    def load_dataset(self) -> List[Dict[str, Any]]:
        filename = "aider_polyglot_mini.json" if self.quick_test else "aider_polyglot_full.json"
        self.dataset_path = resolve_data_file(__file__, filename)
        if not self.dataset_path:
            logger.warning("Full Aider Polyglot dataset not found, falling back to mini dataset")
            self.dataset_path = resolve_data_file(__file__, "aider_polyglot_mini.json")
        samples = self._load_json_cached(self.dataset_path)
        for sample in samples:
            sample["test_code"] = self._activate_all_tests(sample["language"], sample["test_code"])
        return samples

    @staticmethod
    def _extract_edited_code(raw_text: str) -> str:
        if not raw_text or not raw_text.strip():
            return ""

        lang_tags = r"(python|javascript|js|java|go|rust|cpp|c\+\+|c|csharp|typescript|ts)"
        patterns = [
            re.compile(r"```" + lang_tags + r"\s*\n(.*?)```", re.DOTALL | re.IGNORECASE),
            re.compile(r"```\s*\n(.*?)```", re.DOTALL),
            re.compile(r"```(.*?)```", re.DOTALL),
        ]

        for pat in patterns:
            m = pat.search(raw_text)
            if m:
                code = m.group(1).strip()
                if code:
                    return code

        lines = raw_text.strip().split("\n")
        code_lines = []
        for line in lines:
            s = line.strip()
            if not s:
                continue
            if any(s.startswith(kw) for kw in [
                "import", "from", "def ", "class ", "function", "const ",
                "let ", "var ", "export", "public ", "private ", "package",
                "use ", "fn ", "struct ", "enum ", "#include", "using ",
                "package ", "pub ", "impl ",
            ]):
                code_lines.append(line)
            elif code_lines:
                code_lines.append(line)

        if len(code_lines) > 2:
            return "\n".join(code_lines).strip()

        return raw_text.strip()

    @staticmethod
    def _build_prompt(sample: Dict[str, Any]) -> str:
        lang = sample["language"]
        parts = [
            f"Edit the file `{sample['source_path']}` to make all tests pass.",
            "",
            "Instructions:",
            sample["instruction"],
            "",
            f"Current source code (`{sample['source_path']}`):",
            f"```{lang}",
            sample["source_code"],
            "```",
            "",
            "Output ONLY the edited file content (the complete file).",
        ]
        return "\n".join(parts)

    @staticmethod
    def _write_temp_workspace(sample: Dict[str, Any], edited_code: str) -> str:
        tmpdir = tempfile.mkdtemp(prefix="aider_")
        lang = sample["language"]

        def write_file(rel_path: str, content: str):
            full = os.path.join(tmpdir, rel_path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)

        write_file(sample["source_path"], edited_code)

        test_content = sample["test_code"]
        if lang == "cpp":
            header_name = Path(sample["source_path"]).stem + ".h"
            source_name = Path(sample["source_path"]).name
            test_content = re.sub(
                r'#include\s+"' + re.escape(header_name) + r'"',
                '#include "' + source_name + '"',
                test_content,
            )
        write_file(sample["test_path"], test_content)

        extra_files = sample.get("extra_files") or {}
        for rel_path, content in extra_files.items():
            write_file(rel_path, content)

        if lang == "javascript":
            extra = extra_files
            if "package.json" not in extra:
                write_file("package.json", json.dumps({
                    "name": "aider-polyglot-js",
                    "private": True,
                    "jest": {
                        "transform": {"^.+\\.jsx?$": "babel-jest"},
                    },
                }))
            if "babel.config.js" not in extra:
                write_file("babel.config.js",
                           "module.exports = { presets: ['@babel/preset-env'] };\n")

        if lang == "go":
            has_mod = any(k.endswith("go.mod") for k in (extra_files or {}) or [])
            if not has_mod:
                write_file("go.mod", "module aider_polyglot\n\ngo 1.22\n")

        return tmpdir

    def _get_executor(self, image_tag):
        if image_tag not in self._docker_executors:
            from backend.sandbox.docker_executor import DockerExecutor
            self._docker_executors[image_tag] = DockerExecutor()
        return self._docker_executors[image_tag]

    def _run_local_test(self, tmpdir: str, sample: Dict[str, Any]) -> Dict[str, Any]:
        config = LANGUAGE_CONFIGS[sample["language"]]
        test_name = sample["test_path"]
        cmd = config["test_cmd"](test_name, tmpdir)
        logger.info("Running local test: %s", " ".join(cmd))
        try:
            result = subprocess.run(
                cmd, cwd=tmpdir, capture_output=True, text=True, timeout=30,
            )
            return {
                "success": result.returncode == 0,
                "stdout": (result.stdout or "")[:5000],
                "stderr": (result.stderr or "")[:2000],
                "error": None,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "stdout": "", "stderr": "", "error": "Test timed out (30s)"}
        except Exception as e:
            return {"success": False, "stdout": "", "stderr": "", "error": str(e)}

    def _run_docker_test(self, tmpdir: str, sample: Dict[str, Any]) -> Dict[str, Any]:
        lang = sample["language"]
        config = LANGUAGE_CONFIGS[lang]
        image_tag = config["image"]
        src_name = sample["source_path"]
        test_cmd = config["test_cmd"](src_name, tmpdir)

        executor = self._get_executor(image_tag)
        if not isinstance(test_cmd, list):
            test_cmd = ["bash", "-c", test_cmd]

        logger.info("Running Docker test for %s on %s...", sample["task_id"], image_tag)
        kwargs = {}
        if "benchmax-node" in image_tag:
            kwargs["env"] = {"NODE_PATH": "/usr/local/lib/node_modules"}
        return executor.execute_command(
            command=test_cmd,
            image_tag=image_tag,
            workspace_dir=tmpdir,
            timeout=120,
            **kwargs,
        )

    def _run_tests(self, tmpdir: str, sample: Dict[str, Any]) -> Dict[str, Any]:
        lang = sample["language"]
        config = LANGUAGE_CONFIGS.get(lang)
        if not config:
            return {"success": False, "stdout": "", "stderr": "",
                    "error": f"Unknown language: {lang}"}

        if config["runner"] == "local":
            return self._run_local_test(tmpdir, sample)
        elif config["runner"] == "docker":
            return self._run_docker_test(tmpdir, sample)
        return {"success": False, "stdout": "", "stderr": "",
                "error": f"Unknown runner: {config['runner']}"}

    async def evaluate_sample(self, sample: Dict[str, Any],
                              params: Dict[str, Any],
                              model_name: str) -> Dict[str, Any]:
        prompt = self._build_prompt(sample)
        task_id = sample["task_id"]

        gen = await self.client.generate_completion(
            prompt=prompt,
            system_prompt=params.get("system_prompt"),
            temperature=params.get("temperature", 0.0),
            max_completion_tokens=params.get("max_completion_tokens", 4096),
            stop_tokens=params.get("stop_tokens"),
            model_name=model_name,
        )

        raw_response = gen["raw_response"]
        answer_content = gen.get("answer_content", "")
        thinking_content = gen.get("thinking_content", "")

        candidates = [
            self._extract_edited_code(answer_content),
            self._extract_edited_code(raw_response),
        ]
        if thinking_content:
            candidates.append(self._extract_edited_code(thinking_content))

        edited_code = next((c for c in candidates if c and len(c) > 10), "")

        if not edited_code:
            return {
                "prompt": prompt, "raw_response": raw_response,
                "extracted_code": "", "correct": False,
                "error_message": "No code extracted from model response",
                "elapsed_time": gen["elapsed_time"],
                "tps": gen["tps"], "ttft": gen["ttft"],
                "thinking_tokens": gen["thinking_tokens"],
                "response_tokens": gen["response_tokens"],
            }

        tmpdir = self._write_temp_workspace(sample, edited_code)
        try:
            tr = self._run_tests(tmpdir, sample)
            if tr["success"]:
                return {
                    "prompt": prompt, "raw_response": raw_response,
                    "extracted_code": edited_code, "correct": True,
                    "error_message": None,
                    "elapsed_time": gen["elapsed_time"],
                    "tps": gen["tps"], "ttft": gen["ttft"],
                    "thinking_tokens": gen["thinking_tokens"],
                    "response_tokens": gen["response_tokens"],
                }

            test_output = (tr["stdout"] + "\n" + tr["stderr"])[:3000]
            retry_prompt = (
                f"The tests failed for `{sample['source_path']}`.\n"
                f"Fix the code to pass all tests.\n\n"
                f"Instructions:\n{sample['instruction']}\n\n"
                f"Source code:\n"
                f"```{sample['language']}\n{sample['source_code']}\n```\n\n"
                f"Test output:\n```\n{test_output}\n```\n\n"
                f"Output ONLY the edited file content."
            )

            gen2 = await self.client.generate_completion(
                prompt=retry_prompt,
                system_prompt=params.get("system_prompt"),
                temperature=params.get("temperature", 0.0),
                max_completion_tokens=params.get("max_completion_tokens", 4096),
                stop_tokens=params.get("stop_tokens"),
                model_name=model_name,
            )

            answer2 = gen2.get("answer_content", "") or gen2["raw_response"]
            edited_code2 = self._extract_edited_code(answer2)
            if not edited_code2 or len(edited_code2) < 10:
                edited_code2 = edited_code

            shutil.rmtree(tmpdir, ignore_errors=True)
            tmpdir = self._write_temp_workspace(sample, edited_code2)
            tr2 = self._run_tests(tmpdir, sample)

            return {
                "prompt": prompt, "raw_response": raw_response,
                "extracted_code": edited_code2,
                "correct": tr2["success"],
                "error_message": (
                    None if tr2["success"]
                    else (tr2["error"] or tr2["stderr"][:500]
                          or "Tests failed after 2 attempts")
                ),
                "elapsed_time": gen["elapsed_time"] + gen2["elapsed_time"],
                "tps": gen2["tps"],
                "ttft": gen2["ttft"],
                "thinking_tokens": (
                    gen["thinking_tokens"] + gen2.get("thinking_tokens", 0)
                ),
                "response_tokens": (
                    gen["response_tokens"] + gen2.get("response_tokens", 0)
                ),
            }
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def cleanup(self) -> None:
        for image_tag, executor in self._docker_executors.items():
            executor.cleanup()
        self._docker_executors.clear()
