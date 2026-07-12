Research whether a given benchmark can be integrated into BenchMax. Check:

1. **Downloadable dataset**: Under 500 MB? Fetchable via Python script?
2. **Scoring logic**: Can it run locally? (regex, AST, multiprocessing code execution, keyword matching — not proprietary API)
3. **No Docker**: Must run via `safe_executor` or `subprocess` with `.runtimes/`
4. **Single-turn compatible**: One LLM call per sample, or can be simplified to that
5. **Architecture fit**: Matches `BaseBenchmark.load_dataset()` → `evaluate_sample()` → standard result dict

Create a research ticket at `tickets/RESEARCH-{short_name}.md` with verdict and detailed findings.

Return: full research findings.
