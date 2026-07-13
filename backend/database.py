import os
import sys
import logging
from pathlib import Path
from datetime import datetime
import json
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

logger = logging.getLogger(__name__)

# In PyInstaller .exe builds, the DB must live next to the exe (persistent),
# not inside the temp _MEIPASS directory which is wiped on exit.
if getattr(sys, 'frozen', False):
    ROOT = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / 'BenchMax'
else:
    ROOT = Path(__file__).parent.parent
os.makedirs(ROOT / "records", exist_ok=True)

# Absolute database path — works regardless of CWD
DATABASE_URL = f"sqlite:///{ROOT / 'records' / 'benchmax.db'}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False, "timeout": 15})
# Enable WAL mode for concurrent read/write from multiple threads
with engine.raw_connection() as conn:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.commit()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Run(Base):
    __tablename__ = "runs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    model_name = Column(String, nullable=False)
    benchmark_name = Column(String, nullable=False)
    status = Column(String, default="PENDING")  # PENDING, RUNNING, PAUSED, COMPLETED, FAILED, HALTED
    current_index = Column(Integer, default=0)
    total_samples = Column(Integer, default=0)
    parameters = Column(Text, nullable=True)  # Store JSON representation of params
    batch_id = Column(String, nullable=True)  # UUID grouping runs in a batch
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to results
    results = relationship("Result", back_populates="run", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_runs_status", "status"),
        Index("ix_runs_batch_id", "batch_id"),
    )

    def get_parameters(self):
        if self.parameters:
            try:
                return json.loads(self.parameters)
            except Exception:
                logger.warning("Failed to parse run parameters JSON", exc_info=True)
                return {}
        return {}

    def set_parameters(self, params_dict):
        self.parameters = json.dumps(params_dict)

class Result(Base):
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
    scoring_details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    run = relationship("Run", back_populates="results")

    __table_args__ = (
        Index("ix_results_run_id", "run_id"),
        Index("ix_results_task_id", "task_id"),
    )

def init_db():
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



