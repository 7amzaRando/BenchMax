import glob as glob_mod
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any, List

from backend.benchmarks.base import BaseBenchmark, resolve_data_file
from backend.sandbox.safe_executor import check_correctness_aider

logger = logging.getLogger(__name__)

RUNTIMES_DIR = Path(__file__).parents[2] / ".runtimes"
RUNTIMES_EXISTS = RUNTIMES_DIR.exists()

# Runtime paths — only valid when .runtimes/ is installed on host.
# In Docker mode, these are not used (container has runtimes at system paths).
GO_BIN = RUNTIMES_DIR / "go" / "go" / "bin" / "go.exe" if RUNTIMES_EXISTS else None
RUST_DIR = RUNTIMES_DIR / "rust_standalone" / "rust-1.97.0-x86_64-pc-windows-msvc" if RUNTIMES_EXISTS else None
RUSTC_BIN = RUST_DIR / "rustc" / "bin" if RUST_DIR else None
CARGO_BIN = RUST_DIR / "cargo" / "bin" if RUST_DIR else None
GCC_BIN = RUNTIMES_DIR / "w64devkit" / "w64devkit" / "bin" if RUNTIMES_EXISTS else None
W64DEVKIT_ROOT = RUNTIMES_DIR / "w64devkit" if RUNTIMES_EXISTS else None
CATCH2_INCLUDE = RUNTIMES_DIR / "include" if RUNTIMES_EXISTS else None
JARS_DIR = RUNTIMES_DIR / "jars" if RUNTIMES_EXISTS else None
NODE_MODULES = RUNTIMES_DIR / "node_pkg" / "node_modules" if RUNTIMES_EXISTS else None


def _java_test_class(src_name: str) -> str:
    stem = Path(src_name).stem
    if stem.endswith("Test"):
        return stem
    return stem.replace("Test", "") + "Test"


LANGUAGE_CONFIGS = {
    "cpp": {
        "test_cmd": None,
        "run_test": lambda src_name, tmpdir: _run_cpp_test(src_name, tmpdir),
    },
    "go": {
        "test_cmd": lambda src_name, tmpdir: [str(GO_BIN), "test", "./..."],
    },
    "java": {
        "test_cmd": None,
        "run_test": lambda src_name, tmpdir: _run_java_test(src_name, tmpdir),
    },
    "javascript": {
        "test_cmd": lambda src_name, tmpdir: [
            os.path.join(NODE_MODULES, ".bin", "jest.cmd"),
            "--no-coverage",
        ],
        "env": {"NODE_PATH": str(NODE_MODULES)},
    },
    "python": {
        "test_cmd": lambda src_name, tmpdir: [
            sys.executable, "-m", "unittest", src_name.replace(os.sep, '.').replace(".py", ""),
        ],
    },
    "rust": {
        "test_cmd": lambda src_name, tmpdir: [str(CARGO_BIN / "cargo.exe"), "test", "--", "--test-threads=1"],
    },
}
# Sorted language list for display
SORTED_LANGUAGES = sorted(LANGUAGE_CONFIGS.keys())


def _run_java_test(src_name: str, tmpdir: str) -> Dict[str, Any]:
    classes_dir = os.path.join(tmpdir, "classes")
    os.makedirs(classes_dir, exist_ok=True)
    javac_cmd = "javac"
    java_cmd = "java"
    junit_jar = str(JARS_DIR / "junit-platform-console-standalone-1.11.4.jar")
    assertj_jar = str(JARS_DIR / "assertj-core-3.27.3.jar")
    sep = ";"

    def run(cmd, timeout=30):
        proc = None
        try:
            proc = subprocess.run(
                cmd, cwd=tmpdir, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=timeout,
            )
            return proc
        except subprocess.TimeoutExpired:
            if proc is not None:
                proc.kill()
                proc.wait()
            return None
        except Exception as e:
            if proc is not None:
                proc.kill()
                proc.wait()
            return type("R", (), {"returncode": -1, "stdout": "", "stderr": str(e)})()

    src_files = glob_mod.glob(os.path.join(tmpdir, "src", "main", "java", "*.java"))
    if not src_files:
        return {"success": False, "stdout": "", "stderr": "", "error": "No Java source files found"}
    r = run([javac_cmd, "-d", classes_dir] + src_files)
    if r is None or r.returncode != 0:
        return {"success": False, "stdout": r.stdout if r else "", "stderr": (r.stderr if r else "Compile timeout"), "error": f"javac main failed: {(r.stderr if r else '')[:500]}"}

    test_files = glob_mod.glob(os.path.join(tmpdir, "src", "test", "java", "*.java"))
    if not test_files:
        return {"success": True, "stdout": "No tests found", "stderr": "", "error": None}
    cp = f"{classes_dir}{sep}{junit_jar}{sep}{assertj_jar}"
    r = run([javac_cmd, "-d", classes_dir, "-cp", cp] + test_files)
    if r is None or r.returncode != 0:
        return {"success": False, "stdout": r.stdout if r else "", "stderr": (r.stderr if r else "Test compile timeout"), "error": f"javac test failed: {(r.stderr if r else '')[:500]}"}

    test_class = _java_test_class(src_name)
    r = run([java_cmd, "-jar", junit_jar, "--classpath", f"{classes_dir}{sep}{junit_jar}{sep}{assertj_jar}", "--select-class", test_class], timeout=30)
    if r is None:
        return {"success": False, "stdout": "", "stderr": "", "error": "JUnit timeout (30s)"}
    return {
        "success": r.returncode == 0,
        "stdout": (r.stdout or "")[:5000],
        "stderr": (r.stderr or "")[:2000],
        "error": None if r.returncode == 0 else f"JUnit exit {r.returncode}",
    }


