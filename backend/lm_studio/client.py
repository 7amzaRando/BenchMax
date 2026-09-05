import time
import json
import re
import orjson as _orjson
import logging
from difflib import SequenceMatcher
from typing import List, Dict, Any, Optional, Tuple
import httpx

logger = logging.getLogger(__name__)

class LMStudioClient:
    async def aclose(self):
        """Close the underlying HTTP client session."""
        if self._client is not None:
            try:
                await self._client.aclose()
            except RuntimeError:
                # Event loop already closed — httpx client was created on a
                # different loop (e.g. _run_async creates fresh loops per call).
                # The connection pool is abandoned; no cleanup needed.
                pass
            self._client = None

    def __init__(self, base_url: str = "http://127.0.0.1:1234", api_key: Optional[str] = None):
        base_url = base_url.rstrip("/")
        self.base_url = base_url
        self.api_key = api_key
        self._headers = {"Content-Type": "application/json"}
        if api_key:
            self._headers["Authorization"] = f"Bearer {api_key}"
        self._client: Optional[httpx.AsyncClient] = None

        # Repetition detection state
        self._rep_buffer = ""        # Sliding buffer of accumulated output (last 1000 chars)
        self._rep_max_len = 1000     # Max chars to retain for loop analysis
        self._rep_check_len = 200    # Length of tail gram to check for repeats (200 chars ≈ 50 tokens)
        self._rep_min_buf = 400      # Minimum total buffer length before we start checking
        self._rep_sim_threshold = 0.95 # SequenceMatcher ratio for adjacent blocks
        self._repetition_detected = False
        self._rep_disabled = False   # Set by operations.py when user disables detection
        self._rep_consecutive_count = 0  # Consecutive checks that flagged (cooldown)
        self._rep_required_count = 3     # Need this many consecutive flags to confirm loop
        self._rep_chunk_count = 0        # Rate-limit: only check every N chunks
        self._rep_check_interval = 50    # Check repetition every 50 chunks

        # Model management state: instance_id captured from last load_model() call
        self._loaded_instance_id: Optional[str] = None

        logger.debug(f"[DEBUG] LMStudioClient.__init__: received={base_url} -> stored as '{self.base_url}'")

    def _get_client(self) -> httpx.AsyncClient:
        """Lazily create httpx.AsyncClient bound to the current event loop."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=None, headers=self._headers)
        return self._client

    def _check_repetition(self) -> bool:
        """
        Detects model looping by checking for repeated long substrings in the output.
        Uses three complementary strategies with a consecutive-repeat cooldown:

        Strategy A (tail-in-body): Check if the last N chars appear as a substring
        anywhere earlier in the buffer.

        Strategy B (adjacent similarity): Compare the last N chars against the N chars
        immediately before them using SequenceMatcher on EQUAL-length strings.

        Strategy C (short fragment count): Check if a shorter substring of the tail
        appears many times in the body.

        A single detection event is NOT enough to flag a loop — the detection counter
        must reach _rep_required_count (3) consecutive triggers to confirm, eliminating
        transient false positives from code boilerplate or reasoning verification.
        """
        buf = self._rep_buffer
        if len(buf) < self._rep_min_buf:
            self._rep_consecutive_count = 0
            return False

        tail = buf[-self._rep_check_len:]
        body = buf[:-self._rep_check_len]

        # Multi-line guard: in code output (>5 lines), require detected fragment
        # to contain a newline to avoid flagging single-line boilerplate.
        is_multiline = buf.count('\n') > 5

        triggered = False

        # Strategy A: 200-char exact substring appears in body
        if tail in body and (not is_multiline or '\n' in tail):
            triggered = True

        # Strategy B: Adjacent block similarity (equal-length comparison)
        if not triggered and len(buf) >= self._rep_check_len * 2:
            preceding = buf[-self._rep_check_len * 2:-self._rep_check_len]
            if len(preceding) == len(tail):
                ratio = SequenceMatcher(None, tail, preceding, autojunk=False).ratio()
                if ratio >= self._rep_sim_threshold and (not is_multiline or '\n' in tail):
                    triggered = True

        # Strategy C: 150-char fragment appearing 3+ times (handles alignment issues)
        if not triggered:
            half = tail[-(self._rep_check_len // 2):]
            if len(half) >= 150 and body.count(half) >= 3:
                triggered = True

        # Cooldown: require consecutive triggers to confirm a real loop
        if triggered:
            self._rep_consecutive_count += 1
        else:
            self._rep_consecutive_count = 0

        return self._rep_consecutive_count >= self._rep_required_count

    async def get_loaded_models(self) -> List[Dict[str, Any]]:
        """Queries the /models endpoint to retrieve loaded models."""
        url = f"{self.base_url}/models"
        try:
            logger.info(f"Querying LM Studio at {url}")
            response = await self._get_client().get(url, timeout=10)
        except Exception as e:
            logger.error(f"Cannot reach provider at {url}: {e}")
            raise  # Connection refused/timeout → provider unreachable
        logger.info(f"Response status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            models = data.get("data", [])
            if not models and "models" in data:
                models = data["models"]
            if not models and isinstance(data, list):
                models = data
            normalized = []
            for m in models:
                if isinstance(m, dict):
                    if "id" not in m:
                        m["id"] = m.get("name") or m.get("model") or str(m)
                    normalized.append(m)
                else:
                    normalized.append({"id": m})
            return normalized
        elif response.status_code == 404 or response.status_code == 500:
            logger.warning(f"LM Studio returned {response.status_code} for /models endpoint - this is normal")
            return []
        return []

    async def get_models_metadata(self) -> Dict[str, Dict[str, Any]]:
        """Queries /api/v0/models for rich metadata (max_context_length, state, etc.). Returns dict keyed by model ID."""
        base = self.base_url.rsplit('/v1', 1)[0] if '/v1' in self.base_url else self.base_url
        url = f"{base}/api/v0/models"
        try:
            resp = await self._get_client().get(url)
            if resp.status_code == 200:
                data = resp.json()
                entries = data.get("data", [])
                return {m["id"]: m for m in entries if isinstance(m, dict) and "id" in m}
        except Exception as e:
            logger.warning(f"Could not fetch model metadata from {url}: {e}")
        return {}

    async def get_active_model_name(self) -> Optional[str]:
        """Returns the ID of the first loaded model, or None."""
        models = await self.get_loaded_models()
        if models:
            return models[0].get("id")
        return None

    def _parse_reasoning_and_answer(self, full_text: str, response_json: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
        """
        Extracts thinking/reasoning and final answer from response.
        Supports both <think>...</think> tags and 'reasoning_content' API field.
        """
        thinking = ""
        answer = full_text

        # 1. Try to read reasoning_content from response json if available
        if response_json:
            try:
                # Some API returns choice['message']['reasoning_content']
                choices = response_json.get("choices", [])
                if choices:
                    msg = choices[0].get("message", {})
                    if "reasoning_content" in msg and msg["reasoning_content"]:
                        thinking = msg["reasoning_content"]
                        # If reasoning_content was split out, answer is just content
                        answer = msg.get("content", "")
                        return thinking, answer
            except Exception as e:
                logger.debug(f"Reasoning/answer parse (choices) failed: {e}")

        # 2. Fallback to parsing <think> tags from full text
        if "<think>" in full_text:
            try:
                parts = re.split(r"\r?\n\s*response\s*\r?\n", full_text, maxsplit=1)
                think_part = parts[0]
                answer = parts[1].strip() if len(parts) > 1 else ""
                t = re.split(r"\r?\n\s*thinking\s*\r?\n", think_part, maxsplit=1)
                if len(t) > 1:
                    thinking = t[1].strip()
                elif " thinking" in think_part:
                    thinking = think_part.split(" thinking", 1)[1].strip()
                else:
                    thinking = ""
            except Exception:
                # If splitting fails, return full text as answer
                logger.debug("Failed to split reasoning/answer on think tags", exc_info=True)
                pass
        
        return thinking, answer

    async def _native_api_url(self, path: str) -> str:
        """Builds a native API URL from the given path (e.g. '/api/v1/models/load')."""
        base = self.base_url.rsplit('/v1', 1)[0] if '/v1' in self.base_url else self.base_url
        return f"{base.rstrip('/')}{path}"

    async def load_model(self, model_id: str) -> Dict[str, Any]:
        """Loads a model into memory via LM Studio native API.
        Stores the returned instance_id on self for later unload."""
        url = await self._native_api_url("/api/v1/models/load")
        payload = {"model": model_id}
        try:
            resp = await self._get_client().post(url, json=payload, timeout=httpx.Timeout(300.0))
            body = resp.json() if resp.text else {}
            result = {"status_code": resp.status_code, "body": body}
            if isinstance(body, dict):
                iid = (
                    body.get("instance_id")
                    or body.get("id")
                    or body.get("model_id")
                    or body.get("data", {}).get("instance_id")
                    or body.get("data", {}).get("id")
                )
                if iid:
                    self._loaded_instance_id = str(iid)
                    result["instance_id"] = str(iid)
                    logger.info(f"Captured instance_id '{iid}' from load response")
                else:
                    logger.info(f"load_model response (no instance_id found): {json.dumps(body)[:500]}")
            return result
        except Exception as e:
            logger.error(f"load_model failed for {model_id}: {e}")
            return {"error": str(e)}

    async def _fetch_instance_id_from_models(self, model_id: str) -> Optional[str]:
        """Queries /api/v1/models and tries every field of every entry to find instance_id."""
        url = await self._native_api_url("/api/v1/models")
        try:
            resp = await self._get_client().get(url, timeout=10)
            if resp.status_code != 200:
                logger.warning(f"/api/v1/models returned {resp.status_code}")
                return None
            data = resp.json()
            logger.info(f"/api/v1/models raw keys: {list(data.keys())}")
            entries = data.get("data", data.get("models", []))
            logger.info(f"/api/v1/models entry count: {len(entries)}")
            for m in entries:
                if not isinstance(m, dict):
                    continue
                logger.info(f"Model entry keys: {list(m.keys())} | raw: {json.dumps(m)[:300]}")
                if m.get("id") == model_id:
                    iid = (
                        m.get("instance_id")
                        or m.get("id")
                        or m.get("model_id")
                        or m.get("key")
                        or str(m.get("index", ""))
                    )
                    if iid:
                        logger.info(f"Found instance_id '{iid}' for model '{model_id}' via /api/v1/models")
                        return str(iid)
            for m in entries:
                if isinstance(m, dict) and m.get("state") == "loaded":
                    for k, v in m.items():
                        if k and v and ("id" in k.lower() or "instance" in k.lower()):
                            logger.info(f"Fallback instance_id from key '{k}' = '{v}'")
                            return str(v)
        except Exception as e:
            logger.warning(f"_fetch_instance_id_from_models failed: {e}")
        return None

    async def unload_model(self, model_id: Optional[str] = None) -> Dict[str, Any]:
        """Unloads a model. Uses stored instance_id, then queries /api/v1/models,
        then tries model_id as instance_id, then sends empty payload as last resort."""
        url = await self._native_api_url("/api/v1/models/unload")
        instance_id = self._loaded_instance_id
        source = "from_load_response"

        if not instance_id and model_id:
            instance_id = await self._fetch_instance_id_from_models(model_id)
            source = "from_models_query" if instance_id else "none"

        payload = {}
        if instance_id:
            payload["instance_id"] = instance_id
        elif model_id:
            # Try model_id as instance_id (some LM Studio versions use this)
            payload["instance_id"] = model_id
            source = "model_id_as_instance_id"

        logger.info(f"Unloading model '{model_id}' using {source}: payload={payload}")
        try:
            resp = await self._get_client().post(url, json=payload, timeout=httpx.Timeout(60.0))
            body = resp.json() if resp.text else {}
            logger.info(f"Unload response ({resp.status_code}): {json.dumps(body)[:300]}")
            if resp.status_code != 200 and model_id and isinstance(body, dict):
                err_msg = body.get("error", {}).get("message", "")
                if "instance_id" in err_msg and source == "from_models_query":
                    payload2 = {"instance_id": model_id}
                    logger.info(f"Retrying unload with model_id as instance_id: {payload2}")
                    resp2 = await self._get_client().post(url, json=payload2, timeout=httpx.Timeout(60.0))
                    body2 = resp2.json() if resp2.text else {}
                    return {"status_code": resp2.status_code, "body": body2}
            return {"status_code": resp.status_code, "body": body}
        except Exception as e:
            logger.error(f"unload_model failed: {e}")
            return {"error": str(e)}

    async def get_model_state(self, model_id: str) -> Optional[str]:
        """Returns the state of a model ('loaded' or 'not-loaded') or None if not found."""
        base = self.base_url.rsplit('/v1', 1)[0] if '/v1' in self.base_url else self.base_url
        native_url = f"{base}/api/v1/models"
        try:
            resp = await self._get_client().get(native_url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                entries = data.get("data", data.get("models", []))
                for m in entries:
                    if isinstance(m, dict) and m.get("id") == model_id:
                        return m.get("state", "unknown")
        except Exception as e:
            logger.warning(f"get_model_state failed: {e}")
        return None

    async def stop_generation(
        self,
        model_name: str,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Sends a stop command to LM Studio via POST /v1/chat/completions.
        Uses a cancel instruction message to avoid API rejection of empty messages array.
        """
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": "[STOP]"}],
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        try:
            response = await self._get_client().post(url, json=payload, timeout=httpx.Timeout(5.0))
            return {"status_code": response.status_code}
        except Exception as e:
            logger.warning(f"stop_generation failed: {e}")
            return {"error": str(e)}

    async def generate_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        max_completion_tokens: Optional[int] = None,
        stop_tokens: Optional[List[str]] = None,
        model_name: Optional[str] = None,
        images: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Send a completions request to LM Studio.

        Uses stream=True to measure accurate TTFT and TPS.
        If images is provided (list of base64 PNG strings), sends as multimodal message.

        Args:
            prompt: The user prompt text.
            system_prompt: Optional system message prepended to the conversation.
            temperature: Sampling temperature (0.0 = deterministic).
            max_tokens: Maximum tokens to generate (alias for max_completion_tokens).
            max_completion_tokens: Maximum tokens to generate.
            stop_tokens: Optional list of strings that halt generation when encountered.
            model_name: Model ID to use. If None, uses the currently loaded model.
            images: Optional list of base64-encoded PNG image strings (for vision models).

        Returns:
            dict with keys:
                - raw_response (dict): The full API response JSON.
                - thinking_content (str): Reasoning/thinking content (if model outputs it).
                - answer_content (str): The final answer text.
                - tps (float): Tokens per second during generation.
                - ttft (float): Time to first token in seconds.
                - elapsed_time (float): Total generation time in seconds.
                - prompt_tokens (int): Number of input tokens (estimated or from API).
                - completion_tokens (int): Number of output tokens (estimated or from API).
                - total_tokens (int): Total token count.
                - thinking_tokens (int): Tokens in thinking_content (estimated).
                - response_tokens (int): Tokens in answer_content (estimated).
                - stop_reason (str): Why generation stopped ("stop", "length", "repetition", etc.).
        """
        # Accept both max_tokens and max_completion_tokens as aliases
        if max_completion_tokens is not None:
            max_tokens = max_completion_tokens

        if not model_name:
            logger.info("No model_name provided, fetching active model...")
            model_name = await self.get_active_model_name()
            if not model_name:
                raise ValueError("No model is loaded in LM Studio, or server is unreachable.")
        
        # LM Studio expects /v1/chat/completions for OpenAI-compatible API (base_url already includes /v1)
        url = f"{self.base_url}/chat/completions"
        logger.debug("Sending to %s model=%s", url, model_name)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if images:
            content_parts = [{"type": "text", "text": prompt}]
            for b64 in images:
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"}
                })
            messages.append({"role": "user", "content": content_parts})
        else:
            messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model_name,
            "messages": messages,
            "stream": True
        }
        if temperature is not None:
            payload["temperature"] = temperature

        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        if stop_tokens:
            payload["stop"] = stop_tokens

        # Reset repetition detection for this generation call
        self._rep_buffer = ""
        self._repetition_detected = False
        self._rep_consecutive_count = 0
        self._rep_chunk_count = 0

        full_text_parts: list[str] = []
        ttft = 0.0
        start_time = time.time()
        first_chunk_received = False
        _last_token_time = time.time()
        _stream_timed_out = False
        
        # We will parse usage info if sent at the end of the stream, or estimate it
        prompt_tokens_est = int(len(prompt) / 4)
        completion_tokens_est = 0
        thinking_parts: list[str] = []
        answer_content = ""
        
        try:
            logger.debug("Starting streaming request to %s", url)
            async with self._get_client().stream("POST", url, json=payload, timeout=httpx.Timeout(None, connect=30.0, read=600.0, write=60.0, pool=30.0)) as response:
                logger.debug("Response status: %d", response.status_code)

                if response.status_code != 200:
                    error_body = await response.aread()
                    logger.error(f"Error body: {error_body.decode('utf-8', errors='ignore')}")
                    raise RuntimeError(f"LM Studio returned status {response.status_code}: {error_body.decode('utf-8', errors='ignore')}")

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        
                        try:
                            chunk_json = _orjson.loads(data_str)
                            choices = chunk_json.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                
                                if not first_chunk_received:
                                    has_content = delta.get("content") is not None and delta["content"] != ""
                                    has_reasoning = delta.get("reasoning_content") is not None and delta["reasoning_content"] != ""
                                    if has_content or has_reasoning:
                                        ttft = time.time() - start_time
                                        first_chunk_received = True
                                
                                rc = delta.get("reasoning_content")
                                if rc is not None:
                                    thinking_parts.append(rc)
                                    if not self._rep_disabled:
                                        self._rep_buffer += rc
                                        if len(self._rep_buffer) > self._rep_max_len:
                                            self._rep_buffer = self._rep_buffer[-self._rep_max_len:]
                                    _last_token_time = time.time()
                                    self._rep_chunk_count += 1
                                    if not self._rep_disabled and self._rep_chunk_count % self._rep_check_interval == 0 and self._check_repetition():
                                        logger.warning("Repetition detected in reasoning — model may be looping.")
                                        self._repetition_detected = True
                                        break
                                content = delta.get("content")
                                if content is not None:
                                    _last_token_time = time.time()
                                    full_text_parts.append(content)
                                    if not self._rep_disabled:
                                        self._rep_buffer += content
                                        if len(self._rep_buffer) > self._rep_max_len:
                                            self._rep_buffer = self._rep_buffer[-self._rep_max_len:]
                                    self._rep_chunk_count += 1
                                    if not self._rep_disabled and self._rep_chunk_count % self._rep_check_interval == 0 and self._check_repetition():
                                        logger.warning("Repetition detected — model may be looping.")
                                        self._repetition_detected = True
                                        break
                                
                            if "usage" in chunk_json:
                                usage = chunk_json["usage"]
                                prompt_tokens_est = usage.get("prompt_tokens", prompt_tokens_est)
                                completion_tokens_est = usage.get("completion_tokens", completion_tokens_est)
                        except Exception as parse_err:
                            logger.debug(f"Chunk parsing warning: {parse_err}")

        except Exception as e:
            logger.error(f"Inference calling error: {e}", exc_info=True)
            raise

        end_time = time.time()
        total_time = end_time - start_time

        full_text = "".join(full_text_parts)
        thinking_content = "".join(thinking_parts)

        # If not streamed via reasoning_content, parse full_text for <think> tags
        if not thinking_content:
            thinking_content, answer_content = self._parse_reasoning_and_answer(full_text)
        else:
            answer_content = full_text

        # Estimate tokens if API didn't return usage dict
        if completion_tokens_est == 0:
            thinking_tokens = int(len(thinking_content) / 4)
            answer_tokens = int(len(answer_content) / 4)
            completion_tokens_est = thinking_tokens + answer_tokens
        elif thinking_content:
            thinking_ratio = len(thinking_content) / (len(thinking_content) + len(answer_content) + 1)
            thinking_tokens = max(1, int(completion_tokens_est * thinking_ratio))
            answer_tokens = max(1, completion_tokens_est - thinking_tokens)
        else:
            thinking_tokens = 0
            answer_tokens = completion_tokens_est

        generation_time = total_time - ttft
        if generation_time > 0.01 and completion_tokens_est > 0:
            tps = completion_tokens_est / generation_time
        else:
            tps = 0.0

        logger.debug(
            "Generation complete: model=%s tps=%.1f ttft=%.3f tokens=%d elapsed=%.2fs",
            model_name, tps, ttft if first_chunk_received else total_time,
            completion_tokens_est, total_time,
        )

        return {
            "model_name": model_name,
            "raw_response": full_text if not thinking_content else f"<think>\n{thinking_content}\n</think>\n{answer_content}",
            "thinking_content": thinking_content,
            "answer_content": answer_content,
            "elapsed_time": total_time,
            "ttft": ttft if first_chunk_received else total_time,
            "tps": tps,
            "prompt_tokens": prompt_tokens_est,
            "response_tokens": completion_tokens_est,
            "thinking_tokens": thinking_tokens,
            "answer_tokens": answer_tokens,
        }

    async def generate_chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        max_completion_tokens: Optional[int] = None,
        stop_tokens: Optional[List[str]] = None,
        model_name: Optional[str] = None,
        images: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Send a chat completion request with a pre-built messages array.

        Unlike generate_completion(), this accepts a full conversation history
        (list of {"role": ..., "content": ...} dicts) directly, enabling
        true multi-turn conversations via the OpenAI messages API.

        Args:
            messages: Full message history. Each dict has "role" ("system", "user", "assistant") and "content".
            temperature: Sampling temperature (0.0 = deterministic).
            max_tokens: Maximum tokens to generate (alias for max_completion_tokens).
            max_completion_tokens: Maximum tokens to generate.
            stop_tokens: Optional list of strings that halt generation when encountered.
            model_name: Model ID to use. If None, uses the currently loaded model.
            images: Optional list of base64-encoded PNG image strings (appended as user image content).

        Returns:
            Same dict as generate_completion().
        """
        if max_completion_tokens is not None:
            max_tokens = max_completion_tokens

        if not model_name:
            model_name = await self.get_active_model_name()
            if not model_name:
                raise ValueError("No model is loaded in LM Studio, or server is unreachable.")

        url = f"{self.base_url}/chat/completions"
        logger.debug("Sending chat completion to %s model=%s messages=%d", url, model_name, len(messages))

        # Build final messages list, handling images if provided
        final_messages = []
        for msg in messages:
            final_messages.append(msg)

        # Append images to the last user message if provided
        if images and final_messages:
            last_msg = final_messages[-1]
            if last_msg.get("role") == "user":
                content_parts = [{"type": "text", "text": last_msg.get("content", "")}]
                for b64 in images:
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"}
                    })
                final_messages[-1] = {"role": "user", "content": content_parts}

        # Estimate prompt tokens from all message content
        prompt_text = " ".join(
            m.get("content", "") if isinstance(m.get("content"), str) else ""
            for m in final_messages
        )
        prompt_tokens_est = int(len(prompt_text) / 4)

        payload = {
            "model": model_name,
            "messages": final_messages,
            "stream": True,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if stop_tokens:
            payload["stop"] = stop_tokens

        # Reset repetition detection
        self._rep_buffer = ""
        self._repetition_detected = False
        self._rep_consecutive_count = 0
        self._rep_chunk_count = 0

        full_text_parts: list[str] = []
        ttft = 0.0
        start_time = time.time()
        first_chunk_received = False
        _last_token_time = time.time()
        thinking_parts: list[str] = []
        completion_tokens_est = 0

        try:
            async with self._get_client().stream("POST", url, json=payload, timeout=httpx.Timeout(None, connect=30.0, read=600.0, write=60.0, pool=30.0)) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    raise RuntimeError(f"LM Studio returned status {response.status_code}: {error_body.decode('utf-8', errors='ignore')}")

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            chunk_json = _orjson.loads(data_str)
                            choices = chunk_json.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                if not first_chunk_received:
                                    has_content = delta.get("content") is not None and delta["content"] != ""
                                    has_reasoning = delta.get("reasoning_content") is not None and delta["reasoning_content"] != ""
                                    if has_content or has_reasoning:
                                        ttft = time.time() - start_time
                                        first_chunk_received = True
                                rc = delta.get("reasoning_content")
                                if rc is not None:
                                    thinking_parts.append(rc)
                                    if not self._rep_disabled:
                                        self._rep_buffer += rc
                                        if len(self._rep_buffer) > self._rep_max_len:
                                            self._rep_buffer = self._rep_buffer[-self._rep_max_len:]
                                    _last_token_time = time.time()
                                    self._rep_chunk_count += 1
                                    if not self._rep_disabled and self._rep_chunk_count % self._rep_check_interval == 0 and self._check_repetition():
                                        self._repetition_detected = True
                                        break
                                content = delta.get("content")
                                if content is not None:
                                    _last_token_time = time.time()
                                    full_text_parts.append(content)
                                    if not self._rep_disabled:
                                        self._rep_buffer += content
                                        if len(self._rep_buffer) > self._rep_max_len:
                                            self._rep_buffer = self._rep_buffer[-self._rep_max_len:]
                                    self._rep_chunk_count += 1
                                    if not self._rep_disabled and self._rep_chunk_count % self._rep_check_interval == 0 and self._check_repetition():
                                        self._repetition_detected = True
                                        break
                            if "usage" in chunk_json:
                                usage = chunk_json["usage"]
                                prompt_tokens_est = usage.get("prompt_tokens", prompt_tokens_est)
                                completion_tokens_est = usage.get("completion_tokens", completion_tokens_est)
                        except Exception as parse_err:
                            logger.debug(f"Chunk parsing warning: {parse_err}")
        except Exception as e:
            logger.error(f"Inference calling error: {e}", exc_info=True)
            raise

        end_time = time.time()
        total_time = end_time - start_time
        full_text = "".join(full_text_parts)
        thinking_content = "".join(thinking_parts)

        if not thinking_content:
            thinking_content, answer_content = self._parse_reasoning_and_answer(full_text)
        else:
            answer_content = full_text

        if completion_tokens_est == 0:
            thinking_tokens = int(len(thinking_content) / 4)
            answer_tokens = int(len(answer_content) / 4)
            completion_tokens_est = thinking_tokens + answer_tokens
        elif thinking_content:
            thinking_ratio = len(thinking_content) / (len(thinking_content) + len(answer_content) + 1)
            thinking_tokens = max(1, int(completion_tokens_est * thinking_ratio))
            answer_tokens = max(1, completion_tokens_est - thinking_tokens)
        else:
            thinking_tokens = 0
            answer_tokens = completion_tokens_est

        generation_time = total_time - ttft
        if generation_time > 0.01 and completion_tokens_est > 0:
            tps = completion_tokens_est / generation_time
        else:
            tps = 0.0

        return {
            "model_name": model_name,
            "raw_response": full_text if not thinking_content else f"<think>\n{thinking_content}\n</think>\n{answer_content}",
            "thinking_content": thinking_content,
            "answer_content": answer_content,
            "elapsed_time": total_time,
            "ttft": ttft if first_chunk_received else total_time,
            "tps": tps,
            "prompt_tokens": prompt_tokens_est,
            "response_tokens": completion_tokens_est,
            "thinking_tokens": thinking_tokens,
            "answer_tokens": answer_tokens,
        }

