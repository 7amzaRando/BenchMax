import asyncio
from pathlib import Path
from backend.database import SessionLocal, Run, Result
from backend.lm_studio.client import LMStudioClient
from backend.benchmarks.bfcl import BFCLBenchmark
import httpx

async def test_benchmark_quick(benchmark_name, benchmark_class, db, client):
    """Test a benchmark with 5 samples (quick_test mode)"""
    
    print(f"\n{'=' * 70}")
    print(f"Testing {benchmark_name} Quick Test (5 questions)")
    print(f"{'=' * 70}")
    
    bench = benchmark_class(db, client, quick_test=True)
    
    print("Loading dataset...")
    dataset = bench.load_dataset()
    print(f"Loaded {len(dataset)} samples (should be ~5 for quick_test)")
    
    if not dataset:
        print("No samples found!")
        return
    
    run = Run(
        model_name="qwen3.5-9b",
        benchmark_name=benchmark_name,
        status="RUNNING",
        total_samples=len(dataset),
        current_index=0,
        parameters='{"temperature": 0.7}'
    )
    db.add(run)
    db.commit()
    
    print(f"\nEvaluating {len(dataset)} samples...")
    results = []
    
    for i, sample in enumerate(dataset):
        task_id = sample.get("task_id", f"unknown_{i}")
        entry_point = sample.get("entry_point", "check_function_call")
        
        print(f"\n[{i+1}/{len(dataset)}] Testing {task_id}...")
        print("-" * 60)
        
        params = {
            "system_prompt": None,
            "temperature": 0.7,
            "max_completion_tokens": 512,
            "stop_tokens": None
        }
        
        try:
            result = await bench.evaluate_sample(sample, params, "qwen3.5-9b")
            
            print(f"  Correct: {result.get('correct', False)}")
            if 'ast_score' in result and result['ast_score'] is not None:
                print(f"  AST Score: {result['ast_score']}")
            if 'url_score' in result and result['url_score'] is not None:
                print(f"  URL Score: {result['url_score']}")
            
            results.append(result)
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    print("\nSaving results to database...")
    for r in results:
        db_result = Result(
            run_id=run.id,
            task_id=r.get("task_id", ""),
            prompt=r.get("prompt", ""),
            raw_response=r.get("raw_response", ""),
            extracted_code=r.get("extracted_code", ""),
            correct=r.get("correct", False),
            error_message=r.get("error_message", "")
        )
        db.add(db_result)
    db.commit()
    
    run.current_index = len(dataset)
    run.status = "COMPLETED"
    db.commit()
    
    print("\n" + "=" * 70)
    print(f"SUMMARY: {benchmark_name} Quick Test")
    print("=" * 70)
    passed = sum(1 for r in results if r.get("correct", False))
    print(f"Passed: {passed}/{len(results)}")
    
    if results:
        print("\nSample Response (first result):")
        print("-" * 60)
        first = results[0]
        response = first.get("raw_response", "")
        if len(response) > 500:
            print(response[:500] + "...")
        else:
            print(response)

async def main():
    db = SessionLocal()
    client = LMStudioClient(base_url="http://localhost:1234")
    
    try:
        await test_benchmark_quick(
            "bfcl",
            BFCLBenchmark,
            db,
            client
        )
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
