import logging
import re
import textwrap
from typing import Dict, Any, List
from backend.benchmarks.base import BaseBenchmark
from backend.benchmarks.humaneval import extract_python_code
from backend.sandbox.safe_executor import check_correctness_bigcodebench

logger = logging.getLogger(__name__)


def _prompt_imports(prompt: str, entry_point: str) -> str:
    """Stub header from the prompt's "starting with" code block.

    BigCodeBench prompts show a block like
        ```
        import os
        import shutil
        def task_func(...):
        ```
    (sometimes with `# Constants` + `LETTERS = ...` assignments) and datasets
    pair it with body-only canonical solutions. Solution and test code exec
    in ONE module namespace, so everything before the `def` line must be
    prepended — otherwise model code (`random.seed`), test helpers
    (`shutil.rmtree` in tearDown) and fixtures (`LETTERS` in setUp) raise
    NameError.
    """
    block = None
    for m in re.finditer(r"```(?:\w*\n)?(.*?)```", prompt, re.DOTALL):
        if re.search(rf'def\s+{re.escape(entry_point)}\s*\(', m.group(1)):
            block = m.group(1)
            break
    if not block:
        return ""
    header = []
    for line in block.splitlines():
        if re.match(rf'def\s+{re.escape(entry_point)}\s*\(', line.strip()):
            break
        header.append(line.rstrip())
    return "\n".join(header).strip()


def _prepare_bcb_code(extracted_code: str, entry_point: str, prompt: str) -> str:
    """Accept full definitions or canonical-style bodies.

    BigCodeBench prompts invite code "starting with" an import + signature
    block, and canonical solutions are body-only (no `def`). If the model
    emits just the body, wrap it with the signature scraped from the prompt
    (same approach as HumanEval's _validate_and_prepare_code). The prompt's
    import preamble is prepended when the code lacks it. Returns "" when
    neither a definition nor a usable signature is found.
    """
    if not extracted_code or not extracted_code.strip():
        return ""
    preamble = _prompt_imports(prompt, entry_point)

    def _with_imports(code: str) -> str:
        if not preamble:
            return code
        existing = set(
            line.strip() for line in code.splitlines()
            if line.strip().startswith(("import ", "from "))
        )
        missing = [ln for ln in preamble.splitlines() if ln.strip() not in existing]
        return ("\n".join(missing) + "\n" + code).strip() if missing else code

    if re.search(rf'def\s+{re.escape(entry_point)}\s*\(', extracted_code):
        return _with_imports(extracted_code.strip())
    # Signature may carry a return annotation (e.g. `) -> str:`).
    sig_match = re.search(
        rf'def\s+{re.escape(entry_point)}\s*\(.*?\)\s*(?:->\s*[^:]+)?:',
        prompt, re.DOTALL,
    )
    if sig_match:
        sig = " ".join(sig_match.group(0).split())
        body = textwrap.dedent(extracted_code).strip()
        if body:
            return _with_imports(f"{sig}\n{textwrap.indent(body, '    ')}".strip())
    return ""

class BigCodeBenchBenchmark(BaseBenchmark):

    def __init__(self, db, client, quick_test=False, hard=False):
        super().__init__(db, client, quick_test)
        self.hard = hard

    def load_dataset(self) -> List[Dict[str, Any]]:
        suffix = "_hard" if self.hard else ""
        full_name = f"bigcodebench{suffix}_full.json"
        mini_name = f"bigcodebench{suffix}_mini.json"
        fetch_hint = f"Run 'scripts/fetch_bigcodebench{'_hard' if self.hard else ''}.py' to download it."
        path = self._resolve_dataset(full_name, mini_name=mini_name, fetch_hint=fetch_hint)
        return self._load_json_cached(path)

    async def evaluate_sample(self, sample: Dict[str, Any], params: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        prompt = sample.get("prompt", "")
        entry_point = sample.get("entry_point", "")
        test_suite = sample.get("test", "")
        task_id = sample.get("task_id", "")

        generation = await self._generate(prompt, params, model_name, stop_tokens=["\nif __name__"])

        raw_response = generation["raw_response"]
        answer_content = generation["answer_content"]

        raw_code = extract_python_code(answer_content, entry_point)
        if not raw_code:
            raw_code = extract_python_code(raw_response, entry_point)
        if not raw_code:
            thinking = generation.get("thinking_content", "")
            if thinking:
                raw_code = extract_python_code(thinking, entry_point)

        label = "BigCodeBench-Hard" if self.hard else "BigCodeBench"
        scoring = {"category": label}

        extracted_code = _prepare_bcb_code(raw_code or "", entry_point, prompt)
        if not extracted_code:
            return self._result(prompt, generation, extracted_code=raw_code or "",
                                error_message="No valid code extracted",
                                scoring_details=scoring)

        if not test_suite or not test_suite.strip():
            return self._result(prompt, generation, extracted_code=extracted_code,
                                error_message="No test suite available for this sample",
                                scoring_details=scoring)

        logger.info(f"Running {label} code execution for {task_id}")
        try:
            timeout = min(10.0, max(5.0, 3.0 + len(extracted_code) / 500))
            result = check_correctness_bigcodebench(
                code=extracted_code,
                test_code=test_suite,
                timeout=timeout,
                block_child_processes=False,
                block_network=False,
            )
            correct = result["passed"]
            error_msg = None if result["passed"] else result["result"]
            if not correct and result["details"]:
                error_msg = "; ".join(d[:500] for d in result["details"][:3])[:1500]
            elif error_msg:
                error_msg = error_msg[:1500]
        except Exception as e:
            return self._result(prompt, generation, extracted_code=extracted_code,
                                error_message=f"Execution error: {str(e)[:500]}",
                                scoring_details=scoring)

        return self._result(prompt, generation, extracted_code=extracted_code,
                            correct=correct, error_message=error_msg,
                            scoring_details=scoring)
