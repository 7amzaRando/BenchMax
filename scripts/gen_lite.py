"""
Generate C:\Main\BenchMax\data\lite_full.json — 50 challenging, objective, unbiased benchmark questions.
"""
import json
import os

QUESTIONS = []

# ── CODE (15) ──
CODE = [
    {
        "task_id": "lite_code_01",
        "category": "Code",
        "type": "code",
        "prompt": "Write a Python function called `two_sum` that takes a list of integers `nums` and an integer `target`, and returns the indices of the two numbers that add up to `target`. You may assume each input has exactly one solution, and you may not use the same element twice. Return the answer as a list [idx1, idx2].",
        "answer": "def two_sum(nums, target)"
    },
    {
        "task_id": "lite_code_02",
        "category": "Code",
        "type": "code",
        "prompt": "Write a Python function called `is_valid_parentheses` that takes a string `s` containing just the characters '(', ')', '{', '}', '[' and ']', and returns True if the brackets are matched correctly and False otherwise.",
        "answer": "def is_valid_parentheses(s)"
    },
    {
        "task_id": "lite_code_03",
        "category": "Code",
        "type": "code",
        "prompt": "Write a Python function called `merge_sorted` that takes two sorted lists of integers `a` and `b` and returns a single sorted list containing all elements from both inputs.",
        "answer": "def merge_sorted(a, b)"
    },
    {
        "task_id": "lite_code_04",
        "category": "Code",
        "type": "code",
        "prompt": "Write a Python function called `max_subarray_sum` that takes a list of integers `nums` and returns the sum of the contiguous subarray with the largest sum (Kadane's algorithm).",
        "answer": "def max_subarray_sum(nums)"
    },
    {
        "task_id": "lite_code_05",
        "category": "Code",
        "type": "code",
        "prompt": "Write a Python function called `reverse_linked_list` that takes the head of a singly linked list (a `ListNode` with attributes `val` and `next`) and returns the head of the reversed list. Implement the reversal iteratively, not recursively.",
        "answer": "def reverse_linked_list(head)"
    },
    {
        "task_id": "lite_code_06",
        "category": "Code",
        "type": "code",
        "prompt": "Write a Python function called `binary_search` that takes a sorted list of integers `arr` and an integer `target`, and returns the index of `target` in `arr`, or -1 if it is not found.",
        "answer": "def binary_search(arr, target)"
    },
    {
        "task_id": "lite_code_07",
        "category": "Code",
        "type": "code",
        "prompt": "Write a Python function called `longest_palindrome` that takes a string `s` and returns the longest palindromic substring in `s`. If there are multiple, return any one.",
        "answer": "def longest_palindrome(s)"
    },
    {
        "task_id": "lite_code_08",
        "category": "Code",
        "type": "code",
        "prompt": "Write a Python function called `first_missing_positive` that takes a list of integers `nums` and returns the smallest positive integer that does not appear in the list. Your algorithm must run in O(n) time and use O(1) extra space.",
        "answer": "def first_missing_positive(nums)"
    },
    {
        "task_id": "lite_code_09",
        "category": "Code",
        "type": "code",
        "prompt": "Write a Python function called `max_area` that takes a list of non-negative integers `height` where each represents a vertical line at position i, and returns the maximum amount of water a container formed by two lines and the x-axis can hold (the two-pointer approach).",
        "answer": "def max_area(height)"
    },
    {
        "task_id": "lite_code_10",
        "category": "Code",
        "type": "code",
        "prompt": "Write a Python function called `num_islands` that takes a 2D grid of characters ('1' for land, '0' for water) and returns the number of islands (connected groups of '1's, connected horizontally or vertically).",
        "answer": "def num_islands(grid)"
    },
    {
        "task_id": "lite_code_11",
        "category": "Code",
        "type": "code",
        "prompt": "Write a Python function called `min_path_sum` that takes a 2D grid of non-negative integers and returns the minimum sum along a path from top-left to bottom-right, moving only down or right.",
        "answer": "def min_path_sum(grid)"
    },
    {
        "task_id": "lite_code_12",
        "category": "Code",
        "type": "code",
        "prompt": "Write a Python function called `trap_rain_water` that takes a list of non-negative integers `height` representing an elevation map and returns how much water can be trapped after rain (the two-pointer approach).",
        "answer": "def trap_rain_water(height)"
    },
    {
        "task_id": "lite_code_13",
        "category": "Code",
        "type": "code",
        "prompt": "Write a Python function called `word_break` that takes a string `s` and a list of strings `word_dict`, and returns True if `s` can be segmented into a space-separated sequence of words from `word_dict` (you may reuse words).",
        "answer": "def word_break(s, word_dict)"
    },
    {
        "task_id": "lite_code_14",
        "category": "Code",
        "type": "code",
        "prompt": "Write a Python function called `lcs_length` that takes two strings `a` and `b` and returns the length of their longest common subsequence.",
        "answer": "def lcs_length(a, b)"
    },
    {
        "task_id": "lite_code_15",
        "category": "Code",
        "type": "code",
        "prompt": "Write a Python function called `group_anagrams` that takes a list of strings `strs` and returns a list of lists, grouping all anagrams together. The order within each group does not matter.",
        "answer": "def group_anagrams(strs)"
    },
]

