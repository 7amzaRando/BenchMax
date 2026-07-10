"""Generate C:\Main\BenchMax\data\reason_full.json — 100 challenging reasoning questions."""

import json
import os

QUESTIONS = [
    # ===== MATH (35 questions) =====
    {
        "task_id": "reason_math_01",
        "category": "Math",
        "type": "free_form",
        "prompt": "A train leaves Station A at 60 km/h. Another train leaves Station B, 300 km away, at 90 km/h heading toward A. A bird flies back and forth between them at 120 km/h until they meet. How far does the bird travel? Output only the final number in kilometers.",
        "answer": "240"
    },
    {
        "task_id": "reason_math_02",
        "category": "Math",
        "type": "free_form",
        "prompt": "You have a 3-liter jug and a 5-liter jug. How many steps are needed to measure exactly 4 liters, if each step can be: fill a jug, empty a jug, or pour from one jug to the other until one is full or empty? Output only the minimum number of steps.",
        "answer": "6"
    },
    {
        "task_id": "reason_math_03",
        "category": "Math",
        "type": "free_form",
        "prompt": "A snail climbs 3 meters up a wall each day and slips back 2 meters each night. The wall is 10 meters high. How many full days does it take for the snail to reach the top? Output only the number of days.",
        "answer": "8"
    },
    {
        "task_id": "reason_math_04",
        "category": "Math",
        "type": "free_form",
        "prompt": "What is the sum of all integers from 1 to 100? Output only the final number.",
        "answer": "5050"
    },
    {
        "task_id": "reason_math_05",
        "category": "Math",
        "type": "free_form",
        "prompt": "Alice is twice as old as Bob was when Alice was as old as Bob is now. Their current ages sum to 56. How old is Alice? Output only the number.",
        "answer": "32"
    },
    {
        "task_id": "reason_math_06",
        "category": "Math",
        "type": "free_form",
        "prompt": "If it takes 5 machines 5 minutes to make 5 widgets, how long would it take 100 machines to make 100 widgets? Output only the number of minutes.",
        "answer": "5"
    },
    {
        "task_id": "reason_math_07",
        "category": "Math",
        "type": "free_form",
        "prompt": "What is the next prime number after 97? Output only the number.",
        "answer": "101"
    },
    {
        "task_id": "reason_math_08",
        "category": "Math",
        "type": "free_form",
        "prompt": "A rectangle's length is twice its width. Its perimeter is 54. What is the area in square units? Output only the final number.",
        "answer": "162"
    },
    {
        "task_id": "reason_math_09",
        "category": "Math",
        "type": "free_form",
        "prompt": "How many distinct four-digit numbers can be formed from the digits 1, 2, 3, 4 if no digit is repeated? Output only the number.",
        "answer": "24"
    },
    {
        "task_id": "reason_math_10",
        "category": "Math",
        "type": "free_form",
        "prompt": "What is 7! (7 factorial)? Output only the number.",
        "answer": "5040"
    },
    {
        "task_id": "reason_math_11",
        "category": "Math",
        "type": "free_form",
        "prompt": "A car travels at 40 km/h for the first half of a trip and 60 km/h for the second half. What is the average speed for the whole trip in km/h? Output only the final number.",
        "answer": "48"
    },
    {
        "task_id": "reason_math_12",
        "category": "Math",
        "type": "free_form",
        "prompt": "The sum of three consecutive odd integers is 231. What is the largest of the three? Output only the number.",
        "answer": "79"
    },
    {
        "task_id": "reason_math_13",
        "category": "Math",
        "type": "free_form",
        "prompt": "How many trailing zeros are in 100! (100 factorial)? Output only the number.",
        "answer": "24"
    },
    {
        "task_id": "reason_math_14",
        "category": "Math",
        "type": "free_form",
        "prompt": "A water tank has three pipes. Pipe A fills in 6 hours, Pipe B fills in 8 hours, Pipe C empties in 12 hours. If all three are opened simultaneously, how many hours will it take to fill the tank? Output only the number rounded to one decimal place.",
        "answer": "4.8"
    },
    {
        "task_id": "reason_math_15",
        "category": "Math",
        "type": "free_form",
        "prompt": "What is the 8th term of the Fibonacci sequence starting with 1, 1? Output only the number.",
        "answer": "21"
    },
    {
        "task_id": "reason_math_16",
        "category": "Math",
        "type": "free_form",
        "prompt": "If 5x + 3 = 2x + 18, what is x? Output only the number.",
        "answer": "5"
    },
    {
        "task_id": "reason_math_17",
        "category": "Math",
        "type": "free_form",
        "prompt": "A farmer has chickens and cows. There are 30 heads and 80 legs. How many chickens are there? Output only the number.",
        "answer": "20"
    },
    {
        "task_id": "reason_math_18",
        "category": "Math",
        "type": "free_form",
        "prompt": "What is the greatest common divisor of 48 and 180? Output only the number.",
        "answer": "12"
    },
    {
        "task_id": "reason_math_19",
        "category": "Math",
        "type": "free_form",
        "prompt": "What is the least common multiple of 12 and 18? Output only the number.",
        "answer": "36"
    },
    {
        "task_id": "reason_math_20",
        "category": "Math",
        "type": "free_form",
        "prompt": "How many sides does a regular polygon have if each interior angle is 156 degrees? Output only the number.",
        "answer": "15"
    },
    {
        "task_id": "reason_math_21",
        "category": "Math",
        "type": "free_form",
        "prompt": "A number when divided by 7 leaves remainder 4. When the same number is divided by 9, it leaves remainder 6. What is the smallest such positive number? Output only the number.",
        "answer": "60"
    },
    {
        "task_id": "reason_math_22",
        "category": "Math",
        "type": "free_form",
        "prompt": "What is the value of the infinite sum: 1/2 + 1/4 + 1/8 + 1/16 + ...? Output only the fraction or number.",
        "answer": "1"
    },
    {
        "task_id": "reason_math_23",
        "category": "Math",
        "type": "free_form",
        "prompt": "If the probability of event A is 0.4 and event B is 0.3, and they are independent, what is the probability that both occur? Output only the decimal.",
        "answer": "0.12"
    },
    {
        "task_id": "reason_math_24",
        "category": "Math",
        "type": "free_form",
        "prompt": "A cube has a surface area of 150 square cm. What is its volume in cubic cm? Output only the number.",
        "answer": "125"
    },
    {
        "task_id": "reason_math_25",
        "category": "Math",
        "type": "free_form",
        "prompt": "How many ways can 5 people be seated around a circular table? Output only the number.",
        "answer": "24"
    },
    {
        "task_id": "reason_math_26",
        "category": "Math",
        "type": "free_form",
        "prompt": "If log base 10 of x is 2.5, what is x? Output only the number.",
        "answer": "316.227766"
    },
    {
        "task_id": "reason_math_27",
        "category": "Math",
        "type": "free_form",
        "prompt": "A bag contains 5 red and 3 blue marbles. Two are drawn without replacement. What is the probability both are red? Output as a simplified fraction.",
        "answer": "5/14"
    },
    {
        "task_id": "reason_math_28",
        "category": "Math",
        "type": "free_form",
        "prompt": "What is 2^10? Output only the number.",
        "answer": "1024"
    },
    {
        "task_id": "reason_math_29",
        "category": "Math",
        "type": "free_form",
        "prompt": "The product of two consecutive even integers is 168. What is the smaller integer? Output only the number.",
        "answer": "12"
    },
    {
        "task_id": "reason_math_30",
        "category": "Math",
        "type": "free_form",
        "prompt": "A sphere has radius 3. What is its volume? Use pi=3.14159 and round to the nearest integer. Output only the number.",
        "answer": "113"
    },
    {
        "task_id": "reason_math_31",
        "category": "Math",
        "type": "free_form",
        "prompt": "In how many years will a sum of money double at 5% simple interest per year? Output only the integer number of years.",
        "answer": "20"
    },
    {
        "task_id": "reason_math_32",
        "category": "Math",
        "type": "free_form",
        "prompt": "What is the 100th digit after the decimal point of 1/7? Output only the digit (0-9).",
        "answer": "8"
    },
    {
        "task_id": "reason_math_33",
        "category": "Math",
        "type": "free_form",
        "prompt": "How many distinct prime factors does 210 have? Output only the number.",
        "answer": "4"
    },
    {
        "task_id": "reason_math_34",
        "category": "Math",
        "type": "free_form",
        "prompt": "What is the determinant of the matrix [[2, 3], [1, 4]]? Output only the number.",
        "answer": "5"
    },
    {
        "task_id": "reason_math_35",
        "category": "Math",
        "type": "free_form",
        "prompt": "An investment of $1000 grows at 10% compounded annually. After 5 years, what is the total value? Round to the nearest dollar. Output only the number.",
        "answer": "1610"
    },
    # ===== LOGIC PUZZLES (30 questions) =====
    {
        "task_id": "reason_logic_01",
        "category": "Logic Puzzles",
        "type": "free_form",
        "prompt": "Three people check into a hotel room that costs $30. They each pay $10. Later the clerk realizes the room is only $25 and sends the bellhop with $5. The bellhop keeps $2 and gives $1 back to each person. So each paid $9 for a total of $27, plus the $2 the bellhop kept is $29. Where is the missing $1? Respond with just the explanation phrase: \"no missing dollar\" if there is no missing dollar, or \"missing dollar\" if there is.",
        "answer": "no missing dollar"
    },
    {
        "task_id": "reason_logic_02",
        "category": "Logic Puzzles",
        "type": "free_form",
        "prompt": "You have two ropes that each take exactly 60 minutes to burn, but they burn unevenly (i.e., half the rope does not necessarily burn in 30 minutes). How can you measure exactly 45 minutes? Respond with just the key phrase: \"light both ends\" if that is part of the solution, or \"light one rope\" if that is sufficient.",
        "answer": "light both ends"
    },
    {
        "task_id": "reason_logic_03",
        "category": "Logic Puzzles",
        "type": "free_form",
        "prompt": "There are five houses in a row, each of a different color. Five people of different nationalities live in them. Each drinks a different beverage, smokes a different brand, and keeps a different pet. Using the following clues: (1) The Brit lives in the red house. (2) The Swede keeps dogs. (3) The Dane drinks tea. (4) The green house is immediately left of the white house. (5) The green house owner drinks coffee. (6) The person who smokes Pall Mall keeps birds. (7) The owner of the yellow house smokes Dunhill. (8) The man living in the center house drinks milk. (9) The Norwegian lives in the first house. (10) The man who smokes Blends lives next to the one who keeps cats. (11) The man who keeps horses lives next to the man who smokes Dunhill. (12) The man who smokes Blue Master drinks beer. (13) The German smokes Prince. (14) The Norwegian lives next to the blue house. (15) The man who smokes Blends has a neighbor who drinks water. Who owns the fish? Respond with just the nationality.",
        "answer": "German"
    },
    {
        "task_id": "reason_logic_04",
        "category": "Logic Puzzles",
        "type": "free_form",
        "prompt": "A truth-teller always tells the truth, a liar always lies, and a randomist answers randomly. You meet three people A, B, C. A says \"B is a liar.\" B says \"C is a liar.\" C says \"A is a liar.\" How many are truth-tellers? Output only the number (0, 1, 2, or 3).",
        "answer": "0"
    },
    {
        "task_id": "reason_logic_05",
        "category": "Logic Puzzles",
        "type": "free_form",
        "prompt": "You have 12 identical-looking coins, one of which is counterfeit and either heavier or lighter. Using a balance scale, what is the minimum number of weighings needed to guarantee finding the counterfeit and determining whether it is heavier or lighter? Output only the number.",
        "answer": "3"
    },
    {
        "task_id": "reason_logic_06",
        "category": "Logic Puzzles",
        "type": "free_form",
        "prompt": "Three light switches control three bulbs in another room. You can flip the switches any way you want but can only enter the other room once. How can you determine which switch controls which bulb? Respond with just the strategy keyword: \"heat\" or \"timing\" or \"sequence\".",
        "answer": "heat"
    },
    {
        "task_id": "reason_logic_07",
        "category": "Logic Puzzles",
        "type": "free_form",
        "prompt": "Two doors, two guards. One door leads to freedom, the other to death. One guard always tells the truth, the other always lies. You may ask one guard exactly one question. What question should you ask to find the safe door? Respond with just the key phrase: \"other guard\" if the question involves asking what the other guard would say.",
        "answer": "other guard"
    },
    {
        "task_id": "reason_logic_08",
        "category": "Logic Puzzles",
        "type": "free_form",
        "prompt": "A, B, C, D, and E are five friends. A is taller than B. C is taller than D but shorter than E. B is taller than C. Who is the shortest? Output only the letter (A, B, C, D, or E).",
        "answer": "D"
    },
    {
        "task_id": "reason_logic_09",
        "category": "Logic Puzzles",
        "type": "free_form",
        "prompt": "If all Bloops are Razzies and some Razzies are Lazzies, which of the following is necessarily true? Is it: (a) All Bloops are Lazzies, (b) Some Lazzies are Bloops, (c) Some Razzies are not Bloops, (d) None of the above. Output only the letter (a, b, c, or d).",
        "answer": "d"
    },
    {
        "task_id": "reason_logic_10",
        "category": "Logic Puzzles",
        "type": "free_form",
        "prompt": "What number comes next in this sequence: 2, 6, 18, 54, ? Output only the number.",
        "answer": "162"
    },
    {
        "task_id": "reason_logic_11",
        "category": "Logic Puzzles",
        "type": "free_form",
        "prompt": "In a race, you pass the person in second place. What position are you in now? Output only the ordinal (first, second, third, etc.) in lowercase.",
        "answer": "second"
    },
    {
        "task_id": "reason_logic_12",
        "category": "Logic Puzzles",
        "type": "free_form",
        "prompt": "A bat and a ball cost $1.10 in total. The bat costs $1.00 more than the ball. How much does the ball cost in cents? Output only the number.",
        "answer": "5"
    },
    {
        "task_id": "reason_logic_13",
        "category": "Logic Puzzles",
        "type": "free_form",
        "prompt": "If you have a 7-minute hourglass and an 11-minute hourglass, what is the minimum number of flips (turning over an hourglass counts as one flip) needed to measure exactly 15 minutes? Assume you can start timing from the moment any flip occurs. Output only the number.",
        "answer": "3"
    },
    {
        "task_id": "reason_logic_14",
        "category": "Logic Puzzles",
        "type": "free_form",
        "prompt": "There are three boxes: one contains only apples, one only oranges, and one both. All boxes are mislabeled. You may reach into one box and take out one fruit without looking inside. Which box should you pick from to determine the correct labels? Output only the box label: \"apples\", \"oranges\", or \"both\" in lowercase.",
        "answer": "both"
    },
    {
        "task_id": "reason_logic_15",
        "category": "Logic Puzzles",
        "type": "free_form",
        "prompt": "What is the missing letter in this sequence: J, F, M, A, M, J, J, A, S, O, N, ? Output only the uppercase letter.",
        "answer": "D"
    },
    {
        "task_id": "reason_logic_16",
        "category": "Logic Puzzles",
        "type": "free_form",
        "prompt": "Five people: Alan, Beth, Carl, Dana, and Eva each have a different job: Doctor, Lawyer, Teacher, Chef, and Pilot. Alan is not the Doctor or Lawyer. Beth works with food. Carl is not the Pilot. Dana is the Teacher. Eva is the Lawyer. Who is the Doctor? Output only the name (Alan, Beth, Carl, Dana, or Eva).",
        "answer": "Carl"
    },
    {
        "task_id": "reason_logic_17",
        "category": "Logic Puzzles",
        "type": "free_form",
        "prompt": "At a party, everyone shakes hands with everyone else exactly once. There are 66 handshakes. How many people are at the party? Output only the number.",
        "answer": "12"
    },
    {
        "task_id": "reason_logic_18",
        "category": "Logic Puzzles",
        "type": "free_form",
        "prompt": "You see a house with a blue door and a red roof. All houses in this town have either a blue or green door, and either a red or black roof. The statement \"This house has a blue door\" is true. The statement \"This house has a black roof\" is false. What color is the roof? Output only the color in lowercase.",
        "answer": "red"
    },
    {
        "task_id": "reason_logic_19",
        "category": "Logic Puzzles",
        "type": "free_form",
        "prompt": "A farmer needs to cross a river with a wolf, a goat, and a cabbage. The boat can carry only the farmer and one item. If left alone, the wolf eats the goat, and the goat eats the cabbage. What is the minimum number of crossings (one crossing = one trip in either direction) needed to get all across safely? Output only the number.",
        "answer": "7"
    },
    {
        "task_id": "reason_logic_20",
        "category": "Logic Puzzles",
        "type": "free_form",
        "prompt": "Complete the analogy: apple is to tree as puppy is to ___. Output only the single word in lowercase.",
        "answer": "dog"
    },
    {
        "task_id": "reason_logic_21",
        "category": "Logic Puzzles",
        "type": "free_form",
        "prompt": "In a certain code language, 'BOOK' is written as 'CPPK'. How is 'PENCIL' written in that code? Output only the coded word in uppercase letters.",
        "answer": "QEPCKJ"
    },
    {
        "task_id": "reason_logic_22",
        "category": "Logic Puzzles",
        "type": "free_form",
        "prompt": "You have 8 balls, one is heavier than the others. Using a balance scale, what is the minimum number of weighings needed to guarantee finding the heavier ball? Output only the number.",
        "answer": "2"
    },
    {
        "task_id": "reason_logic_23",
        "category": "Logic Puzzles",
        "type": "free_form",
        "prompt": "Mary's father has four daughters: Nana, Nene, Nini, Nono. What is the fourth daughter's name? Output only the name with proper capitalization.",
        "answer": "Mary"
    },
    {
        "task_id": "reason_logic_24",
        "category": "Logic Puzzles",
        "type": "free_form",
        "prompt": "Which number is the odd one out: 1, 4, 9, 16, 23, 36? Output only the number.",
        "answer": "23"
    },
    {
        "task_id": "reason_logic_25",
        "category": "Logic Puzzles",
        "type": "free_form",
        "prompt": "If it takes 6 days for 8 men to build a wall, how many days would it take 12 men to build the same wall working at the same rate? Output only the number.",
        "answer": "4"
    },
    {
        "task_id": "reason_logic_26",
        "category": "Logic Puzzles",
        "type": "free_form",
        "prompt": "What comes next in the pattern: O, T, T, F, F, S, S, E, ? Output only the uppercase letter.",
        "answer": "N"
    },
    {
        "task_id": "reason_logic_27",
        "category": "Logic Puzzles",
        "type": "free_form",
        "prompt": "If a doctor gives you three pills and tells you to take one every hour, how long will the pills last in hours? Output only the number.",
        "answer": "2"
    },
    {
        "task_id": "reason_logic_28",
        "category": "Logic Puzzles",
        "type": "free_form",
        "prompt": "Which number should replace the question mark: 3, 8, 15, 24, 35, ? Output only the number.",
        "answer": "48"
    },
    {
        "task_id": "reason_logic_29",
        "category": "Logic Puzzles",
        "type": "free_form",
        "prompt": "You enter a room with 34 people. All but 11 leave. How many people are left? Output only the number.",
        "answer": "11"
    },
    {
        "task_id": "reason_logic_30",
        "category": "Logic Puzzles",
        "type": "free_form",
        "prompt": "If the day after tomorrow is Monday, what day was the day before yesterday? Output only the day name (e.g., Monday, Tuesday) with capital first letter.",
        "answer": "Thursday"
    },
    # ===== DATA ANALYSIS (20 questions) =====
    {
        "task_id": "reason_data_01",
        "category": "Data Analysis",
        "type": "free_form",
        "prompt": "A company's revenue was $500,000 in 2020 and grew by 15% each year for 3 years. What is the revenue after 3 years? Round to the nearest thousand dollars. Output only the number.",
        "answer": "760000"
    },
    {
        "task_id": "reason_data_02",
        "category": "Data Analysis",
        "type": "free_form",
        "prompt": "A survey of 200 people found: 120 like coffee, 80 like tea, 50 like both. How many like neither coffee nor tea? Output only the number.",
        "answer": "50"
    },
    {
        "task_id": "reason_data_03",
        "category": "Data Analysis",
        "type": "free_form",
        "prompt": "In a class of 30 students, the average score on a test was 75. If the teacher adds 5 bonus points to every student's score, what is the new average? Output only the number.",
        "answer": "80"
    },
    {
        "task_id": "reason_data_04",
        "category": "Data Analysis",
        "type": "free_form",
        "prompt": "A dataset has numbers: 4, 8, 6, 5, 3, 7, 9, 5, 8, 6. What is the median? Output only the number.",
        "answer": "6"
    },
    {
        "task_id": "reason_data_05",
        "category": "Data Analysis",
        "type": "free_form",
        "prompt": "A store has a 30% off sale. An item costs $140 after the discount. What was the original price in dollars? Output only the number.",
        "answer": "200"
    },
    {
        "task_id": "reason_data_06",
        "category": "Data Analysis",
        "type": "free_form",
        "prompt": "Population of Town A is 50,000 growing at 2% per year. Population of Town B is 40,000 growing at 4% per year. After how many years will Town B surpass Town A in population? Output only the nearest integer number of years.",
        "answer": "12"
    },
    {
        "task_id": "reason_data_07",
        "category": "Data Analysis",
        "type": "free_form",
        "prompt": "A test has a mean of 72 and standard deviation of 8. Assuming a normal distribution, approximately what percentage of scores fall between 64 and 80? Output only the number (the percentage).",
        "answer": "68"
    },
    {
        "task_id": "reason_data_08",
        "category": "Data Analysis",
        "type": "free_form",
        "prompt": "In a pie chart, sector A has angle 90 degrees, sector B has 120 degrees, sector C has 150 degrees. What percentage of the total does sector B represent? Round to one decimal place. Output only the number followed by a percent sign.",
        "answer": "33.3%"
    },
    {
        "task_id": "reason_data_09",
        "category": "Data Analysis",
        "type": "free_form",
        "prompt": "A car's value depreciates 20% per year. It was bought for $25,000. What is its value after 3 years? Round to the nearest dollar. Output only the number.",
        "answer": "12800"
    },
    {
        "task_id": "reason_data_10",
        "category": "Data Analysis",
        "type": "free_form",
        "prompt": "A bag contains 40 marbles: 12 red, 14 blue, and the rest green. If you randomly pick one, what is the probability it is green? Output as a simplified fraction.",
        "answer": "7/20"
    },
    {
        "task_id": "reason_data_11",
        "category": "Data Analysis",
        "type": "free_form",
        "prompt": "In the dataset: 2, 5, 7, 9, 11, 15, 18, 22, 25, 30, what is the interquartile range (IQR)? Output only the number.",
        "answer": "16"
    },
    {
        "task_id": "reason_data_12",
        "category": "Data Analysis",
        "type": "free_form",
        "prompt": "A factory produces light bulbs with a 2% defect rate. In a box of 500 bulbs, how many are expected to be defective? Output only the number.",
        "answer": "10"
    },
    {
        "task_id": "reason_data_13",
        "category": "Data Analysis",
        "type": "free_form",
        "prompt": "A library has 60% fiction books and 40% non-fiction. If 30% of fiction and 10% of non-fiction are checked out, what percentage of total books are checked out? Output only the number (the percentage).",
        "answer": "22"
    },
    {
        "task_id": "reason_data_14",
        "category": "Data Analysis",
        "type": "free_form",
        "prompt": "Five numbers have a mean of 10 and a median of 12. The four smallest numbers are 3, 7, 12, 14. What is the largest number? Output only the number.",
        "answer": "14"
    },
    {
        "task_id": "reason_data_15",
        "category": "Data Analysis",
        "type": "free_form",
        "prompt": "An investor buys $10,000 of stock that grows 8% annually for 5 years. How much is the investment worth after 5 years? Use compound interest formula and round to the nearest dollar. Output only the number.",
        "answer": "14693"
    },
    {
        "task_id": "reason_data_16",
        "category": "Data Analysis",
        "type": "free_form",
        "prompt": "In a weighted grading system: Homework is 20% (score 85), Quizzes 30% (score 72), Final Exam 50% (score 90). What is the weighted average? Output only the number rounded to one decimal place.",
        "answer": "83.6"
    },
    {
        "task_id": "reason_data_17",
        "category": "Data Analysis",
        "type": "free_form",
        "prompt": "A salesperson earns a base salary of $30,000 plus 5% commission on sales. If total earnings are $52,500, what were total sales in dollars? Output only the number.",
        "answer": "450000"
    },
    {
        "task_id": "reason_data_18",
        "category": "Data Analysis",
        "type": "free_form",
        "prompt": "In a school, the ratio of boys to girls is 3:2. If there are 600 students total, how many more boys than girls are there? Output only the number.",
        "answer": "120"
    },
    {
        "task_id": "reason_data_19",
        "category": "Data Analysis",
        "type": "free_form",
        "prompt": "A researcher surveys 1000 people: 400 use Product X, 300 use Product Y, 200 use both. How many use neither product? Output only the number.",
        "answer": "500"
    },
    {
        "task_id": "reason_data_20",
        "category": "Data Analysis",
        "type": "free_form",
        "prompt": "A data set has five values. The mean is 20 and the sum of the first four values is 72. What is the fifth value? Output only the number.",
        "answer": "28"
    },
    # ===== SCIENTIFIC REASONING (15 questions) =====
    {
        "task_id": "reason_sci_01",
        "category": "Scientific Reasoning",
        "type": "free_form",
        "prompt": "A rock is dropped from a height of 45 meters. Ignoring air resistance and using g=10 m/s^2, how many seconds does it take to hit the ground? Output only the number.",
        "answer": "3"
    },
    {
        "task_id": "reason_sci_02",
        "category": "Scientific Reasoning",
        "type": "free_form",
        "prompt": "Water boils at 100 degrees C at sea level. On a mountain where atmospheric pressure is 80% of sea level, which of the following is true: water boils (a) above 100C, (b) at 100C, or (c) below 100C? Output only the letter (a, b, or c).",
        "answer": "c"
    },
    {
        "task_id": "reason_sci_03",
        "category": "Scientific Reasoning",
        "type": "free_form",
        "prompt": "A car moving at 20 m/s applies brakes and decelerates uniformly at 4 m/s^2. How far does it travel before stopping in meters? Output only the number.",
        "answer": "50"
    },
    {
        "task_id": "reason_sci_04",
        "category": "Scientific Reasoning",
        "type": "free_form",
        "prompt": "How many grams of sodium chloride (NaCl) are needed to make 500 mL of a 2 M solution? Atomic masses: Na=23, Cl=35.5. Output only the number rounded to one decimal place.",
        "answer": "58.5"
    },
    {
        "task_id": "reason_sci_05",
        "category": "Scientific Reasoning",
        "type": "free_form",
        "prompt": "A 2 kg object is moving at 3 m/s. What is its kinetic energy in joules? Output only the number.",
        "answer": "9"
    },
    {
        "task_id": "reason_sci_06",
        "category": "Scientific Reasoning",
        "type": "free_form",
        "prompt": "If a gas occupies 2 liters at 300 K, what volume in liters would it occupy at 450 K at constant pressure? Output only the number.",
        "answer": "3"
    },
    {
        "task_id": "reason_sci_07",
        "category": "Scientific Reasoning",
        "type": "free_form",
        "prompt": "You have 100 mL of 0.5 M HCl. How many mL of 0.1 M NaOH are needed to completely neutralize it? Output only the number.",
        "answer": "500"
    },
    {
        "task_id": "reason_sci_08",
        "category": "Scientific Reasoning",
        "type": "free_form",
        "prompt": "A 60-watt light bulb is left on for 5 hours. How much energy in watt-hours does it consume? Output only the number.",
        "answer": "300"
    },
    {
        "task_id": "reason_sci_09",
        "category": "Scientific Reasoning",
        "type": "free_form",
        "prompt": "A car travels 150 km in 2 hours. What is its average speed in km/h? Output only the number.",
        "answer": "75"
    },
    {
        "task_id": "reason_sci_10",
        "category": "Scientific Reasoning",
        "type": "free_form",
        "prompt": "What is the pH of a 0.001 M HCl solution? Output only the number.",
        "answer": "3"
    },
    {
        "task_id": "reason_sci_11",
        "category": "Scientific Reasoning",
        "type": "free_form",
        "prompt": "A 5 kg mass is at rest on a frictionless surface. A force of 10 N is applied horizontally for 3 seconds. What is the final velocity in m/s? Output only the number.",
        "answer": "6"
    },
    {
        "task_id": "reason_sci_12",
        "category": "Scientific Reasoning",
        "type": "free_form",
        "prompt": "A 10-gram ice cube at 0 degrees C is placed in 100 grams of water at 20 degrees C. Assuming no heat loss, what is the final temperature in degrees C? Specific heat of water: 4.2 J/gC, latent heat of fusion: 334 J/g. Round to the nearest whole degree Celsius. Output only the number.",
        "answer": "11"
    },
    {
        "task_id": "reason_sci_13",
        "category": "Scientific Reasoning",
        "type": "free_form",
        "prompt": "A light-year is the distance light travels in one year. Light speed is 300,000 km/s. Approximately how many kilometers is a light-year? Express in scientific notation: output only the form like \"9.46e12\".",
        "answer": "9.46e12"
    },
    {
        "task_id": "reason_sci_14",
        "category": "Scientific Reasoning",
        "type": "free_form",
        "prompt": "A 20-ohm resistor has 5 A of current flowing through it. What is the voltage across it? Output only the number in volts.",
        "answer": "100"
    },
    {
        "task_id": "reason_sci_15",
        "category": "Scientific Reasoning",
        "type": "free_form",
        "prompt": "An object with mass 2 kg has a weight of 19.6 N on Earth. If g on the Moon is 1/6 of Earth's g, what is the weight of the object on the Moon in newtons? Round to one decimal place. Output only the number.",
        "answer": "3.3"
    },
]


def main():
    output_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    output_path = os.path.join(output_dir, "reason_full.json")

    os.makedirs(output_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(QUESTIONS, f, indent=2)

    count = len(QUESTIONS)
    print(f"Generated {count} questions -> {output_path}")


if __name__ == "__main__":
    main()
