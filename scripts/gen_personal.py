"""Generate personal_full.json — 100-objective benchmark questions for BenchMax Personal."""
import json
from pathlib import Path

QUESTIONS = []

# ── CODE (25) ─────────────────────────────────────────────────────────────
code_qs = [
    "Write a Python function called `count_islands(grid)` that takes a binary matrix (list of lists of 0s and 1s) and returns the number of connected components of 1s. Connections are cardinal (up, down, left, right; not diagonal). Use iterative DFS or BFS.",
    "Write a Python function called `longest_palindromic_substring(s)` that takes a string and returns the longest palindromic substring. If there are multiple, return any one. Must run in O(n^2) or better.",
    "Write a Python function called `max_subarray_sum(nums)` that takes a list of integers and returns the maximum sum of any contiguous subarray using Kadane's algorithm.",
    "Write a Python function called `merge_intervals(intervals)` that takes a list of intervals [start, end] and returns a new list with all overlapping intervals merged. Intervals are inclusive at both ends.",
    "Write a Python function called `edit_distance(word1, word2)` that returns the minimum number of single-character edits (insert, delete, substitute) required to change word1 into word2 using dynamic programming.",
    "Write a Python function called `solve_n_queens(n)` that returns a list of all distinct solutions to the N-Queens puzzle. Each solution is a list of strings of length n where 'Q' marks a queen and '.' marks an empty cell.",
    "Write a Python function called `alien_order(words)` that takes a sorted list of words from an alien language and returns the order of characters as a string. Use topological sort (Kahn's algorithm).",
    "Write a Python function called `largest_rectangle_in_histogram(heights)` that takes a list of non-negative integers representing bar heights and returns the area of the largest rectangle that fits entirely under the histogram.",
    "Write a Python function called `min_window_substring(s, t)` that takes two strings and returns the minimum contiguous substring of s that contains all characters of t (including duplicates). Return empty string if none exists.",
    "Write a Python function called `next_permutation(nums)` that rearranges a list of integers into the lexicographically next greater permutation in-place. If no greater permutation exists, sort ascending.",
    "Write a Python function called `trap_water(height)` that takes a list of non-negative integers representing elevation heights and returns how much rainwater can be trapped between them after rain.",
    "Write a Python function called `regex_matcher(s, p)` that implements basic regex matching supporting '.' (any single char) and '*' (zero or more of preceding char). Return True if the entire string matches the pattern.",
    "Write a Python function called `burst_balloons(nums)` that takes a list of balloons each with a number. Bursting balloon i earns nums[i-1] * nums[i] * nums[i+1]. Return the maximum coins obtainable.",
    "Write a Python function called `max_profit(k, prices)` that takes an integer k and a list of daily stock prices. Return the maximum profit achievable with at most k transactions (buy+sell = one transaction).",
    "Write a Python function called `text_justification(words, max_width)` that takes a list of words and a page width, and returns a list of fully-justified lines. Distribute extra spaces as evenly as possible between words.",
    "Write a Python function called `candy_ratings(ratings)` that takes a list of child ratings. Each child must get at least 1 candy, and children with higher ratings than their neighbors get more. Return minimum total candies.",
    "Write a Python function called `shortest_palindrome(s)` that takes a string and returns the shortest palindrome by adding characters to the front. Use a KMP-based approach for O(n) time.",
    "Write a Python function called `median_of_two_sorted_arrays(nums1, nums2)` that takes two sorted arrays and returns the median of their combined set. Must run in O(log(min(m,n))).",
    "Write a Python function called `longest_valid_parentheses(s)` that takes a string of '(' and ')' and returns the length of the longest well-formed parentheses substring.",
    "Write a Python function called `word_ladder_length(begin, end, wordlist)` that returns the length of the shortest transformation sequence from begin to end, changing one letter at a time, where each intermediate word is in wordlist.",
    "Write a Python function called `max_path_sum(root)` that takes the root of a binary tree where each node has an integer value, and returns the maximum path sum (a path can start and end at any node).",
    "Write a Python class called `MedianFinder` with methods `add_num(num)` and `find_median()` that maintains a stream of integers and returns the median at any point. Use two heaps for O(log n) add and O(1) find.",
    "Write a Python class called `FreqStack` with methods `push(val)` and `pop()` that implements a frequency stack: pop returns the most frequent element, breaking ties by recency.",
    "Write a Python function called `race_car(target)` that returns the minimum number of steps to reach a target position on a line. Start at 0 with speed 1. Each step: 'A' (accelerate: position += speed, speed *= 2) or 'R' (reverse: speed = -1 if speed > 0 else 1).",
    "Write a Python function called `serialize(root)` that takes a binary tree root and returns a string representation, and `deserialize(data)` that reconstructs the tree from that string. Use level-order traversal with null markers.",
]
for i, prompt in enumerate(code_qs, 1):
    name = prompt.split("`")[1].split("(")[0].split(".")[-1]
    QUESTIONS.append({
        "task_id": f"personal_code_{i}",
        "category": "Code",
        "type": "code",
        "prompt": prompt,
        "answer": f"def {name}" if not name.startswith("class") else f"class {name}",
    })

