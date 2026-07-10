import json
from pathlib import Path

questions = []

# ──────────────────────────────────────────────
# ALGORITHMS (40)
# ──────────────────────────────────────────────

questions.extend([
    {
        "task_id": "code_algorithms_01",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `dfs_all_paths` that takes an undirected graph (as an adjacency list dict[int, list[int]]), a start node, and an end node, and returns a list of all simple paths from start to end (each path is a list of nodes). Use depth-first search. Example: graph={1:[2,3],2:[1,4],3:[1,4],4:[2,3]}, start=1, end=4 returns [[1,2,4],[1,3,4]].",
        "answer": "dfs_all_paths"
    },
    {
        "task_id": "code_algorithms_02",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `dijkstra_shortest` that takes a weighted graph (adjacency list dict[int, list[tuple[int,int]]] where each tuple is (neighbor, weight)) and a start node, and returns a dict mapping each reachable node to the shortest distance from start. Use Dijkstra's algorithm with a priority queue. Example: graph={0:[(1,4),(2,1)],1:[(3,1)],2:[(1,2),(3,5)],3:[]}, start=0 returns {0:0,1:3,2:1,3:4}.",
        "answer": "dijkstra_shortest"
    },
    {
        "task_id": "code_algorithms_03",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `bellman_ford` that takes a weighted directed graph (adjacency list dict[int, list[tuple[int,int]]]) with possible negative weights and a start node, and returns a dict of shortest distances. If a negative-weight cycle is reachable, return an empty dict. Example: graph={0:[(1,4),(2,5)],1:[(2,-3)],2:[]}, start=0 returns {0:0,1:4,2:1}.",
        "answer": "bellman_ford"
    },
    {
        "task_id": "code_algorithms_04",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `kruskal_mst` that takes a number of nodes n and a list of edges as tuples (u, v, weight), and returns the total weight of the minimum spanning tree using Kruskal's algorithm with union-find. Example: n=4, edges=[(0,1,10),(0,2,6),(0,3,5),(1,3,15),(2,3,4)] returns 19.",
        "answer": "kruskal_mst"
    },
    {
        "task_id": "code_algorithms_05",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `topological_sort` that takes a directed acyclic graph (adjacency list dict[int, list[int]]) and returns a list of nodes in topological order. If the graph contains a cycle, return an empty list. Example: graph={0:[1,2],1:[3],2:[3],3:[]} returns [0,1,2,3] or [0,2,1,3].",
        "answer": "topological_sort"
    },
    {
        "task_id": "code_algorithms_06",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `rabin_karp` that takes a text string and a pattern string, and returns a list of all starting indices where the pattern appears in text, using the Rabin-Karp algorithm with rolling hash (base 256, prime modulus 101). Example: text='hello world hello', pattern='hello' returns [0, 12].",
        "answer": "rabin_karp"
    },
    {
        "task_id": "code_algorithms_07",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `kmp_search` that takes a text string and a pattern string, and returns a list of all starting indices where the pattern appears, using the Knuth-Morris-Pratt algorithm (build LPS array). Example: text='abxabcabcaby', pattern='abcaby' returns [6].",
        "answer": "kmp_search"
    },
    {
        "task_id": "code_algorithms_08",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `merge_sort_list` that takes a list of integers and returns a new list sorted in ascending order using the merge sort algorithm (divide and conquer, O(n log n)). Example: [38,27,43,3,9,82,10] returns [3,9,10,27,38,43,82].",
        "answer": "merge_sort_list"
    },
    {
        "task_id": "code_algorithms_09",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `quick_sort_inplace` that takes a list of integers and sorts it in-place using the Quicksort algorithm (Lomuto or Hoare partition). Returns None. Example: arr=[10,7,8,9,1,5]; quick_sort_inplace(arr); arr is now [1,5,7,8,9,10].",
        "answer": "quick_sort_inplace"
    },
    {
        "task_id": "code_algorithms_10",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `binary_search_rotated` that takes a sorted array of distinct integers that has been rotated at an unknown pivot, and a target integer, and returns the index of target or -1 if not found. Must be O(log n). Example: nums=[4,5,6,7,0,1,2], target=0 returns 4.",
        "answer": "binary_search_rotated"
    },
    {
        "task_id": "code_algorithms_11",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `kth_smallest_quickselect` that takes a list of integers and an integer k (1-indexed), and returns the kth smallest element using the Quickselect algorithm (O(n) average). Example: arr=[7,10,4,3,20,15], k=3 returns 7.",
        "answer": "kth_smallest_quickselect"
    },
    {
        "task_id": "code_algorithms_12",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `heap_sort` that takes a list of integers and returns a new list sorted in ascending order using heapsort (build max-heap, then extract). Example: [4,10,3,5,1] returns [1,3,4,5,10].",
        "answer": "heap_sort"
    },
    {
        "task_id": "code_algorithms_13",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `counting_sort_negatives` that takes a list of integers (may include negatives) and returns a new list sorted in ascending order using counting sort. Example: [3,-1,2,-5,0,4] returns [-5,-1,0,2,3,4].",
        "answer": "counting_sort_negatives"
    },
    {
        "task_id": "code_algorithms_14",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `radix_sort_integers` that takes a list of non-negative integers and returns a new list sorted in ascending order using radix sort (base 10, counting sort per digit). Example: [170,45,75,90,802,24,2,66] returns [2,24,45,66,75,90,170,802].",
        "answer": "radix_sort_integers"
    },
    {
        "task_id": "code_algorithms_15",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `longest_increasing_subsequence` that takes a list of integers and returns the length of the longest strictly increasing subsequence using dynamic programming (O(n^2) or O(n log n)). Example: [10,9,2,5,3,7,101,18] returns 4 (from [2,3,7,101] or [2,5,7,101]).",
        "answer": "longest_increasing_subsequence"
    },
    {
        "task_id": "code_algorithms_16",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `edit_distance_dp` that takes two strings and returns the minimum edit distance (Levenshtein distance: insert, delete, substitute cost 1 each) using dynamic programming. Example: 'kitten', 'sitting' returns 3.",
        "answer": "edit_distance_dp"
    },
    {
        "task_id": "code_algorithms_17",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `knapsack_01` that takes a list of (weight, value) tuples and a capacity integer, and returns the maximum total value achievable (0/1 knapsack, each item used at most once). Use DP. Example: items=[(2,3),(3,4),(4,5),(5,6)], capacity=5 returns 7 (items 0 and 1).",
        "answer": "knapsack_01"
    },
    {
        "task_id": "code_algorithms_18",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `coin_change_combinations` that takes a list of coin denominations (positive ints, unlimited supply) and a target amount, and returns the number of distinct combinations that make up the amount. Use DP. Example: coins=[1,2,5], amount=5 returns 4 (5, 2+2+1, 2+1+1+1, 1+1+1+1+1).",
        "answer": "coin_change_combinations"
    },
    {
        "task_id": "code_algorithms_19",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `matrix_chain_multiplication` that takes a list of dimensions (list of ints where matrix i has dimensions dims[i] x dims[i+1]) and returns the minimum number of scalar multiplications needed. Use DP. Example: dims=[10,30,5,60] returns 4500.",
        "answer": "matrix_chain_multiplication"
    },
    {
        "task_id": "code_algorithms_20",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `longest_common_subsequence` that takes two strings and returns the length of their longest common subsequence using DP. Example: 'abcde', 'ace' returns 3 (the subsequence 'ace').",
        "answer": "longest_common_subsequence"
    },
    {
        "task_id": "code_algorithms_21",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `max_subarray_kadane` that takes a list of integers and returns the maximum sum of any contiguous subarray using Kadane's algorithm (O(n)). Example: [-2,1,-3,4,-1,2,1,-5,4] returns 6 (subarray [4,-1,2,1]).",
        "answer": "max_subarray_kadane"
    },
    {
        "task_id": "code_algorithms_22",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `floyd_warshall` that takes an n x n weight matrix (list of lists, with float('inf') for no direct edge) and returns an n x n matrix of shortest distances between all pairs using Floyd-Warshall. Example: dist=[[0,3,inf],[2,0,inf],[inf,7,0]] returns [[0,3,inf],[2,0,inf],[9,7,0]].",
        "answer": "floyd_warshall"
    },
    {
        "task_id": "code_algorithms_23",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `max_flow_ford_fulkerson` that takes a directed weighted graph (adjacency matrix n x n of capacities) with source and sink, and returns the maximum flow using the Ford-Fulkerson method with DFS. Example: cap=[[0,16,13,0,0,0],[0,0,10,12,0,0],[0,4,0,0,14,0],[0,0,9,0,0,20],[0,0,0,7,0,4],[0,0,0,0,0,0]], source=0, sink=5 returns 23.",
        "answer": "max_flow_ford_fulkerson"
    },
    {
        "task_id": "code_algorithms_24",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `bipartite_check` that takes an undirected graph (adjacency list dict[int, list[int]]) and returns True if the graph is bipartite, False otherwise. Use BFS coloring (0/1). Example: graph={0:[1,3],1:[0,2],2:[1,3],3:[0,2]} returns True; graph={0:[1,2],1:[0,2],2:[0,1]} returns False.",
        "answer": "bipartite_check"
    },
    {
        "task_id": "code_algorithms_25",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `tarjan_scc` that takes a directed graph (adjacency list dict[int, list[int]]) and returns a list of strongly connected components, each as a list of nodes, using Tarjan's algorithm (DFS + low-link values). Example: graph={0:[1],1:[2],2:[0,3],3:[4],4:[3]} returns [[0,1,2],[3,4]].",
        "answer": "tarjan_scc"
    },
    {
        "task_id": "code_algorithms_26",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `nqueens_solver` that takes an integer n and returns all distinct solutions to the n-queens puzzle (placing n queens on an n x n board so no two attack each other). Each solution is a list of strings where 'Q' marks a queen and '.' marks an empty cell. Example: n=4 returns [['.Q..','...Q','Q...','..Q.'],['..Q.','Q...','...Q','.Q..']].",
        "answer": "nqueens_solver"
    },
    {
        "task_id": "code_algorithms_27",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `sudoku_solver` that takes a 9x9 list of lists representing a partially filled Sudoku board (0 = empty), and solves it in-place using backtracking. Returns True if solvable, False otherwise. Example: board with a valid puzzle returns True and board is filled.",
        "answer": "sudoku_solver"
    },
    {
        "task_id": "code_algorithms_28",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `word_break_segment` that takes a string s and a set of words word_dict, and returns True if s can be segmented into a space-separated sequence of dictionary words using DP. Example: s='leetcode', word_dict={'leet','code'} returns True; s='catsandog', word_dict={'cats','dog','sand','and','cat'} returns False.",
        "answer": "word_break_segment"
    },
    {
        "task_id": "code_algorithms_29",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `job_scheduling_max_profit` that takes a list of jobs (start_time, end_time, profit) and returns the maximum profit achievable by scheduling non-overlapping jobs. Use DP with binary search. Example: jobs=[(1,2,50),(3,5,20),(6,19,100),(2,100,200)], sorted by end, returns 250 (jobs 0+2 or job 3).",
        "answer": "job_scheduling_max_profit"
    },
    {
        "task_id": "code_algorithms_30",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `huffman_encode` that takes a string and returns a tuple (huffman_codes, encoded_string) where huffman_codes is a dict mapping each character to its binary code (string of '0'/'1') using Huffman encoding, and encoded_string is the binary string. Example: 'aaabbc' returns e.g. ({'a':'0','b':'11','c':'10'}, '000111110').",
        "answer": "huffman_encode"
    },
    {
        "task_id": "code_algorithms_31",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `graham_scan_convex_hull` that takes a list of (x,y) points and returns the convex hull as a list of points in counterclockwise order using Graham scan. Example: points=[(0,0),(1,1),(2,2),(2,0),(2,4),(3,3),(4,2)] returns [(0,0),(2,0),(4,2),(2,4)] or equivalent.",
        "answer": "graham_scan_convex_hull"
    },
    {
        "task_id": "code_algorithms_32",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `kmeans_cluster` that takes a list of 2D points (tuples (x,y)), k clusters, and max_iterations, and returns a list of k cluster centroids and a list assigning each point to a centroid index, using the k-means++ initialization. Example: points=[(1,2),(1,4),(5,6),(8,9)], k=2 returns e.g. centroids=[(1,3),(6.5,7.5)], assignments=[0,0,1,1].",
        "answer": "kmeans_cluster"
    },
    {
        "task_id": "code_algorithms_33",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `maze_solver_bfs` that takes a 2D grid (list of list of ints, 0=open, 1=wall), a start tuple (r,c), and an end tuple, and returns the shortest path as a list of (r,c) tuples from start to end using BFS. If no path exists, return None. Example: grid=[[0,0,1],[1,0,1],[0,0,0]], start=(0,0), end=(2,0) returns [(0,0),(0,1),(1,1),(2,1),(2,0)].",
        "answer": "maze_solver_bfs"
    },
    {
        "task_id": "code_algorithms_34",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `game_of_life_step` that takes a 2D list (m x n, 0=dead, 1=alive) and returns the next state of Conway's Game of Life (compute in-place with out-of-place return). Rules: live cell <2 or >3 neighbors dies; live cell 2-3 neighbors lives; dead cell 3 neighbors becomes alive. Example: [[0,1,0],[0,1,0],[0,1,0]] returns [[0,0,0],[1,1,1],[0,0,0]].",
        "answer": "game_of_life_step"
    },
    {
        "task_id": "code_algorithms_35",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `skyline_problem` that takes a list of buildings as (left, right, height) tuples and returns the skyline as a list of (x, y) key points (result of merging building silhouettes). Example: buildings=[(2,9,10),(3,7,15),(5,12,12),(15,20,10),(19,24,8)] returns [(2,10),(3,15),(7,12),(12,0),(15,10),(20,8),(24,0)].",
        "answer": "skyline_problem"
    },
    {
        "task_id": "code_algorithms_36",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `prim_mst` that takes a weighted undirected graph (adjacency list dict[int, list[tuple[int,int]]]) and returns the total weight of the minimum spanning tree using Prim's algorithm with a priority queue. Example: graph={0:[(1,4),(2,3)],1:[(0,4),(2,1),(3,2)],2:[(0,3),(1,1),(3,5)],3:[(1,2),(2,5)]} returns 6.",
        "answer": "prim_mst"
    },
    {
        "task_id": "code_algorithms_37",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `alien_dictionary` that takes a list of words sorted in an alien language's lexicographical order and returns the order of characters as a string (topological sort of character graph). If invalid, return empty string. Example: words=['wrt','wrf','er','ett','rftt'] returns 'wertf'.",
        "answer": "alien_dictionary"
    },
    {
        "task_id": "code_algorithms_38",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `minimum_spanning_tree_kruskal_edges` that takes n nodes and a list of edges (u, v, weight) and returns the list of edges in the minimum spanning tree (as tuples (u,v,weight)) using Kruskal's algorithm. Example: n=4, edges=[(0,1,1),(0,2,3),(0,3,4),(1,3,2),(2,3,5)] returns [(0,1,1),(1,3,2),(0,2,3)].",
        "answer": "minimum_spanning_tree_kruskal_edges"
    },
    {
        "task_id": "code_algorithms_39",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `traveling_salesman_dp` that takes a distance matrix (n x n list of lists) and returns the minimum cost to visit all cities exactly once and return to the start (TSP) using DP with bitmask (Held-Karp algorithm). Example: dist=[[0,10,15,20],[10,0,35,25],[15,35,0,30],[20,25,30,0]] returns 80.",
        "answer": "traveling_salesman_dp"
    },
    {
        "task_id": "code_algorithms_40",
        "category": "Algorithms",
        "type": "code",
        "prompt": "Write a Python function called `pancake_sort` that takes a list of integers and returns a new list sorted in ascending order using pancake sort (flip prefix by finding max). Example: [3,6,1,5,2,4] returns [1,2,3,4,5,6].",
        "answer": "pancake_sort"
    },
])

