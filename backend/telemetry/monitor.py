import logging
import time
import psutil
import subprocess
import shutil
import platform

logger = logging.getLogger(__name__)

# winreg is Windows-only standard library for registry access
try:
    import winreg
    WINREG_AVAILABLE = True
except ImportError:
    WINREG_AVAILABLE = False

# Try to import GPUtil. If it fails, we fall back gracefully.
GPUTIL_AVAILABLE = False
try:
    import GPUtil
    GPUTIL_AVAILABLE = True
except ImportError:
    logger.warning("GPUtil module not available. GPU monitoring will be disabled or mocked.")

# Telemetry cache to avoid expensive GPU counter queries every call
_telemetry_cache: dict = {}
_telemetry_cache_ttl = 2.0  # seconds


def _get_gpu_counters_typeperf() -> dict:
    """
    Reads real-time GPU metrics via typeperf (fast, no PowerShell overhead).
    Works on Windows 10+ for AMD, NVIDIA, and Intel GPUs.
    Runs in ~0.3-0.5s vs ~1.7s for Get-Counter.
    Returns dict with gpu_load, vram_used_mb, or empty dict.
    """
    result = {}

    # --- GPU utilization ---
    try:
        cmd = ["typeperf", "-sc", "1", "-si", "0", r"\GPU Engine(*)\Utilization Percentage"]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=6.0)
        if r.returncode == 0 and r.stdout.strip():
            lines = r.stdout.strip().splitlines()
            if len(lines) >= 2:
                data_line = lines[1]
                parts = data_line.split('","')
                vals = []
                for p in parts:
                    clean = p.strip('"')
                    try:
                        vals.append(abs(float(clean)))
                    except ValueError:
                        pass
                # Max utilization across all engines (3D, Copy, Compute, etc.)
                if vals:
                    result["gpu_load"] = round(max(vals), 1)
    except Exception as e:
        logger.debug(f"typeperf GPU load failed: {e}")

    # --- VRAM usage ---
    try:
        cmd = ["typeperf", "-sc", "1", "-si", "0", r"\GPU Adapter Memory(*)\Dedicated Usage"]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=6.0)
        if r.returncode == 0 and r.stdout.strip():
            lines = r.stdout.strip().splitlines()
            if len(lines) >= 2:
                data_line = lines[1]
                parts = data_line.split('","')
                for p in parts:
                    clean = p.strip('"')
                    try:
                        v = float(clean)
                        if v > 0:
                            result["vram_used_mb"] = round(v / (1024 * 1024), 0)
                            break
                    except ValueError:
                        pass
    except Exception as e:
        logger.debug(f"typeperf VRAM failed: {e}")

    return result


def _get_vram_total_from_registry(gpu_name: str) -> int | None:
    """Read VRAM total from driver registry key.

    WMI Win32_VideoController.AdapterRAM is a UInt32, capped at ~4 GB.
    The driver registry key 'HardwareInformation.qwMemorySize' is a QWORD (64-bit)
    and correctly reports VRAM for >4 GB cards (AMD, NVIDIA, Intel).
    """
    if not WINREG_AVAILABLE:
        return None
    try:
        base_path = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base_path) as base_key:
            i = 0
            while True:
                try:
                    sub_key_name = winreg.EnumKey(base_key, i)
                    i += 1
                    try:
                        with winreg.OpenKey(base_key, sub_key_name) as sub_key:
                            driver_desc = winreg.QueryValueEx(sub_key, "DriverDesc")[0]
                            if gpu_name.upper() in driver_desc.upper() or driver_desc.upper() in gpu_name.upper():
                                vram = winreg.QueryValueEx(sub_key, "HardwareInformation.qwMemorySize")[0]
                                if isinstance(vram, int) and vram > 0:
                                    return vram
                    except (FileNotFoundError, OSError):
                        continue
                except OSError:
                    break
    except Exception:
        pass
    return None


