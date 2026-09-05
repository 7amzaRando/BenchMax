"""Windows Job Object sandbox for restricting child process capabilities.

Uses native Windows APIs via ctypes to create isolated process groups with
resource limits, network blocking, and process creation restrictions.
"""

import ctypes
import ctypes.wintypes
import logging
import sys
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger(__name__)

# Only available on Windows
if sys.platform != "win32":
    raise ImportError("job_sandbox is Windows-only")

# Job Object limit flags
JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
JOB_OBJECT_LIMIT_JOB_TIME = 0x00000004
JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION = 0x00000400

# Information class constants (different from structure class names)
JOB_OBJECT_BASIC_LIMIT_INFO_CLASS = 1
JOB_OBJECT_EXTENDED_LIMIT_INFO_CLASS = 9
JOB_OBJECT_NET_RATE_LIMIT_INFO_CLASS = 15

# Network rate control
JOB_OBJECT_NET_RATE_CONTROL_ENABLE = 0x1

# Process creation flags
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000
CREATE_SUSPENDED = 0x00000004
CREATE_BREAKAWAY_FROM_JOB = 0x01000000

# Load Windows DLLs
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

# Set function signatures
kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
kernel32.CreateJobObjectW.restype = ctypes.c_void_p

kernel32.SetInformationJobObject.argtypes = [
    ctypes.c_void_p,    # hJob
    ctypes.c_uint32,    # JobObjectInformationClass
    ctypes.c_void_p,    # lpJobObjectInfo
    ctypes.c_uint32,    # cbJobObjectInfoLength
]
kernel32.SetInformationJobObject.restype = ctypes.c_bool

kernel32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
kernel32.AssignProcessToJobObject.restype = ctypes.c_bool

kernel32.TerminateJobObject.argtypes = [ctypes.c_void_p, ctypes.c_uint]
kernel32.TerminateJobObject.restype = ctypes.c_bool

kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
kernel32.CloseHandle.restype = ctypes.c_bool


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ('PerProcessUserTimeLimit', ctypes.c_int64),
        ('PerJobUserTimeLimit', ctypes.c_int64),
        ('LimitFlags', ctypes.c_uint32),
        ('MinimumWorkingSetSize', ctypes.c_size_t),
        ('MaximumWorkingSetSize', ctypes.c_size_t),
        ('ActiveProcessLimit', ctypes.c_uint32),
        ('Affinity', ctypes.c_size_t),
        ('PriorityClass', ctypes.c_uint32),
        ('SchedulingClass', ctypes.c_uint32),
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ('BasicLimitInformation', JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ('ProcessMemoryLimit', ctypes.c_size_t),
        ('JobMemoryLimit', ctypes.c_size_t),
        ('PeakProcessMemoryUsed', ctypes.c_size_t),
        ('PeakJobMemoryUsed', ctypes.c_size_t),
    ]


class JOBOBJECT_NET_RATE_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ('MaxBandwidth', ctypes.c_uint64),
        ('JobNetIoControl', ctypes.c_uint32),
        ('Reserved', ctypes.c_uint32),
    ]