# ──────────────────────────────────────────────
# DATA STRUCTURES (25)
# ──────────────────────────────────────────────

questions.extend([
    {
        "task_id": "code_data_structures_01",
        "category": "Data Structures",
        "type": "code",
        "prompt": "Write a Python class called `Trie` with methods `insert(word)`, `search(word)` (returns bool), and `starts_with(prefix)` (returns bool) implementing a trie (prefix tree). Example: t=Trie(); t.insert('apple'); t.search('apple') returns True; t.search('app') returns False; t.starts_with('app') returns True.",
        "answer": "Trie"
    },
    {
        "task_id": "code_data_structures_02",
        "category": "Data Structures",
        "type": "code",
        "prompt": "Write a Python class called `MinStack` that supports push(val), pop(), top(), and get_min() — all in O(1) time. Maintain an auxiliary stack tracking the minimum at each state. Example: ms=MinStack(); ms.push(-2); ms.push(0); ms.push(-3); ms.get_min() returns -3; ms.pop(); ms.top() returns 0; ms.get_min() returns -2.",
        "answer": "MinStack"
    },
    {
        "task_id": "code_data_structures_03",
        "category": "Data Structures",
        "type": "code",
        "prompt": "Write a Python class called `LRUCache` with methods `get(key)` (returns value or -1) and `put(key, value)` using O(1) average time. Capacity is passed to __init__(capacity). Evict least recently used item when over capacity. Use dict + doubly linked list. Example: c=LRUCache(2); c.put(1,1); c.put(2,2); c.get(1) returns 1; c.put(3,3) evicts key 2; c.get(2) returns -1.",
        "answer": "LRUCache"
    },
    {
        "task_id": "code_data_structures_04",
        "category": "Data Structures",
        "type": "code",
        "prompt": "Write a Python function called `merge_k_sorted_lists` that takes a list of sorted linked lists (each is a ListNode with val and next) and returns a single sorted linked list using a min-heap. Define ListNode class internally. Example: lists [1->4->5, 1->3->4, 2->6] returns 1->1->2->3->4->4->5->6.",
        "answer": "merge_k_sorted_lists"
    },
    {
        "task_id": "code_data_structures_05",
        "category": "Data Structures",
        "type": "code",
        "prompt": "Write a Python class called `SegmentTree` with methods `__init__(arr)` that builds a segment tree (for range sum queries), `query(l, r)` (inclusive) that returns the sum, and `update(idx, val)` that updates arr[idx] to val. Example: st=SegmentTree([1,3,5,7,9,11]); st.query(1,3) returns 15; st.update(1,10); st.query(1,3) returns 22.",
        "answer": "SegmentTree"
    },
    {
        "task_id": "code_data_structures_06",
        "category": "Data Structures",
        "type": "code",
        "prompt": "Write a Python function called `reverse_linked_list_in_groups` that takes a linked list (ListNode with val, next) and an integer k, and reverses every group of k nodes. Returns the new head. If length < k, leave as is. Example: 1->2->3->4->5, k=2 returns 2->1->4->3->5.",
        "answer": "reverse_linked_list_in_groups"
    },
    {
        "task_id": "code_data_structures_07",
        "category": "Data Structures",
        "type": "code",
        "prompt": "Write a Python class called `MedianFinder` that supports `add_num(num)` (adds integer) and `find_median()` (returns float median of all numbers) using two heaps (max-heap for lower half, min-heap for upper half). Example: mf=MedianFinder(); mf.add_num(1); mf.add_num(2); mf.find_median() returns 1.5; mf.add_num(3); mf.find_median() returns 2.0.",
        "answer": "MedianFinder"
    },
    {
        "task_id": "code_data_structures_08",
        "category": "Data Structures",
        "type": "code",
        "prompt": "Write a Python function called `detect_cycle_linked_list` that takes a ListNode (possibly containing a cycle) and returns the node where the cycle begins, or None if no cycle. Use Floyd's tortoise and hare algorithm. Example: 1->2->3->4->2 (cycle at 2) returns node with value 2.",
        "answer": "detect_cycle_linked_list"
    },
    {
        "task_id": "code_data_structures_09",
        "category": "Data Structures",
        "type": "code",
        "prompt": "Write a Python function called `lru_cache_decorator` that returns a decorator that caches function results with an LRU eviction policy of a given max size. The decorator should accept `maxsize` as argument. Example: @lru_cache_decorator(maxsize=3); def fib(n): ...  — cache stores last 3 distinct calls.",
        "answer": "lru_cache_decorator"
    },
    {
        "task_id": "code_data_structures_10",
        "category": "Data Structures",
        "type": "code",
        "prompt": "Write a Python class called `UnionFind` (Disjoint Set Union) with methods `find(x)` (with path compression) and `union(x, y)` (by rank). Also include `connected(x, y)` returning bool. Example: uf=UnionFind(10); uf.union(1,2); uf.union(2,3); uf.connected(1,3) returns True; uf.connected(1,4) returns False.",
        "answer": "UnionFind"
    },
    {
        "task_id": "code_data_structures_11",
        "category": "Data Structures",
        "type": "code",
        "prompt": "Write a Python class called `FenwickTree` (Binary Indexed Tree) with methods `__init__(n)` and `update(i, delta)` (add delta at index i, 1-indexed) and `query(i)` (sum from 1 to i). Example: ft=FenwickTree(5); ft.update(1,3); ft.update(2,5); ft.query(3) returns 8.",
        "answer": "FenwickTree"
    },
    {
        "task_id": "code_data_structures_12",
        "category": "Data Structures",
        "type": "code",
        "prompt": "Write a Python function called `flatten_nested_list` that takes a nested list of integers (e.g., [1,[2,[3,4],5],6]) and returns a flat list of all integers using iterative stack (not recursion). Example: [1,[2,[3,4],5],6] returns [1,2,3,4,5,6].",
        "answer": "flatten_nested_list"
    },
    {
        "task_id": "code_data_structures_13",
        "category": "Data Structures",
        "type": "code",
        "prompt": "Write a Python function called `serialize_binary_tree` that takes a TreeNode (val, left, right) and returns a string in level-order (BFS) with 'null' for missing nodes, and a function `deserialize_binary_tree` that takes the string and rebuilds the tree. Example: root=TreeNode(1, TreeNode(2), TreeNode(3, TreeNode(4), TreeNode(5))); serialize returns '[1,2,3,null,null,4,5]'; deserialize reconstructs it.",
        "answer": "serialize_binary_tree"
    },
    {
        "task_id": "code_data_structures_14",
        "category": "Data Structures",
        "type": "code",
        "prompt": "Write a Python class called `CircularQueue` with methods `enqueue(val)`, `dequeue()` (returns value or -1), `front()`, `rear()`, `is_empty()`, `is_full()` using a fixed-size list (array-based circular buffer). Example: q=CircularQueue(3); q.enqueue(1); q.enqueue(2); q.enqueue(3); q.enqueue(4) returns False (full); q.dequeue() returns 1; q.enqueue(4) returns True.",
        "answer": "CircularQueue"
    },
    {
        "task_id": "code_data_structures_15",
        "category": "Data Structures",
        "type": "code",
        "prompt": "Write a Python function called `is_valid_bst` that takes a TreeNode (val, left, right) and returns True if the binary tree is a valid BST (all left descendants < node, all right descendants > node, no duplicates). Use min/max range recursion. Example: root=TreeNode(2, TreeNode(1), TreeNode(3)) returns True; root=TreeNode(5, TreeNode(1), TreeNode(4, TreeNode(3), TreeNode(6))) returns False.",
        "answer": "is_valid_bst"
    },
    {
        "task_id": "code_data_structures_16",
        "category": "Data Structures",
        "type": "code",
        "prompt": "Write a Python function called `lowest_common_ancestor_bst` that takes a BST root (TreeNode) and two node values p and q, and returns the LCA node's value. Example: root with nodes [6,2,8,0,4,7,9,null,null,3,5], p=2, q=8 returns 6; p=2, q=4 returns 2.",
        "answer": "lowest_common_ancestor_bst"
    },
    {
        "task_id": "code_data_structures_17",
        "category": "Data Structures",
        "type": "code",
        "prompt": "Write a Python class called `BloomFilter` with methods `add(item)` (hashes using multiple hash functions) and `contains(item)` (returns bool, may have false positives but never false negatives). Use bit array of size m and k hash functions (use Python's hash with different seeds). Example: bf=BloomFilter(1000,3); bf.add('hello'); bf.contains('hello') returns True; bf.contains('world') likely returns False.",
        "answer": "BloomFilter"
    },
    {
        "task_id": "code_data_structures_18",
        "category": "Data Structures",
        "type": "code",
        "prompt": "Write a Python function called `reorder_list` that takes a linked list (ListNode) and reorders it in-place to L0->Ln->L1->Ln-1->... (interleave first half with reversed second half). Returns None. Example: 1->2->3->4 becomes 1->4->2->3.",
        "answer": "reorder_list"
    },
    {
        "task_id": "code_data_structures_19",
        "category": "Data Structures",
        "type": "code",
        "prompt": "Write a Python function called `max_sliding_window` that takes a list of integers and window size k, and returns a list of maximum values in each sliding window using a deque (O(n)). Example: nums=[1,3,-1,-3,5,3,6,7], k=3 returns [3,3,5,5,6,7].",
        "answer": "max_sliding_window"
    },
    {
        "task_id": "code_data_structures_20",
        "category": "Data Structures",
        "type": "code",
        "prompt": "Write a Python class called `SparseVector` that stores a vector of large dimension efficiently (only non-zero entries), with methods `dot_product(other)` and `add(other)` returning a new SparseVector. Store as dict[int, float]. Example: v1=SparseVector({0:1, 3:4}); v2=SparseVector({0:2, 3:1, 5:3}); v1.dot_product(v2) returns 6.",
        "answer": "SparseVector"
    },
    {
        "task_id": "code_data_structures_21",
        "category": "Data Structures",
        "type": "code",
        "prompt": "Write a Python class called `SkipList` with methods `insert(val)`, `search(val)` (return bool), and `erase(val)` (return bool). Skip list uses multiple levels of linked lists for O(log n) average operations. Example: sl=SkipList(); sl.insert(1); sl.insert(3); sl.search(1) returns True; sl.erase(1) returns True; sl.search(1) returns False.",
        "answer": "SkipList"
    },
    {
        "task_id": "code_data_structures_22",
        "category": "Data Structures",
        "type": "code",
        "prompt": "Write a Python function called `clone_graph` that takes a Node (val, neighbors list) from a connected undirected graph and returns a deep copy (clone all nodes and edges). Use DFS with a hash map. Example: adj list [[2,4],[1,3],[2,4],[1,3]] returns a deep copy with identical structure.",
        "answer": "clone_graph"
    },
    {
        "task_id": "code_data_structures_23",
        "category": "Data Structures",
        "type": "code",
        "prompt": "Write a Python class called `LFUCache` with methods `get(key)` (returns value or -1) and `put(key, value)`. When cache reaches capacity, evict the least frequently used item. If tie, evict LRU among ties. Use dict of freq-buckets with doubly linked lists. Example: c=LFUCache(2); c.put(1,1); c.put(2,2); c.get(1) returns 1; c.put(3,3) evicts key 2; c.get(2) returns -1.",
        "answer": "LFUCache"
    },
    {
        "task_id": "code_data_structures_24",
        "category": "Data Structures",
        "type": "code",
        "prompt": "Write a Python function called `level_order_zigzag` that takes a TreeNode (binary tree) and returns a list of lists of node values in zigzag level order (alternating left-to-right then right-to-left per level). Example: root with values [3,9,20,null,null,15,7] returns [[3],[20,9],[15,7]].",
        "answer": "level_order_zigzag"
    },
    {
        "task_id": "code_data_structures_25",
        "category": "Data Structures",
        "type": "code",
        "prompt": "Write a Python function called `time_based_key_value_store` that implements a class `TimeMap` with methods `set(key, value, timestamp)` and `get(key, timestamp)` that returns the value with the largest timestamp <= given timestamp (or '' if none). Use dict + binary search on timestamps. Example: tm=TimeMap(); tm.set('foo','bar',1); tm.get('foo',1) returns 'bar'; tm.get('foo',3) returns 'bar'; tm.set('foo','bar2',4); tm.get('foo',4) returns 'bar2'; tm.get('foo',5) returns 'bar2'.",
        "answer": "TimeMap"
    },
])

