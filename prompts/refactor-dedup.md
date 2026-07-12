Find and eliminate code duplication across the whole project. Scan all `.py` and `.tsx` files for repeated code blocks appearing 3+ times, then:

1. Extract a shared helper function/component
2. Replace all occurrences with calls to the helper
3. Keep original signatures unchanged for external callers

Common patterns to watch for:
- Stats computation (`tps_vals`, `ttft_vals`, `total_tk`, etc.) → `_compute_result_stats()`
- `sample["prompt"]` → `sample.get("prompt", "")`
- Repeated chart/component rendering blocks → shared sub-component
- Repeated API response building → helper function
- Repeated try/except/finally/close patterns → context manager

Do NOT change external API contracts, database schema, or evaluation logic correctness.

Return: before/after line counts and summary of extracted helpers.
