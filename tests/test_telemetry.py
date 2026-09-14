"""Tests for backend/telemetry/monitor.py — sanitize, shape, cache (all mocked, no hardware)."""
from unittest.mock import patch


class TestSanitizeFloat:
    def test_nan_inf_none(self):
        from backend.telemetry.monitor import _sanitize_float
        assert _sanitize_float(float("nan")) == 0.0
        assert _sanitize_float(float("inf")) == 0.0
        assert _sanitize_float(float("-inf")) == 0.0
        assert _sanitize_float(None) == 0.0
        assert _sanitize_float("bad") == 0.0
        assert _sanitize_float(12.5) == 12.5

    def test_all_floats_finite(self):
        import math
        from backend.telemetry import monitor
        from backend.telemetry.monitor import get_system_metrics
        monitor._telemetry_cache = {}
        with patch("backend.telemetry.monitor.psutil") as ps:
            ps.cpu_percent.return_value = 10.0
            ps.virtual_memory.return_value = type("V", (), {
                "used": 4 * 2**30, "total": 16 * 2**30, "percent": 25.0})()
            with patch("backend.telemetry.monitor._get_gpu_counters_typeperf", return_value={}), \
                 patch("backend.telemetry.monitor._get_vram_total_from_registry", return_value=0):
                m = get_system_metrics()
        for k, v in m.items():
            if isinstance(v, float):
                assert math.isfinite(v), k


class TestMetricsShape:
    def test_expected_keys(self):
        from backend.telemetry import monitor
        from backend.telemetry.monitor import get_system_metrics
        monitor._telemetry_cache = {}
        with patch("backend.telemetry.monitor.psutil") as ps:
            ps.cpu_percent.return_value = 5.0
            ps.virtual_memory.return_value = type("V", (), {
                "used": 2 * 2**30, "total": 8 * 2**30, "percent": 25.0})()
            with patch("backend.telemetry.monitor._get_gpu_counters_typeperf", return_value={}), \
                 patch("backend.telemetry.monitor._get_vram_total_from_registry", return_value=0):
                m = get_system_metrics()
        for key in ("cpu_percent", "ram_used_gb", "ram_total_gb", "ram_percent",
                    "gpu_available", "gpu_name", "gpu_load",
                    "vram_total_mb", "vram_used_mb", "vram_percent"):
            assert key in m, key


class TestCache:
    def test_returns_copy_not_reference(self):
        from backend.telemetry import monitor
        monitor._telemetry_cache = {}
        with patch.object(monitor, "psutil") as ps:
            ps.cpu_percent.return_value = 1.0
            ps.virtual_memory.return_value = type("V", (), {
                "used": 1 * 2**30, "total": 8 * 2**30, "percent": 12.5})()
            with patch.object(monitor, "_get_gpu_counters_typeperf", return_value={}), \
                 patch.object(monitor, "_get_vram_total_from_registry", return_value=0):
                a = monitor.get_system_metrics()
                b = monitor.get_system_metrics()
        assert a == b
        assert a is not b