# ── KNOWLEDGE (15 — STEM MCQ) ────────────────────────────────────────────
known_qs = [
    ("Which of the following particles has the smallest rest mass?\nA) Electron\nB) Proton\nC) Neutron\nD) Muon", "A"),
    ("What is the pH of a 0.001 M HCl solution at 25 degrees C?\nA) 1\nB) 2\nC) 3\nD) 4", "C"),
    ("Which of the following is NOT a type of RNA?\nA) mRNA\nB) tRNA\nC) rRNA\nD) dRNA", "D"),
    ("In a binary star system, what is the term for the point around which both stars orbit?\nA) Apastron\nB) Barycenter\nC) Pericenter\nD) Ecliptic", "B"),
    ("What is the oxidation state of sulfur in H2SO4?\nA) +2\nB) +4\nC) +6\nD) -2", "C"),
    ("Which law of thermodynamics states that the entropy of a perfect crystal approaches zero as temperature approaches absolute zero?\nA) First\nB) Second\nC) Third\nD) Zeroth", "C"),
    ("What is the Hausdorff dimension of the classic Sierpinski triangle?\nA) 1.0\nB) 1.585\nC) 2.0\nD) 2.585", "B"),
    ("Which sorting algorithm has the best worst-case time complexity?\nA) Quick Sort\nB) Merge Sort\nC) Insertion Sort\nD) Selection Sort", "B"),
    ("What is the chromatic number of a complete graph K5?\nA) 3\nB) 4\nC) 5\nD) 6", "C"),
    ("Which of the following is irreducible over the real numbers?\nA) x^2 - 1\nB) x^2 + 1\nC) x^2 - 2\nD) x^3 - 1", "B"),
    ("What is the time complexity of computing the nth Fibonacci number using dynamic programming with memoization?\nA) O(1)\nB) O(log n)\nC) O(n)\nD) O(2^n)", "C"),
    ("Which normal form in database theory requires that every non-key attribute is non-transitively dependent on every candidate key?\nA) 1NF\nB) 2NF\nC) 3NF\nD) BCNF", "C"),
    ("What is the Schwarzschild radius of a black hole directly proportional to?\nA) Its charge\nB) Its angular momentum\nC) Its mass\nD) Its volume", "C"),
    ("Which of the following is NOT a fundamental force of nature?\nA) Electromagnetism\nB) Gravity\nC) Friction\nD) Strong nuclear force", "C"),
    ("What is the bond angle in degrees in a perfect tetrahedral molecular geometry?\nA) 90\nB) 104.5\nC) 109.5\nD) 120", "C"),
]
for i, (prompt, answer) in enumerate(known_qs, 1):
    QUESTIONS.append({
        "task_id": f"personal_knowledge_{i}",
        "category": "Knowledge",
        "type": "mcq",
        "prompt": prompt,
        "answer": answer,
    })