def _get_wmi_gpu_static() -> dict:
    """
    Gets static GPU info via WMI Win32_VideoController.
    Returns GPU name and VRAM total. Works for all vendors.
    WMI /format:csv returns columns in order: Node,AdapterRAM,Name

    Note: WMI AdapterRAM is a UInt32 (max ~4 GB). For >4 GB cards,
    the driver registry fallback in _get_vram_total_from_registry is used.
    
    If wmic is unavailable, falls back to reading GPU name from registry DriverDesc.
    """
    result = {}
    try:
        res = subprocess.run(
            ["wmic", "path", "Win32_VideoController", "get", "Name,AdapterRAM", "/format:csv"],
            capture_output=True, text=True, timeout=3.0
        )
        if res.returncode == 0:
            for line in res.stdout.strip().splitlines():
                line = line.strip()
                if not line or "Node" in line:
                    continue
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 3:
                    name = parts[2]
                    if any(kw in name.upper() for kw in ["AMD", "RADEON", "RX ", "NVIDIA", "GEFORCE", "QUADRO", "INTEL", "ARC"]):
                        result["gpu_name"] = name
                        # Prefer registry key (supports >4 GB, unlike WMI AdapterRAM UInt32)
                        vram_bytes = _get_vram_total_from_registry(name)
                        if vram_bytes is not None:
                            result["vram_total_mb"] = round(vram_bytes / (1024 * 1024), 0)
                        else:
                            vram_str = parts[1]
                            if vram_str.isdigit():
                                result["vram_total_mb"] = round(int(vram_str) / (1024 * 1024), 0)
                        break
    except Exception as e:
        logger.debug(f"WMI static GPU query failed: {e}")

    # Fallback: if wmic is unavailable, try registry to get GPU name
    if not result.get("gpu_name") and WINREG_AVAILABLE:
        try:
            base_path = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base_path) as key_handle:
                for i in range(10):
                    try:
                        sub_key_name = winreg.EnumKey(key_handle, i)
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{base_path}\\{sub_key_name}") as key:
                            driver_desc = winreg.QueryValueEx(key, "DriverDesc")[0]
                            if any(kw in driver_desc.upper() for kw in ["AMD", "RADEON", "RX ", "NVIDIA", "GEFORCE", "QUADRO", "INTEL", "ARC"]):
                                result["gpu_name"] = driver_desc
                                # Get VRAM from registry (supports >4 GB)
                                vram_bytes = winreg.QueryValueEx(key, "HardwareInformation.qwMemorySize")[0]
                                if isinstance(vram_bytes, int) and vram_bytes > 0:
                                    result["vram_total_mb"] = round(vram_bytes / (1024 * 1024), 0)
                                break
                    except (FileNotFoundError, OSError):
                        continue
        except Exception as e:
            logger.debug(f"Registry GPU name fallback failed: {e}")

    return result