# ── KNOWLEDGE (10) — STEM MCQ ──
KNOWLEDGE = [
    {
        "task_id": "lite_knowledge_01",
        "category": "Knowledge",
        "type": "mcq",
        "prompt": "Which fundamental particle is its own antiparticle?\nA. Electron\nB. Proton\nC. Photon\nD. Neutron\n\nAnswer with the single letter A, B, C, or D.",
        "answer": "C"
    },
    {
        "task_id": "lite_knowledge_02",
        "category": "Knowledge",
        "type": "mcq",
        "prompt": "Approximately what is the Chandrasekhar limit (in solar masses), beyond which a white dwarf collapses into a neutron star?\nA. 1.4\nB. 2.4\nC. 3.0\nD. 0.8\n\nAnswer with the single letter A, B, C, or D.",
        "answer": "A"
    },
    {
        "task_id": "lite_knowledge_03",
        "category": "Knowledge",
        "type": "mcq",
        "prompt": "What is the oxidation state of sulfur in sulfuric acid (H\u2082SO\u2084)?\nA. +2\nB. +4\nC. +6\nD. -2\n\nAnswer with the single letter A, B, C, or D.",
        "answer": "C"
    },
    {
        "task_id": "lite_knowledge_04",
        "category": "Knowledge",
        "type": "mcq",
        "prompt": "Which of the following is NOT one of the four fundamental forces of nature?\nA. Electromagnetism\nB. Friction\nC. Strong nuclear interaction\nD. Weak nuclear interaction\n\nAnswer with the single letter A, B, C, or D.",
        "answer": "B"
    },
    {
        "task_id": "lite_knowledge_05",
        "category": "Knowledge",
        "type": "mcq",
        "prompt": "What is the half-life of Carbon-14 in years?\nA. 1,250\nB. 5,730\nC. 12,500\nD. 50,000\n\nAnswer with the single letter A, B, C, or D.",
        "answer": "B"
    },
    {
        "task_id": "lite_knowledge_06",
        "category": "Knowledge",
        "type": "mcq",
        "prompt": "In which atmospheric layer does the ozone layer primarily reside?\nA. Troposphere\nB. Stratosphere\nC. Mesosphere\nD. Thermosphere\n\nAnswer with the single letter A, B, C, or D.",
        "answer": "B"
    },
    {
        "task_id": "lite_knowledge_07",
        "category": "Knowledge",
        "type": "mcq",
        "prompt": "What is the pH of a 0.001 M aqueous solution of hydrochloric acid (HCl) at 25 \u00b0C?\nA. 1\nB. 2\nC. 3\nD. 4\n\nAnswer with the single letter A, B, C, or D.",
        "answer": "C"
    },
    {
        "task_id": "lite_knowledge_08",
        "category": "Knowledge",
        "type": "mcq",
        "prompt": "What is the approximate escape velocity from Earth's surface in km/s?\nA. 7.9\nB. 11.2\nC. 15.5\nD. 25.0\n\nAnswer with the single letter A, B, C, or D.",
        "answer": "B"
    },
    {
        "task_id": "lite_knowledge_09",
        "category": "Knowledge",
        "type": "mcq",
        "prompt": "Which element has the highest electronegativity on the Pauling scale?\nA. Oxygen\nB. Chlorine\nC. Fluorine\nD. Nitrogen\n\nAnswer with the single letter A, B, C, or D.",
        "answer": "C"
    },
    {
        "task_id": "lite_knowledge_10",
        "category": "Knowledge",
        "type": "mcq",
        "prompt": "The Schwarzschild radius of a black hole is directly proportional to which property?\nA. Its density\nB. Its mass\nC. Its volume\nD. Its angular momentum\n\nAnswer with the single letter A, B, C, or D.",
        "answer": "B"
    },
]

