"""Tests for backend/benchmarks/scoring.py — shared MCQ/code/exact/free-form scorers."""
import pytest
from backend.benchmarks.scoring import (
    normalize_code_answer,
    score_mcq,
    score_mcq_multi,
    score_code,
    score_exact,
    score_exact_multi,
    score_constraints,
    score_sample,
    score_free_form,
    get_scorer,
)


# ── normalize_code_answer ──────────────────────────────────────────

class TestNormalizeCodeAnswer:
    def test_def_with_parens(self):
        assert normalize_code_answer("def hello_world(x):") == "hello_world"

    def test_bare_call(self):
        assert normalize_code_answer("hello_world(x)") == "hello_world"

    def test_plain_name(self):
        assert normalize_code_answer("hello_world") == "hello_world"

    def test_empty(self):
        assert normalize_code_answer("") == ""

    def test_def_with_spaces(self):
        assert normalize_code_answer("  def  my_func( a, b ):") == "my_func"

    def test_short_name(self):
        assert normalize_code_answer("def f(x):") == "f"


# ── score_mcq ──────────────────────────────────────────────────────

class TestScoreMcq:
    def test_correct(self):
        ok, err = score_mcq("The answer is B", "B")
        assert ok is True
        assert err == ""

    def test_wrong(self):
        ok, err = score_mcq("The answer is B", "A")
        assert ok is False
        assert "Expected A" in err
        assert "got B" in err

    def test_empty_response(self):
        ok, err = score_mcq("", "A")
        assert ok is False
        assert "Empty" in err

    def test_no_letter(self):
        ok, err = score_mcq("no answer here", "A")
        assert ok is False
        assert "No letter" in err

    def test_last_match(self):
        ok, err = score_mcq("X is right, Y is wrong, A wins", "A")
        assert ok is True

    def test_single_letter(self):
        ok, err = score_mcq("A", "A")
        assert ok is True

    def test_hedging_fails_with_valid_letters(self):
        ok, err = score_mcq("I think A, but actually B", "B", "A-D")
        assert ok is False
        assert "hedging" in err.lower() or "Multiple" in err

    def test_hedging_opt_out(self):
        ok, _ = score_mcq("I think A, but actually B", "B", "A-D", single_answer=False)
        assert ok is True

    def test_single_option_repeated_is_fine(self):
        ok, _ = score_mcq("B is wrong? No — B is right. Answer B", "B", "A-D")
        assert ok is True

    def test_dash_range_expansion(self):
        # Regression: set("A-D") == {'A','-','D'} silently dropped B/C.
        ok, _ = score_mcq("Answer: C", "C", "A-D")
        assert ok is True
        ok, _ = score_mcq("Answer: B", "B", "A-D")
        assert ok is True


# ── score_mcq_multi ──────────────────────────────────────────────

class TestScoreMcqMulti:
    def test_exact_set(self):
        ok, err = score_mcq_multi("A and C", ["A", "C"], "A-F")
        assert ok is True

    def test_order_insensitive(self):
        ok, _ = score_mcq_multi("C, A", ["A", "C"], "A-F")
        assert ok is True

    def test_missing_fails(self):
        ok, _ = score_mcq_multi("A", ["A", "C"], "A-F")
        assert ok is False

    def test_extra_fails(self):
        ok, _ = score_mcq_multi("A, B, C", ["A", "C"], "A-F")
        assert ok is False

    def test_empty(self):
        ok, _ = score_mcq_multi("", ["A"], "A-F")
        assert ok is False


# ── score_code ─────────────────────────────────────────────────────

class TestScoreCode:
    def test_def_match(self):
        ok, err = score_code("def encode(s):", "encode")
        assert ok is True

    def test_def_with_spaces(self):
        ok, err = score_code("def encode( s ):", "encode")
        assert ok is True

    def test_no_match(self):
        ok, err = score_code("class Foo:", "Foo")
        assert ok is False
        assert "not found" in err

    def test_empty(self):
        ok, err = score_code("", "foo")
        assert ok is False
        assert "Empty" in err

    def test_code_fence(self):
        ok, err = score_code("```python\ndef bar():\n    pass\n```", "bar")
        assert ok is True

    def test_similar_name_no_match(self):
        ok, err = score_code("def foo_bar(x):", "foo")
        assert ok is False


# ── score_exact ────────────────────────────────────────────────────

class TestScoreExact:
    def test_match(self):
        ok, err = score_exact("The answer is 42", "42")
        assert ok is True

    def test_no_match(self):
        ok, err = score_exact("The answer is 142", "42")
        assert ok is False

    def test_case_insensitive(self):
        ok, err = score_exact("hello world", "HELLO")
        assert ok is True

    def test_empty_response(self):
        ok, err = score_exact("", "42")
        assert ok is False
        assert "Empty" in err

    def test_word_boundary(self):
        ok, err = score_exact("foo42bar", "42")
        assert ok is False

    def test_numeric_fraction_equivalent(self):
        ok, _ = score_exact("The probability is 0.0555555556", "1/18", match="numeric")
        assert ok is True

    def test_numeric_thousands_separator(self):
        ok, _ = score_exact("Answer: 1,283", "1283", match="numeric")
        assert ok is True

    def test_numeric_wrong_value(self):
        ok, _ = score_exact("Answer: 1284", "1283", match="numeric")
        assert ok is False

    def test_numeric_falls_back_when_answer_not_numeric(self):
        ok, _ = score_exact("Paris is the capital", "Paris", match="numeric")
        assert ok is True


