import json
import pytest
from backend.sandbox.safe_executor import check_correctness_livecodebench


class TestLCBInputParsing:
    """Bug 1: input strings contain literal \n that need unescaping before splitting."""

    def test_two_sum_class(self):
        code = '''
class Solution:
    def twoSum(self, nums, target):
        for i in range(len(nums)):
            for j in range(i+1, len(nums)):
                if nums[i] + nums[j] == target:
                    return [i, j]
        return []
'''
        io = {
            'inputs': ['[2,7,11,15]\\n9', '[3,2,4]\\n6', '[3,3]\\n6'],
            'outputs': ['[0, 1]', '[1, 2]', '[0, 1]'],
            'fn_name': 'twoSum'
        }
        result = check_correctness_livecodebench(code, json.dumps(io), timeout=10.0)
        assert result["passed"], f"Expected pass but got: {result}"

    def test_two_sum_function(self):
        code = '''
def twoSum(nums, target):
    for i in range(len(nums)):
        for j in range(i+1, len(nums)):
            if nums[i] + nums[j] == target:
                return [i, j]
    return []
'''
        io = {
            'inputs': ['[2,7,11,15]\\n9'],
            'outputs': ['[0, 1]'],
            'fn_name': 'twoSum'
        }
        result = check_correctness_livecodebench(code, json.dumps(io), timeout=10.0)
        assert result["passed"], f"Expected pass but got: {result}"

    def test_single_arg_function(self):
        code = '''
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)
'''
        io = {
            'inputs': ['5', '0', '1'],
            'outputs': ['120', '1', '1'],
            'fn_name': 'factorial'
        }
        result = check_correctness_livecodebench(code, json.dumps(io), timeout=10.0)
        assert result["passed"], f"Expected pass but got: {result}"


class TestLCBImportStar:
    """Bug 2: _safe_lcb_import crashes on 'from module import *' with 'No module named string.*'."""

    def test_from_string_import_star(self):
        code = '''
from string import *

def is_palindrome(s):
    cleaned = ''.join(c.lower() for c in s if c.isalnum())
    return cleaned == cleaned[::-1]
'''
        io = {
            'inputs': ['"racecar"'],
            'outputs': ['true'],
            'fn_name': 'is_palindrome'
        }
        result = check_correctness_livecodebench(code, json.dumps(io), timeout=10.0)
        assert result["passed"], f"Expected pass but got: {result}"

    def test_from_collections_import_star(self):
        code = '''
from collections import *

def count_chars(s):
    return dict(Counter(s))
'''
        io = {
            'inputs': ['"hello"'],
            'outputs': ['{"h": 1, "e": 1, "l": 2, "o": 1}'],
            'fn_name': 'count_chars'
        }
        result = check_correctness_livecodebench(code, json.dumps(io), timeout=10.0)
        assert result["passed"], f"Expected pass but got: {result}"