def _gather_system_metrics_fresh() -> dict:
    """Internal: collects fresh system metrics without cache."""
    metrics = {
        "cpu_percent": 0.0,
        "ram_total_gb": 0.0,
        "ram_used_gb": 0.0,
        "ram_percent": 0.0,
        "gpu_available": False,
        "gpu_name": None,
        "vram_total_mb": 0.0,
        "vram_used_mb": 0.0,
        "vram_percent": 0.0,
        "cpu_load": 0.0,
        "gpu_load": 0.0,
    }

    # 1. CPU and System RAM (these are cheap)
    try:
        metrics["cpu_percent"] = psutil.cpu_percent(interval=None)
        vm = psutil.virtual_memory()
        metrics["ram_total_gb"] = round(vm.total / (1024 ** 3), 2)
        metrics["ram_used_gb"] = round(vm.used / (1024 ** 3), 2)
        metrics["ram_percent"] = vm.percent
    except Exception as e:
        logger.error(f"Error gathering CPU/RAM telemetry: {e}")

    # 2. GPU via GPUtil (cheap — local library call)
    gpu_list = []
    if GPUTIL_AVAILABLE:
        try:
            gpu_list = GPUtil.getGPUs()
        except Exception as e:
            logger.debug(f"GPUtil.getGPUs() failed (expected if no NVIDIA GPU is active): {e}")

    if gpu_list:
        try:
            gpu = gpu_list[0]
            metrics["gpu_available"] = True
            metrics["gpu_name"] = gpu.name
            metrics["gpu_load"] = round(gpu.load * 100, 1)
            metrics["vram_total_mb"] = gpu.memoryTotal
            metrics["vram_used_mb"] = gpu.memoryUsed
            metrics["vram_percent"] = min(round(gpu.memoryUtil * 100, 1), 100.0) if gpu.memoryTotal > 0 else 0.0
            return metrics
        except Exception as e:
            logger.error(f"Error reading GPUtil data: {e}")

    # 3. Fallback: nvidia-smi (subprocess — medium cost)
    if not metrics["gpu_available"] and shutil.which("nvidia-smi"):
        try:
            cmd = ["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.total,memory.used", "--format=json"]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=2.0)
            if res.returncode == 0 and res.stdout.strip():
                import json as _json
                info = _json.loads(res.stdout.strip())
                gpus = info.get("gpus", [])
                if gpus:
                    gpu = gpus[0]
                    metrics["gpu_available"] = True
                    metrics["gpu_name"] = gpu.get("name", "")
                    metrics["gpu_load"] = float(str(gpu.get("utilization.gpu", "0")).split()[0])
                    metrics["vram_total_mb"] = float(str(gpu.get("memory.total", "0")).split()[0])
                    metrics["vram_used_mb"] = float(str(gpu.get("memory.used", "0")).split()[0])
                    metrics["vram_percent"] = min(round((metrics["vram_used_mb"] / metrics["vram_total_mb"]) * 100, 1), 100.0) if metrics["vram_total_mb"] > 0 else 0.0
                    return metrics
        except Exception as e:
            logger.debug(f"Direct nvidia-smi query fallback failed: {e}")

    # 4. Fallback: AMD/Intel via WMI + PowerShell (expensive — cached separately)
    if not metrics["gpu_available"] and platform.system() == "Windows":
        wmi_info = _get_wmi_gpu_static()
        if wmi_info.get("gpu_name"):
            metrics["gpu_available"] = True
            metrics["gpu_name"] = wmi_info["gpu_name"]
            if "vram_total_mb" in wmi_info:
                metrics["vram_total_mb"] = wmi_info["vram_total_mb"]

        if metrics["gpu_available"]:
            counters = _get_gpu_counters_typeperf()
            if "gpu_load" in counters:
                metrics["gpu_load"] = counters["gpu_load"]
            if "vram_used_mb" in counters:
                metrics["vram_used_mb"] = counters["vram_used_mb"]
                if metrics["vram_total_mb"] > 0:
                    metrics["vram_percent"] = min(
                        round((metrics["vram_used_mb"] / metrics["vram_total_mb"]) * 100, 1),
                        100.0
                    )

    return metrics


def get_system_metrics() -> dict:
    """
    Returns system metrics with a short-lived cache to avoid spawning
    expensive subprocesses (PowerShell, nvidia-smi) on every call.
    CPU and RAM are always fresh (cheap); GPU metrics are cached for TTL seconds.
    """
    global _telemetry_cache
    now = time.time()
    cached = _telemetry_cache.get("last_result")
    cached_at = _telemetry_cache.get("cached_at", 0)
    if cached and (now - cached_at) < _telemetry_cache_ttl:
        # Update cheap CPU/RAM values even from cache, but skip expensive GPU
        try:
            cached["cpu_percent"] = psutil.cpu_percent(interval=None)
            vm = psutil.virtual_memory()
            cached["ram_total_gb"] = round(vm.total / (1024 ** 3), 2)
            cached["ram_used_gb"] = round(vm.used / (1024 ** 3), 2)
            cached["ram_percent"] = vm.percent
        except Exception:
            pass
        return cached

    fresh = _gather_system_metrics_fresh()
    _telemetry_cache = {"last_result": fresh, "cached_at": now}
    return fresh