# ──────────────────────────────────────────────
# STRING MANIPULATION (20)
# ──────────────────────────────────────────────

questions.extend([
    {
        "task_id": "code_string_01",
        "category": "String Manipulation",
        "type": "code",
        "prompt": "Write a Python function called `regex_simple_match` that implements regular expression matching with support for '.' (any single char) and '*' (zero or more of preceding char). Takes a string s and pattern p, returns bool. Must handle full string match. Example: is_match('aa','a') returns False; is_match('aa','a*') returns True; is_match('ab','.*') returns True; is_match('aab','c*a*b') returns True.",
        "answer": "regex_simple_match"
    },
    {
        "task_id": "code_string_02",
        "category": "String Manipulation",
        "type": "code",
        "prompt": "Write a Python function called `longest_palindromic_substring` that takes a string and returns the longest palindromic substring using expand-around-center (O(n^2)). Example: 'babad' returns 'bab' or 'aba'; 'cbbd' returns 'bb'; 'a' returns 'a'; 'ac' returns 'a'.",
        "answer": "longest_palindromic_substring"
    },
    {
        "task_id": "code_string_03",
        "category": "String Manipulation",
        "type": "code",
        "prompt": "Write a Python function called `valid_parentheses` that takes a string containing '()', '{}', '[]' and returns True if brackets are correctly matched and nested. Use a stack. Example: '()[]{}' returns True; '([)]' returns False; '{[]}' returns True.",
        "answer": "valid_parentheses"
    },
    {
        "task_id": "code_string_04",
        "category": "String Manipulation",
        "type": "code",
        "prompt": "Write a Python function called `decode_string` that takes an encoded string like '3[a]2[bc]' and returns the decoded string 'aaabcbc'. The encoding is k[encoded_string] where k is a positive integer. Supports nesting: '3[a2[c]]' returns 'accaccacc'. Use a stack. Example: '2[abc]3[cd]ef' returns 'abcabccdcdcdef'.",
        "answer": "decode_string"
    },
    {
        "task_id": "code_string_05",
        "category": "String Manipulation",
        "type": "code",
        "prompt": "Write a Python function called `group_anagrams` that takes a list of strings and returns a list of lists, grouping anagrams together. Use a dict keyed by sorted string or char count tuple. Example: ['eat','tea','tan','ate','nat','bat'] returns [['eat','tea','ate'],['tan','nat'],['bat']].",
        "answer": "group_anagrams"
    },
    {
        "task_id": "code_string_06",
        "category": "String Manipulation",
        "type": "code",
        "prompt": "Write a Python function called `minimum_window_substring` that takes strings s and t, and returns the minimum contiguous substring of s that contains all characters of t (including duplicates). If none, return ''. Use sliding window with counter. Example: s='ADOBECODEBANC', t='ABC' returns 'BANC'.",
        "answer": "minimum_window_substring"
    },
    {
        "task_id": "code_string_07",
        "category": "String Manipulation",
        "type": "code",
        "prompt": "Write a Python function called `word_break_all` that takes a string s and a list of words word_dict, and returns all possible sentences (space-separated strings) that can be formed by segmenting s. Use DFS with memoization. Example: s='catsanddog', word_dict=['cat','cats','and','sand','dog'] returns ['cat sand dog','cats and dog'].",
        "answer": "word_break_all"
    },
    {
        "task_id": "code_string_08",
        "category": "String Manipulation",
        "type": "code",
        "prompt": "Write a Python function called `basic_calculator` that evaluates a simple expression string with non-negative integers and operators +, -, *, / (integer division truncating toward zero) and parentheses. No spaces or handle them. Example: '3+2*2' returns 7; ' 3/2 ' returns 1; ' (1+(4+5+2)-3)+(6+8) ' returns 23.",
        "answer": "basic_calculator"
    },
    {
        "task_id": "code_string_09",
        "category": "String Manipulation",
        "type": "code",
        "prompt": "Write a Python function called `text_justify` that takes a list of words and maxWidth per line, and returns a list of fully-justified lines. Greedily pack words; extra spaces distributed left to right. Last line left-justified. Example: words=['This','is','an','example','of','text','justification.'], maxWidth=16 returns ['This    is    an','example  of text','justification.  '].",
        "answer": "text_justify"
    },
    {
        "task_id": "code_string_10",
        "category": "String Manipulation",
        "type": "code",
        "prompt": "Write a Python function called `longest_substring_no_repeat` that takes a string and returns the length of the longest substring without repeating characters. Use sliding window with a set or dict. Example: 'abcabcbb' returns 3 ('abc'); 'bbbbb' returns 1 ('b'); 'pwwkew' returns 3 ('wke').",
        "answer": "longest_substring_no_repeat"
    },
    {
        "task_id": "code_string_11",
        "category": "String Manipulation",
        "type": "code",
        "prompt": "Write a Python function called `count_and_say` that takes an integer n (1-indexed) and returns the nth term of the count-and-say sequence: 1->'1', 2->'11', 3->'21', 4->'1211', 5->'111221'. Example: n=4 returns '1211'.",
        "answer": "count_and_say"
    },
    {
        "task_id": "code_string_12",
        "category": "String Manipulation",
        "type": "code",
        "prompt": "Write a Python function called `full_justify` that takes words list and maxWidth, and returns a list of justified lines (same as text justification problem — distribute spaces evenly, extra spaces leftmost; last line left-justified). Example: words=['Science','is','what','we','understand','well','enough','to','explain','to','a','computer.'], maxWidth=20 returns 3 justified lines.",
        "answer": "full_justify"
    },
    {
        "task_id": "code_string_13",
        "category": "String Manipulation",
        "type": "code",
        "prompt": "Write a Python function called `restore_ip_addresses` that takes a string of digits and returns all valid IP addresses (4 dot-separated decimal parts, each 0-255, no leading zeros unless part is exactly '0'). Use backtracking. Example: '25525511135' returns ['255.255.11.135','255.255.111.35']; '0000' returns ['0.0.0.0'].",
        "answer": "restore_ip_addresses"
    },
    {
        "task_id": "code_string_14",
        "category": "String Manipulation",
        "type": "code",
        "prompt": "Write a Python function called `find_all_concatenated_words` that takes a list of words (without duplicates) and returns a list of words that can be formed by concatenating at least two other words from the list (not necessarily distinct). Use DP/Trie. Example: words=['cat','cats','dog','catsdog','rat'] returns ['catsdog'].",
        "answer": "find_all_concatenated_words"
    },
    {
        "task_id": "code_string_15",
        "category": "String Manipulation",
        "type": "code",
        "prompt": "Write a Python function called `str_str_kmp` that takes a haystack string and a needle string, and returns the index of the first occurrence of needle in haystack (-1 if not found) using the KMP algorithm. Example: haystack='sadbutsad', needle='sad' returns 0; haystack='leetcode', needle='leeto' returns -1.",
        "answer": "str_str_kmp"
    },
    {
        "task_id": "code_string_16",
        "category": "String Manipulation",
        "type": "code",
        "prompt": "Write a Python function called `simplify_path` that takes a Unix-style absolute path string (with '..', '.', multiple slashes) and returns the canonical path (single slash, no trailing slash, no '..' or '.'). Example: '/home//foo/' returns '/home/foo'; '/a/./b/../../c/' returns '/c'; '/../' returns '/'.",
        "answer": "simplify_path"
    },
    {
        "task_id": "code_string_17",
        "category": "String Manipulation",
        "type": "code",
        "prompt": "Write a Python function called `frequency_sort` that takes a string and returns it sorted in decreasing order of character frequency (tiebreak by any order). Example: 'tree' returns 'eert' or 'eetr'; 'cccaaa' returns 'cccaaa' or 'aaaccc'; 'Aabb' returns 'bbAa' or 'bbaA'.",
        "answer": "frequency_sort"
    },
    {
        "task_id": "code_string_18",
        "category": "String Manipulation",
        "type": "code",
        "prompt": "Write a Python function called `make_string_sorted_palindrome_min_insertions` that takes a string and returns the minimum number of insertions needed to make it a palindrome. Use DP (LCS between string and its reverse). Example: 'leetcode' returns 5; 'mbadm' returns 2 (e.g., 'mbdadbm' or 'mdbabdm'); 'zzazz' returns 0.",
        "answer": "make_string_sorted_palindrome_min_insertions"
    },
    {
        "task_id": "code_string_19",
        "category": "String Manipulation",
        "type": "code",
        "prompt": "Write a Python function called `multiply_strings` that takes two non-negative integer strings num1 and num2 (each up to 200 digits) and returns their product as a string. Do not use built-in big integers or convert to int. Use manual digit-by-digit multiplication. Example: '123', '456' returns '56088'.",
        "answer": "multiply_strings"
    },
    {
        "task_id": "code_string_20",
        "category": "String Manipulation",
        "type": "code",
        "prompt": "Write a Python function called `wildcard_match` that takes a string s and a pattern p containing '?' (any single char) and '*' (any sequence of chars, including empty) and returns True if they match (full string). Use DP or two-pointer greedy. Example: is_match('aa','a') returns False; is_match('aa','*') returns True; is_match('cb','?a') returns False; is_match('adceb','*a*b') returns True.",
        "answer": "wildcard_match"
    },
])

