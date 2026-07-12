Add a new benchmark to BenchMax. I'll tell you the benchmark name, class name, display name, and what it does. You need to:

1. Create dataset files `data/{name}_{full,mini}.json`
2. Create `backend/benchmarks/{name}.py` with proper `BaseBenchmark` subclass
3. Register in `backend/config.py` (BENCHMARKS + DATASETS)
4. Register in `backend/operations.py` (BENCHMARK_CLASSES dict)
5. Add to `benchmax.spec` (hidden import + datas)

Dataset format: `[{"task_id": "{name}/0", "prompt": "...", "answer": "...", "type": "mcq|code|exact|free_form", ...}]`

Verify: `.venv\Scripts\python -c "from backend.main import app; print('OK')"`

Return: summary of all files created/modified.
