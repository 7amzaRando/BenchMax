import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Dict, Any, List

from backend.benchmarks.base import BaseBenchmark, resolve_data_file
from backend.sandbox.safe_executor import check_correctness_aider

logger = logging.getLogger(__name__)


def _java_test_class(test_src_name: str) -> str:
    """Derive the JUnit test class from the TEST file path (not source).

    Passing the source path (e.g. Tree.java) yields a wrong class (TreeTest)
    when the real test class differs (e.g. PovTest.java → PovTest).
    """
    stem = Path(test_src_name).stem
    if stem.endswith("Test"):
        return stem
    return stem.replace("Test", "") + "Test"


def _cpp_test_rel(src_name: str, test_rel: str | None = None) -> str:
    """Test file location, suffix-safe. Prefers the dataset test_path."""
    if test_rel:
        return test_rel
    if src_name.endswith(".cpp"):
        return src_name[:-4] + "_test.cpp"
    return src_name + "_test.cpp"


# Languages covered by the Docker image (benchmax-sandbox has all toolchains
# at system paths). Sorted for display.
SORTED_LANGUAGES = sorted(["cpp", "go", "java", "javascript", "python", "rust"])


def _write_temp_workspace(sample: Dict[str, Any], edited_code: str, tmpdir: str) -> None:
    """Write the grading workspace (source + tests + toolchain files).

    MIRROR: backend/sandbox/container_runner.py::_write_workspace implements
    the same layout for the Docker path. The container copy is stdlib-only
    (baked into the benchmax-sandbox image, no backend imports allowed), so
    the two cannot share code — keep them in sync. tests/test_aider_workspace_sync.py
    fails if their outputs diverge.
    """
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
        # Only write generic toolchain files when the dataset doesn't ship
        # its own (some samples pin a specific babel preset in extra_files).
        if "babel.config.js" not in (extra_files or {}):
            write_file("babel.config.js",
                       "module.exports = { presets: ['@babel/preset-env'] };\n")
        if "package.json" not in (extra_files or {}):
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
                "import", "from", "def ", "class ", "function", "func ",
                "const ", "let ", "var ", "export", "public ", "private ",
                "package", "use ", "fn ", "struct ", "enum ", "#include",
                "using ", "pub ", "impl ", "namespace ", "return", "if ",
                "for ", "while ", "with ", "TEST", "EXPECT", "ASSERT",
                "console.", "expect(", "describe(", "test(", "it(",
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

        _t0 = time.monotonic()
        tr = check_correctness_aider(
            sample, edited_code,
            timeout=300,
        )
        _test_secs_1 = time.monotonic() - _t0

        if tr["success"]:
            return {
                "prompt": prompt, "raw_response": raw_response,
                "extracted_code": edited_code, "correct": True,
                "error_message": None,
                "elapsed_time": gen["elapsed_time"] + _test_secs_1,
                "tps": gen["tps"], "ttft": gen["ttft"],
                "thinking_tokens": gen["thinking_tokens"],
                "response_tokens": gen["response_tokens"],
                "prompt_tokens": gen.get("prompt_tokens", 0),
                "scoring_details": {"category": sample.get("language", "unknown")},
            }

        test_output = (tr.get("stdout", "") + "\n" + tr.get("stderr", ""))[:3000]

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

        # Same 3-candidate extraction as attempt 1 (answer → raw → thinking).
        answer2 = gen2.get("answer_content", "")
        raw2 = gen2.get("raw_response", "")
        thinking2 = gen2.get("thinking_content", "")
        edited_code2 = next(
            (c for c in [
                self._extract_edited_code(answer2),
                self._extract_edited_code(raw2),
                self._extract_edited_code(thinking2) if thinking2 else "",
            ] if c and len(c) > 10),
            "",
        )
        if not edited_code2:
            edited_code2 = edited_code

        _t1 = time.monotonic()
        tr2 = check_correctness_aider(
            sample, edited_code2,
            timeout=300,
        )
        _test_secs_2 = time.monotonic() - _t1

        total_elapsed = (
            gen["elapsed_time"] + gen2["elapsed_time"]
            + _test_secs_1 + _test_secs_2
        )
        total_resp = gen["response_tokens"] + gen2.get("response_tokens", 0)
        # Combined throughput across both LLM calls; TTFT is first-token
        # latency of the initial attempt.
        combined_tps = (
            total_resp / (gen["elapsed_time"] + gen2["elapsed_time"])
            if (gen["elapsed_time"] + gen2["elapsed_time"]) > 0
            else gen2["tps"]
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
            "elapsed_time": total_elapsed,
            "tps": combined_tps,
            "ttft": gen["ttft"],
            "thinking_tokens": (
                gen["thinking_tokens"] + gen2.get("thinking_tokens", 0)
            ),
            "response_tokens": total_resp,
            "prompt_tokens": gen.get("prompt_tokens", 0) + gen2.get("prompt_tokens", 0),
            "scoring_details": {"category": sample.get("language", "unknown")},
        }
