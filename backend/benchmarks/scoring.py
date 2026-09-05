import re
import logging
from fractions import Fraction
from typing import Dict, Any, List, Sequence, Tuple

logger = logging.getLogger(__name__)


def normalize_code_answer(answer: str) -> str:
    """Extract function name from a code-type answer string."""
    ans = answer.strip()
    if ans.startswith("def "):
        return ans.split("(")[0].replace("def ", "").strip()
    return ans.split("(")[0].strip() if "(" in ans else (ans.split()[0] if ans else "")


def _infer_valid_letters(prompt: str) -> str | None:
    """Infer option universe (e.g. 'A-F') from '\nX.' option markers in a prompt."""
    opts = re.findall(r'\n([A-Z])\.', prompt)
    if opts:
        max_letter = max(opts)
        return "".join(chr(ord('A') + i) for i in range(ord(max_letter) - ord('A') + 1))
    return None


def _expand_valid_letters(valid_letters: str) -> set:
    """Expand an option universe like 'A-D', 'A-D,F' or 'ABCD' to {'A','B','C','D'}.

    NOTE: plain ``set("A-D")`` gives {'A','-','D'} — silently dropping B/C.
    Always expand ranges through this helper.
    """
    allowed: set = set()
    for part in valid_letters.upper().replace(',', ' ').split():
        m = re.fullmatch(r'([A-Z])-([A-Z])', part)
        if m:
            lo, hi = sorted((m.group(1), m.group(2)))
            allowed.update(chr(c) for c in range(ord(lo), ord(hi) + 1))
        else:
            allowed.update(ch for ch in part if ch.isalpha())
    return allowed


def score_mcq(response: str, answer: str, valid_letters: str | None = None,
              single_answer: bool = True) -> Tuple[bool, str]:
    """Strict single-answer MCQ scorer.

    Takes the last valid option letter as the model's choice. When
    ``single_answer`` is True (default) and the option universe is known,
    responses naming 2+ distinct valid options are marked wrong — this
    penalizes hedging ("A... actually B"), which the old last-match-wins
    rule credited.
    """
    if not response or not response.strip():
        return False, "Empty response"
    extracted = re.findall(r'\b([A-Z])\b', response.upper())
    if valid_letters:
        allowed = _expand_valid_letters(valid_letters)
        extracted = [c for c in extracted if c in allowed]
        if not extracted:
            return False, f"No valid letter in {valid_letters} found, expected {answer}"
        if single_answer and len(set(extracted)) > 1:
            return False, f"Multiple distinct options given ({', '.join(sorted(set(extracted)))}) — hedging not allowed"
    if not extracted:
        return False, f"No letter answer found, expected {answer}"
    chosen = extracted[-1]
    if chosen == answer.upper().strip():
        return True, ""
    return False, f"Expected {answer}, got {chosen}"


def score_mcq_multi(response: str, answers: Sequence[str],
                    valid_letters: str | None = None) -> Tuple[bool, str]:
    """'Select all that apply' MCQ scorer — exact set match, order-insensitive.

    Extra letters (hedging) or missing letters both fail. ``answers`` is the
    full set of correct option letters.
    """
    if not response or not response.strip():
        return False, "Empty response"
    expected = {a.upper().strip() for a in answers if str(a).strip()}
    if not expected:
        return False, "No ground-truth answers configured"
    extracted = re.findall(r'\b([A-Z])\b', response.upper())
    if valid_letters:
        allowed = _expand_valid_letters(valid_letters)
        extracted = [c for c in extracted if c in allowed]
    if not extracted:
        return False, f"No valid letters found, expected {{{', '.join(sorted(expected))}}}"
    chosen = set(extracted)
    if chosen == expected:
        return True, ""
    return False, f"Expected {{{', '.join(sorted(expected))}}}, got {{{', '.join(sorted(chosen))}}}"

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

def _unwrap_math(text: str) -> str:
    """Strip LaTeX/box wrappers so equivalent forms compare cleanly."""
    t = text.strip()
    t = re.sub(r'\\{0,2}boxed\{([^{}]*)\}', r'\1', t)
    t = re.sub(r'\\frac\{([^{}]*)\}\{([^{}]*)\}', r'\1/\2', t)
    t = t.replace('$', '').replace('\\', '')
    return t.strip()


