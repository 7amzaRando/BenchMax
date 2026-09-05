"""Tests for WritingSpeedTestBenchmark and CodingSpeedTestBenchmark."""
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Test imports work without LM Studio running
def test_imports():
    """Both benchmark classes can be imported without errors."""
    from backend.benchmarks.speed_test import (
        WritingSpeedTestBenchmark,
        CodingSpeedTestBenchmark,
    )
    assert WritingSpeedTestBenchmark is not None
    assert CodingSpeedTestBenchmark is not None


def test_dataset_structure_writing():
    """Writing speed test dataset has correct structure and 5 samples."""
    from backend.benchmarks.speed_test import WritingSpeedTestBenchmark

    # Create mock objects (no DB/client needed for load_dataset)
    db = MagicMock()
    client = MagicMock()

    bench = WritingSpeedTestBenchmark(db, client, quick_test=True)
    dataset = bench.load_dataset()

    assert len(dataset) == 5, f"Expected 5 samples, got {len(dataset)}"
    for sample in dataset:
        assert "prompt" in sample, "Missing 'prompt' field"
        assert "task_id" in sample, "Missing 'task_id' field"
        assert "category" in sample, "Missing 'category' field"
        assert isinstance(sample["prompt"], str) and len(sample["prompt"]) > 0


def test_dataset_structure_coding():
    """Coding speed test dataset has correct structure and 5 samples."""
    from backend.benchmarks.speed_test import CodingSpeedTestBenchmark

    db = MagicMock()
    client = MagicMock()

    bench = CodingSpeedTestBenchmark(db, client, quick_test=True)
    dataset = bench.load_dataset()

    assert len(dataset) == 5, f"Expected 5 samples, got {len(dataset)}"
    for sample in dataset:
        assert "prompt" in sample, "Missing 'prompt' field"
        assert "task_id" in sample, "Missing 'task_id' field"
        assert "category" in sample, "Missing 'category' field"
        assert isinstance(sample["prompt"], str) and len(sample["prompt"]) > 0


def test_writing_speed_test_evaluate_sample():
    """evaluate_sample returns correct structure with mocked client."""
    from backend.benchmarks.speed_test import WritingSpeedTestBenchmark

    db = MagicMock()
    mock_client = MagicMock()
    mock_client.generate_completion = AsyncMock(return_value={
        "raw_response": "test creative writing response",
        "answer_content": "",
        "thinking_tokens": 10,
        "response_tokens": 280,
        "elapsed_time": 3.5,
        "tps": 79.0,
        "ttft": 1.2,
    })

    bench = WritingSpeedTestBenchmark(db, mock_client)

    # Load a sample manually for testing
    dataset = bench.load_dataset()
    assert len(dataset) == 5
    sample = dataset[0]

    import asyncio
    result = asyncio.run(bench.evaluate_sample(sample, {}, "test-model"))

    # Verify return structure
    assert "prompt" in result
    assert "raw_response" in result
    assert "extracted_code" in result
    assert "correct" in result
    assert "error_message" in result
    assert "elapsed_time" in result
    assert "tps" in result
    assert "ttft" in result
    assert "thinking_tokens" in result
    assert "response_tokens" in result

    # Speed test always passes (correct=True)
    assert result["correct"] is True
    assert result["extracted_code"] == ""  # No code extraction for writing


def test_coding_speed_test_evaluate_sample():
    """evaluate_sample returns correct structure with mocked client."""
    from backend.benchmarks.speed_test import CodingSpeedTestBenchmark

    db = MagicMock()
    mock_client = MagicMock()
    mock_client.generate_completion = AsyncMock(return_value={
        "raw_response": "def fibonacci(n):\n    a, b = 0, 1\n    for _ in range(n):",
        "answer_content": "",
        "thinking_tokens": 5,
        "response_tokens": 290,
        "elapsed_time": 4.1,
        "tps": 70.0,
        "ttft": 0.8,
    })

    bench = CodingSpeedTestBenchmark(db, mock_client)

    dataset = bench.load_dataset()
    assert len(dataset) == 5
    sample = dataset[0]

    import asyncio
    result = asyncio.run(bench.evaluate_sample(sample, {}, "test-model"))

    # Verify return structure
    assert "prompt" in result
    assert "raw_response" in result
    assert "extracted_code" in result
    assert "correct" in result
    assert "error_message" in result
    assert "elapsed_time" in result
    assert "tps" in result
    assert "ttft" in result
    assert "thinking_tokens" in result
    assert "response_tokens" in result

    # Speed test always passes (correct=True)
    assert result["correct"] is True


def test_quick_test_uses_mini_dataset():
    """quick_test=True loads mini dataset (5 samples)."""
    from backend.benchmarks.speed_test import WritingSpeedTestBenchmark, CodingSpeedTestBenchmark

    db = MagicMock()
    client = MagicMock()

    writing_bench = WritingSpeedTestBenchmark(db, client, quick_test=True)
    assert len(writing_bench.load_dataset()) == 5

    coding_bench = CodingSpeedTestBenchmark(db, client, quick_test=True)
    assert len(coding_bench.load_dataset()) == 5


def test_scoring_details_included():
    """scoring_details dict is included in evaluate_sample output."""
    from backend.benchmarks.speed_test import WritingSpeedTestBenchmark

    db = MagicMock()
    mock_client = MagicMock()
    mock_client.generate_completion = AsyncMock(return_value={
        "raw_response": "test response",
        "answer_content": "",
        "thinking_tokens": 0,
        "response_tokens": 300,
        "elapsed_time": 2.0,
        "tps": 150.0,
        "ttft": 0.5,
    })

    bench = WritingSpeedTestBenchmark(db, mock_client)
    dataset = bench.load_dataset()
    sample = dataset[0]

    import asyncio
    result = asyncio.run(bench.evaluate_sample(sample, {}, "test-model"))

    # scoring_details should be a dict with category and token info (not a JSON string)
    assert "scoring_details" in result
    details = result["scoring_details"]
    assert isinstance(details, dict)
    assert "category" in details
    assert "target_tokens" in details
    assert "generated_tokens" in details


if __name__ == "__main__":
    print("Running speed_test.py benchmark tests...")
    print()

    # Run all tests manually (no pytest needed)
    tests = [
        ("test_imports", test_imports),
        ("test_dataset_structure_writing", test_dataset_structure_writing),
        ("test_dataset_structure_coding", test_dataset_structure_coding),
        ("test_writing_speed_test_evaluate_sample", test_writing_speed_test_evaluate_sample),
        ("test_coding_speed_test_evaluate_sample", test_coding_speed_test_evaluate_sample),
        ("test_quick_test_uses_mini_dataset", test_quick_test_uses_mini_dataset),
        ("test_scoring_details_included", test_scoring_details_included),
    ]

    passed = 0
    failed = 0
    for name, test_func in tests:
        try:
            test_func()
            print(f"✓ {name}")
            passed += 1
        except Exception as e:
            print(f"✗ {name}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print()
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    if failed == 0:
        print("All tests passed!")
    else:
        print("Some tests FAILED!")
        exit(1)
