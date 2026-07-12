import json
import logging
import re
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.benchmarks.base import BaseBenchmark, resolve_data_file
from backend.lm_studio.client import LMStudioClient
from backend.sandbox.bfcl_checker import ast_checker, Language, multi_turn_simplified_checker

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
        if sample.get("multi_turn"):
            return await self._evaluate_multi_turn(sample, params, model_name)
        return await self._evaluate_single_turn(sample, params, model_name)

    async def _evaluate_single_turn(self, sample: Dict[str, Any], params: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        question = sample["question"]
        category = sample.get("category", "unknown")
        functions = sample.get("function", [])
        expected_answer = sample.get("answer", [])
        task_id = sample.get("id", f"bfcl_{sample.get('index', 'unknown')}")

        system_prompt = self._build_function_prompt(functions)

        generation = await self.client.generate_completion(
            prompt=system_prompt + "\n\n" + question,
            system_prompt=None,
            temperature=params.get("temperature", 0.7),
            max_completion_tokens=params.get("max_completion_tokens"),
            stop_tokens=params.get("stop_tokens"),
            model_name=model_name,
        )

        logger.debug(f"RAW_GENERATION_DEBUG: {generation!r}")

        raw_response = generation["raw_response"]

        extracted = raw_response.strip()
        cleaned = re.sub(r'```(?:json)?\s*([\s\S]*?)\s*```', r'\1', extracted)
        cleaned = cleaned.strip()

        actual_calls = _extract_bfcl_json(cleaned)
        if actual_calls is None:
            actual_calls = _extract_bfcl_json(extracted)

        if actual_calls is None:
            actual_calls = []

        if category in ("irrelevance", "live_irrelevance") or not expected_answer:
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
                    "error_message": f"Checker error: {e}",
                }

        return {
            "prompt": system_prompt + "\n\n" + question,
            "raw_response": raw_response,
            "extracted_code": json.dumps(actual_calls),
            "correct": correct,
            "error_message": score_data.get("error_message"),
            "elapsed_time": generation.get("elapsed_time", 0.0),
            "tps": generation.get("tps", 0.0),
            "ttft": generation.get("ttft", 0.0),
            "thinking_tokens": generation.get("thinking_tokens", 0),
            "response_tokens": generation.get("response_tokens", 0),
            "scoring_details": score_data,
        }

    async def _evaluate_multi_turn(self, sample: Dict[str, Any], params: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        question_turns = sample.get("question", [])
        ground_truth = sample.get("answer", [])
        category = sample.get("category", "multi_turn_base")
        involved_classes = sample.get("involved_classes", [])
        initial_config = sample.get("initial_config", {})
        excluded_function = sample.get("excluded_function", "")
        missed_function = sample.get("missed_function", "")

        system_prompt = "You have access to the following system classes and methods.\n"
        for cls_name in involved_classes:
            system_prompt += f"\n- {cls_name}: Available for file system and data operations.\n"
        if initial_config:
            system_prompt += f"\nInitial state: {json.dumps(initial_config)}\n"
        system_prompt += "\nRespond with a JSON array of function calls, e.g. [{\"name\": \"cd\", \"arguments\": {\"folder\": \"documents\"}}]"

        all_turns_output = []
        raw_responses = []
        total_elapsed = 0.0
        total_tps = 0.0
        total_ttft = 0.0
        total_thinking = 0
        total_response_tokens = 0
        conversation_history = []

        for turn_idx, turn in enumerate(question_turns):
            user_msg = turn[0]["content"] if isinstance(turn, list) and turn else str(turn)

            prompt_parts = [system_prompt]
            if conversation_history:
                prompt_parts.append("\nConversation so far:")
                for entry in conversation_history:
                    prompt_parts.append(f"\nUser: {entry['user']}")
                    if entry["model_calls"]:
                        prompt_parts.append(f"Assistant: {json.dumps(entry['model_calls'])}")
            prompt_parts.append(f"\n\nNew request: {user_msg}")
            full_prompt = "\n".join(prompt_parts)

            generation = await self.client.generate_completion(
                prompt=full_prompt,
                system_prompt=None,
                temperature=params.get("temperature", 0.7),
                max_completion_tokens=params.get("max_completion_tokens"),
                stop_tokens=params.get("stop_tokens"),
                model_name=model_name,
            )

            raw_response = generation["raw_response"]
            raw_responses.append(raw_response)

            extracted = raw_response.strip()
            cleaned = re.sub(r'```(?:json)?\s*([\s\S]*?)\s*```', r'\1', extracted)
            cleaned = cleaned.strip()
            turn_calls = _extract_bfcl_json(cleaned)
            if turn_calls is None:
                turn_calls = _extract_bfcl_json(extracted)
            if turn_calls is None:
                turn_calls = []

            all_turns_output.append(turn_calls)
            conversation_history.append({"user": user_msg, "model_calls": turn_calls})

            total_elapsed += generation.get("elapsed_time", 0.0)
            total_tps += generation.get("tps", 0.0)
            total_ttft += generation.get("ttft", 0.0)
            total_thinking += generation.get("thinking_tokens", 0)
            total_response_tokens += generation.get("response_tokens", 0)

        result_check = multi_turn_simplified_checker(
            model_turns=all_turns_output,
            ground_truth_turns=ground_truth,
            test_category=category,
            excluded_function=excluded_function,
            missed_function=missed_function,
        )
        correct = result_check["valid"]

        return {
            "prompt": json.dumps({"turns": question_turns, "system": system_prompt}),
            "raw_response": json.dumps(raw_responses),
            "extracted_code": json.dumps(all_turns_output),
            "correct": correct,
            "error_message": result_check.get("error_message") if not correct else None,
            "elapsed_time": total_elapsed,
            "tps": total_tps / max(len(question_turns), 1),
            "ttft": total_ttft / max(len(question_turns), 1),
            "thinking_tokens": total_thinking,
            "response_tokens": total_response_tokens,
            "scoring_details": {
                "multi_turn": True,
                "checker_result": result_check,
                "per_turn_output": all_turns_output,
                "categories": [category],
            },
        }

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
