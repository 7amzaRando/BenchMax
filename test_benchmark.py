import asyncio
from pathlib import Path
from backend.database import SessionLocal, Run, Result
from backend.lm_studio.client import LMStudioClient
from backend.benchmarks.humaneval import HumanEvalBenchmark
import httpx

async def check_model_loaded():
    """Check if qwen3.5-9b is loaded in LM Studio"""
    client = LMStudioClient(base_url="http://localhost:1234")
    
    print("\nChecking loaded models...")
    try:
        active_model = await client.get_active_model_name()
        
        if not active_model:
            print("No active model found via API. LM Studio may not expose /models endpoint.")
            print("Proceeding with direct model name 'qwen3.5-9b'...")
            return True  # Assume it's loaded and proceed
        
        print(f"Active model: {active_model}")
        
        if "qwen" in active_model.lower():
            print(f"\n✓ Found Qwen model: {active_model}")
            return True
        else:
            print(f"\nNo Qwen models found. Active: {active_model}")
            return False
    except Exception as e:
        print(f"Error checking models: {e}")
        import traceback
        traceback.print_exc()
        # Don't fail - proceed anyway since LM Studio might not expose /models
        print("Proceeding with direct model name 'qwen3.5-9b'...")
        return True

async def test_single_sample():
    """Test benchmark with a single sample using qwen3.5-9b"""
    
    db = SessionLocal()
    client = LMStudioClient(base_url="http://localhost:1234")
    benchmark = HumanEvalBenchmark(db, client)
    
    print("Loading dataset...")
    dataset = benchmark.load_dataset()
    print(f"Loaded {len(dataset)} samples")
    
    if not dataset:
        print("No samples found!")
        return
    
    sample = dataset[0]
    task_id = sample["task_id"]
    entry_point = sample["entry_point"]
    
    print(f"\nTesting {task_id} with entry point: {entry_point}")
    print("=" * 60)
    
    run = Run(
        model_name="qwen3.5-9b",
        benchmark_name="humaneval",
        status="RUNNING",
        total_samples=1,
        current_index=0,
        parameters='{"temperature": 0.0, "max_completion_tokens": 256}'
    )
    db.add(run)
    db.commit()
    
    params = {
        "system_prompt": None,
        "temperature": 0.7,
        "max_completion_tokens": 512,
        "stop_tokens": ["\nclass", "\ndef", "\nif __name__"]
    }
    
    print("Running evaluation...")
    try:
        result = await benchmark.evaluate_sample(sample, params, "qwen3.5-9b")
        
        print("\n" + "=" * 60)
        print("DETAILED RESULTS:")
        print("=" * 60)
        print(f"Task ID: {task_id}")
        print(f"Correct: {result['correct']}")
        print(f"Error Message: {result.get('error_message', 'None')}")
        print(f"Elapsed Time: {result.get('elapsed_time', 0):.2f}s")
        print(f"TPS: {result.get('tps', 0):.2f}")
        
        if result.get("raw_response"):
            print("\nRaw Response (first 500 chars):")
            print("-" * 40)
            print(result["raw_response"][:500])
    except Exception as e:
        print(f"Error during evaluation: {e}")
        import traceback
        traceback.print_exc()
        db.close()
        return
    
    db_result = Result(
        run_id=run.id,
        task_id=task_id,
        prompt=result["prompt"],
        raw_response=result.get("raw_response", ""),
        extracted_code=result.get("extracted_code", ""),
        correct=result.get("correct", False),
        error_message=result.get("error_message", "")
    )
    db.add(db_result)
    db.commit()
    
    print("\n" + "=" * 60)
    print("RESULTS:")
    print("=" * 60)
    print(f"Task ID: {task_id}")
    print(f"Correct: {result['correct']}")
    print(f"Error Message: {result.get('error_message', 'None')}")
    print(f"Elapsed Time: {result.get('elapsed_time', 0):.2f}s")
    print(f"TPS: {result.get('tps', 0):.2f}")
    
    if result.get("extracted_code"):
        print("\nExtracted Code:")
        print("-" * 40)
        print(result["extracted_code"][:500])
    
    run.current_index = 1
    run.status = "COMPLETED"
    db.commit()
    
    print(f"\n✓ Test completed. Results saved to database.")
    db.close()

if __name__ == "__main__":
    print("=" * 60)
    print("Testing HumanEval Benchmark with qwen3.5-9b")
    print("=" * 60)
    
    model_loaded = asyncio.run(check_model_loaded())
    
    asyncio.run(test_single_sample())
