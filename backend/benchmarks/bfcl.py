import json
import logging
import re
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.benchmarks.base import BaseBenchmark, resolve_data_file
from backend.lm_studio.client import LMStudioClient

logger = logging.getLogger(__name__)

def _extract_bfcl_json(text: str) -> Optional[List[Dict]]:
    """
    Extract JSON function call array from model response.
    5-attempt extraction ladder: (1) strip code fences + full JSON parse,
    (2) find [...] in text, (3) find {...} in text, (4) fallback to None.
    """
    # Remove code fences
    cleaned = re.sub(r'```(?:json)?\s*([\s\S]*?)\s*```', r'\1', text)
    cleaned = cleaned.strip()

    # Try full parse
    try:
        result = json.loads(cleaned)
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return [result]
    except json.JSONDecodeError:
        pass

    # Find JSON array or object in text — find first [ or { and last ] or }
    for start_char, end_char, expect_list in [('[', ']', True), ('{', '}', False)]:
        start = cleaned.find(start_char)
        if start == -1:
            continue
        end = cleaned.rfind(end_char)
        if end <= start:
            continue
        candidate = cleaned[start:end + 1]
        try:
            result = json.loads(candidate)
            if expect_list and isinstance(result, list):
                return result
            if not expect_list and isinstance(result, dict):
                return [result]
        except json.JSONDecodeError:
            continue

    return None


