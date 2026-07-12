Audit data quality across all benchmark datasets and their loader code. For every benchmark under `backend/benchmarks/` and its corresponding data file, check:

1. **task_id**: Every dataset entry has a `task_id` field (set from `_id`, `key`, `question_id`, or index fallback in `load_dataset()`)
2. **Bracket access → .get()**: Benchmark code uses `sample.get("field", default)` not `sample["field"]`
3. **Answer consistency**: Answer format matches what the scorer expects (single letter for MCQ, integer for exact, etc.)
4. **Path resolution**: Dataset paths work in both dev (`Path(__file__)`) and PyInstaller frozen builds (`sys._MEIPASS`, exe parent/grandparent/cwd)
5. **Empty response guard**: `evaluate_sample()` returns `correct=False` with descriptive `error_message` for blank responses

Fix every issue found. If fixing a dataset JSON, update both full and mini versions.

Return: table of all benchmarks checked and fixes applied.
