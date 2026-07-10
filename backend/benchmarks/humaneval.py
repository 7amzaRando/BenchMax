import logging
import re
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from backend.benchmarks.base import BaseBenchmark, resolve_data_file
from backend.lm_studio.client import LMStudioClient
from backend.sandbox.docker_executor import DockerExecutor

logger = logging.getLogger(__name__)

class HumanEvalBenchmark(BaseBenchmark):
    requires_docker = True

    def __init__(self, db: Session, client: LMStudioClient, quick_test: bool = False):
        super().__init__(db, client, quick_test)
        self.executor = DockerExecutor()

    def load_dataset(self) -> List[Dict[str, Any]]:
        filename = "humaneval_mini.json" if self.quick_test else "humaneval_full.json"
        self.dataset_path = resolve_data_file(__file__, filename)
        if not self.dataset_path:
            logger.warning("Full HumanEval dataset not found, falling back to mini dataset")
            fallback = "humaneval_mini.json"
            self.dataset_path = resolve_data_file(__file__, fallback)
        if not self.dataset_path:
            raise FileNotFoundError(f"HumanEval dataset not found. Run 'scripts/fetch_humaneval.py' to download it.")
        return self._load_json_cached(self.dataset_path)

    def _extract_python_code(self, raw_text: str, entry_point: str) -> str:
        """
        Parses output to extract the executable Python code block.
        Multi-stage extraction with validation and fallback strategies.
        """
        if not raw_text or not raw_text.strip():
            logger.warning(f"Empty response for {entry_point}")
            return ""

        # Stage 1: Extract from ```python ... ``` blocks (most reliable)
        # Handles both ```python and indented (e.g., inside <think>) ```python blocks
        matches = re.findall(r"\s*```python\s*(.*?)\s*```", raw_text, re.DOTALL | re.IGNORECASE)
        if matches:
            code = matches[0].strip()
            if code:
                logger.debug(f"Extracted from python block for {entry_point}")
                return code

        # Stage 2: Extract from generic ``` ... ``` blocks (any language, indented ok)
        matches = re.findall(r"\s*```\w*\s*(.*?)\s*```", raw_text, re.DOTALL)
        if matches:
            code = matches[0].strip()
            if code:
                logger.debug(f"Extracted from generic block for {entry_point}")
                return code

        # Stage 3: Extract last contiguous non-prose block (handles conversational models)
        lines = raw_text.split('\n')
        code_lines = []
        in_code_block = False
        
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            
            # Check if this looks like Python code (not prose)
            if any(stripped.startswith(kw) for kw in ['def ', 'class ', 'for ', 'if ', 'while ',
                                                        'return ', 'import ', 'from ', 'assert ',
                                                        'print(', 'raise ', 'yield ', 'del ',
                                                        '[', ']', '{', '}', ':']):
                code_lines.append(line)
            else:
                # If we have collected code, return it
                if code_lines and len(code_lines) > 1:
                    logger.debug(f"Extracted from prose fallback for {entry_point}")
                    return '\n'.join(code_lines).strip()
        
        # Stage 4: Return raw text as last resort (with warning)
        logger.warning(f"No code block found, returning raw response for {entry_point}")
        return raw_text.strip()

    def _validate_and_prepare_code(self, extracted_code: str, entry_point: str, prompt: str) -> tuple[str, bool]:
        """
        Validates extracted code and prepares runnable version.
        Returns (runnable_code, is_valid).
        """
        if not extracted_code or not extracted_code.strip():
            logger.error(f"Empty extracted code for {entry_point}")
            return "", False

        # Check if entry point definition exists in extracted code
        has_definition = bool(re.search(rf'def\s+{re.escape(entry_point)}\s*\(', extracted_code))
        
        if has_definition:
            runnable_code = extracted_code.strip()
            logger.debug(f"Code contains {entry_point} definition")
        else:
            # Model provided only function body - concatenate with prompt signature
            # Extract the function signature from prompt (last def line)
            sig_match = re.search(rf'def\s+{re.escape(entry_point)}\s*\([^)]*\)\s*:', prompt)
            if sig_match:
                runnable_code = f"{sig_match.group(0)}\n    {extracted_code.strip()}"
                logger.debug(f"Reconstructed function from body-only response")
            else:
                # Fallback: use full prompt + extracted code
                runnable_code = f"{prompt}\n{extracted_code}"
                logger.warning(f"Could not find signature, using full prompt concatenation")

        return runnable_code.strip(), True

    async def evaluate_sample(self, sample: Dict[str, Any], params: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        """
        Runs completions against the local LLM and sends code to Docker for execution.
        """
        prompt = sample["prompt"]
        entry_point = sample["entry_point"]
        test_suite = sample["test"]
        task_id = sample["task_id"]

        # Run inference using LM Studio client
        generation = await self.client.generate_completion(
            prompt=prompt,
            system_prompt=params.get("system_prompt"),
            temperature=params.get("temperature", 0.0),
            max_completion_tokens=params.get("max_completion_tokens"),
            stop_tokens=params.get("stop_tokens", ["\nif __name__"]),
            model_name=model_name,
        )

        logger.debug(f"RAW_GENERATION_DEBUG: {generation!r}")

        raw_response = generation["raw_response"]
        answer_content = generation["answer_content"]
        thinking_content = generation.get("thinking_content", "")

        # Extract code from all sources, pick the best one (containing the function def)
        candidates = [
            ("answer", self._extract_python_code(answer_content, entry_point)),
            ("raw", self._extract_python_code(raw_response, entry_point)),
        ]
        if thinking_content:
            candidates.append(("think", self._extract_python_code(thinking_content, entry_point)))

        extracted_code = ""
        for src, code in candidates:
            if code and re.search(rf'def\s+{re.escape(entry_point)}\s*\(', code):
                extracted_code = code
                logger.debug(f"Using code from {src} for {entry_point}")
                break
        if not extracted_code:
            for src, code in candidates:
                if code:
                    extracted_code = code
                    logger.debug(f"Using fallback code from {src} for {entry_point}")
                    break

        # Validate and prepare runnable code
        runnable_code, is_valid = self._validate_and_prepare_code(extracted_code, entry_point, prompt)
        
        if not is_valid:
            logger.error(f"Failed to prepare runnable code for {task_id}")
            return {
                "prompt": prompt,
                "raw_response": raw_response,
                "extracted_code": extracted_code,
                "correct": False,
                "error_message": f"Code preparation failed: empty or invalid response",
                "elapsed_time": generation["elapsed_time"],
                "tps": generation["tps"],
                "ttft": generation["ttft"],
                "thinking_tokens": generation["thinking_tokens"],
                "response_tokens": generation["response_tokens"]
            }

        # Combine with test suite and invocation command
        test_script = f"{runnable_code}\n\n{test_suite}\n\ncheck({entry_point})\n"

        logger.info(f"Running sandbox execution for {task_id} in model {model_name}")
        
        try:
            code_size = len(runnable_code)
            timeout = min(10.0, max(5.0, 3.0 + (code_size / 500)))
            sandbox_res = self.executor.execute_python_code(test_script, timeout=timeout, benchmark_name="HumanEval")
        except Exception as e:
            logger.error(f"Sandbox execution error for {task_id}: {e}")
            return {
                "prompt": prompt,
                "raw_response": raw_response,
                "extracted_code": extracted_code,
                "correct": False,
                "error_message": f"Sandbox timeout or error: {str(e)}",
                "elapsed_time": generation["elapsed_time"],
                "tps": generation["tps"],
                "ttft": generation["ttft"],
                "thinking_tokens": generation["thinking_tokens"],
                "response_tokens": generation["response_tokens"]
            }

        return {
            "prompt": prompt,
            "raw_response": raw_response,
            "extracted_code": extracted_code,
            "correct": sandbox_res["success"],
            "error_message": "",
            "elapsed_time": generation["elapsed_time"],
            "tps": generation["tps"],
            "ttft": generation["ttft"],
            "thinking_tokens": generation["thinking_tokens"],
            "response_tokens": generation["response_tokens"]
        }

    def cleanup(self) -> None:
        self.executor.cleanup()

    def generate_diff(self, sample: dict, result_data: dict) -> str:
        import difflib
        prompt = sample.get("prompt", "")
        entry_point = sample.get("entry_point", "")
        canonical = (prompt + "\n" + sample.get("canonical_solution", "")).splitlines()
        generated = (result_data.get("extracted_code") or "").splitlines()
        if entry_point not in (result_data.get("extracted_code") or ""):
            generated = (prompt + "\n" + (result_data.get("extracted_code") or "")).splitlines()
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

