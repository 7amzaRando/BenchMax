Audit all API endpoints across the project. Read `backend/api.py` and `backend/operations.py`, then check every endpoint:

1. **Error handling**: Exceptions caught with try/except? Logged at appropriate level (ERROR for failures)?
2. **DB sessions**: Opened in try/finally with `db.close()`? No early returns that skip the close?
3. **N+1 queries**: Related data loaded with `joinedload()`? Count the queries per request.
4. **Thread safety**: Shared state (`_active_batch_id`, `_model_queue_state`) protected by locks?
5. **Return type**: Consistent — `{status, message}` for mutations, `{data}` for queries?
6. **Input validation**: Pydantic models for request bodies? Optional fields use `Optional[type] = None`?
7. **Security**: No secrets/stack traces leaked in responses? `api_key` handled properly?

Fix every issue found. Verify: `.venv\Scripts\python -c "from backend.main import app; print('OK')"`

Return: table of all endpoints checked, issues found, and fixes applied.
