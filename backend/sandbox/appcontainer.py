"""Windows AppContainer sandbox for code execution isolation.

Uses Windows AppContainer (SID S-1-15-2-*) for native process isolation.
AppContainer provides OS-level security: deny-by-default filesystem,
network, registry, and process access. Only explicitly granted resources
are accessible.

Architecture:
    1. Create (or reuse) an AppContainer profile via userenv.dll.
    2. Set filesystem ACLs via icacls.exe for granted directories.
    3. Build SECURITY_CAPABILITIES with optional capability SIDs.
    4. Launch python.exe inside the AppContainer via CreateProcessW.
    5. Capture stdout/stderr via pipes, parse JSON result.
    6. Clean up profile and SID memory in finally block.

Requirements:
    - Windows 8+ (all editions including Home)
    - No external dependencies (pure ctypes + system icacls.exe)
"""

import ctypes
import ctypes.wintypes
import json
import logging
import os
import secrets
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

if sys.platform != "win32":
    raise ImportError("appcontainer is Windows-only")

# ---------------------------------------------------------------------------
# Win32 DLL bindings
# ---------------------------------------------------------------------------
userenv = ctypes.WinDLL("userenv", use_last_error=True)
advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# ---------------------------------------------------------------------------
# Win32 constants
# ---------------------------------------------------------------------------
PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES = 0x00020009  # 131081
EXTENDED_STARTUPINFO_PRESENT = 0x00080000
SE_GROUP_ENABLED = 0x00000004
INFINITE = 0xFFFFFFFF

# ACL constants
SET_ACCESS = 0
SUB_CONTAINERS_AND_OBJECTS_INHERIT = 0x00000003
GRANT_ACCESS = 0x00000002
FILE_GENERIC_READ = 0x00120089
FILE_GENERIC_WRITE = 0x00120116
FILE_ALL_ACCESS = 0x001F01FF

# Trustee constants
TRUSTEE_IS_SID = 0
TRUSTEE_IS_USER = 1

# HRESULT error codes
HRESULT_FROM_WIN32 = lambda x: x  # simplified for error checking
ERROR_ALREADY_EXISTS = 183

# Process creation flags
CREATE_NO_WINDOW = 0x08000000
STARTF_USESTDHANDLES = 0x00000100

# ---------------------------------------------------------------------------
# ctypes structures
# ---------------------------------------------------------------------------

class SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("Sid", ctypes.c_void_p),
        ("Attributes", ctypes.c_ulong),
    ]


class SECURITY_CAPABILITIES(ctypes.Structure):
    _fields_ = [
        ("AppContainerSid", ctypes.c_void_p),
        ("Capabilities", ctypes.POINTER(SID_AND_ATTRIBUTES)),
        ("CapabilityCount", ctypes.c_ulong),
        ("Reserved", ctypes.c_ulong),
    ]


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_ulong),
        ("lpReserved", ctypes.c_void_p),
        ("lpDesktop", ctypes.c_void_p),
        ("lpTitle", ctypes.c_void_p),
        ("dwX", ctypes.c_ulong),
        ("dwY", ctypes.c_ulong),
        ("dwXSize", ctypes.c_ulong),
        ("dwYSize", ctypes.c_ulong),
        ("dwXCountChars", ctypes.c_ulong),
        ("dwYCountChars", ctypes.c_ulong),
        ("dwFillAttribute", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("wShowWindow", ctypes.c_ushort),
        ("cbReserved2", ctypes.c_ushort),
        ("lpReserved2", ctypes.c_void_p),
        ("hStdInput", ctypes.c_void_p),
        ("hStdOutput", ctypes.c_void_p),
        ("hStdError", ctypes.c_void_p),
    ]


class STARTUPINFOEXW(ctypes.Structure):
    _fields_ = [
        ("StartupInfo", STARTUPINFOW),
        ("lpAttributeList", ctypes.c_void_p),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", ctypes.c_void_p),
        ("hThread", ctypes.c_void_p),
        ("dwProcessId", ctypes.c_ulong),
        ("dwThreadId", ctypes.c_ulong),
    ]


# ---------------------------------------------------------------------------
# Helper: SID → string
# ---------------------------------------------------------------------------