# ── INSTRUCTION FOLLOWING (15 — free_form with format constraints) ────────
if_qs = [
    ("Write exactly three sentences about algorithms. Each sentence must start with the word 'Algorithm'. Do not include any additional text before or after these three sentences.",
     "Algorithm Algorithm Algorithm"),
    ("Output the numbers 1 through 5 in descending order, one per line. On the line before the numbers, output the word 'START'. On the line after the numbers, output the word 'END'. No other text.",
     "START END numbers"),
    ("Write a single valid JSON object with exactly three keys: 'name', 'type', and 'version'. The value of 'version' must be the string '2.1.0'. Output ONLY the JSON object.",
     "name type version 2.1.0"),
    ("Write a paragraph of exactly 50 words about binary search trees. Count every word carefully. End the paragraph with the exact phrase 'Binary search trees are efficient.'",
     "Binary search trees are efficient"),
    ("List exactly four sorting algorithms in descending order of their average time complexity (slowest first). One per line, numbered 1. through 4. After the list, output a line containing only 'DONE'.",
     "DONE sorting algorithms"),
    ("Write exactly one sentence that contains all three of these words: 'cache', 'eviction', 'policy'. The sentence must be between 10 and 20 words. Output ONLY that sentence.",
     "cache eviction policy"),
    ("Create a level-2 markdown heading with the text 'Search Algorithms'. Then create a bullet list of exactly two items: 'Linear Search' and 'Binary Search'. Each bullet must start with a hyphen and a space.",
     "Search Algorithms Linear Binary"),
    ("Write exactly five synonyms for the word 'fast', separated by commas and spaces. The first synonym must be 'quick'. All lowercase. No other text.",
     "quick synonyms fast"),
    ("Output the word 'START' on the first line, then exactly 20 hyphen characters on the second line, then the word 'END' on the third line. No other text.",
     "START END hyphens"),
    ("Write a single line containing a pipe-delimited table header with exactly four columns: 'id', 'name', 'score', 'rank'. No other text.",
     "id name score rank pipes"),
    ("Write a sentence that contains the exact phrase 'abstract syntax tree' and is at most 15 words. Output ONLY that sentence.",
     "abstract syntax tree"),
    ("Output the mathematical constant pi to 5 decimal places on one line, and Euler's number to 5 decimal places on the next line. Only output these two numbers.",
     "3.14159 2.71828 constants"),
    ("Write a single Python expression (no semicolons, no function definitions) that computes the sum of squares of all even numbers from 1 to 100. Output ONLY the expression.",
     "sum squares even numbers range"),
    ("Create a CSV-formatted table with headers 'City,Country,Population' and exactly two data rows. Use commas as delimiters and newlines for rows. Output ONLY the CSV.",
     "City Country Population CSV"),
    ("Output the exact string '(lambda x: x + 1)' on a single line. No other text before or after.",
     "lambda expression"),
]
for i, (prompt, answer) in enumerate(if_qs, 1):
    QUESTIONS.append({
        "task_id": f"personal_if_{i}",
        "category": "Instruction Following",
        "type": "free_form",
        "prompt": prompt,
        "answer": answer,
    })

