"""Shared fixtures for BenchMax tests.

Test-DB isolation: backend tests must never touch records/benchmax.db.
A session-scoped tmp SQLite file backs a patched SessionLocal; a
function-scoped autouse fixture wipes runs/results before each test.

Coverage map (which modules each test file covers):
- test_api.py ............ backend/main.py, backend/api.py (contract), sanitize_for_json
- test_run_lifecycle.py .. backend/operations.py (readiness/instantiate/params/poll/progress),
                           backend/benchmarks/base.py (live progress)
- test_scoring.py ........ backend/benchmarks/scoring.py (all scorers)
- test_benchmarks.py ..... mmlu_pro, humaneval, aime, truthfulqa, gaia, uncensor (via mocks)
- test_benchmark_sweep_fixes.py .. scoring fail-closed, mcq routing, livebench/bfcl/ifeval/mmmu/lcm/niahs guards
- test_bcb_polyglot_fixes.py .... bigcodebench, aider helpers, operations registration
- test_lcb_fixes.py ...... safe_executor livecodebench paths
- test_safe_executor.py .. backend/sandbox/safe_executor.py (INTEGRATION: real child procs)
- test_speed_test.py ..... speed_test benchmarks
- test_taubench.py ....... taubench_airline (tools, communicate match, gold replay, loop)
- test_client.py ......... backend/lm_studio/client.py (repetition, parsing, loop-switch)
- test_database.py ....... backend/database.py (models, params JSON, migrations)
- test_telemetry.py ...... backend/telemetry/monitor.py (sanitize, cache, metrics shape)
- test_bfcl_checker.py ... backend/sandbox/bfcl_checker.py (AST single/parallel/multiple)
- test_benchmark_smoke.py  all 30 benchmark registrations (dataset + evaluate_sample shape)
- test_ops_extended.py ... backend/operations.py (pause/halt/resume/delete/export/diff),
                           backend/benchmarks/base.py + multi_turn_base.py loops
"""
import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture(scope="session", autouse=True)
def _isolated_test_db(tmp_path_factory):
    """Redirect backend.database.SessionLocal to a tmp SQLite file.

    backend.main imports init_db() at import time (production DB); every
    test-time get_db() call looks up SessionLocal as a module global, so
    patching it here steers ALL backend code (api.py, operations.py,
    benchmarks) to the tmp DB without touching production code.
    """
    import backend.database as dbmod
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    tmpdir = tmp_path_factory.mktemp("benchmax_test_db")
    test_path = tmpdir / "test_benchmax.db"
    test_url = f"sqlite:///{test_path}"
    test_engine = create_engine(test_url, connect_args={"check_same_thread": False, "timeout": 15})
    dbmod.Base.metadata.create_all(bind=test_engine)
    test_session_factory = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    orig_session_local = dbmod.SessionLocal
    dbmod.SessionLocal = test_session_factory
    try:
        yield test_path
    finally:
        dbmod.SessionLocal = orig_session_local


@pytest.fixture(autouse=True)
def _clean_test_db(_isolated_test_db):
    """Wipe runs/results before each test so tests never see each other's rows."""
    import backend.database as dbmod
    sess = dbmod.SessionLocal()
    try:
        sess.query(dbmod.Result).delete()
        sess.query(dbmod.Run).delete()
        sess.commit()
    finally:
        sess.close()
    yield
    # Cleanup after too (keeps tmp DB small; no-op if already empty)
    sess = dbmod.SessionLocal()
    try:
        sess.query(dbmod.Result).delete()
        sess.query(dbmod.Run).delete()
        sess.commit()
    finally:
        sess.close()


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


@pytest.fixture
def uuid_run_ids():
    """Unique run IDs per test — avoids live-progress collisions under xdist."""
    import uuid
    return [int(uuid.uuid4().int % 10**9) for _ in range(4)]