# ── MATH (15) — free_form ──
MATH = [
    {
        "task_id": "lite_math_01",
        "category": "Math",
        "type": "free_form",
        "prompt": "Evaluate the definite integral: \u222b from 0 to \u03c0 of sin(x) dx. Give your answer as a number.",
        "answer": "2"
    },
    {
        "task_id": "lite_math_02",
        "category": "Math",
        "type": "free_form",
        "prompt": "If f(x) = x\u00b3 - 3x\u00b2 + 2, find the value of f'(x) at x = 1. Give your answer as a single number.",
        "answer": "-3"
    },
    {
        "task_id": "lite_math_03",
        "category": "Math",
        "type": "free_form",
        "prompt": "Solve for x: 3^(x+1) = 27^x. Give your answer as a simplified fraction or decimal.",
        "answer": "0.5"
    },
    {
        "task_id": "lite_math_04",
        "category": "Math",
        "type": "free_form",
        "prompt": "Calculate the sum of the infinite geometric series: 1 + 1/3 + 1/9 + 1/27 + ... Give your answer as a simplified fraction.",
        "answer": "3/2"
    },
    {
        "task_id": "lite_math_05",
        "category": "Math",
        "type": "free_form",
        "prompt": "A rectangle's length is twice its width. If the perimeter is 36, what is the area? Give your answer as a single number.",
        "answer": "72"
    },
    {
        "task_id": "lite_math_06",
        "category": "Math",
        "type": "free_form",
        "prompt": "How many trailing zeros does the number 25! (25 factorial) have? Give your answer as a single integer.",
        "answer": "6"
    },
    {
        "task_id": "lite_math_07",
        "category": "Math",
        "type": "free_form",
        "prompt": "Evaluate the definite integral: \u222b from 1 to 2 of (1/x) dx. Give your answer in exact form (not a decimal approximation).",
        "answer": "ln(2)"
    },
    {
        "task_id": "lite_math_08",
        "category": "Math",
        "type": "free_form",
        "prompt": "Calculate the determinant of the 2x2 matrix [[1, 2], [3, 4]]. Give your answer as a single integer.",
        "answer": "-2"
    },
    {
        "task_id": "lite_math_09",
        "category": "Math",
        "type": "free_form",
        "prompt": "What is the sum of the first 20 odd positive integers? Give your answer as a single integer.",
        "answer": "400"
    },
    {
        "task_id": "lite_math_10",
        "category": "Math",
        "type": "free_form",
        "prompt": "Compute 2^100 mod 7. Give your answer as an integer between 0 and 6.",
        "answer": "2"
    },
    {
        "task_id": "lite_math_11",
        "category": "Math",
        "type": "free_form",
        "prompt": "What is the probability of getting at least one head when tossing a fair coin three times? Give your answer as a simplified fraction.",
        "answer": "7/8"
    },
    {
        "task_id": "lite_math_12",
        "category": "Math",
        "type": "free_form",
        "prompt": "What is the volume of a sphere with radius 3? Give your answer in terms of \u03c0.",
        "answer": "36\u03c0"
    },
    {
        "task_id": "lite_math_13",
        "category": "Math",
        "type": "free_form",
        "prompt": "Solve for x: log\u2082(x) + log\u2082(x - 2) = 3. Give your answer as a single integer.",
        "answer": "4"
    },
    {
        "task_id": "lite_math_14",
        "category": "Math",
        "type": "free_form",
        "prompt": "What is the discriminant of the quadratic equation x\u00b2 - 6x + 9 = 0? Give your answer as a single integer.",
        "answer": "0"
    },
    {
        "task_id": "lite_math_15",
        "category": "Math",
        "type": "free_form",
        "prompt": "If tan(\u03b8) = 1 and \u03b8 is acute (0\u00b0 < \u03b8 < 90\u00b0), what is sin(\u03b8) + cos(\u03b8)? Give your answer in simplified exact form.",
        "answer": "\u221a2"
    },
]