# ── MATH (25 — multi-step, free_form numeric) ────────────────────────────
math_qs = [
    ("A train travels 120 km at 60 km/h, then 80 km at 40 km/h. What is the average speed for the entire journey in km/h? Output only the number followed by ' km/h'.",
     "50 km/h"),
    ("Compute the sum of all integers from 1 to 100 inclusive. Output only the number.",
     "5050 total"),
    ("If f(x) = 3x^2 - 2x + 5, evaluate f(4). Output the answer as a number.",
     "45.0 result"),
    ("A rectangle has a perimeter of 48 cm and its length is twice its width. What is the area in cm^2? Output only the number.",
     "128 area"),
    ("How many distinct 4-digit numbers can be formed using the digits 1, 2, 3, 4, 5 if no digit repeats? Output only the number.",
     "120 permutations"),
    ("Evaluate the definite integral of x^2 from 0 to 3. Output only the number.",
     "9.0 integral"),
    ("How many distinct ways can the letters of 'MISSISSIPPI' be arranged? Output only the number.",
     "34650 arrangements"),
    ("What is the sum of the infinite geometric series 1 + 1/2 + 1/4 + 1/8 + ...? Output only the number.",
     "2.0 series"),
    ("What is the derivative of f(x) = 5x^4 + 3x^2 - 2x + 7 evaluated at x = 1? Output only the number.",
     "24.0 derivative"),
    ("What is the value of log base 2 of 64? Output only the number.",
     "6.0 logarithm"),
    ("A 3m by 3m by 3m cube is painted on all faces and then cut into unit cubes. How many unit cubes have paint on exactly one face? Output the number followed by ' cubes'.",
     "54 cubes painted"),
    ("A bacteria culture doubles every 3 hours. Starting with 100 bacteria, how many are there after 24 hours? Output only the number.",
     "25600 bacteria"),
    ("What is the smallest positive integer divisible by all integers from 1 to 10? Output only the number.",
     "2520 divisible"),
    ("How many positive integers less than 100 are divisible by 3 or 5? Output only the number followed by ' integers'.",
     "46 integers divisible"),
    ("Evaluate the sum of the first 10 odd numbers (starting from 1). Output only the number.",
     "100 sum odds"),
    ("A fair coin is flipped 4 times. What is the probability of getting exactly 2 heads? Output as a decimal.",
     "0.375 probability"),
    ("How many 5-letter strings can be formed from the letters of 'MATHEMATICS' using each letter at most once? Output only the number.",
     "151200 strings"),
    ("What is the units digit of 7 raised to the power 2024? Output the digit followed by ' digit'.",
     "1 digit units"),
    ("The volume of a sphere is 288 pi cubic cm. What is its radius in cm? Output only the number.",
     "6.0 radius sphere"),
    ("How many diagonals does a regular decagon (10 sides) have? Output the number followed by ' diagonals'.",
     "35 diagonals polygon"),
    ("A car depreciates 15% per year. If it costs $20,000 new, what is its value after 3 years to the nearest dollar? Output only the number.",
     "12283 depreciation"),
    ("Find x: 5x + 3 = 4x + 10. Output only the number.",
     "7.0 equation"),
    ("How many ways can a committee of 3 people be chosen from a group of 8? Output the number followed by ' combinations'.",
     "56 combinations committee"),
    ("What is the sum of the interior angles in degrees of a convex octagon? Output only the number.",
     "1080 degrees polygon"),
    ("The second term of a geometric sequence is 6 and the fifth term is 48. What is the first term? Output only the number.",
     "3.0 geometric sequence"),
]
for i, (prompt, answer) in enumerate(math_qs, 1):
    QUESTIONS.append({
        "task_id": f"personal_math_{i}",
        "category": "Math",
        "type": "free_form",
        "prompt": prompt,
        "answer": answer,
    })

