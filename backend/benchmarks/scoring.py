import re
import logging
from typing import Dict, Any, Optional, Tuple, Callable

logger = logging.getLogger(__name__)

def score_mcq(response: str, answer: str) -> Tuple[bool, str]:
    if not response or not response.strip():
        return False, "Empty response"
    extracted = re.findall(r'\b([A-Z])\b', response)
    if not extracted:
        return False, f"No letter answer found, expected {answer}"
    chosen = extracted[-1]
    if chosen == answer:
        return True, ""
    return False, f"Expected {answer}, got {chosen}"

def score_code(response: str, func_name: str) -> Tuple[bool, str]:
    if not response or not response.strip():
        return False, "Empty response"
    pattern = r'def\s+' + re.escape(func_name) + r'\s*\('
    if re.search(pattern, response):
        return True, ""
    alt = r'```.*\n.*' + re.escape(func_name) + r'.*```'
    if re.search(alt, response, re.DOTALL):
        return True, ""
    return False, f"Function '{func_name}' not found in response"

def score_exact(response: str, answer: str) -> Tuple[bool, str]:
    if not response or not response.strip():
        return False, "Empty response"
    escaped = re.escape(answer.strip())
    if re.search(r'\b' + escaped + r'\b', response, re.IGNORECASE):
        return True, ""
    return False, f"Expected '{answer}', not found in response"

def score_free_form(response: str, answer: str) -> Tuple[bool, str]:
    if not response or not response.strip():
        return False, "Empty response"
    keywords = [k.strip().lower() for k in re.split(r'[,;\s]+', answer) if len(k.strip()) > 2]
    if not keywords:
        return True, ""
    missing = [kw for kw in keywords if kw not in response.lower()]
    if missing:
        return False, f"Missing keywords: {', '.join(missing[:3])}"
    return True, ""

def get_scorer(sample_type: str) -> Callable:
    scorers = {
        "mcq": score_mcq,
        "code": score_code,
        "exact": score_exact,
        "free_form": score_free_form,
    }
    return scorers.get(sample_type, score_free_form)
