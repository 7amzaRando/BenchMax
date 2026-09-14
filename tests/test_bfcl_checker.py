"""Tests for backend/sandbox/bfcl_checker.py — direct AST scoring (no mocks)."""


def _func(name="get_weather", params=None):
    return [{
        "name": name,
        "description": "test fn",
        "parameters": {
            "type": "dict",
            "properties": params or {
                "city": {"type": "string", "description": "city"},
            },
            "required": ["city"],
        },
    }]


class TestSingleTurn:
    def test_exact_match_valid(self):
        from backend.sandbox.bfcl_checker import ast_checker
        out = ast_checker(_func(), [{"get_weather": {"city": "Paris"}}],
                          [{"get_weather": {"city": ["Paris"]}}],
                          "python", "simple", "test-model")
        assert out["valid"] is True

    def test_wrong_name_invalid(self):
        from backend.sandbox.bfcl_checker import ast_checker
        out = ast_checker(_func(), [{"get_stock": {"city": "Paris"}}],
                          [{"get_weather": {"city": ["Paris"]}}],
                          "python", "simple", "test-model")
        assert out["valid"] is False

    def test_wrong_count_invalid(self):
        from backend.sandbox.bfcl_checker import ast_checker
        out = ast_checker(_func(), [{}], [{"get_weather": {"city": ["Paris"]}}],
                          "python", "simple", "test-model")
        assert out["valid"] is False

    def test_multi_turn_category_rejected(self):
        from backend.sandbox.bfcl_checker import ast_checker
        out = ast_checker(_func(), [{"name": "get_weather", "arguments": {}}],
                          [{"get_weather": {}}],
                          "python", "multi_turn", "test-model")
        assert out["valid"] is False
        assert out["error_type"] == "wrong_checker"


class TestParallel:
    def test_order_independent_valid(self):
        from backend.sandbox.bfcl_checker import ast_checker
        funcs = _func("fn_a") + _func("fn_b")
        model_out = [{"fn_b": {"city": "Y"}}, {"fn_a": {"city": "X"}}]
        possible = [{"fn_a": {"city": ["X"]}}, {"fn_b": {"city": ["Y"]}}]
        out = ast_checker(funcs, model_out, possible, "python", "parallel", "test-model")
        assert out["valid"] is True


class TestMultiTurnSimplified:
    def test_empty_model_invalid(self):
        from backend.sandbox.bfcl_checker import multi_turn_simplified_checker
        out = multi_turn_simplified_checker([], [[{"get_weather": {}}]], "multi_turn")
        assert out["valid"] is False

    def test_empty_ground_truth_invalid(self):
        from backend.sandbox.bfcl_checker import multi_turn_simplified_checker
        out = multi_turn_simplified_checker([[ {"name": "f", "arguments": {}} ]], [], "multi_turn")
        assert out["valid"] is False

    def test_matching_turn_valid(self):
        from backend.sandbox.bfcl_checker import multi_turn_simplified_checker
        out = multi_turn_simplified_checker(
            [[{"name": "get_weather", "arguments": {"city": "Paris"}}]],
            [["get_weather(city='Paris')"]],
            "multi_turn")
        assert out["valid"] is True

    def test_abstain_violation_fails_with_turn(self):
        from backend.sandbox.bfcl_checker import multi_turn_simplified_checker
        out = multi_turn_simplified_checker(
            [[{"name": "get_weather", "arguments": {}}]], [[]], "multi_turn")
        assert out["valid"] is False
        assert out["failed_turn"] == 0