def _run_cpp_test(src_name: str, tmpdir: str) -> Dict[str, Any]:
    gxx = str(GCC_BIN / "g++.exe")
    test_file = src_name.replace('.cpp', '_test.cpp')
    test_path = os.path.join(tmpdir, test_file)
    exe_path = os.path.join(tmpdir, "test.exe")

    try:
        cpp_env = os.environ.copy()
        cpp_env["PATH"] = str(GCC_BIN) + os.pathsep + cpp_env.get("PATH", "")
        r = subprocess.run(
            [gxx, "-std=c++20", "-DEXERCISM_RUN_ALL_TESTS", "-DEXERCISM_TEST_SUITE", "-DCATCH_CONFIG_MAIN",
             f"-I{W64DEVKIT_ROOT / 'include'}", f"-I{CATCH2_INCLUDE}",
             "-o", exe_path, test_path],
            cwd=tmpdir, capture_output=True, text=True, timeout=60, env=cpp_env,
            encoding="utf-8", errors="replace",
        )
        if r.returncode != 0:
            return {"success": False, "stdout": r.stdout, "stderr": r.stderr, "error": f"g++ compile failed: {r.stderr[:500]}"}
    except subprocess.TimeoutExpired:
        return {"success": False, "stdout": "", "stderr": "", "error": "g++ compile timeout (60s)"}
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": "", "error": str(e)}

    try:
        cpp_env = os.environ.copy()
        cpp_env["PATH"] = str(GCC_BIN) + os.pathsep + cpp_env.get("PATH", "")
        r = subprocess.run([exe_path], cwd=tmpdir, capture_output=True, text=True, timeout=30, env=cpp_env,
            encoding="utf-8", errors="replace")
        return {
            "success": r.returncode == 0,
            "stdout": (r.stdout or "")[:5000],
            "stderr": (r.stderr or "")[:2000],
            "error": None if r.returncode == 0 else f"Test exit {r.returncode}",
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "stdout": "", "stderr": "", "error": "C++ test timeout (30s)"}
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": "", "error": str(e)}


def _write_temp_workspace(sample: Dict[str, Any], edited_code: str, tmpdir: str) -> None:
    lang = sample.get("language", "")

    def write_file(rel_path: str, content: str):
        full = os.path.join(tmpdir, rel_path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)

    write_file(sample.get("source_path", ""), edited_code)

    test_content = sample.get("test_code", "")
    if lang == "cpp":
        header_name = Path(sample.get("source_path", "")).stem + ".h"
        source_name = Path(sample.get("source_path", "")).name
        test_content = re.sub(
            r'#include\s+"' + re.escape(header_name) + r'"',
            '#include "' + source_name + '"',
            test_content,
        )
    write_file(sample.get("test_path", ""), test_content)

    extra_files = sample.get("extra_files") or {}
    for rel_path, content in extra_files.items():
        write_file(rel_path, content)

    if lang == "javascript":
        write_file("babel.config.js",
                   "module.exports = { presets: ['@babel/preset-env'] };\n")
        write_file("package.json", json.dumps({
            "name": "aider-polyglot-js",
            "private": True,
            "jest": {
                "transform": {"^.+\\.jsx?$": "babel-jest"},
            },
        }))

    if lang == "go":
        has_mod = any(k.endswith("go.mod") for k in (extra_files or {}))
        if not has_mod:
            write_file("go.mod", "module aider_polyglot\n\ngo 1.22\n")