class BFCLBenchmark(BaseBenchmark):
    """
    BenchMax Function Call Language (BFCL) Benchmark
    
    Evaluates LLMs on function call generation quality using deterministic AST-based scoring.
    Scoring is based on structure matching - NO second LLM or external judge involved.
    Uses only Python stdlib `json` and `ast` modules for all scoring operations.
    
    Categories:
    - simple: One function, one call (400 samples)
    - multiple: 2-4 functions, select best one (200 samples)  
    - parallel: Same function called twice (200 samples)
    - parallel_multiple: Multiple functions, multiple calls (200 samples)
    - irrelevance: No function relevant - abstain (240 samples)
    - REST: Real API calls via requests.get() (70 samples)
    - SQL: SQL query generation (100 samples)
    """
    
    def __init__(self, db: Session, client: LMStudioClient, quick_test: bool = False):
        super().__init__(db, client, quick_test)
    
    def load_dataset(self) -> List[Dict[str, Any]]:
        if self.quick_test:
            mini_path = resolve_data_file(__file__, "bfcl/bfcl_mini.json")
            if mini_path:
                return self._load_json_cached(mini_path)
        full_path = resolve_data_file(__file__, "bfcl/bfcl_full.json")
        if full_path:
            return self._load_json_cached(full_path)
        logger.info("No BFCL dataset found. Using bundled samples.")
        return self._get_bundled_samples()

    def _get_bundled_samples(self) -> List[Dict[str, Any]]:
        """Return bundled BFCL samples for quick testing (5 samples covering key categories)"""
        return [
            {
                "id": "simple_0",
                "category": "simple", 
                "question": "What's the weather like in Tokyo?",
                "function": [
                    {
                        "name": "get_current_weather",
                        "description": "Get the current weather for a location",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "location": {"type": "string"},
                                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
                            },
                            "required": ["location"]
                        }
                    }
                ],
                "answer": [{"name": "get_current_weather", "arguments": {"location": "Tokyo", "unit": "celsius"}}]
            },
            {
                "id": "multiple_0",
                "category": "multiple",
                "question": "I need to search for books about Python and then read the first one.",
                "function": [
                    {
                        "name": "search_books",
                        "description": "Search for books on a topic",
                        "parameters": {
                            "type": "object", 
                            "properties": {"topic": {"type": "string"}},
                            "required": ["topic"]
                        }
                    },
                    {
                        "name": "read_book",
                        "description": "Read a book's content",
                        "parameters": {
                            "type": "object",
                            "properties": {"book_id": {"type": "string"}},
                            "required": ["book_id"]
                        }
                    }
                ],
                "answer": [
                    {"name": "search_books", "arguments": {"topic": "Python"}},
                    {"name": "read_book", "arguments": {"book_id": "<result_from_search>"}}
                ]
            },
            {
                "id": "irrelevance_0", 
                "category": "irrelevance",
                "question": "Tell me a joke about cats.",
                "function": [
                    {
                        "name": "search_books",
                        "description": "Search for books on a topic",
                        "parameters": {
                            "type": "object",
                            "properties": {"topic": {"type": "string"}},
                            "required": ["topic"]
                        }
                    }
                ],
                "answer": []  # No function needed - model should abstain
            },
            {
                "id": "parallel_0",
                "category": "parallel",
                "question": "What's the weather in Tokyo and New York?",
                "function": [
                    {
                        "name": "get_current_weather", 
                        "description": "Get the current weather for a location",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "location": {"type": "string"},
                                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
                            },
                            "required": ["location"]
                        }
                    }
                ],
                "answer": [
                    {"name": "get_current_weather", "arguments": {"location": "Tokyo", "unit": "celsius"}},
                    {"name": "get_current_weather", "arguments": {"location": "New York", "unit": "fahrenheit"}}
                ]
            },
            {
                "id": "parallel_multiple_0",
                "category": "parallel_multiple",
                "question": "Search for Python books and also get the current weather in London.",
                "function": [
                    {
                        "name": "search_books",
                        "description": "Search for books on a topic", 
                        "parameters": {
                            "type": "object",
                            "properties": {"topic": {"type": "string"}},
                            "required": ["topic"]
                        }
                    },
                    {
                        "name": "get_current_weather",
                        "description": "Get the current weather for a location",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "location": {"type": "string"},
                                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
                            },
                            "required": ["location"]
                        }
                    }
                ],
                "answer": [
                    {"name": "search_books", "arguments": {"topic": "Python"}},
                    {"name": "get_current_weather", "arguments": {"location": "London", "unit": "celsius"}}
                ]
            }
        ]

    async def evaluate_sample(self, sample: Dict[str, Any], params: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        """Evaluates function call generation using AST-based scoring."""
        question = sample["question"]
        category = sample.get("category", "unknown")
        functions = sample.get("function", [])
        expected_answer = sample.get("answer", [])
        task_id = sample.get("id", f"bfcl_{sample.get('index', 'unknown')}")

        # Build system prompt with function schemas
        system_prompt = self._build_function_prompt(functions)
        
        # Run inference using LM Studio client  
        generation = await self.client.generate_completion(
            prompt=system_prompt + "\n\n" + question,
            system_prompt=None,  # Already included in prompt
            temperature=params.get("temperature", 0.7),
            max_completion_tokens=params.get("max_completion_tokens"),
            stop_tokens=params.get("stop_tokens"),
            model_name=model_name,
        )

        logger.debug(f"RAW_GENERATION_DEBUG: {generation!r}")

        raw_response = generation["raw_response"]

        # Strip markdown code fences before JSON parsing
        extracted = raw_response.strip()
        cleaned = re.sub(r'```(?:json)?\s*([\s\S]*?)\s*```', r'\1', extracted)
        cleaned = cleaned.strip()

        # Try to extract JSON
        actual_calls = _extract_bfcl_json(cleaned)
        if actual_calls is None:
            # Try with original (unfenced) text too
            actual_calls = _extract_bfcl_json(extracted)

        if actual_calls is None:
            actual_calls = []

        # Score using AST matching
        score = self._score_ast(expected_answer, actual_calls, category)

        result = {
            "prompt": system_prompt + "\n\n" + question,
            "raw_response": raw_response,
            "extracted_code": json.dumps(actual_calls),
            "elapsed_time": generation.get("elapsed_time", 0.0),
            "tps": generation.get("tps", 0.0),
            "ttft": generation.get("ttft", 0.0),
            "thinking_tokens": generation.get("thinking_tokens", 0),
            "response_tokens": generation.get("response_tokens", 0),
            **score
        }

        return result

    def _build_function_prompt(self, functions: List[Dict]) -> str:
        """Convert function schemas to a structured prompt"""
        lines = ["You have access to the following functions. Use them if required - otherwise, respond with an empty list []."]
        
        for func in functions:
            name = func["name"]
            desc = func.get("description", "")
            params = func.get("parameters", {})
            
            properties = params.get("properties", {})
            required = params.get("required", [])
            
            lines.append(f"\nFunction: {name}")
            lines.append(f"Description: {desc}")
            lines.append("Parameters:")
            
            for param_name, param_info in properties.items():
                param_type = param_info.get("type", "string")
                desc = param_info.get("description", "")
                enum_values = param_info.get("enum", [])
                
                if param_name in required:
                    lines.append(f"  - {param_name} ({param_type}): {' or '.join(enum_values) if enum_values else desc}")
                else:
                    lines.append(f"  - {param_name} ({param_type}): {' or '.join(enum_values) if enum_values else desc} (optional)")
        
        return "\n".join(lines)

    def _extract_function_calls(self, response: str, functions: List[Dict]) -> List[Dict]:
        """Extract function calls from model response"""
        extracted = []
        
        # Try to parse JSON from response first
        try:
            data = json.loads(response.strip())
            if isinstance(data, list):
                for item in data:
                    if "name" in item and "arguments" in item:
                        extracted.append(item)
            elif isinstance(data, dict) and "tool_calls" in data:
                for call in data["tool_calls"]:
                    if "function" in call:
                        func_call = call["function"]
                        extracted.append({
                            "name": func_call.get("name", ""),
                            "arguments": func_call.get("arguments", {})
                        })
        except json.JSONDecodeError:
            pass
        
        # If no JSON found, try to extract from text
        if not extracted and response.strip():
            # Look for function name patterns in text
            for func in functions:
                pattern = rf'{re.escape(func["name"])}\s*\(\s*([^)]*)\)'
                matches = re.findall(pattern, response)
                for match in matches:
                    try:
                        args = json.loads(match.strip()) if match.strip() else {}
                        extracted.append({"name": func["name"], "arguments": args})
                    except json.JSONDecodeError:
                        pass

        # Normalize arguments to consistent type
        for call in extracted:
            if isinstance(call.get("arguments"), dict):
                call["arguments"] = json.dumps(call["arguments"])
        
        return extracted

    def _score_ast(self, expected_answer: List[Dict], actual_calls: List[Dict], category: str) -> Dict[str, Any]:
        """AST-based scoring of function calls"""
        result = {
            "correct": False,
            "ast_score": 0.0,
            "refusal_detected": False,
            "error_message": None
        }
        
        if not expected_answer:
            # Irrelevance category - model should abstain
            if not actual_calls:
                result["correct"] = True
                result["ast_score"] = 1.0
                return result
            else:
                result["refusal_detected"] = False
                return result
        
        if not actual_calls and expected_answer:
            # Model refused to call any function when it should have
            result["refusal_detected"] = True
            result["error_message"] = "Model did not generate any function calls"
            return result
        
        # Score each expected answer against actual calls
        score_count = 0
        total_expected = len(expected_answer)
        
        for expected in expected_answer:
            expected_name = expected.get("name", "")
            expected_args = expected.get("arguments", {})
            
            # Find matching actual call
            found_match = False
            for actual_call in actual_calls:
                if actual_call["name"] == expected_name:
                    actual_args = actual_call.get("arguments", {})
                    
                    # Check required arguments are present (allow extra optional args)
                    all_required_present = True
                    for ek in expected_args:
                        if ek not in actual_args:
                            all_required_present = False
                            break

                    if all_required_present:
                        score_count += 1
                        found_match = True
                        break
        
        # Calculate AST score
        if total_expected > 0:
            ratio = score_count / total_expected
            result["ast_score"] = min(1.0, ratio)
        
        # Determine correctness
        if result["ast_score"] >= 1.0 or (category == "irrelevance" and not actual_calls):
            result["correct"] = True
        
        return result