def _sid_to_string(sid_ptr: ctypes.c_void_p) -> str:
    """Convert a SID pointer to its string representation (S-1-15-2-...)."""
    sid_str = ctypes.c_wchar_p()
    if not advapi32.ConvertSidToStringSidW(sid_ptr, ctypes.byref(sid_str)):
        error = ctypes.get_last_error()
        raise OSError(f"ConvertSidToStringSidW failed: {error}")
    result = sid_str.value
    kernel32.LocalFree(sid_str)
    return result


# ---------------------------------------------------------------------------
# Helper: run icacls
# ---------------------------------------------------------------------------

def _run_icacls(args: list) -> bool:
    """Run icacls.exe with given arguments. Returns True on success."""
    try:
        cmd = ["icacls"] + args
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10,
            creationflags=CREATE_NO_WINDOW,
        )
        if result.returncode != 0:
            logger.warning("icacls %s failed: %s", args[0] if args else "", result.stderr.strip())
            return False
        return True
    except Exception as e:
        logger.warning("icacls execution error: %s", e)
        return False


# ---------------------------------------------------------------------------
# AppContainerSandbox
# ---------------------------------------------------------------------------

class AppContainerSandbox:
    """Windows AppContainer sandbox for process isolation.

    Usage:
        sbx = AppContainerSandbox("benchmax_run1", fs_read_write=["/tmp/bm_xxx"])
        sbx.setup()
        result = sbx.launch(sys.executable, "script.py", timeout=60)
        sbx.cleanup()
    """

    def __init__(self, name: str, capabilities: Optional[List[str]] = None,
                 fs_read: Optional[List[str]] = None,
                 fs_read_write: Optional[List[str]] = None):
        """Create an AppContainer sandbox.

        Args:
            name: Profile name (max 64 chars, alphanumeric + _-.).
            capabilities: Capability names to grant (e.g. ["internetClient"]).
            fs_read: Directories to grant read-only access.
            fs_read_write: Directories to grant read/write access.
        """
        self._name = name
        self._capabilities = capabilities or []
        self._fs_read = fs_read or []
        self._fs_read_write = fs_read_write or []
        self._sid = None
        self._sid_str = None
        self._cap_sids = []        # track for LocalFree
        self._cap_attrs = None     # ctypes array for SECURITY_CAPABILITIES
        self._attr_list = None     # PROC_THREAD_ATTRIBUTE_LIST
        self._setup_done = False

    def setup(self):
        """Create profile, derive SIDs, apply ACLs, build attribute list."""
        if self._setup_done:
            return

        # 1. Create or reuse profile → Package SID
        self._create_profile()

        # 2. Derive capability SIDs
        cap_attrs, cap_count = self._derive_capability_sids(self._capabilities)

        # 3. Apply filesystem ACLs
        self._apply_fs_acls()

        # 4. Build attribute list
        self._attr_list = self._build_attribute_list(cap_attrs, cap_count)

        self._setup_done = True

    def _create_profile(self):
        """Create AppContainer profile, return Package SID."""
        sid_ptr = ctypes.c_void_p()

        # Try creating new profile
        hr = userenv.CreateAppContainerProfile(
            self._name,                    # pszAppContainerName
            self._name,                    # pszDisplayName
            "BenchMax sandbox",            # pszDescription
            None,                          # pCapabilities
            0,                             # dwCapabilityCount
            ctypes.byref(sid_ptr),         # ppSidAppContainerSid
        )

        if hr == 0:  # S_OK
            self._sid = sid_ptr
            self._sid_str = _sid_to_string(sid_ptr)
            logger.debug("Created AppContainer profile '%s' → %s", self._name, self._sid_str)
            return

        if ctypes.get_last_error() == ERROR_ALREADY_EXISTS or hr == -2147024713:  # ERROR_ALREADY_EXISTS as HRESULT
            # Profile exists — derive SID from name
            hr2 = userenv.DeriveAppContainerSidFromAppContainerName(
                self._name, ctypes.byref(sid_ptr)
            )
            if hr2 < 0:
                raise OSError(f"DeriveAppContainerSidFromAppContainerName('{self._name}') failed: 0x{hr2:08x}")
            self._sid = sid_ptr
            self._sid_str = _sid_to_string(sid_ptr)
            logger.debug("Reused AppContainer profile '%s' → %s", self._name, self._sid_str)
            return

        raise OSError(f"CreateAppContainerProfile('{self._name}') failed: 0x{hr:08x}")

    def _derive_capability_sids(self, cap_names: List[str]):
        """Derive capability SIDs from names like 'internetClient'."""
        if not cap_names:
            return None, 0

        cap_attrs = (SID_AND_ATTRIBUTES * len(cap_names))()
        for i, name in enumerate(cap_names):
            sid_ptr = ctypes.c_void_p()
            hr = advapi32.DeriveCapabilitySidsFromName(
                name, ctypes.byref(sid_ptr)
            )
            if hr < 0:
                raise OSError(f"DeriveCapabilitySidsFromName('{name}') failed: 0x{hr:08x}")
            cap_attrs[i].Sid = sid_ptr
            cap_attrs[i].Attributes = SE_GROUP_ENABLED
            self._cap_sids.append(sid_ptr)
            logger.debug("Derived capability SID for '%s'", name)

        return cap_attrs, len(cap_names)

    def _apply_fs_acls(self):
        """Grant filesystem ACLs to the AppContainer SID using icacls."""
        if not self._sid_str:
            return

        # Grant read/write to specified directories
        for path in self._fs_read_write:
            _run_icacls([path, "/grant", f"*{self._sid_str}:(OI)(CI)(F)"])

        # Grant read-only to specified directories
        for path in self._fs_read:
            _run_icacls([path, "/grant", f"*{self._sid_str}:(OI)(CI)(RX)"])

    def _build_attribute_list(self, cap_attrs, cap_count):
        """Build PROC_THREAD_ATTRIBUTE_LIST with SECURITY_CAPABILITIES."""
        # First call: get required size
        attr_size = ctypes.c_size_t(0)
        kernel32.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(attr_size))

        # Allocate buffer
        attr_buf = (ctypes.c_char * attr_size.value)()

        # Initialize
        if not kernel32.InitializeProcThreadAttributeList(
            ctypes.byref(attr_buf), 1, 0, ctypes.byref(attr_size)
        ):
            error = ctypes.get_last_error()
            raise OSError(f"InitializeProcThreadAttributeList failed: {error}")

        # Build SECURITY_CAPABILITIES
        sec_caps = SECURITY_CAPABILITIES()
        sec_caps.AppContainerSid = self._sid
        if cap_attrs and cap_count > 0:
            sec_caps.Capabilities = ctypes.cast(cap_attrs, ctypes.POINTER(SID_AND_ATTRIBUTES))
            sec_caps.CapabilityCount = cap_count
        else:
            sec_caps.Capabilities = None
            sec_caps.CapabilityCount = 0
        sec_caps.Reserved = 0

        # Add to attribute list
        if not kernel32.UpdateProcThreadAttribute(
            ctypes.byref(attr_buf), 0,
            PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES,
            ctypes.byref(sec_caps), ctypes.sizeof(sec_caps),
            None, None
        ):
            error = ctypes.get_last_error()
            raise OSError(f"UpdateProcThreadAttribute failed: {error}")

        return attr_buf

    def launch(self, python_exe: str, script_path: str,
               args: Optional[List[str]] = None,
               stdin_data: Optional[bytes] = None,
               timeout: float = 300) -> Dict[str, Any]:
        """Launch python.exe inside the AppContainer.

        Args:
            python_exe: Path to python.exe.
            script_path: Path to script to execute.
            args: Additional arguments to pass to the script.
            stdin_data: Data to write to stdin (optional).
            timeout: Timeout in seconds.

        Returns:
            Dict with 'stdout', 'stderr', 'returncode', 'timed_out'.
        """
        if not self._setup_done:
            self.setup()

        # Build command line
        cmd_parts = [f'"{python_exe}"', f'"{script_path}"']
        if args:
            cmd_parts.extend(f'"{a}"' for a in args)
        cmd_line = " ".join(cmd_parts)

        # Create STARTUPINFOEXW
        si = STARTUPINFOEXW()
        si.StartupInfo.cb = ctypes.sizeof(si)
        si.StartupInfo.dwFlags = STARTF_USESTDHANDLES
        si.lpAttributeList = self._attr_list

        # Create pipes for stdout/stderr/stdin
        stdout_read, stdout_write = self._create_pipe()
        stderr_read, stderr_write = self._create_pipe()
        stdin_read, stdin_write = None, None
        if stdin_data is not None:
            stdin_read, stdin_write = self._create_pipe()

        si.StartupInfo.hStdOutput = stdout_write
        si.StartupInfo.hStdError = stderr_write
        if stdin_read:
            si.StartupInfo.hStdInput = stdin_read

        pi = PROCESS_INFORMATION()

        try:
            # CreateProcessW
            success = kernel32.CreateProcessW(
                None,                # lpApplicationName
                cmd_line,            # lpCommandLine
                None,                # lpProcessAttributes
                None,                # lpThreadAttributes
                True,                # bInheritHandles (for pipes)
                EXTENDED_STARTUPINFO_PRESENT,  # dwCreationFlags
                None,                # lpEnvironment
                None,                # lpCurrentDirectory
                ctypes.byref(si),    # lpStartupInfo
                ctypes.byref(pi),    # lpProcessInformation
            )
            if not success:
                error = ctypes.get_last_error()
                raise OSError(f"CreateProcessW failed: {error}")

            # Close write ends of pipes in parent
            self._close_handle(stdout_write)
            self._close_handle(stderr_write)
            stdout_write = None
            stderr_write = None
            if stdin_read:
                self._close_handle(stdin_read)
                stdin_read = None

            # Write stdin data if provided
            if stdin_data is not None and stdin_write is not None:
                self._write_pipe(stdin_write, stdin_data)
                self._close_handle(stdin_write)
                stdin_write = None

            # Wait for process with timeout
            timeout_ms = int(timeout * 1000) + 5000  # add 5s buffer
            wait_result = kernel32.WaitForSingleObject(pi.hProcess, timeout_ms)

            timed_out = wait_result == 0x00000102  # WAIT_TIMEOUT
            if timed_out:
                logger.warning("AppContainer process timed out after %ss", timeout)
                kernel32.TerminateProcess(pi.hProcess, 1)
                kernel32.WaitForSingleObject(pi.hProcess, 5000)

            # Read stdout/stderr
            stdout_data = self._read_pipe(stdout_read)
            stderr_data = self._read_pipe(stderr_read)

            # Get exit code
            exit_code = ctypes.c_ulong(0)
            kernel32.GetExitCodeProcess(pi.hProcess, ctypes.byref(exit_code))

            return {
                "stdout": stdout_data,
                "stderr": stderr_data,
                "returncode": exit_code.value,
                "timed_out": timed_out,
            }
        finally:
            # Close all handles
            for h in [stdout_read, stderr_read, stdout_write, stderr_write, stdin_read, stdin_write]:
                if h:
                    self._close_handle(h)
            if pi.hProcess:
                self._close_handle(pi.hProcess)
            if pi.hThread:
                self._close_handle(pi.hThread)

    def cleanup(self):
        """Delete profile and free SIDs."""
        if self._sid:
            try:
                userenv.DeleteAppContainerProfile(self._name)
                logger.debug("Deleted AppContainer profile '%s'", self._name)
            except Exception as e:
                logger.debug("DeleteAppContainerProfile failed (may not exist): %s", e)
            kernel32.LocalFree(self._sid)
            self._sid = None

        for sid in self._cap_sids:
            try:
                kernel32.LocalFree(sid)
            except Exception:
                pass
        self._cap_sids.clear()

    # -------------------------------------------------------------------
    # Pipe helpers
    # -------------------------------------------------------------------

    @staticmethod
    def _create_pipe():
        """Create a Windows pipe. Returns (read_handle, write_handle)."""
        read_handle = ctypes.c_void_p()
        write_handle = ctypes.c_void_p()
        if not kernel32.CreatePipe(
            ctypes.byref(read_handle), ctypes.byref(write_handle), None, 0
        ):
            raise OSError(f"CreatePipe failed: {ctypes.get_last_error()}")
        return read_handle, write_handle

    @staticmethod
    def _close_handle(handle):
        """Close a Windows handle."""
        if handle:
            try:
                kernel32.CloseHandle(handle)
            except Exception:
                pass

    @staticmethod
    def _write_pipe(handle, data: bytes):
        """Write bytes to a pipe handle."""
        written = ctypes.c_ulong(0)
        buf = ctypes.create_string_buffer(data)
        kernel32.WriteFile(handle, buf, len(data), ctypes.byref(written), None)

    @staticmethod
    def _read_pipe(handle, max_size: int = 10 * 1024 * 1024) -> str:
        """Read all data from a pipe handle."""
        chunks = []
        total = 0
        buf_size = 8192
        while total < max_size:
            buf = ctypes.create_string_buffer(buf_size)
            bytes_read = ctypes.c_ulong(0)
            success = kernel32.ReadFile(
                handle, buf, buf_size, ctypes.byref(bytes_read), None
            )
            if not success or bytes_read.value == 0:
                break
            chunks.append(buf.raw[:bytes_read.value])
            total += bytes_read.value
        return b"".join(chunks).decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------