# ── score_exact_multi ────────────────────────────────────────────

class TestScoreExactMulti:
    def test_all_parts(self):
        ok, _ = score_exact_multi("A=6 then B=44", ["6", "44"])
        assert ok is True

    def test_missing_part_fails(self):
        ok, err = score_exact_multi("A=6", ["6", "44"])
        assert ok is False
        assert "44" in err


# ── score_constraints ────────────────────────────────────────────

class TestScoreConstraints:
    def test_all_pass(self):
        ok, _ = score_constraints(
            "Dogs run swiftly; cats nap quietly?",
            [{"rule": "ends_with", "text": "?"},
             {"rule": "contains", "text": ";"},
             {"rule": "comma_count", "max": 0}])
        assert ok is True

    def test_failure_reported(self):
        ok, err = score_constraints(
            "Dogs run.",
            [{"rule": "ends_with", "text": "?"}])
        assert ok is False
        assert "ends_with" in err

    def test_nth_word(self):
        ok, _ = score_constraints(
            "one two three befuddled five",
            [{"rule": "nth_word", "n": 4, "word": "befuddled"}])
        assert ok is True
        ok, _ = score_constraints(
            "one two three confused five",
            [{"rule": "nth_word", "n": 4, "word": "befuddled"}])
        assert ok is False

    def test_no_consecutive_initial(self):
        ok, _ = score_constraints("Dogs run swiftly.", [{"rule": "no_consecutive_initial"}])
        assert ok is True
        ok, _ = score_constraints("Dogs dash swiftly.", [{"rule": "no_consecutive_initial"}])
        assert ok is False

    def test_unknown_rule_fails(self):
        ok, _ = score_constraints("anything", [{"rule": "telepathy"}])
        assert ok is False

    def test_empty_constraints(self):
        ok, _ = score_constraints("anything", [])
        assert ok is False


# ── score_sample dispatch ────────────────────────────────────────

class TestScoreSample:
    def test_mcq_dispatch_with_inferred_letters(self):
        sample = {"type": "mcq", "answer": "B",
                  "prompt": "Q?\nA. x\nB. y\nC. z\nD. w"}
        ok, _ = score_sample("Answer: B", sample)
        assert ok is True

    def test_mcq_hedge_dispatched(self):
        sample = {"type": "mcq", "answer": "B",
                  "prompt": "Q?\nA. x\nB. y\nC. z\nD. w"}
        ok, _ = score_sample("A or B", sample)
        assert ok is False

    def test_exact_multi_dispatch(self):
        sample = {"type": "exact", "answers": ["6", "44"]}
        ok, _ = score_sample("6 and 44", sample)
        assert ok is True

    def test_constraint_dispatch(self):
        sample = {"type": "constraint",
                  "constraints": [{"rule": "ends_with", "text": "?"}]}
        ok, _ = score_sample("Is this right?", sample)
        assert ok is True


# ── score_free_form ────────────────────────────────────────────────

class TestScoreFreeForm:
    def test_keyword_match(self):
        ok, err = score_free_form("I love Python coding", "python")
        assert ok is True

    def test_keyword_missing(self):
        ok, err = score_free_form("I love Java", "python")
        assert ok is False
        assert "Missing" in err

    def test_empty_response(self):
        ok, err = score_free_form("", "test")
        assert ok is False
        assert "Empty" in err

    def test_short_answer_vacuously_true(self):
        ok, err = score_free_form("any text", "a")
        assert ok is True

    def test_multiple_keywords(self):
        ok, err = score_free_form("contains apple and banana", "apple, banana")
        assert ok is True

    def test_partial_keyword_missing(self):
        ok, err = score_free_form("contains apple but not cherry", "apple, banana, cherry")
        assert ok is False


# ── get_scorer ─────────────────────────────────────────────────────

class TestGetScorer:
    def test_mcq(self):
        assert get_scorer("mcq") is score_mcq

    def test_code(self):
        assert get_scorer("code") is score_code

    def test_exact(self):
        assert get_scorer("exact") is score_exact

    def test_mcq_multi(self):
        assert get_scorer("mcq_multi") is score_mcq_multi

    def test_constraint(self):
        assert get_scorer("constraint") is score_constraints

    def test_free_form(self):
        assert get_scorer("free_form") is score_free_form

    def test_unknown_falls_back(self):
        assert get_scorer("unknown") is score_free_form

    def test_empty_falls_back(self):
        assert get_scorer("") is score_free_form
