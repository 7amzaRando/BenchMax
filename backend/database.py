import os
import logging
from datetime import datetime
import json
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from contextlib import contextmanager

from backend.config import ROOT

logger = logging.getLogger(__name__)

# Absolute database path — works regardless of CWD
DATABASE_URL = f"sqlite:///{ROOT / 'records' / 'benchmax.db'}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False, "timeout": 15})
# Enable WAL mode for concurrent read/write from multiple threads
from sqlalchemy import text as _sa_text_wal  # noqa: E402
with engine.connect() as conn:
    conn.execute(_sa_text_wal("PRAGMA journal_mode=WAL"))
    conn.execute(_sa_text_wal("PRAGMA synchronous=NORMAL"))
    conn.commit()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

@contextmanager
def get_db():
    """Context manager for database sessions — ensures cleanup on exception paths."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class Run(Base):
    """Represents a single benchmark run.

    Lifecycle: PENDING → RUNNING → PAUSED → RUNNING → COMPLETED | FAILED | HALTED

    Columns:
        id: Auto-incrementing primary key.
        model_name: Model identifier (e.g. "deepseek-r1-distill-qwen-7b").
        benchmark_name: Benchmark name (e.g. "HumanEval", "MMLU-Pro").
        status: Current run state — one of PENDING, RUNNING, PAUSED, COMPLETED, FAILED, HALTED.
        current_index: Index of the next sample to process (enables resume from exact position).
        total_samples: Total number of samples in the dataset (set when dataset loads).
        parameters: JSON string of run configuration (temperature, max_tokens, system_prompt, etc.).
        batch_id: Optional UUID grouping runs in a batch.
        notes: Optional user annotations (e.g. "temp=1, presence_penalty 1.1").
        created_at: UTC timestamp when the run was created.
        updated_at: UTC timestamp of last modification.
    """
    __tablename__ = "runs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    model_name = Column(String, nullable=False)
    benchmark_name = Column(String, nullable=False)
    status = Column(String, default="PENDING")  # PENDING, RUNNING, PAUSED, COMPLETED, FAILED, HALTED
    current_index = Column(Integer, default=0)
    total_samples = Column(Integer, default=0)
    parameters = Column(Text, nullable=True)  # Store JSON representation of params
    batch_id = Column(String, nullable=True)  # UUID grouping runs in a batch
    notes = Column(Text, nullable=True)  # User annotations (e.g., "temp=1, presence_penalty 1.1")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to results
    results = relationship("Result", back_populates="run", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_runs_status", "status"),
        Index("ix_runs_batch_id", "batch_id"),
    )

    def get_parameters(self):
        """Deserialize the parameters JSON column into a dict.

        Returns:
            Dict of run parameters, or empty dict if None or malformed.
        """
        if self.parameters:
            try:
                return json.loads(self.parameters)
            except Exception:
                logger.warning("Failed to parse run parameters JSON", exc_info=True)
                return {}
        return {}

    def set_parameters(self, params_dict):
        """Serialize a dict to JSON and store it in the parameters column.

        Args:
            params_dict: Run configuration dictionary to persist.
        """
        self.parameters = json.dumps(params_dict)

class Result(Base):
    """Stores the outcome of evaluating a single sample within a run.

    Each Result row captures the model's response, whether it was correct,
    and timing/token telemetry for that sample.

    Columns:
        id: Auto-incrementing primary key.
        run_id: Foreign key to the parent Run.
        task_id: Sample identifier (e.g. "HumanEval/0").
        prompt: The full prompt sent to the model.
        raw_response: The model's raw output.
        extracted_code: The parsed/extracted code or answer from the response.
        correct: Whether the sample was scored as correct.
        error_message: Execution error or timeout message (if any).
        elapsed_time: Wall-clock time for generation in seconds.
        tps: Tokens per second during generation.
        ttft: Time to first token in seconds.
        thinking_tokens: Number of reasoning/thinking tokens (if tracked).
        response_tokens: Number of answer tokens.
        prompt_tokens: Number of input tokens.
        scoring_details: JSON string with extra scoring fields (e.g. server_match, ast_score).
        created_at: UTC timestamp when the result was recorded.
    """
    __tablename__ = "results"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("runs.id"), nullable=False)
    task_id = Column(String, nullable=False)
    prompt = Column(Text, nullable=True)
    raw_response = Column(Text, nullable=True)
    extracted_code = Column(Text, nullable=True)
    correct = Column(Boolean, default=False)
    error_message = Column(Text, nullable=True)
    elapsed_time = Column(Float, default=0.0)
    tps = Column(Float, default=0.0)
    ttft = Column(Float, default=0.0)
    thinking_tokens = Column(Integer, default=0)
    response_tokens = Column(Integer, default=0)
    prompt_tokens = Column(Integer, default=0)
    scoring_details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    run = relationship("Run", back_populates="results")

    __table_args__ = (
        Index("ix_results_run_id", "run_id"),
        Index("ix_results_task_id", "task_id"),
    )

def init_db():
    """Create all tables and run any pending schema migrations.

    Uses SQLAlchemy create_all() for initial table creation, then applies
    incremental ALTER TABLE migrations for columns added after the initial
    schema (batch_id, scoring_details, updated_at, prompt_tokens, notes).
    Each migration is idempotent — safe to run on every startup.
    """
    os.makedirs(ROOT / "records", exist_ok=True)
    Base.metadata.create_all(bind=engine)
    # Migration: add batch_id column if missing (added after initial schema creation)
    try:
        from sqlalchemy import text as sa_text
        with engine.connect() as conn:
            # Check if column exists
            result = conn.execute(sa_text(
                "SELECT COUNT(*) AS cnt FROM pragma_table_info('runs') WHERE name='batch_id'"
            )).fetchone()
            if result and result[0] == 0:
                conn.execute(sa_text("ALTER TABLE runs ADD COLUMN batch_id VARCHAR"))
                conn.commit()
    except Exception as mig_err:
        logger.warning(f"Migration note (non-fatal): {mig_err}")
    # Migration: add scoring_details column if missing
    try:
        from sqlalchemy import text as sa_text
        with engine.connect() as conn:
            result = conn.execute(sa_text(
                "SELECT COUNT(*) AS cnt FROM pragma_table_info('results') WHERE name='scoring_details'"
            )).fetchone()
            if result and result[0] == 0:
                conn.execute(sa_text("ALTER TABLE results ADD COLUMN scoring_details TEXT"))
                conn.commit()
    except Exception as mig_err:
        logger.warning(f"Migration note (non-fatal): {mig_err}")
    # Migration: add updated_at column if missing
    try:
        from sqlalchemy import text as sa_text
        with engine.connect() as conn:
            result = conn.execute(sa_text(
                "SELECT COUNT(*) AS cnt FROM pragma_table_info('runs') WHERE name='updated_at'"
            )).fetchone()
            if result and result[0] == 0:
                conn.execute(sa_text("ALTER TABLE runs ADD COLUMN updated_at DATETIME"))
                conn.commit()
    except Exception as mig_err:
        logger.warning(f"Migration note (non-fatal): {mig_err}")
    # Migration: add prompt_tokens column if missing
    try:
        from sqlalchemy import text as sa_text
        with engine.connect() as conn:
            result = conn.execute(sa_text(
                "SELECT COUNT(*) AS cnt FROM pragma_table_info('results') WHERE name='prompt_tokens'"
            )).fetchone()
            if result and result[0] == 0:
                conn.execute(sa_text("ALTER TABLE results ADD COLUMN prompt_tokens INTEGER DEFAULT 0"))
                conn.commit()
    except Exception as mig_err:
        logger.warning(f"Migration note (non-fatal): {mig_err}")
    # Migration: add notes column to runs if missing
    try:
        from sqlalchemy import text as sa_text
        with engine.connect() as conn:
            result = conn.execute(sa_text(
                "SELECT COUNT(*) AS cnt FROM pragma_table_info('runs') WHERE name='notes'"
            )).fetchone()
            if result and result[0] == 0:
                conn.execute(sa_text("ALTER TABLE runs ADD COLUMN notes TEXT"))
                conn.commit()
    except Exception as mig_err:
        logger.warning(f"Migration note (non-fatal): {mig_err}")



