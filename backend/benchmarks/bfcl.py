import json
import logging
import re
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.benchmarks.base import BaseBenchmark, resolve_data_file
from backend.lm_studio.client import LMStudioClient
from backend.sandbox.bfcl_checker import ast_checker, Language

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

        # Score using official BFCL AST checker
        if category == "irrelevance" or not expected_answer:
            # Irrelevance: model should abstain
            correct = len(actual_calls) == 0
            score_data = {
                "ast_score": 1.0 if correct else 0.0,
                "refusal_detected": len(actual_calls) > 0 if not expected_answer else False,
                "error_message": None if correct else "Model called functions when it should abstain",
            }
        else:
            try:
                official_answer = self._bm_to_official(expected_answer)
                official_model_out = self._model_output_to_official(actual_calls)
                result_check = ast_checker(
                    func_description=functions,
                    model_output=official_model_out,
                    possible_answer=official_answer,
                    language=Language.PYTHON,
                    test_category=category,
                    model_name=model_name,
                )
                correct = result_check["valid"]
                err = "; ".join(result_check.get("error", [])) if not correct else None
                score_data = {
                    "ast_score": 1.0 if correct else 0.0,
                    "refusal_detected": False,
                    "error_message": err,
                }
            except Exception as e:
                logger.warning(f"Official AST checker failed for {task_id}, using fallback: {e}")
                correct = False
                score_data = {
                    "ast_score": 0.0,
                    "refusal_detected": False,
                    "error_message": f"Official checker error: {e}",
                }

        result = {
            "prompt": system_prompt + "\n\n" + question,
            "raw_response": raw_response,
            "extracted_code": json.dumps(actual_calls),
            "correct": correct,
            "elapsed_time": generation.get("elapsed_time", 0.0),
            "tps": generation.get("tps", 0.0),
            "ttft": generation.get("ttft", 0.0),
            "thinking_tokens": generation.get("thinking_tokens", 0),
            "response_tokens": generation.get("response_tokens", 0),
            **score_data
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

    @staticmethod
    def _bm_to_official(answer: List[Dict]) -> List[Dict]:
        """Convert BenchMax answer format to bfcl-eval expected format.
        
        BenchMax: [{"name": "func", "arguments": {"param": "val"}}]
        Official: [{"func": {"param": ["val"]}}]
        """
        result = []
        for item in answer:
            name = item["name"]
            args = item.get("arguments", {})
            converted = {name: {k: [v] for k, v in args.items()}}
            result.append(converted)
        return result

    @staticmethod
    def _model_output_to_official(calls: List[Dict]) -> List[Dict]:
        """Convert BenchMax model output format to bfcl-eval format.
        
        BenchMax: [{"name": "func", "arguments": {"param": "val"}}]
        Official: [{"func": {"param": "val"}}]
        """
        if not calls:
            return [{}]
        valid = [c for c in calls if isinstance(c, dict)]
        if not valid:
            return [{}]
        return [{c["name"]: c.get("arguments", {})} for c in valid]