# ──────────────────────────────────────────────
# MATH / NUMBER THEORY (15)
# ──────────────────────────────────────────────

questions.extend([
    {
        "task_id": "code_math_01",
        "category": "Math",
        "type": "code",
        "prompt": "Write a Python function called `sieve_prime_count` that takes an integer n and returns the number of prime numbers less than n using the Sieve of Eratosthenes (O(n log log n)). Example: n=10 returns 4 (primes 2,3,5,7); n=0 returns 0; n=1 returns 0; n=100 returns 25.",
        "answer": "sieve_prime_count"
    },
    {
        "task_id": "code_math_02",
        "category": "Math",
        "type": "code",
        "prompt": "Write a Python function called `nth_ugly_number` that takes integers n and returns the nth ugly number (positive integers whose prime factors are only 2, 3, and 5). 1 is the first ugly number. Use DP with three pointers. Example: n=10 returns 12; n=1 returns 1; n=7 returns 8; n=1690 returns 2123366400.",
        "answer": "nth_ugly_number"
    },
    {
        "task_id": "code_math_03",
        "category": "Math",
        "type": "code",
        "prompt": "Write a Python function called `nth_super_ugly_number` that takes n and a list of primes, and returns the nth super ugly number (positive integers whose prime factors are only from the given prime list). Use DP with pointers. Example: n=12, primes=[2,7,13,19] returns 32; n=1 returns 1.",
        "answer": "nth_super_ugly_number"
    },
    {
        "task_id": "code_math_04",
        "category": "Math",
        "type": "code",
        "prompt": "Write a Python function called `nth_fibonacci_matrix` that takes an integer n and returns the nth Fibonacci number (F(0)=0, F(1)=1) using matrix exponentiation (O(log n)). Example: n=10 returns 55; n=0 returns 0; n=1 returns 1; n=50 returns 12586269025.",
        "answer": "nth_fibonacci_matrix"
    },
    {
        "task_id": "code_math_05",
        "category": "Math",
        "type": "code",
        "prompt": "Write a Python function called `gcd_of_array` that takes a list of positive integers and returns their greatest common divisor using Euclid's algorithm. Example: [12, 18, 24] returns 6; [7, 11, 13] returns 1; [100, 25, 50] returns 25.",
        "answer": "gcd_of_array"
    },
    {
        "task_id": "code_math_06",
        "category": "Math",
        "type": "code",
        "prompt": "Write a Python function called `find_missing_positive` that takes a list of unsorted integers and returns the smallest missing positive integer (greater than 0) using O(n) time and O(1) extra space (cycle-sort / reorder in-place). Example: [3,4,-1,1] returns 2; [1,2,0] returns 3; [7,8,9,11,12] returns 1.",
        "answer": "find_missing_positive"
    },
    {
        "task_id": "code_math_07",
        "category": "Math",
        "type": "code",
        "prompt": "Write a Python function called `combination_sum_count` that takes an array of distinct positive integers candidates and a target integer target, and returns the number of unique combinations that sum to target (unlimited use of each element, sequences considered same regardless of order). Use DP. Example: candidates=[1,2,3], target=4 returns 4 (1+1+1+1, 1+1+2, 1+3, 2+2).",
        "answer": "combination_sum_count"
    },
    {
        "task_id": "code_math_08",
        "category": "Math",
        "type": "code",
        "prompt": "Write a Python function called `nth_catalan_number` that takes n and returns the nth Catalan number using DP (C(n) = sum of C(i)*C(n-1-i)). Catalan numbers: C(0)=1, C(1)=1, C(2)=2, C(3)=5, C(4)=14. Example: n=5 returns 42; n=10 returns 16796.",
        "answer": "nth_catalan_number"
    },
    {
        "task_id": "code_math_09",
        "category": "Math",
        "type": "code",
        "prompt": "Write a Python function called `integer_sqrt` that takes a non-negative integer x and returns the integer square root (floor of sqrt(x)) using binary search without using math.sqrt or **. Example: 8 returns 2; 9 returns 3; 0 returns 0; 2147395600 returns 46340.",
        "answer": "integer_sqrt"
    },
    {
        "task_id": "code_math_10",
        "category": "Math",
        "type": "code",
        "prompt": "Write a Python function called `modular_exponent` that takes base, exponent, and mod (all integers) and returns (base ** exponent) % mod efficiently using fast modular exponentiation (binary exponentiation). Example: base=2, exp=10, mod=1000 returns 24; base=3, exp=7, mod=100 returns 87.",
        "answer": "modular_exponent"
    },
    {
        "task_id": "code_math_11",
        "category": "Math",
        "type": "code",
        "prompt": "Write a Python function called `perfect_square_min` that takes a positive integer n and returns the least number of perfect square numbers (e.g., 1, 4, 9, 16, ...) that sum to n. Use DP (similar to coin change). Example: n=12 returns 3 (4+4+4); n=13 returns 2 (4+9); n=1 returns 1.",
        "answer": "perfect_square_min"
    },
    {
        "task_id": "code_math_12",
        "category": "Math",
        "type": "code",
        "prompt": "Write a Python function called `chinese_remainder` that takes two lists of equal length, `remainders` and `moduli` (pairwise coprime), and returns the smallest non-negative integer x such that x ≡ remainders[i] (mod moduli[i]) for all i, using the Chinese Remainder Theorem. Example: remainders=[2,3,2], moduli=[3,5,7] returns 23.",
        "answer": "chinese_remainder"
    },
    {
        "task_id": "code_math_13",
        "category": "Math",
        "type": "code",
        "prompt": "Write a Python function called `count_primes_range` that takes two integers L and R (inclusive) and returns the count of prime numbers in [L, R] using a segmented sieve (optimized for ranges where R-L is up to 10^6, R up to 10^9). Example: L=10, R=20 returns 4 (11,13,17,19); L=1, R=10 returns 4 (2,3,5,7).",
        "answer": "count_primes_range"
    },
    {
        "task_id": "code_math_14",
        "category": "Math",
        "type": "code",
        "prompt": "Write a Python function called `largest_rectangle_in_histogram` that takes a list of non-negative integers representing bar heights in a histogram, and returns the area of the largest rectangle. Use a stack-based O(n) algorithm. Example: heights=[2,1,5,6,2,3] returns 10; heights=[2,4] returns 4.",
        "answer": "largest_rectangle_in_histogram"
    },
    {
        "task_id": "code_math_15",
        "category": "Math",
        "type": "code",
        "prompt": "Write a Python function called `next_permutation` that takes a list of integers and rearranges it in-place to the next lexicographically greater permutation. Returns False if already the greatest (then arrange to smallest), else True. Example: arr=[1,2,3]; next_permutation(arr); arr becomes [1,3,2], returns True. arr=[3,2,1]; next_permutation(arr); arr becomes [1,2,3], returns False.",
        "answer": "next_permutation"
    },
])

# ──────────────────────────────────────────────
# Write output
# ──────────────────────────────────────────────

output_path = Path(__file__).resolve().parents[1] / "data" / "code_full.json"
output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(json.dumps(questions, indent=2), encoding="utf-8")

print(f"Generated {len(questions)} questions -> {output_path}")