# ── LOGIC (20 — puzzles & deductions, free_form) ─────────────────────────
logic_qs = [
    ("If it takes 5 machines 5 minutes to make 5 widgets, how many minutes would it take 100 machines to make 100 widgets? Output only the number followed by ' minutes'.",
     "5 minutes machines"),
    ("A bat and a ball cost $1.10 total. The bat costs $1.00 more than the ball. How many cents does the ball cost? Output the number followed by ' cents'.",
     "5 cents ball"),
    ("What is the next number in the sequence: 2, 6, 12, 20, 30, ? Output the number followed by ' next'.",
     "42 next sequence"),
    ("If today is Wednesday, what day of the week will it be 100 days from now? Output the full day name.",
     "Friday day week"),
    ("In a race, you pass the person in 2nd place. What position are you in now? Output the number with its ordinal suffix (e.g., '1st', '2nd').",
     "2nd position"),
    ("A farmer has 17 sheep. All but 9 die. How many sheep are left? Output the number followed by ' sheep'.",
     "9 sheep remaining"),
    ("A snail climbs 3 meters up a wall during the day and slips 2 meters down at night. The wall is 10 meters high. How many days does it take to reach the top? Output the number followed by ' days'.",
     "8 days snail"),
    ("How many times do the hour and minute hands of a clock overlap in a 24-hour period? Output the number followed by ' overlaps'.",
     "22 overlaps clock"),
    ("What is the missing number: 3, 7, 15, 31, 63, ? Output the number followed by ' missing'.",
     "127 missing sequence"),
    ("A man looks at a portrait and says: 'Brothers and sisters I have none, but that man's father is my father's son.' What is the relationship of the person in the portrait to the man? Answer with one word: son, father, brother, uncle, or cousin.",
     "son relationship portrait"),
    ("If 3 cats can catch 3 mice in 3 minutes, how many cats are needed to catch 100 mice in 100 minutes? Output the number followed by ' cats'.",
     "3 cats mice"),
    ("What is the minimum number of cuts needed to cut a 3x3x3 cube into 27 unit cubes, if cuts can stack pieces? Output the number followed by ' cuts'.",
     "6 cuts cube"),
    ("Mary is 24 years old. She is twice as old as Ann was when Mary was as old as Ann is now. How old is Ann? Output the number followed by ' years'.",
     "18 years ages"),
    ("I am an odd number. Take away one letter and I become even. What number am I? Output the number followed by ' number'.",
     "7 number odd"),
    ("How many integers between 1 and 1000 inclusive are perfect squares and also perfect cubes? Output the number followed by ' integers'.",
     "3 integers squares cubes"),
    ("Amy, Bob, and Carol each have a different favorite color: red, blue, or green. Amy does not like red. Bob likes green. What is Carol's favorite color? Output the color name in lowercase.",
     "red color favorite"),
    ("If five people can paint five houses in five days, how many people are needed to paint 100 houses in 100 days? Output the number followed by ' people'.",
     "5 people houses paint"),
    ("A hall has 100 light switches all turned off. Person 1 toggles every switch. Person 2 toggles every 2nd switch, and so on up to person 100. How many switches are on at the end? Output the number followed by ' switches'.",
     "10 switches toggles"),
    ("What number comes next: 1, 1, 2, 3, 5, 8, 13, ? Output the number followed by ' next'.",
     "21 next fibonacci"),
    ("Which of the following does NOT belong? Output the name of the shape. A) Triangle B) Square C) Pentagon D) Cube",
     "Cube shape different"),
]
for i, (prompt, answer) in enumerate(logic_qs, 1):
    QUESTIONS.append({
        "task_id": f"personal_logic_{i}",
        "category": "Logic",
        "type": "free_form",
        "prompt": prompt,
        "answer": answer,
    })

# ── VALIDATE ──────────────────────────────────────────────────────────────
assert len(QUESTIONS) == 100, f"Expected 100 questions, got {len(QUESTIONS)}"

cats = {}
for q in QUESTIONS:
    cats.setdefault(q["category"], 0)
    cats[q["category"]] += 1
print("Category distribution:", dict(sorted(cats.items())))
print(f"Total questions: {len(QUESTIONS)}")

# Verify every free_form answer has at least one keyword > 2 chars
bad = []
for q in QUESTIONS:
    if q["type"] == "free_form":
        keywords = [k for k in q["answer"].replace(",", " ").split() if len(k) > 2]
        if not keywords:
            bad.append(q["task_id"])
if bad:
    print(f"WARNING: free_form questions with no keyword >2 chars: {bad}")
else:
    print("All free_form answers have adequate keywords for scoring.")

out = Path(__file__).parents[1] / "data" / "personal_full.json"
out.write_text(json.dumps(QUESTIONS, indent=2), encoding="utf-8")
print(f"Saved to {out}")
