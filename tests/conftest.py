"""Shared fixtures for BenchMax tests."""
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _preserve_docker_config():
    """Preserve the real Docker configuration for tests.

    Code-execution benchmarks (HumanEval, BigCodeBench, LiveCodeBench,
    Aider Polyglot) require Docker. Tests that exercise the
    sandbox must use the real Docker path.
    """
    yield


@pytest.fixture
def mock_client():
    """A mock LMStudioClient that returns a canned generation response."""
    client = MagicMock()
    client.generate_completion = AsyncMock(return_value={
        "model_name": "test-model",
        "raw_response": "The answer is B.",
        "thinking_content": "",
        "answer_content": "The answer is B.",
        "elapsed_time": 1.5,
        "ttft": 0.3,
        "tps": 50.0,
        "prompt_tokens": 100,
        "response_tokens": 20,
        "thinking_tokens": 0,
        "answer_tokens": 20,
        "stream_timed_out": False,
    })
    client._rep_disabled = False
    client._repetition_detected = False
    return client


@pytest.fixture
def mock_db():
    """A mock SQLAlchemy session."""
    db = MagicMock()
    run = MagicMock()
    run.id = 1
    run.status = "PENDING"
    run.model_name = "test-model"
    run.benchmark_name = "TestBenchmark"
    run.current_index = 0
    run.total_samples = 5
    run.get_parameters = MagicMock(return_value={
        "temperature": 0.0,
        "max_completion_tokens": 2048,
        "system_prompt": "",
        "api_key": "",
        "quick_test": True,
    })
    run.set_parameters = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = run
    db.query.return_value.filter.return_value.all.return_value = []
    return db


@pytest.fixture
def sample_dataset():
    """A minimal dataset for testing."""
    return [
        {"task_id": "test/0", "prompt": "What is 2+2?", "answer": "4", "category": "math"},
        {"task_id": "test/1", "prompt": "What is 3+3?", "answer": "6", "category": "math"},
    ]


@pytest.fixture
def tmp_dir():
    """A temporary directory that is cleaned up after the test."""
    d = tempfile.mkdtemp(prefix="benchmax_test_")
    yield d
    import shutil
    shutil.rmtree(d, ignore_errors=True)