def create_locked_down_sandbox(tmpdir: str, run_id: int = 0) -> AppContainerSandbox:
    """Create a fully locked-down AppContainer (no network, tmpdir only).

    For: HumanEval, BigCodeBench, LiveCodeBench, UncensorBench code_execution.
    """
    name = f"bm_{run_id:06x}_{secrets.token_hex(4)}"
    return AppContainerSandbox(
        name=name,
        capabilities=None,           # no network
        fs_read=None,                # no read dirs beyond default
        fs_read_write=[tmpdir],      # full access to tmpdir only
    )


def create_aider_sandbox(tmpdir: str, runtimes_dir: str) -> AppContainerSandbox:
    """Create an AppContainer with network + runtime access for Aider.

    For: Aider Polyglot (needs compilers, npm, cargo, etc.).
    """
    name = f"bm_aider_{secrets.token_hex(4)}"
    return AppContainerSandbox(
        name=name,
        capabilities=["internetClient", "privateNetworkClientServer"],
        fs_read=[str(runtimes_dir)],
        fs_read_write=[tmpdir],
    )


# ---------------------------------------------------------------------------
# Runner script
# ---------------------------------------------------------------------------

_RUNNER_TEMPLATE = '''\
"""AppContainer runner script — auto-generated by BenchMax."""
import importlib
import json
import sys

def main():
    config_path = sys.argv[1]
    output_path = sys.argv[2]

    with open(config_path, "r") as f:
        config = json.load(f)

    module = importlib.import_module(config["module"])
    func = getattr(module, config["function"])

    result_container = []
    try:
        func(*config["args"], result_container, config["tmpdir"])
    except Exception as e:
        result_container.append(f"failed: {{e}}")

    with open(output_path, "w") as f:
        json.dump(result_container, f)

if __name__ == "__main__":
    main()
'''


def write_runner_script(tmpdir: str) -> str:
    """Write the AppContainer runner script to tmpdir. Returns path."""
    path = os.path.join(tmpdir, "_appcontainer_runner.py")
    with open(path, "w") as f:
        f.write(_RUNNER_TEMPLATE)
    return path


def write_run_config(tmpdir: str, module_name: str, function_name: str,
                     args: list) -> str:
    """Write a JSON config file for the runner. Returns path."""
    config = {
        "module": module_name,
        "function": function_name,
        "args": args,
        "tmpdir": tmpdir,
    }
    path = os.path.join(tmpdir, "_run_config.json")
    with open(path, "w") as f:
        json.dump(config, f)
    return path


def parse_appcontainer_result(output: str) -> list:
    """Parse JSON result from runner script stdout."""
    try:
        # Find JSON array in output (may have other output before it)
        start = output.find("[")
        if start == -1:
            return ["failed: no JSON result found in AppContainer output"]
        end = output.rfind("]")
        if end == -1:
            return ["failed: incomplete JSON result in AppContainer output"]
        return json.loads(output[start:end + 1])
    except json.JSONDecodeError as e:
        return [f"failed: invalid JSON in AppContainer output: {e}"]
