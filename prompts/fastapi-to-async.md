Find sync API endpoints that would benefit from async conversion. Scan `backend/api.py` and `backend/operations.py`:

1. Identify endpoints that call I/O-bound operations (DB queries, HTTP calls, file I/O, subprocess)
2. If the operations function is sync + does I/O, convert it to async
3. Update the api.py endpoint to `async def` and `await` the call
4. Use `asyncio.to_thread()` for CPU-bound or blocking sync code that can't be made async
5. Keep SQLAlchemy sync — wrap with `asyncio.to_thread` if needed, or keep sync if performance is acceptable

Only convert when there's clear performance benefit (blocking I/O during streaming/SSE, long queries, concurrent request handling).

Return: summary of all endpoints reviewed and which were converted (with reasoning).
