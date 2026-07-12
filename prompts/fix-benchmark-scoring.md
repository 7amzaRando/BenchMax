Audit all benchmark scoring across the project. Find every benchmark file under `backend/benchmarks/` that has `evaluate_sample()`, then check each one:

1. Returns dict with all standard keys: `prompt`, `raw_response`, `extracted_code`, `correct`, `error_message`, `elapsed_time`, `tps`, `ttft`, `thinking_tokens`, `response_tokens`
2. `error_message` is descriptive (not `None`) when `correct=False`
3. `scoring_details` passed as dict (not `json.dumps()`)
4. `sample.get("prompt", "")` not `sample["prompt"]`
5. `generate_completion()` does NOT pass `reasoning_tokens` or `disable_reasoning`
6. `max_completion_tokens` used (not `max_tokens`)
7. Dataset-loading uses `resolve_data_file()` or equivalent .exe-compatible path

Fix every issue found. Verify: `.venv\Scripts\python -c "from backend.main import app; print('OK')"`

Return: table of all benchmarks checked, issues found, and fixes applied.
