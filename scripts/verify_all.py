"""Run all verification checks: graders, datasets, compilers, and imports."""
import json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def check(label: str, ok: bool, detail: str = ""):
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {label}" + (f" - {detail}" if detail else ""))


def test_bfcl_checker():
    from backend.sandbox.bfcl_checker import multi_turn_simplified_checker, _parse_func_call_string

    p = _parse_func_call_string('cd(folder="document")')
    check("Parse func call string", p["name"] == "cd" and p["arguments"].get("folder") == "document")

    gt = [['cd(folder="documents")'], ['grep(file_name="log.txt",pattern="Error")']]
    model = [[{"name": "cd", "arguments": {"folder": "documents"}}],
             [{"name": "grep", "arguments": {"file_name": "log.txt", "pattern": "Error"}}]]
    check("Multi-turn exact match", multi_turn_simplified_checker(model, gt, "multi_turn_base", "", "")["valid"])

    model_bad = [[{"name": "rm", "arguments": {}}], []]
    r = multi_turn_simplified_checker(model_bad, gt, "multi_turn_base", "", "")
    check("Multi-turn wrong function", not r["valid"] and "rm" in r["error_message"])

    model_excl = [[{"name": "cp", "arguments": {}}]]
    r = multi_turn_simplified_checker(model_excl, [["cp(...)"]], "multi_turn_miss_func", ["cp"], "")
    check("Multi-turn excluded function", not r["valid"] and "excluded" in r["error_message"])


def test_datasets():
    from backend.database import SessionLocal
    from backend.config import BENCH_NAMES
    from backend.operations import _instantiate_benchmark
    db = SessionLocal()
    for bn in BENCH_NAMES:
        bench = _instantiate_benchmark(bn, db, None, quick_test=True)
        ds = bench.load_dataset()
        check(f"{bn} loads", len(ds) > 0, f"{len(ds)} samples")
    db.close()


def test_safe_executor():
    from backend.sandbox.safe_executor import check_correctness_humaneval
    r = check_correctness_humaneval("add", "def add(a,b):\n    ", "return a+b",
                                    "def check(add):\n    assert add(1,2)==3", timeout=5.0)
    check("safe_executor humaneval", r["passed"], r["result"])


def test_cpp_compiler():
    import shutil
    if shutil.which("docker") is None:
        check("benchmax-sandbox image (C++/Java/Go/Rust toolchains)", False, "docker CLI not found")
        return
    r = subprocess.run(["docker", "image", "inspect", "benchmax-sandbox:latest"],
                       capture_output=True, text=True, timeout=30)
    check("benchmax-sandbox image (C++/Java/Go/Rust toolchains)", r.returncode == 0,
          "image present" if r.returncode == 0 else "image not built — POST /api/docker/build")


def test_bfcl_data():
    d = json.loads(open("data/bfcl/bfcl_full.json", "r", encoding="utf-8").read())
    mt = [s for s in d if s.get("multi_turn")]
    check("BFCL dataset total", len(d) == 4696, f"{len(d)} samples")
    check("BFCL multi-turn count", len(mt) == 800, f"{len(mt)} samples")
    check("BFCL multi-turn has ground truth", all(s.get("answer") for s in mt))
    check("BFCL multi-turn has questions", all(s.get("question") for s in mt))


def test_imports():
    from backend.main import app
    check("FastAPI app import", True)


if __name__ == "__main__":
    print("=== BFCL Multi-turn Checker ===")
    test_bfcl_checker()

    print("\n=== BFCL Dataset ===")
    test_bfcl_data()

    print("\n=== All Benchmarks Load ===")
    test_datasets()

    print("\n=== safe_executor ===")
    test_safe_executor()

    print("\n=== C++ Compile + Catch2 ===")
    test_cpp_compiler()

    print("\n=== Backend Imports ===")
    test_imports()

    print("\nDone.")
