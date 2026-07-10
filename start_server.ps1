$env:PYTHONPATH = $PSScriptRoot
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000 --log-level warning