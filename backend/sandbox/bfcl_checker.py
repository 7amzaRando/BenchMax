"""
Standalone BFCL AST checker.
Adapted from bfcl-eval's ast_checker.py to avoid importing the full bfcl_eval
package (which pulls in anthropic, openai, google-generativeai, etc.).
"""
import re
from typing import Dict, Any, List, Optional

Language = type("Language", (), {"PYTHON": "python", "JAVA": "java", "JAVASCRIPT": "javascript"})()

PYTHON_TYPE_MAPPING = {
    "string": str, "integer": int, "float": float, "boolean": bool,
    "array": list, "tuple": list, "dict": dict, "any": str,
}
PYTHON_NESTED_TYPE_CHECK_LIST = ["array", "tuple"]


def ast_checker(
    func_description: List[Dict],
    model_output: List[Dict],
    possible_answer: List[Dict],
    language: str,
    test_category: str,
    model_name: str,
) -> Dict[str, Any]:
    if "parallel" in test_category:
        return _parallel_function_checker_no_order(func_description, model_output, possible_answer, model_name)
    elif "multiple" in test_category:
        return _multiple_function_checker(func_description, model_output, possible_answer, model_name)
    else:
        if len(model_output) != 1:
            return {"valid": False, "error": ["Wrong number of functions."], "error_type": "wrong_count"}
        return _simple_function_checker(func_description[0], model_output[0], possible_answer[0], model_name)


def _find_description(func_descriptions, name):
    if isinstance(func_descriptions, list):
        for fd in func_descriptions:
            if fd["name"] == name:
                return fd
        return None
    return func_descriptions


def _convert_func_name(function_name, model_name):
    if "." in function_name and any(kw in model_name.lower() for kw in ["gpt", "oai", "mistral", "gemini"]):
        return re.sub(r"\.", "_", function_name)
    return function_name


def _type_checker(param, value, possible_answer, expected_type_desc, expected_type, nested_type):
    result = {"valid": True, "error": [], "is_variable": False, "error_type": "type_error"}

    possible_answer_type = None
    for ans in possible_answer:
        if ans != "":
            possible_answer_type = type(ans)
            break

    if possible_answer_type is not None and possible_answer_type != expected_type:
        result["is_variable"] = True

    if type(value) == expected_type:
        if nested_type is None:
            result["is_variable"] = result.get("is_variable", False)
            return result
        for possible_answer_item in possible_answer:
            flag = True
            if isinstance(possible_answer_item, list):
                for value_item in value:
                    cr = _type_checker(param, value_item, possible_answer_item, str(nested_type), nested_type, None)
                    if not cr["valid"]:
                        flag = False
                        break
            if flag:
                return {"valid": True, "error": [], "is_variable": result.get("is_variable", False)}
        return {"valid": False, "error": [f"Nested type check failed for {param}"], "error_type": "nested"}

    if possible_answer_type is not None and type(value) == possible_answer_type:
        result["is_variable"] = True
        return result

    return {"valid": False, "error": [f"Type mismatch for {param}"], "error_type": "type_error"}


def _standardize_string(s):
    return re.sub(r"[ \,\.\/\-\_\*\^]", "", s).lower().replace("'", '"')


def _string_checker(param, model_output, possible_answer):
    std_possible = [_standardize_string(p) if isinstance(p, str) else p for p in possible_answer]
    if _standardize_string(model_output) not in std_possible:
        return {"valid": False, "error": [f"Invalid string for {param}"], "error_type": "string_error"}
    return {"valid": True, "error": []}