# ── LOGIC (10) — free_form ──
LOGIC = [
    {
        "task_id": "lite_logic_01",
        "category": "Logic",
        "type": "free_form",
        "prompt": "If a clock reads 3:15, what is the acute angle (in degrees) between the hour hand and the minute hand? Give your answer as a number.",
        "answer": "7.5"
    },
    {
        "task_id": "lite_logic_02",
        "category": "Logic",
        "type": "free_form",
        "prompt": "You have 9 identical-looking balls. One is slightly heavier than the others. You have a balance scale. What is the minimum number of weighings required to guarantee finding the heavier ball? Give your answer as a single integer.",
        "answer": "2"
    },
    {
        "task_id": "lite_logic_03",
        "category": "Logic",
        "type": "free_form",
        "prompt": "How many single-digit positive integers (1 through 9) have exactly 4 letters when spelled out in English? Give your answer as a single integer.",
        "answer": "3"
    },
    {
        "task_id": "lite_logic_04",
        "category": "Logic",
        "type": "free_form",
        "prompt": "What is the next number in the sequence: 2, 6, 18, 54, ? Give your answer as a single integer.",
        "answer": "162"
    },
    {
        "task_id": "lite_logic_05",
        "category": "Logic",
        "type": "free_form",
        "prompt": "A farmer has chickens and rabbits in a pen. He counts 17 heads and 50 legs. How many rabbits are there? Give your answer as a single integer.",
        "answer": "8"
    },
    {
        "task_id": "lite_logic_06",
        "category": "Logic",
        "type": "free_form",
        "prompt": "What day of the week follows the day before yesterday if today is Thursday? Give your answer as the day name (e.g., Monday).",
        "answer": "Wednesday"
    },
    {
        "task_id": "lite_logic_07",
        "category": "Logic",
        "type": "free_form",
        "prompt": "All Bloops are Gleeks. Some Gleeks are Troopers. Based only on these statements, can we logically conclude that all Bloops are Troopers? Answer 'Yes' or 'No'.",
        "answer": "No"
    },
    {
        "task_id": "lite_logic_08",
        "category": "Logic",
        "type": "free_form",
        "prompt": "A bat and a ball together cost $1.10. The bat costs $1.00 more than the ball. How many cents does the ball cost? Give your answer as a single integer (the number of cents).",
        "answer": "5"
    },
    {
        "task_id": "lite_logic_09",
        "category": "Logic",
        "type": "free_form",
        "prompt": "A wooden cube is painted red on all faces and then cut into 27 identical smaller cubes. How many of the small cubes have paint on exactly 2 faces? Give your answer as a single integer.",
        "answer": "12"
    },
    {
        "task_id": "lite_logic_10",
        "category": "Logic",
        "type": "free_form",
        "prompt": "How many total squares (of all sizes) are there on a standard 8x8 chessboard? Give your answer as a single integer.",
        "answer": "204"
    },
]

QUESTIONS = CODE + KNOWLEDGE + MATH + LOGIC

def main():
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(data_dir, exist_ok=True)
    out_path = os.path.join(data_dir, "lite_full.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(QUESTIONS, f, indent=2, ensure_ascii=False)
    print(f"Generated {len(QUESTIONS)} questions -> {out_path}")

if __name__ == "__main__":
    main()