class JobSandbox:
    """Windows Job Object sandbox for process isolation.
    
    Provides:
    - Memory limits (per-process and per-job)
    - Process count limits
    - CPU time limits
    - Network blocking via rate control
    - Job termination for cleanup
    
    Usage:
        sandbox = JobSandbox()
        sandbox.set_limits(memory_mb=256)
        sandbox.assign_process(process_handle)
        ...
        sandbox.close()
    """
    
    def __init__(self):
        self.job_handle = None
        self._create_job()
    
    def _create_job(self):
        """Create a Windows Job Object with default security."""
        self.job_handle = kernel32.CreateJobObjectW(None, None)
        if not self.job_handle:
            error = ctypes.get_last_error()
            raise OSError(f"CreateJobObjectW failed: {error}")
        logger.debug("Created Job Object handle=%s", self.job_handle)
    
    def set_limits(
        self,
        memory_mb: int = 256,
        process_count: int = 1,
        cpu_time_sec: int = 300,
        block_network: bool = True,
    ):
        """Apply restrictions to the Job Object.
        
        Args:
            memory_mb: Maximum memory per-process and per-job in MB
            process_count: Maximum number of active processes
            cpu_time_sec: Maximum CPU time per-process in seconds
            block_network: If True, block all network traffic
        """
        # Configure basic limits
        basic_info = JOBOBJECT_BASIC_LIMIT_INFORMATION()
        basic_info.LimitFlags = (
            JOB_OBJECT_LIMIT_ACTIVE_PROCESS |
            JOB_OBJECT_LIMIT_PROCESS_MEMORY |
            JOB_OBJECT_LIMIT_JOB_MEMORY |
            JOB_OBJECT_LIMIT_JOB_TIME
        )
        basic_info.ActiveProcessLimit = process_count
        basic_info.PerProcessUserTimeLimit = int(cpu_time_sec * 10_000_000)  # 100ns units
        basic_info.PerJobUserTimeLimit = int(cpu_time_sec * 10_000_000)
        basic_info.MinimumWorkingSetSize = 1 * 1024 * 1024  # 1 MB minimum
        basic_info.MaximumWorkingSetSize = memory_mb * 1024 * 1024
        basic_info.Affinity = 0  # No affinity restriction
        
        # Configure extended limits (includes memory)
        extended_info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        extended_info.BasicLimitInformation = basic_info
        extended_info.ProcessMemoryLimit = memory_mb * 1024 * 1024
        extended_info.JobMemoryLimit = memory_mb * 1024 * 1024
        
        success = kernel32.SetInformationJobObject(
            self.job_handle,
            JOB_OBJECT_EXTENDED_LIMIT_INFO_CLASS,
            ctypes.byref(extended_info),
            ctypes.sizeof(extended_info)
        )
        if not success:
            error = ctypes.get_last_error()
            logger.warning("SetInformationJobObject (limits) failed: %s", error)
        
        # Configure network rate limit (0 = block all)
        if block_network:
            net_info = JOBOBJECT_NET_RATE_LIMIT_INFORMATION()
            net_info.MaxBandwidth = 0  # Block all network
            net_info.JobNetIoControl = JOB_OBJECT_NET_RATE_CONTROL_ENABLE
            
            success = kernel32.SetInformationJobObject(
                self.job_handle,
                JOB_OBJECT_NET_RATE_LIMIT_INFO_CLASS,
                ctypes.byref(net_info),
                ctypes.sizeof(net_info)
            )
            if not success:
                error = ctypes.get_last_error()
                # Network rate control may not be available on all Windows versions
                logger.warning("Network blocking failed (error %s) — child may have network access", error)
        
        logger.info(
            "Job Object configured: memory=%dMB, processes=%d, cpu=%ds, network=%s",
            memory_mb, process_count, cpu_time_sec, "blocked" if block_network else "allowed"
        )
    
    def assign_process(self, process_handle):
        """Assign a process to this Job Object.
        
        Args:
            process_handle: Handle to the process (int or HANDLE)
        """
        if not kernel32.AssignProcessToJobObject(self.job_handle, process_handle):
            error = ctypes.get_last_error()
            # ERROR_ALREADY_IN_JOB (341) means the process is already in a job
            # This can happen if the parent process is in a job
            if error != 341:
                logger.warning("AssignProcessToJobObject failed: %s", error)
    
    def terminate(self):
        """Terminate all processes in the Job Object."""
        if self.job_handle:
            kernel32.TerminateJobObject(self.job_handle, 1)
            logger.debug("Terminated Job Object and all child processes")
    
    def close(self):
        """Close the Job Object handle."""
        if self.job_handle:
            kernel32.CloseHandle(self.job_handle)
            self.job_handle = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
