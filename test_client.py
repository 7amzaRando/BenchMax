import asyncio
import httpx

async def test_endpoints():
    base_url = "http://127.0.0.1:1234"
    
    endpoints = [
        "/models",
        "/v1/models", 
        "/chat/completions",
        "/v1/chat/completions",
        "/completions",
        "/v1/completions",
        "/embeddings",
        "/v1/embeddings"
    ]
    
    endpoint_methods = {
        "/models": "GET",
        "/v1/models": "GET",
        "/chat/completions": "POST",
        "/v1/chat/completions": "POST",
        "/completions": "POST",
        "/v1/completions": "POST",
        "/embeddings": "POST",
        "/v1/embeddings": "POST",
    }

    for endpoint, method in endpoint_methods.items():
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                url = f"{base_url}{endpoint}"
                if method == "GET":
                    resp = await c.get(url)
                else:
                    payload = {"model": "test", "messages": [{"role": "user", "content": "Hello"}]}
                    resp = await c.post(url, json=payload)
                print(f"{method} {endpoint}: Status={resp.status_code}, Content='{str(resp.text)[:80]}'")
        except Exception as e:
            print(f"{method} {endpoint}: Error - {e}")

asyncio.run(test_endpoints())