def _parse_number(token: str):
    """Parse a numeric token to Fraction (exact) or float. Returns None if not numeric."""
    t = token.strip().replace(',', '').replace(' ', '')
    if not t:
        return None
    try:
        return Fraction(t)
    except (ValueError, ZeroDivisionError):
        pass
    try:
        return float(t)
    except ValueError:
        return None


_NUMBER_RE = re.compile(r'-?\d[\d,]*(?:\.\d+)?(?:/\d[\d,]*(?:\.\d+)?)?')


def _numbers_equal(a, b, tol: float = 1e-9) -> bool:
    # Exact path for integers (no float precision loss on big ints).
    if isinstance(a, Fraction) and isinstance(b, Fraction):
        if a.denominator == 1 and b.denominator == 1:
            return a == b
    try:
        return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(a)), abs(float(b)))
    except (ValueError, OverflowError):
        return False


def score_exact(response: str, answer: str, match: str = "strict") -> Tuple[bool, str]:
    if not response or not response.strip():
        return False, "Empty response"
    if match == "numeric":
        expected = _parse_number(_unwrap_math(answer))
        if expected is None:
            # Ground truth isn't numeric — fall back to strict substring.
            return score_exact(response, answer, match="strict")
        for tok in _NUMBER_RE.findall(_unwrap_math(response)):
            cand = _parse_number(tok)
            if cand is not None and _numbers_equal(cand, expected):
                return True, ""
        return False, f"Expected numeric value '{answer.strip()}', not found in response"
    escaped = re.escape(answer.strip())
    if re.search(r'(?<!\w)' + escaped + r'(?!\w)', response, re.IGNORECASE):
        return True, ""
    return False, f"Expected '{answer}', not found in response"


def score_exact_multi(response: str, answers: Sequence[str],
                      match: str = "strict") -> Tuple[bool, str]:
    """Chained exact scorer — ALL parts must be present (conjunction).

    Enables multi-step items ("compute A, then use A to get B") where
    single-step recall earns nothing.
    """
    if not response or not response.strip():
        return False, "Empty response"
    parts = [str(a) for a in answers if str(a).strip()]
    if not parts:
        return False, "No ground-truth answers configured"
    missing = []
    for part in parts:
        ok, _ = score_exact(response, part, match=match)
        if not ok:
            missing.append(part)
    if missing:
        return False, f"Missing required part(s): {', '.join(missing[:3])}"
    return True, ""

def score_free_form(response: str, answer: str) -> Tuple[bool, str]:
    if not response or not response.strip():
        return False, "Empty response"
    keywords = [k.strip().lower() for k in re.split(r'[,;\s]+', answer) if k.strip()]
    if not keywords:
        return True, ""
    missing = [kw for kw in keywords if kw not in response.lower()]
    if missing:
        return False, f"Missing keywords: {', '.join(missing[:3])}"
    return True, ""

def get_scorer(sample_type: str):
    scorers = {
        "mcq": score_mcq,
        "mcq_multi": score_mcq_multi,
        "code": score_code,
        "exact": score_exact,
        "exact_multi": score_exact_multi,
        "constraint": score_constraints,
        "free_form": score_free_form,
    }
    return scorers.get(sample_type, score_free_form)


def _words(text: str) -> List[str]:
    return re.findall(r"[A-Za-z0-9']+", text)