def _simple_function_checker(func_description, model_output, possible_answer, model_name):
    possible_answer = list(possible_answer.values())[0]
    func_name = func_description["name"]
    param_details = func_description["parameters"]["properties"]
    required_params = func_description["parameters"]["required"]

    func_name = _convert_func_name(func_name, model_name)

    if func_name not in model_output:
        return {"valid": False, "error": [f"Function {func_name} not found"], "error_type": "wrong_func_name"}

    model_params = model_output[func_name]

    for param in required_params:
        if param not in model_params:
            return {"valid": False, "error": [f"Missing required param: {param}"], "error_type": "missing_required"}

    for param, value in model_params.items():
        if param not in param_details or param not in possible_answer:
            return {"valid": False, "error": [f"Unexpected param: {param}"], "error_type": "unexpected_param"}

        full_details = param_details[param]
        expected_type_desc = full_details["type"]
        nested_type = None

        expected_type = PYTHON_TYPE_MAPPING.get(expected_type_desc, str)
        if expected_type_desc in PYTHON_NESTED_TYPE_CHECK_LIST:
            nested_type = PYTHON_TYPE_MAPPING.get(full_details.get("items", {}).get("type", "string"), str)

        if expected_type_desc == "tuple" and isinstance(value, tuple):
            value = list(value)

        if expected_type_desc == "float" and isinstance(value, int):
            value = float(value)

        tc = _type_checker(param, value, possible_answer[param], expected_type_desc, expected_type, nested_type)
        if not tc["valid"]:
            return tc

        if not tc.get("is_variable", False):
            if expected_type == dict:
                dcr = _dict_checker(param, value, possible_answer[param])
                if not dcr["valid"]:
                    return dcr
            elif expected_type_desc == "array" and nested_type == dict:
                ldr = _list_dict_checker(param, value, possible_answer[param])
                if not ldr["valid"]:
                    return ldr
            elif expected_type == str:
                scr = _string_checker(param, value, possible_answer[param])
                if not scr["valid"]:
                    return scr
            elif expected_type == list:
                lcr = _list_checker(param, value, possible_answer[param])
                if not lcr["valid"]:
                    return lcr

        if value not in possible_answer[param]:
            return {"valid": False, "error": [f"Invalid value for {param}"], "error_type": "value_error"}

    for param in possible_answer:
        if param not in model_params and "" not in possible_answer[param]:
            return {"valid": False, "error": [f"Optional param {param} not provided"], "error_type": "missing_optional"}

    return {"valid": True, "error": []}


def _parallel_function_checker_no_order(func_descriptions, model_output, possible_answers, model_name):
    if len(model_output) != len(possible_answers):
        return {"valid": False, "error": ["Wrong number of functions."], "error_type": "wrong_count"}

    matched_indices = []
    for i in range(len(possible_answers)):
        func_name_expected = list(possible_answers[i].keys())[0]
        func_desc = _find_description(func_descriptions, func_name_expected)

        found = False
        for idx in range(len(model_output)):
            if idx in matched_indices:
                continue
            result = _simple_function_checker(func_desc, model_output[idx], possible_answers[i], model_name)
            if result["valid"]:
                matched_indices.append(idx)
                found = True
                break

        if not found:
            return {"valid": False, "error": [f"No match for possible answer {i}"], "error_type": "no_match"}

    return {"valid": True, "error": []}


def _multiple_function_checker(func_descriptions, model_output, possible_answers, model_name):
    if len(model_output) != len(possible_answers):
        return {"valid": False, "error": ["Wrong number of functions."], "error_type": "wrong_count"}

    func_name_expected = list(possible_answers[0].keys())[0]
    func_desc = _find_description(func_descriptions, func_name_expected)
    return _simple_function_checker(func_desc, model_output[0], possible_answers[0], model_name)


def _dict_checker(param, model_output, possible_answers):
    for pa in possible_answers:
        if pa == "":
            continue
        flag = True
        for key, value in model_output.items():
            if key not in pa:
                flag = False
                break
            sv = _standardize_string(value) if isinstance(value, str) else value
            sp = [_standardize_string(p) if isinstance(p, str) else p for p in pa[key]]
            if sv not in sp:
                flag = False
                break
        if flag:
            return {"valid": True, "error": []}
    return {"valid": False, "error": [f"Dict value mismatch for {param}"], "error_type": "dict_error"}


def _list_checker(param, model_output, possible_answer):
    std_out = list(model_output)
    for i in range(len(std_out)):
        if isinstance(std_out[i], str):
            std_out[i] = _standardize_string(model_output[i])

    std_pa = []
    for pa in possible_answer:
        std_pa.append([])
        for j in range(len(pa)):
            if isinstance(pa[j], str):
                std_pa[-1].append(_standardize_string(pa[j]))
            else:
                std_pa[-1].append(pa[j])

    if std_out not in std_pa:
        return {"valid": False, "error": [f"List value mismatch for {param}"], "error_type": "list_error"}
    return {"valid": True, "error": []}


def _list_dict_checker(param, model_output, possible_answers):
    for pa in possible_answers:
        if pa == "":
            continue
        if len(model_output) != len(pa):
            continue
        match = True
        for i, item in enumerate(model_output):
            if isinstance(item, dict):
                dr = _dict_checker(f"{param}[{i}]", item, [pa[i]] if i < len(pa) else [])
                if not dr["valid"]:
                    match = False
                    break
        if match:
            return {"valid": True, "error": []}
    return {"valid": False, "error": [f"List of dicts mismatch for {param}"], "error_type": "list_dict_error"}