def _run_test(tmpdir: str, sample: Dict[str, Any]) -> Dict[str, Any]:
    if not RUNTIMES_EXISTS:
        return {"success": False, "stdout": "", "stderr": "",
                "error": ".runtimes/ not installed — run scripts/setup_runtimes.py or use Docker sandbox"}
    lang = sample["language"]
    config = LANGUAGE_CONFIGS.get(lang)
    if not config:
        return {"success": False, "stdout": "", "stderr": "",
                "error": f"Unknown language: {lang}"}

    if "run_test" in config:
        return config["run_test"](sample["source_path"], tmpdir)

    test_name = sample["test_path"]
    cmd = config["test_cmd"](test_name, tmpdir)
    env = config.get("env", {})
    full_env = os.environ.copy()
    full_env.update(env)
    if lang == "rust":
        full_env["PATH"] = str(RUSTC_BIN) + os.pathsep + str(CARGO_BIN) + os.pathsep + full_env.get("PATH", "")
        full_env["CARGO_HOME"] = os.path.join(tmpdir, ".cargo")
    if lang == "go":
        full_env["PATH"] = str(GO_BIN.parent) + os.pathsep + full_env.get("PATH", "")
        full_env["GOCACHE"] = os.path.join(tmpdir, ".gocache")
        full_env["GOPATH"] = os.path.join(tmpdir, ".gopath")
    if lang == "cpp":
        full_env["PATH"] = str(GCC_BIN) + os.pathsep + full_env.get("PATH", "")

    logger.info("Running %s test: %s", lang, " ".join(str(c) for c in cmd))
    proc = None
    try:
        proc = subprocess.run(
            cmd, cwd=tmpdir, capture_output=True, text=True, timeout=120, env=full_env,
            encoding="utf-8", errors="replace",
        )
        return {
            "success": proc.returncode == 0,
            "stdout": (proc.stdout or "")[:5000],
            "stderr": (proc.stderr or "")[:2000],
            "error": None,
        }
    except subprocess.TimeoutExpired:
        if proc is not None:
            proc.kill()
            proc.wait()
        return {"success": False, "stdout": "", "stderr": "", "error": "Test timed out (120s)"}
    except Exception as e:
        if proc is not None:
            proc.kill()
            proc.wait()
        return {"success": False, "stdout": "", "stderr": "", "error": str(e)}


def _run_test_in_sandbox(sample, edited_code, tmpdir):
    """Standalone function for sandboxed aider test execution.
    
    Uses tmpdir created by parent process (check_correctness_aider).
    Parent handles cleanup in its finally block — guaranteed even on kill.
    """
    _write_temp_workspace(sample, edited_code, tmpdir)
    return _run_test(tmpdir, sample)


class AiderPolyglotBenchmark(BaseBenchmark):
    def __init__(self, db, client, quick_test=False):
        super().__init__(db, client, quick_test)

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
                code = m.group(m.lastindex).strip()
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
        lang = sample.get("language", "")
        parts = [
            f"Edit the file `{sample.get('source_path', '')}` to make all tests pass.",
            "",
            "Instructions:",
            sample.get("instruction", ""),
            "",
            f"Current source code (`{sample.get('source_path', '')}`):",
            f"```{lang}",
            sample.get("source_code", ""),
            "```",
            "",
            "Output ONLY the edited file content (the complete file).",
        ]
        return "\n".join(parts)

    async def evaluate_sample(self, sample: Dict[str, Any],
                              params: Dict[str, Any],
                              model_name: str) -> Dict[str, Any]:
        prompt = self._build_prompt(sample)

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
                "prompt_tokens": gen.get("prompt_tokens", 0),
                "scoring_details": {"category": sample.get("language", "unknown")},
            }

        tr = check_correctness_aider(
            _run_test_in_sandbox, sample, edited_code,
            timeout=300,
        )

        if tr["success"]:
            return {
                "prompt": prompt, "raw_response": raw_response,
                "extracted_code": edited_code, "correct": True,
                "error_message": None,
                "elapsed_time": gen["elapsed_time"],
                "tps": gen["tps"], "ttft": gen["ttft"],
                "thinking_tokens": gen["thinking_tokens"],
                "response_tokens": gen["response_tokens"],
                "prompt_tokens": gen.get("prompt_tokens", 0),
                "scoring_details": {"category": sample.get("language", "unknown")},
            }

        test_output = (tr.get("stdout", "") + "\n" + tr.get("stderr", ""))[:3000]

        if not edited_code or len(edited_code) < 10:
            return {
                "prompt": prompt, "raw_response": raw_response,
                "extracted_code": edited_code, "correct": False,
                "error_message": (
                    tr.get("error")
                    or (tr.get("stderr") or "")[:500]
                    or "Tests failed on first attempt"
                ),
                "elapsed_time": gen["elapsed_time"],
                "tps": gen["tps"], "ttft": gen["ttft"],
                "thinking_tokens": gen["thinking_tokens"],
                "response_tokens": gen["response_tokens"],
                "prompt_tokens": gen.get("prompt_tokens", 0),
                "scoring_details": {"category": sample.get("language", "unknown")},
            }

        retry_prompt = (
            f"The tests failed for `{sample.get('source_path', '')}`.\n"
            f"Fix the code to pass all tests.\n\n"
            f"Instructions:\n{sample.get('instruction', '')}\n\n"
            f"Source code:\n"
            f"```{sample.get('language', '')}\n{sample.get('source_code', '')}\n```\n\n"
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

        tr2 = check_correctness_aider(
            _run_test_in_sandbox, sample, edited_code2,
            timeout=300,
        )

        return {
            "prompt": prompt, "raw_response": raw_response,
            "extracted_code": edited_code2,
            "correct": tr2["success"],
            "error_message": (
                None if tr2["success"]
                else (tr2.get("error") or tr2.get("stderr", "")[:500]
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
            "prompt_tokens": gen.get("prompt_tokens", 0) + gen2.get("prompt_tokens", 0),
            "scoring_details": {"category": sample.get("language", "unknown")},
        }
