import json

data = [
  {
    "task_id": "reason_math_01",
    "category": "Math",
    "type": "exact",
    "prompt": "Find the number of integers between 1 and 10^6 inclusive that are NOT divisible by 2, 3, 5, or 7. Use inclusion-exclusion with four sets. Output only the number.",
    "answer": "228571"
  },
  {
    "task_id": "reason_math_02",
    "category": "Math",
    "type": "exact",
    "prompt": "A random permutation of the set {1, 2, 3, 4, 5, 6, 7} is chosen uniformly. What is the probability that no element is in its original position (a derangement)? Express as a simplified fraction. Output only the fraction.",
    "answer": "103/280"
  },
  {
    "task_id": "reason_math_03",
    "category": "Math",
    "type": "exact",
    "prompt": "Let p = 7919 which is prime. Compute 2^p modulo p using Fermat's Little Theorem. Output only the number.",
    "answer": "2"
  },
  {
    "task_id": "reason_math_04",
    "category": "Math",
    "type": "exact",
    "prompt": "Find the smallest positive integer n satisfying the system: n ≡ 2 (mod 3), n ≡ 3 (mod 5), n ≡ 2 (mod 7). Output only the number.",
    "answer": "23"
  },
  {
    "task_id": "reason_math_05",
    "category": "Math",
    "type": "exact",
    "prompt": "Compute Euler's totient function φ(2024) where 2024 = 2^3 × 11 × 23. Output only the number.",
    "answer": "880"
  },
  {
    "task_id": "reason_math_06",
    "category": "Math",
    "type": "exact",
    "prompt": "Find 7^2025 modulo 11 using Fermat's Little Theorem. Output only the number (0 through 10).",
    "answer": "10"
  },
  {
    "task_id": "reason_math_07",
    "category": "Math",
    "type": "exact",
    "prompt": "How many ways can a set of 7 distinct elements be partitioned into exactly 3 non-empty unlabeled subsets? This is the Stirling number of the second kind S(7,3). Output only the number.",
    "answer": "301"
  },
  {
    "task_id": "reason_math_08",
    "category": "Math",
    "type": "exact",
    "prompt": "Evaluate the triple integral ∫∫∫_E z dV where E is the region bounded by z = 0, z = x + y, and the triangle in the xy-plane with vertices (0,0), (1,0), (0,1). Output only the simplified fraction.",
    "answer": "1/8"
  },
  {
    "task_id": "reason_math_09",
    "category": "Math",
    "type": "exact",
    "prompt": "How many elements of order exactly 12 does the group Z_12 × Z_8 contain? An element (a,b) has order lcm(|a|,|b|). Output only the number.",
    "answer": "24"
  },
  {
    "task_id": "reason_math_10",
    "category": "Math",
    "type": "exact",
    "prompt": "Evaluate the sum Σ_{k=0}^{20} C(20,k) × (-3)^k using the binomial theorem. Output only the number.",
    "answer": "1048576"
  },
  {
    "task_id": "reason_math_11",
    "category": "Math",
    "type": "exact",
    "prompt": "How many distinct 5-card poker hands contain exactly one pair (two cards of the same rank and three other cards all of different ranks)? Compute using combinations. Output only the number.",
    "answer": "1098240"
  },
  {
    "task_id": "reason_math_12",
    "category": "Math",
    "type": "exact",
    "prompt": "Compute 3^2046 modulo 7 using Fermat's Little Theorem. Output only the number (0 through 6).",
    "answer": "1"
  },
  {
    "task_id": "reason_math_13",
    "category": "Math",
    "type": "exact",
    "prompt": "How many positive integers ≤ 1000 are perfect squares or perfect cubes? Use inclusion-exclusion. Output only the number.",
    "answer": "38"
  },
  {
    "task_id": "reason_math_14",
    "category": "Math",
    "type": "exact",
    "prompt": "Find the smallest positive integer n such that n! ends in exactly 100 zeros. Use the formula Σ⌊n/5^k⌋ = 100. Output only the number.",
    "answer": "405"
  },
  {
    "task_id": "reason_math_15",
    "category": "Math",
    "type": "exact",
    "prompt": "Find the sum of all positive integers ≤ 1000 that are NOT divisible by 4 or 6. Compute by subtracting multiples of 4 and 6 from the total and adding back multiples of 12. Output only the number.",
    "answer": "333666"
  },
  {
    "task_id": "reason_math_16",
    "category": "Math",
    "type": "exact",
    "prompt": "Evaluate the telescoping series Σ_{n=1}^{∞} 1/(n^2 + 3n + 2). Express as a simplified fraction. Output only the fraction.",
    "answer": "1/2"
  },
  {
    "task_id": "reason_math_17",
    "category": "Math",
    "type": "exact",
    "prompt": "If A is a 3×3 matrix with determinant 5, what is the determinant of 2A? Use the property det(cA) = c^n det(A). Output only the number.",
    "answer": "40"
  },
  {
    "task_id": "reason_math_18",
    "category": "Math",
    "type": "exact",
    "prompt": "How many distinct arrangements of the letters in MISSISSIPPI have no two I's adjacent? M appears once, I appears 4 times, S appears 4 times, P appears twice. Output only the number.",
    "answer": "7350"
  },
  {
    "task_id": "reason_math_19",
    "category": "Math",
    "type": "exact",
    "prompt": "Solve for x: log_3(x) + log_3(x - 2) = 1. Use logarithm properties and solve the resulting quadratic. Output only the number.",
    "answer": "3"
  },
  {
    "task_id": "reason_math_20",
    "category": "Math",
    "type": "exact",
    "prompt": "A right circular cone has height 12 and base radius 5. Find its slant height. Output only the number.",
    "answer": "13"
  },
  {
    "task_id": "reason_math_21",
    "category": "Math",
    "type": "exact",
    "prompt": "A 5×5 magic square contains the numbers 1 through 25 once each. What is the magic constant (the sum of every row, column, and main diagonal)? Output only the number.",
    "answer": "65"
  },
  {
    "task_id": "reason_math_22",
    "category": "Math",
    "type": "exact",
    "prompt": "A committee of 4 must be selected from 10 people, but the chairperson must be included. In how many ways can this committee be formed? Output only the number.",
    "answer": "840"
  },
  {
    "task_id": "reason_math_23",
    "category": "Math",
    "type": "exact",
    "prompt": "Compute the sum of the squares of the first 50 odd positive integers. Use the formula n(2n-1)(2n+1)/3 with n=50. Output only the number.",
    "answer": "166650"
  },
  {
    "task_id": "reason_math_24",
    "category": "Math",
    "type": "exact",
    "prompt": "Two fair six-sided dice are rolled. What is the expected value of their sum? Output only the number.",
    "answer": "7"
  },
  {
    "task_id": "reason_math_25",
    "category": "Math",
    "type": "exact",
    "prompt": "How many diagonals does a convex decagon (10-sided polygon) have? Use the formula n(n-3)/2. Output only the number.",
    "answer": "35"
  },
  {
    "task_id": "reason_math_26",
    "category": "Math",
    "type": "exact",
    "prompt": "How many ways are there to color each cell of a 3×3 grid either black or white, considering all rotations as distinct? Output only the number.",
    "answer": "512"
  },
  {
    "task_id": "reason_math_27",
    "category": "Math",
    "type": "exact",
    "prompt": "A positive divisor of 2024 (where 2024 = 2^3 × 11 × 23) is chosen uniformly at random. What is the probability it is a multiple of 4? Express as a simplified fraction. Output only the fraction.",
    "answer": "1/2"
  },
  {
    "task_id": "reason_math_28",
    "category": "Math",
    "type": "exact",
    "prompt": "A committee of 5 people is chosen from 6 men and 4 women. What is the probability of selecting exactly 3 men? Express as a simplified fraction. Output only the fraction.",
    "answer": "10/21"
  },
  {
    "task_id": "reason_math_29",
    "category": "Math",
    "type": "exact",
    "prompt": "Let f(x) = x^3 - 3x^2 + 2x + 1. Compute the derivative f'(x) evaluated at x = 2. Output only the number.",
    "answer": "2"
  },
  {
    "task_id": "reason_math_30",
    "category": "Math",
    "type": "exact",
    "prompt": "How many 3-element subsets of {1, 2, 3, 4, 5, 6, 7, 8, 9, 10} have their elements summing to exactly 15? Output only the number.",
    "answer": "10"
  },
  {
    "task_id": "reason_math_31",
    "category": "Math",
    "type": "exact",
    "prompt": "Compute 5^400 modulo 8 by finding the cyclic pattern. Output only the number (0 through 7).",
    "answer": "1"
  },
  {
    "task_id": "reason_math_32",
    "category": "Math",
    "type": "exact",
    "prompt": "How many surjective (onto) functions exist from a set of 5 elements to a set of 3 elements? Use inclusion-exclusion. Output only the number.",
    "answer": "150"
  },
  {
    "task_id": "reason_math_33",
    "category": "Math",
    "type": "exact",
    "prompt": "Find the sum of all 4-digit palindromic numbers of the form abba where a is non-zero. Each such number equals 1001a + 110b. Output only the number.",
    "answer": "499950"
  },
  {
    "task_id": "reason_math_34",
    "category": "Math",
    "type": "exact",
    "prompt": "Evaluate sin^2(π/3) + cos^2(π/3). Output only the number.",
    "answer": "1"
  },
  {
    "task_id": "reason_math_35",
    "category": "Math",
    "type": "exact",
    "prompt": "A bag contains 4 red and 6 blue balls. Two balls are drawn without replacement. What is the probability both are red? Express as a simplified fraction. Output only the fraction.",
    "answer": "2/15"
  },
  {
    "task_id": "reason_math_36",
    "category": "Math",
    "type": "exact",
    "prompt": "How many positive divisors does the number 720 = 2^4 × 3^2 × 5 have? Output only the number.",
    "answer": "30"
  },
  {
    "task_id": "reason_math_37",
    "category": "Math",
    "type": "exact",
    "prompt": "For the geometric series 3 + 6 + 12 + 24 + ... find the sum of the first 10 terms. Output only the number.",
    "answer": "3069"
  },
  {
    "task_id": "reason_math_38",
    "category": "Math",
    "type": "exact",
    "prompt": "Find the rank of the 3×3 matrix where every entry in row i, column j is i × j. Specifically [[1,2,3],[2,4,6],[3,6,9]]. Output only the number.",
    "answer": "1"
  },
  {
    "task_id": "reason_math_39",
    "category": "Math",
    "type": "exact",
    "prompt": "Find the sum of the reciprocals of all positive divisors of 6. Output only the number.",
    "answer": "2"
  },
  {
    "task_id": "reason_math_40",
    "category": "Math",
    "type": "exact",
    "prompt": "Evaluate the definite integral ∫_0^π sin(x) dx. Output only the number.",
    "answer": "2"
  },
  {
    "task_id": "reason_math_41",
    "category": "Math",
    "type": "exact",
    "prompt": "Five cards are drawn from a standard 52-card deck. What is the probability of a flush (all five cards of the same suit)? Express as a simplified fraction. Output only the fraction.",
    "answer": "33/16660"
  },
  {
    "task_id": "reason_math_42",
    "category": "Math",
    "type": "exact",
    "prompt": "Three distinct numbers are chosen uniformly from {1, 2, ..., 15}. What is the probability that their sum is divisible by 3? Express as a simplified fraction. Output only the fraction.",
    "answer": "31/91"
  },
  {
    "task_id": "reason_math_43",
    "category": "Math",
    "type": "exact",
    "prompt": "Evaluate the definite integral ∫_1^2 (x^2 + 1/x^2) dx. Output only the simplified fraction.",
    "answer": "17/6"
  },
  {
    "task_id": "reason_math_44",
    "category": "Math",
    "type": "exact",
    "prompt": "How many positive integers less than 1000 are divisible by 7 but not by 3? Use the floor function and inclusion-exclusion. Output only the number.",
    "answer": "95"
  },
  {
    "task_id": "reason_math_45",
    "category": "Math",
    "type": "exact",
    "prompt": "Ten distinct items are split into two unlabeled groups (empty groups are allowed). In how many distinct ways can this be done? Output only the number.",
    "answer": "512"
  },
  {
    "task_id": "reason_math_46",
    "category": "Math",
    "type": "exact",
    "prompt": "A biased six-sided die has P(1)=P(2)=P(3)=P(4)=0.1 and P(5)=P(6)=0.3. What is the expected value of a single roll? Output only the number.",
    "answer": "4.3"
  },
  {
    "task_id": "reason_math_47",
    "category": "Math",
    "type": "exact",
    "prompt": "Evaluate the limit: lim_{x→0} (e^x - 1 - x) / x^2. Use the Taylor series expansion for e^x. Output only the simplified fraction.",
    "answer": "1/2"
  },
  {
    "task_id": "reason_math_48",
    "category": "Math",
    "type": "exact",
    "prompt": "How many positive integers ≤ 200 are coprime to 200? Compute using Euler's totient function given 200 = 2^3 × 5^2. Output only the number.",
    "answer": "80"
  },
  {
    "task_id": "reason_math_49",
    "category": "Math",
    "type": "exact",
    "prompt": "Find the area of the triangle with vertices at (0,0), (4,1), and (1,5). Use the determinant formula. Output only the simplified fraction.",
    "answer": "19/2"
  },
  {
    "task_id": "reason_math_50",
    "category": "Math",
    "type": "exact",
    "prompt": "Evaluate the sum Σ_{k=1}^{20} k × 2^k using the formula for arithmetico-geometric series. Output only the number.",
    "answer": "39845890"
  },
  {
    "task_id": "reason_math_51",
    "category": "Math",
    "type": "exact",
    "prompt": "A 5-digit number is formed by arranging the digits {1,2,3,4,5} without repetition, uniformly at random. What is the probability the number is even? Express as a simplified fraction. Output only the fraction.",
    "answer": "2/5"
  },
  {
    "task_id": "reason_math_52",
    "category": "Math",
    "type": "exact",
    "prompt": "How many distinct terms appear in the expansion of (x + y + z)^10 before combining like terms? Use stars and bars. Output only the number.",
    "answer": "66"
  },
  {
    "task_id": "reason_math_53",
    "category": "Math",
    "type": "exact",
    "prompt": "Evaluate ln(1/e) + ln(e) + ln(e^2). Output only the number.",
    "answer": "2"
  },
  {
    "task_id": "reason_math_54",
    "category": "Math",
    "type": "exact",
    "prompt": "How many injective (one-to-one) functions exist from a set of 4 elements to a set of 7 elements? Output only the number.",
    "answer": "840"
  },
  {
    "task_id": "reason_math_55",
    "category": "Math",
    "type": "exact",
    "prompt": "A circle has equation x^2 + y^2 + 6x - 8y = 0. Find the radius by completing the square. Output only the number.",
    "answer": "5"
  },
  {
    "task_id": "reason_math_56",
    "category": "Math",
    "type": "exact",
    "prompt": "The Fibonacci sequence is defined by F_1 = 1, F_2 = 1, and F_n = F_{n-1} + F_{n-2} for n ≥ 3. Find F_8. Output only the number.",
    "answer": "21"
  },
  {
    "task_id": "reason_math_57",
    "category": "Math",
    "type": "exact",
    "prompt": "In how many distinct ways can 8 people sit around a circular table if rotations are considered identical but reflections are distinct? Output only the number.",
    "answer": "5040"
  },
  {
    "task_id": "reason_math_58",
    "category": "Math",
    "type": "exact",
    "prompt": "Evaluate the definite integral ∫_0^2 (3x^2 - 4x + 1) dx. Output only the number.",
    "answer": "2"
  },
  {
    "task_id": "reason_math_59",
    "category": "Math",
    "type": "exact",
    "prompt": "Evaluate the limit: lim_{n→∞} (n^2 + n) / (2n^2 + 1). Output only the simplified fraction.",
    "answer": "1/2"
  },
  {
    "task_id": "reason_math_60",
    "category": "Math",
    "type": "exact",
    "prompt": "Two fair six-sided dice are rolled. What is the probability their sum is exactly 10? Express as a simplified fraction. Output only the fraction.",
    "answer": "1/12"
  },
  {
    "task_id": "reason_logic_01",
    "category": "Logic Puzzles",
    "type": "exact",
    "prompt": "Three people A, B, C on an island of knights (always truth) and knaves (always lie). A says: 'B is a knight.' B says: 'A and C are the same type.' C says: 'B is a knave.' How many knights are there? Output only the number (0-3).",
    "answer": "1"
  },
  {
    "task_id": "reason_logic_02",
    "category": "Logic Puzzles",
    "type": "exact",
    "prompt": "Four people need to cross a bridge at night with one torch. Their crossing times are 1, 2, 5, and 10 minutes. At most two people can cross at a time, and when two cross together they travel at the slower person's pace. The torch must be carried back and forth. What is the minimum total time in minutes for all four to cross? Output only the number.",
    "answer": "17"
  },
  {
    "task_id": "reason_logic_03",
    "category": "Logic Puzzles",
    "type": "exact",
    "prompt": "You have a 3-gallon jug and a 5-gallon jug with no markings, and an unlimited water supply. You need exactly 4 gallons in the 5-gallon jug. What is the minimum number of operations (fill a jug, empty a jug, or pour water from one jug to the other) required? Output only the number.",
    "answer": "6"
  },
  {
    "task_id": "reason_logic_04",
    "category": "Logic Puzzles",
    "type": "exact",
    "prompt": "Three prisoners will each receive a black or white hat. Each can see the other two hats but not their own. They must simultaneously guess their own hat color. They win if at least one guesses correctly and no one guesses incorrectly. What is the maximum probability of winning they can guarantee with an optimal strategy? Express as a simplified fraction. Output only the fraction.",
    "answer": "3/4"
  },
  {
    "task_id": "reason_logic_05",
    "category": "Logic Puzzles",
    "type": "exact",
    "prompt": "A says 'The number of knights among us is 1.' B says 'The number of knights among us is 2.' C says 'The number of knights among us is 3.' On an island of knights (always truth) and knaves (always lie), exactly one of them is telling the truth. How many knights are there? Output only the number (0-3).",
    "answer": "1"
  },
  {
    "task_id": "reason_logic_06",
    "category": "Logic Puzzles",
    "type": "exact",
    "prompt": "A farmer must transport a wolf, a goat, and a cabbage across a river. The boat can carry the farmer and at most one item. The wolf will eat the goat if left alone together. The goat will eat the cabbage if left alone together. All items start on the same bank. What is the minimum number of one-way crossings required? Output only the number.",
    "answer": "7"
  },
  {
    "task_id": "reason_logic_07",
    "category": "Logic Puzzles",
    "type": "exact",
    "prompt": "If 1+4=5, 2+5=12, 3+6=21, then what does 5+8 equal? Follow the pattern that each result equals a × (b + 1). Output only the number.",
    "answer": "45"
  },
  {
    "task_id": "reason_logic_08",
    "category": "Logic Puzzles",
    "type": "exact",
    "prompt": "Four people A, B, C, D have different heights. A is taller than B. C is shorter than A. D is the shortest. B is taller than C. Who is the tallest? Output only the uppercase letter of the tallest person.",
    "answer": "A"
  },
  {
    "task_id": "reason_logic_09",
    "category": "Logic Puzzles",
    "type": "exact",
    "prompt": "Start with the number 87. Reverse its digits and add: 87 + 78 = 165. Continue until a palindrome is reached. How many addition steps are needed? Output only the number.",
    "answer": "4"
  },
  {
    "task_id": "reason_logic_10",
    "category": "Logic Puzzles",
    "type": "exact",
    "prompt": "There are 100 lockers, all initially closed. Prisoner 1 toggles every locker. Prisoner 2 toggles every 2nd locker. Prisoner k toggles every k-th locker. After all 100 prisoners have acted, how many lockers are open? Output only the number.",
    "answer": "10"
  },
  {
    "task_id": "reason_logic_11",
    "category": "Logic Puzzles",
    "type": "exact",
    "prompt": "On an island of knights (always truth), knaves (always lie), and spies (can do either), you meet three people A, B, C. Each type appears exactly once. A says 'I am a spy.' B says 'I am a knight.' C says 'I am a knave.' Who is the spy? Output only the uppercase letter of the spy.",
    "answer": "C"
  },
  {
    "task_id": "reason_logic_12",
    "category": "Logic Puzzles",
    "type": "exact",
    "prompt": "Find the missing number in the sequence: 2, 6, 12, 20, 30, 42, ?. The pattern follows n(n+1) for n starting at 1. Output only the number.",
    "answer": "56"
  },
  {
    "task_id": "reason_logic_13",
    "category": "Logic Puzzles",
    "type": "exact",
    "prompt": "Three missionaries and three cannibals must cross a river. The boat holds at most two people. Cannibals must never outnumber missionaries on either bank. What is the minimum number of one-way crossings required? Output only the number.",
    "answer": "11"
  },
  {
    "task_id": "reason_logic_14",
    "category": "Logic Puzzles",
    "type": "exact",
    "prompt": "One hundred light bulbs are all initially off. Person 1 toggles all bulbs. Person 2 toggles bulbs 2, 4, 6, ... Person k toggles every k-th bulb. After 100 people, how many bulbs are on? Output only the number.",
    "answer": "10"
  },
  {
    "task_id": "reason_logic_15",
    "category": "Logic Puzzles",
    "type": "exact",
    "prompt": "You have a 3-liter jug and a 5-liter jug with no markings. You may fill, empty, or pour between them. How many distinct integer liter amounts from 1 to 8 can you measure exactly? Since gcd(3,5)=1, you can measure every integer amount. Output only the number.",
    "answer": "8"
  },
  {
    "task_id": "reason_logic_16",
    "category": "Logic Puzzles",
    "type": "exact",
    "prompt": "Find the 4-digit number ABCD where: digit A is one-third of digit B, digit C equals A plus B, and digit D equals twice digit A. All digits are between 0 and 9, and A is non-zero. Output only the 4-digit number.",
    "answer": "2684"
  },
  {
    "task_id": "reason_logic_17",
    "category": "Logic Puzzles",
    "type": "exact",
    "prompt": "Two chests: one has treasure, one has a trap. Chest 1 says: 'At least one chest has treasure.' Chest 2 says: 'The other chest has a trap.' Exactly one inscription is true. Which chest has treasure? Output only the number 1 or 2.",
    "answer": "1"
  },
  {
    "task_id": "reason_logic_18",
    "category": "Logic Puzzles",
    "type": "exact",
    "prompt": "A clock reads exactly 3:15. What is the smaller angle in degrees between the hour hand and the minute hand? Output only the number.",
    "answer": "7.5"
  },
  {
    "task_id": "reason_logic_19",
    "category": "Logic Puzzles",
    "type": "exact",
    "prompt": "What number comes next in the look-and-say sequence: 1, 11, 21, 1211, 111221, ? Output only the number.",
    "answer": "312211"
  },
  {
    "task_id": "reason_logic_20",
    "category": "Logic Puzzles",
    "type": "exact",
    "prompt": "Find the three-digit number abc such that abc = a! + b! + c! where a, b, c are digits and a is non-zero. Output only the three-digit number.",
    "answer": "145"
  },
  {
    "task_id": "reason_logic_21",
    "category": "Logic Puzzles",
    "type": "exact",
    "prompt": "What letter comes next in the sequence: T, T, F, F, S, S, E, ? (Hint: first letters of the number words One, Two, Three, ...) Output only the uppercase letter.",
    "answer": "N"
  },
  {
    "task_id": "reason_logic_22",
    "category": "Logic Puzzles",
    "type": "exact",
    "prompt": "As I was going to St. Ives, I met a man with 7 wives. Each wife had 7 sacks. Each sack had 7 cats. Each cat had 7 kittens. How many total legs are among the man, his wives, the cats, and the kittens? (Humans have 2 legs, cats and kittens have 4 legs.) Output only the number.",
    "answer": "10992"
  },
  {
    "task_id": "reason_logic_23",
    "category": "Logic Puzzles",
    "type": "exact",
    "prompt": "Five people P, Q, R, S, T have different ages. P is older than Q. R is younger than S. T is older than P. S is younger than Q. Who is the second youngest? Output only the uppercase letter.",
    "answer": "S"
  },
  {
    "task_id": "reason_logic_24",
    "category": "Logic Puzzles",
    "type": "exact",
    "prompt": "A bat and a ball cost $1.10 in total. The bat costs $1.00 more than the ball. How many cents does the ball cost? Output only the number.",
    "answer": "5"
  },
  {
    "task_id": "reason_logic_25",
    "category": "Logic Puzzles",
    "type": "exact",
    "prompt": "How many times per day (24-hour period) do the hour and minute hands of a perfect clock form a 90-degree angle? Output only the number.",
    "answer": "44"
  },
  {
    "task_id": "reason_logic_26",
    "category": "Logic Puzzles",
    "type": "exact",
    "prompt": "Find the next number in the sequence: 9, 73, 241, 561, 1081, 1729, ? The pattern is (2n)^3 + (2n-1)^2 for n = 1,2,3,4,5,6. Output only the number.",
    "answer": "2913"
  },
  {
    "task_id": "reason_logic_27",
    "category": "Logic Puzzles",
    "type": "exact",
    "prompt": "Three boxes: one has two gold coins, one has two silver coins, one has one gold and one silver. You pick a box at random and draw a gold coin. What is the probability the other coin in that box is also gold? Express as a simplified fraction. Output only the fraction.",
    "answer": "2/3"
  },
  {
    "task_id": "reason_logic_28",
    "category": "Logic Puzzles",
    "type": "exact",
    "prompt": "A snail climbs 3 feet up a wall during the day and slips 2 feet down each night. How many days to reach the top of a 30-foot wall? Output only the number.",
    "answer": "28"
  },
  {
    "task_id": "reason_logic_29",
    "category": "Logic Puzzles",
    "type": "exact",
    "prompt": "In a house, there are 6 people. Each person has 6 backpacks. Each backpack contains 6 cats. Each cat has 6 kittens. How many total legs are among the people, cats, and kittens? (Humans have 2 legs, cats and kittens have 4 legs.) Output only the number.",
    "answer": "6060"
  },
  {
    "task_id": "reason_logic_30",
    "category": "Logic Puzzles",
    "type": "exact",
    "prompt": "Consider the 3x3 grid of digits where each row and column contains 1,2,3 exactly once (a Latin square). The top-left entry is 1. The center entry is 2. The bottom-right entry is 3. The anti-diagonal (top-right to bottom-left) sums to 4. What is the top-right entry? Output only the number (1-3).",
    "answer": "3"
  },
  {
    "task_id": "reason_data_01",
    "category": "Data Analysis",
    "type": "exact",
    "prompt": "A dataset contains: 5, 8, 12, 15, 20. Compute the sample standard deviation. Use the formula s = sqrt(SS/(n-1)) where SS is sum of squared deviations from the mean. Round to 3 decimal places. Output only the number.",
    "answer": "5.874"
  },
  {
    "task_id": "reason_data_02",
    "category": "Data Analysis",
    "type": "exact",
    "prompt": "Find the sample standard deviation of: 2, 4, 6, 8, 10. Round to 3 decimal places. Output only the number.",
    "answer": "3.162"
  },
  {
    "task_id": "reason_data_03",
    "category": "Data Analysis",
    "type": "exact",
    "prompt": "A student scores 85 on a test with mean 72 and standard deviation 8. Compute the z-score. Round to 3 decimal places. Output only the number.",
    "answer": "1.625"
  },
  {
    "task_id": "reason_data_04",
    "category": "Data Analysis",
    "type": "exact",
    "prompt": "A disease has prevalence 1%. A test is 99% sensitive and 99% specific. A randomly selected person tests positive. Using Bayes' theorem, what is the probability they have the disease? Round to 3 decimal places. Output only the decimal.",
    "answer": "0.500"
  },
  {
    "task_id": "reason_data_05",
    "category": "Data Analysis",
    "type": "exact",
    "prompt": "A survey of 400 voters finds 60% support a policy. Construct a 95% CI for the true proportion. Using z*=1.96, what is the lower bound? Round to 3 decimal places. Output only the decimal.",
    "answer": "0.552"
  },
  {
    "task_id": "reason_data_06",
    "category": "Data Analysis",
    "type": "exact",
    "prompt": "In linear regression with 10 data points: sum x = 50, sum y = 100, sum xy = 600, sum x^2 = 300. Compute the slope b1 = (n*sum xy - sum x*sum y) / (n*sum x^2 - (sum x)^2). Output only the number.",
    "answer": "2"
  },
  {
    "task_id": "reason_data_07",
    "category": "Data Analysis",
    "type": "exact",
    "prompt": "How many people must be sampled to estimate a population mean with margin of error 3 at 95% confidence? Population SD estimated at 10. Use n = (z*sigma/E)^2 with z=1.96. Round up to nearest integer. Output only the number.",
    "answer": "43"
  },
  {
    "task_id": "reason_data_08",
    "category": "Data Analysis",
    "type": "exact",
    "prompt": "For a two-tailed z-test with critical values of +/-1.96, what is the probability of Type I error (alpha)? Output only the decimal.",
    "answer": "0.05"
  },
  {
    "task_id": "reason_data_09",
    "category": "Data Analysis",
    "type": "exact",
    "prompt": "Compute the coefficient of variation for data with mean 50 and standard deviation 5. CV = SD/mean. Output only the decimal.",
    "answer": "0.1"
  },
  {
    "task_id": "reason_data_10",
    "category": "Data Analysis",
    "type": "exact",
    "prompt": "Three groups: 10 people with average 70, 20 people with average 80, 15 people with average 90. Compute the weighted mean of all 45 people. Round to 2 decimal places. Output only the number.",
    "answer": "81.11"
  }
]

with open('C:/Main/BenchMax/data/reason_full.json', 'w') as f:
    json.dump(data, f, indent=2)

with open('C:/Main/BenchMax/data/reason_mini.json', 'w') as f:
    json.dump(data[:5], f, indent=2)

print(f"Full: {len(data)} questions")
print(f"Mini: {len(data[:5])} questions")
