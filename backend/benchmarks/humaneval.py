import logging
import re
import textwrap
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from backend.benchmarks.base import BaseBenchmark
from backend.lm_studio.client import LMStudioClient
from backend.sandbox.safe_executor import check_correctness_humaneval

logger = logging.getLogger(__name__)

def extract_python_code(raw_text: str, entry_point: str) -> str:
    """Extract Python code from model output. Multi-stage: fence → contiguous lines → raw fallback."""
    if not raw_text or not raw_text.strip():
        return ""

    # Stage 1: ```python fences
    matches = re.findall(r"\s*```python\s*(.*?)\s*```", raw_text, re.DOTALL | re.IGNORECASE)
    if matches:
        code = textwrap.dedent(matches[0]).strip()
        if code:
            return code

    # Stage 2: generic fences
    matches = re.findall(r"\s*```\w*\s*(.*?)\s*```", raw_text, re.DOTALL)
    if matches:
        code = textwrap.dedent(matches[0]).strip()
        if code:
            return code

    # Stage 3: contiguous code lines
    lines = raw_text.split('\n')
    code_lines = []

    def _looks_like_code(stripped):
        if any(stripped.startswith(kw) for kw in ['def ', 'class ', 'for ', 'if ', 'while ',
                                                    'return ', 'import ', 'from ', 'assert ',
                                                    'print(', 'raise ', 'yield ', 'del ',
                                                    '[', ']', '{', '}', ':', 'self.', 'try',
                                                    'except ', 'finally ', 'with ', 'elif ']):
            return True
        if re.search(r'^[A-Za-z_]\w*\s*[+\-*/%&|^]?=', stripped):
            return True
        if re.search(r'^[A-Za-z_][\w.]*\(', stripped):
            return True
        return False

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        if _looks_like_code(stripped):
            code_lines.append(line)
        else:
            if code_lines and len(code_lines) > 1:
                return textwrap.dedent('\n'.join(code_lines)).strip()

    return textwrap.dedent(raw_text).strip()


def _validate_and_prepare_code(extracted_code: str, entry_point: str, prompt: str) -> tuple[str, bool]:
    """Validate extracted code and prepare runnable version."""
    if not extracted_code or not extracted_code.strip():
        return "", False

    has_definition = bool(re.search(rf'def\s+{re.escape(entry_point)}\s*\(', extracted_code))

    if has_definition:
        return extracted_code.strip(), True

    sig_line = None
    for ln in prompt.splitlines():
        if re.match(rf'def\s+{re.escape(entry_point)}\s*\(', ln):
            sig_line = ln
            break
    if sig_line:
        dedented = textwrap.dedent(extracted_code)
        runnable_code = f"{sig_line}\n{textwrap.indent(dedented, '    ')}".rstrip()
        return runnable_code.strip(), True

    return "", False


class HumanEvalBenchmark(BaseBenchmark):

    def __init__(self, db: Session, client: LMStudioClient, quick_test: bool = False):
        super().__init__(db, client, quick_test)

    def load_dataset(self) -> List[Dict[str, Any]]:
        path = self._resolve_dataset("humaneval_full.json", fetch_hint="Run 'scripts/fetch_humaneval.py' to download it.")
        return self._load_json_cached(path)

    async def evaluate_sample(self, sample: Dict[str, Any], params: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        prompt = sample.get("prompt", "")
        entry_point = sample.get("entry_point", "")
        test_suite = sample.get("test", "")
        task_id = sample.get("task_id", "")

        generation = await self._generate(prompt, params, model_name, stop_tokens=["\nif __name__"])

        raw_response = generation["raw_response"]
        answer_content = generation["answer_content"]
        thinking_content = generation.get("thinking_content", "")

        candidates = [
            ("answer", extract_python_code(answer_content, entry_point)),
            ("raw", extract_python_code(raw_response, entry_point)),
        ]
        if thinking_content:
            candidates.append(("think", extract_python_code(thinking_content, entry_point)))

        extracted_code = ""
        for src, code in candidates:
            if code and re.search(rf'def\s+{re.escape(entry_point)}\s*\(', code):
                extracted_code = code
                break
        if not extracted_code:
            for src, code in candidates:
                if code:
                    extracted_code = code
                    break

        runnable_code, is_valid = _validate_and_prepare_code(extracted_code, entry_point, prompt)

        if not is_valid:
            return self._result(prompt, generation, extracted_code=extracted_code,
                                error_message="Code preparation failed: empty or invalid response")

        try:
            code_size = len(runnable_code)
            timeout = min(10.0, max(5.0, 3.0 + (code_size / 500)))
            result = check_correctness_humaneval(
                entry_point=entry_point,
                prompt=prompt,
                completion=runnable_code,
                test_suite=test_suite,
                timeout=timeout,
            )
            correct = result["passed"]
            error_msg = None if result["passed"] else result["result"]
        except Exception as e:
            return self._result(prompt, generation, extracted_code=extracted_code,
                                error_message=f"Execution error: {str(e)}")

        return self._result(prompt, generation, extracted_code=extracted_code,
                            correct=correct, error_message=error_msg)

    def generate_diff(self, sample: dict, result_data: dict) -> str:
        import difflib
        from html import escape
        prompt = sample.get("prompt", "")
        entry_point = sample.get("entry_point", "")
        canonical = (prompt + "\n" + sample.get("canonical_solution", "")).splitlines()
        generated = (result_data.get("extracted_code") or "").splitlines()
        if entry_point not in (result_data.get("extracted_code") or ""):
            generated = (prompt + "\n" + (result_data.get("extracted_code") or "")).splitlines()
        canonical = [escape(line) for line in canonical]
        generated = [escape(line) for line in generated]
        diff_html = difflib.HtmlDiff(wrapcolumn=90).make_table(
            canonical, generated,
            fromdesc="✅ Ground-Truth Solution",
            todesc="❌ Model Generated Code",
            context=False
        )
        return f"""
<style>
table.diff{{font-family:'Fira Code','Courier New',monospace;font-size:12px;
  border-collapse:collapse;width:100%;background:#1e293b;color:#f1f5f9}}
table.diff td{{padding:3px 8px;border:1px solid #334155}}
td.diff_header{{background:#0f172a;color:#64748b;text-align:right;width:2%}}
span.diff_add{{background:#065f46;color:#a7f3d0;border-radius:2px;padding:0 2px}}
span.diff_chg{{background:#1e3a8a;color:#bfdbfe;border-radius:2px;padding:0 2px}}
span.diff_sub{{background:#7f1d1d;color:#fecaca;border-radius:2px;padding:0 2px}}
</style>
<div style="overflow-x:auto;border-radius:8px;border:1px solid #334155;background:#1e293b;padding:8px">
{diff_html}
</div>"""
