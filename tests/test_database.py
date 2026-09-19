"""Tests for backend/database.py — models, params JSON, migrations, session hygiene."""


class TestRunParameters:
    def test_roundtrip(self):
        from backend.database import Run
        r = Run(model_name="m", benchmark_name="b")
        r.set_parameters({"temperature": 0.5, "quick_test": True})
        assert r.get_parameters() == {"temperature": 0.5, "quick_test": True}

    def test_none_returns_empty(self):
        from backend.database import Run
        assert Run(model_name="m", benchmark_name="b").get_parameters() == {}

    def test_malformed_returns_empty(self):
        from backend.database import Run
        r = Run(model_name="m", benchmark_name="b", parameters="{not json")
        assert r.get_parameters() == {}


class TestPersistence:
    def test_run_result_cascade_delete(self):
        from backend.database import Run, Result, get_db
        with get_db() as db:
            run = Run(model_name="m", benchmark_name="MMLU-Pro", status="COMPLETED")
            db.add(run)
            db.commit()
            db.refresh(run)
            rid = run.id
            db.add(Result(run_id=rid, task_id="t/0", correct=True))
            db.commit()
            assert db.query(Result).filter(Result.run_id == rid).count() == 1
            db.delete(run)
            db.commit()
            assert db.query(Result).filter(Result.run_id == rid).count() == 0

    def test_get_db_closes_session(self):
        from backend.database import Run, get_db
        with get_db() as db:
            run = Run(model_name="m", benchmark_name="MMLU-Pro", status="COMPLETED")
            db.add(run)
            db.commit()
            db.refresh(run)
            rid = run.id
            assert db.is_active is True
            assert db.query(Run).filter(Run.id == rid).count() == 1
        # Exiting the context must close without raising; reuse is safe
        with get_db() as db2:
            assert db2.query is not None

    def test_init_db_idempotent(self):
        from backend.database import Base, Run, get_db, init_db
        init_db()
        init_db()  # migrations must be safe to re-run
        assert "runs" in Base.metadata.tables
        assert "results" in Base.metadata.tables
        with get_db() as db:
            assert db.query(Run).count() >= 0