def _check_constraint(response: str, spec: Dict[str, Any]) -> Tuple[bool, str]:
    """Evaluate one verifiable instruction-following constraint."""
    rule = spec.get("rule", "")
    if rule == "word_count":
        n = len(_words(response))
        for key, label in (("eq", "=="), ("min", ">="), ("max", "<=")):
            if key in spec and not eval(f"{n}{label}{int(spec[key])}"):
                return False, f"word_count: got {n}, expected {label} {spec[key]}"
        return True, ""
    if rule == "nth_word":
        words = _words(response)
        n = int(spec.get("n", 1))
        want = str(spec.get("word", "")).lower().strip("'\"")
        got = words[n - 1].lower().strip("'\"") if 0 < n <= len(words) else None
        if got != want:
            return False, f"nth_word: word #{n} is '{got}', expected '{want}'"
        return True, ""
    if rule == "comma_count":
        n = response.count(",")
        for key, label in (("eq", "=="), ("min", ">="), ("max", "<=")):
            if key in spec and not eval(f"{n}{label}{int(spec[key])}"):
                return False, f"comma_count: got {n}, expected {label} {spec[key]}"
        return True, ""
    if rule == "contains":
        text = str(spec.get("text", ""))
        min_count = int(spec.get("min_count", 1))
        n = response.count(text) if spec.get("case_sensitive") else response.lower().count(text.lower())
        if n < min_count:
            return False, f"contains: '{text}' found {n}x, need >={min_count}x"
        return True, ""
    if rule == "forbidden":
        bad = [w for w in spec.get("words", []) if w.lower() in response.lower()]
        if bad:
            return False, f"forbidden: found {', '.join(bad[:3])}"
        return True, ""
    if rule == "ends_with":
        if not response.rstrip().endswith(str(spec.get("text", ""))):
            return False, f"ends_with: response does not end with '{spec.get('text', '')}'"
        return True, ""
    if rule == "starts_with":
        if not response.lstrip().startswith(str(spec.get("text", ""))):
            return False, f"starts_with: response does not start with '{spec.get('text', '')}'"
        return True, ""
    if rule == "no_consecutive_initial":
        words = [w for w in _words(response) if w and w[0].isalpha()]
        for a, b in zip(words, words[1:]):
            if a[0].lower() == b[0].lower():
                return False, f"no_consecutive_initial: '{a} {b}' share initial '{a[0].upper()}'"
        return True, ""
    if rule == "contains_quote":
        if not re.search(r'"[^"]+"|\'[^\']{3,}?\'|`[^`]+`', response):
            return False, "contains_quote: no quoted passage found"
        return True, ""
    return False, f"unknown constraint rule '{rule}'"


def score_constraints(response: str, constraints: Sequence[Dict[str, Any]]) -> Tuple[bool, str]:
    """Programmatic instruction-following scorer — ALL constraints must hold.

    Unlike single-gold-string matching, any response satisfying every
    constraint passes, so the check is strict but not arbitrary.
    """
    if not response or not response.strip():
        return False, "Empty response"
    specs = list(constraints or [])
    if not specs:
        return False, "No constraints configured"
    failures = []
    for spec in specs:
        ok, err = _check_constraint(response, spec)
        if not ok:
            failures.append(err)
    if failures:
        return False, "; ".join(failures[:3])
    return True, ""


def score_sample(raw_response: str, sample: Dict[str, Any]) -> Tuple[bool, str]:
    """Full hardened dispatch for one custom-benchmark sample.

    Routes on ``sample["type"]`` and honors the optional per-sample keys:
    ``valid_letters`` (MCQ universe, inferred from the prompt when absent),
    ``single_answer`` (default True — hedging fails), ``answers`` (list for
    multi-answer / multi-part items), ``match`` ("strict" | "numeric"),
    ``constraints`` (list of rule specs for type "constraint").
    """
    qtype = sample.get("type", "free_form")
    if qtype == "mcq":
        valid_letters = sample.get("valid_letters") or _infer_valid_letters(sample.get("prompt", ""))
        return score_mcq(raw_response, sample.get("answer", ""),
                         valid_letters,
                         single_answer=sample.get("single_answer", True))
    if qtype == "mcq_multi":
        valid_letters = sample.get("valid_letters") or _infer_valid_letters(sample.get("prompt", ""))
        answers = sample.get("answers") or ([sample.get("answer", "")] if sample.get("answer") else [])
        return score_mcq_multi(raw_response, answers, valid_letters)
    if qtype == "exact":
        answers = sample.get("answers")
        match = sample.get("match", "strict")
        if answers:
            return score_exact_multi(raw_response, answers, match=match)
        return score_exact(raw_response, sample.get("answer", ""), match=match)
    if qtype == "exact_multi":
        return score_exact_multi(raw_response, sample.get("answers", []),
                                 match=sample.get("match", "strict"))
    if qtype == "code":
        return score_code(raw_response, normalize_code_answer(sample.get("answer", "")))
    if qtype == "constraint":
        return score_constraints(raw_response, sample.get("constraints", []))
    return score_free_form(raw_response, sample.get("answer", ""))
