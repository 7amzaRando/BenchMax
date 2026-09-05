"""Windows Process Mitigation Policies and Token Restrictions.

Provides additional sandboxing via process mitigation policies and
restricted process tokens to limit what child processes can do.
"""

import ctypes
import ctypes.wintypes
import logging
import sys
from typing import List, Optional

logger = logging.getLogger(__name__)

if sys.platform != "win32":
    raise ImportError("mitigation is Windows-only")

# Load Windows DLLs
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
advapi32 = ctypes.WinDLL('advapi32', use_last_error=True)

# Process Mitigation Policy constants
PROCESS_CREATION_MITIGATION_POLICY = 7

# Mitigation policies
PROCESS_CREATION_MITIGATION_POLICY_NO_CHILD_PROCESS_CREATION_ALWAYS_ON = 0x000000000001
PROCESS_CREATION_MITIGATION_POLICY_NO_CHILD_PROCESS_CREATION_ALLOW_BY_DEFAULT = 0x000000000002
PROCESS_CREATION_MITIGATION_POLICY_BLOCK_NON_MICROSOFT_BINARIES_ALWAYS_ON = 0x100000000000
PROCESS_CREATION_MITIGATION_POLICY_FONT_DISABLE_ALWAYS_ON = 0x000000000004
PROCESS_CREATION_MITIGATION_POLICY_IMAGE_LOAD_NO_REMOTE = 0x000000000080
PROCESS_CREATION_MITIGATION_POLICY_IMAGE_LOAD_NO_LOW_MANDATORY_IMAGE_LABEL = 0x000000000100

# Extended mitigation policy indices
MITIGATION_FONT_DISABLE = 9
MITIGATION_IMAGE_LOAD = 10
MITIGATION_EXTENSION_POINT_DISABLE = 6

# Font disable policy flags
PROCESS_MITIGATION_FONT_DISABLE_POLICY_ENABLE_NON_MICROSOFT_FONT_DISABLE = 0x00000001
PROCESS_MITIGATION_FONT_DISABLE_POLICY_AUDIT_NON_MICROSOFT_FONT_LOAD = 0x00000002

# Image load policy flags
PROCESS_MITIGATION_IMAGE_LOAD_POLICY_NO_REMOTE_IMAGES = 0x00000002
PROCESS_MITIGATION_IMAGE_LOAD_POLICY_NO_LOW_MANDATORY_IMAGE_LABEL = 0x00000004

# Extension point disable policy flags
PROCESS_MITIGATION_EXTENSION_POINT_DISABLE_POLICY_DISABLE_EXTENSION_POINTS = 0x00000001

# Token privilege constants
TOKEN_ADJUST_PRIVILEGES = 0x0020
TOKEN_QUERY = 0x0008
SE_PRIVILEGE_DISABLED = 0x00000002

# Dangerous privileges to remove from child processes
DANGEROUS_PRIVILEGES: List[str] = [
    'SeDebugPrivilege',              # Can debug any process on the system
    'SeTakeOwnershipPrivilege',      # Can take ownership of any object
    'SeCreatePermanentPrivilege',    # Can create permanent shared objects
    'SeShutdownPrivilege',           # Can shut down the system
    'SeLockMemoryPrivilege',         # Can lock physical pages
    'SeIncreaseQuotaPrivilege',      # Can set work set sizes
    'SeManageVolumePrivilege',       # Can perform volume maintenance
    'SeCreateTokenPrivilege',        # Can create access tokens
    'SeCreateGlobalPrivilege',       # Can create global objects in Terminal Services
    'SeTcbPrivilege',                # Acts as part of the operating system
    'SeAssignPrimaryTokenPrivilege', # Can assign primary tokens
    'SeLoadDriverPrivilege',         # Can load/unload device drivers
    'SeSystemEnvironmentPrivilege',  # Can modify firmware environment variables
    'SeProfileSingleProcessPrivilege', # Can profile single process
    'SeSystemtimePrivilege',         # Can change system time
    'SeRelabelPrivilege',            # Can relabel objects
    'SeTrustedCredManAccessPrivilege', # Can access Credential Manager
]


class LUID(ctypes.Structure):
    _fields_ = [
        ('LowPart', ctypes.c_uint32),
        ('HighPart', ctypes.c_long),
    ]


class LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ('Luid', LUID),
        ('Attributes', ctypes.c_uint32),
    ]


class TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = [
        ('PrivilegeCount', ctypes.c_uint32),
        ('Privileges', LUID_AND_ATTRIBUTES * 1),  # Flexible array
    ]


def _get_current_process_token():
    """Get handle to current process token."""
    token_handle = ctypes.c_void_p()
    if not advapi32.OpenProcessToken(
        kernel32.GetCurrentProcess(),
        TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY,
        ctypes.byref(token_handle)
    ):
        error = ctypes.get_last_error()
        raise OSError(f"OpenProcessToken failed: {error}")
    return token_handle


def _lookup_privilege(name: str) -> LUID:
    """Look up a privilege LUID by name."""
    luid = LUID()
    if not advapi32.LookupPrivilegeValueW(None, name, ctypes.byref(luid)):
        error = ctypes.get_last_error()
        raise OSError(f"LookupPrivilegeValueW failed for {name}: {error}")
    return luid


def _set_privilege(token_handle, privilege_name: str, enable: bool):
    """Enable or disable a privilege on a token."""
    luid = _lookup_privilege(privilege_name)
    
    tp = TOKEN_PRIVILEGES()
    tp.PrivilegeCount = 1
    tp.Privileges[0].Luid = luid
    tp.Privileges[0].Attributes = 0 if enable else SE_PRIVILEGE_DISABLED
    
    if not advapi32.AdjustTokenPrivileges(
        token_handle,
        False,  # Don't disable all privileges
        ctypes.byref(tp),
        ctypes.sizeof(tp),
        None,
        None
    ):
        error = ctypes.get_last_error()
        logger.debug("AdjustTokenPrivileges failed for %s: %s", privilege_name, error)


def remove_dangerous_privileges():
    """Remove dangerous privileges from the current process token.
    
    This should be called inside the child process to limit its capabilities.
    """
    try:
        token_handle = _get_current_process_token()
    except OSError as e:
        logger.warning("Failed to get process token: %s", e)
        return
    
    removed = 0
    for priv in DANGEROUS_PRIVILEGES:
        try:
            _set_privilege(token_handle, priv, enable=False)
            removed += 1
        except OSError:
            pass  # Privilege may not exist, ignore
    
    logger.debug("Removed %d/%d dangerous privileges", removed, len(DANGEROUS_PRIVILEGES))


def apply_child_process_mitigation():
    """Apply process mitigation policies inside a child process.
    
    This should be called at the start of the child process function,
    before executing untrusted code.
    
    Policies applied:
    - No child process creation (blocks cmd.exe, powershell.exe, subprocess)
    """
    # Block child process creation
    # This prevents the child from spawning subprocesses (cmd.exe, powershell.exe, etc.)
    policy = ctypes.c_ulonglong(
        PROCESS_CREATION_MITIGATION_POLICY_NO_CHILD_PROCESS_CREATION_ALWAYS_ON
    )
    
    try:
        success = kernel32.SetProcessMitigationPolicy(
            PROCESS_CREATION_MITIGATION_POLICY,
            ctypes.byref(policy),
            ctypes.sizeof(policy)
        )
        if success:
            logger.debug("Applied child process creation mitigation policy")
        else:
            error = ctypes.get_last_error()
            # May fail on older Windows versions (< 10 1709)
            logger.debug("SetProcessMitigationPolicy failed: %s (may not be supported)", error)
    except Exception as e:
        logger.debug("Failed to apply mitigation policy: %s", e)


def _set_mitigation_policy_int(policy: int, flags: int):
    """Set a process mitigation policy using integer flags (best-effort)."""
    try:
        val = ctypes.c_ulong(flags)
        kernel32.SetProcessMitigationPolicy(policy, ctypes.byref(val), ctypes.sizeof(val))
    except Exception:
        pass  # Not all policies supported on all Windows versions


def apply_enhanced_mitigations():
    """Apply enhanced mitigation policies (defense-in-depth).

    These are safe to add and provide additional hardening:
    - FontDisable: block non-system font loading
    - ImageLoadNoRemote: block remote DLL loading
    - ExtensionPointDisable: block AppInit DLLs, hooks, EMET
    """
    # Font disable (block non-system fonts — prevents font exploits)
    _set_mitigation_policy_int(
        MITIGATION_FONT_DISABLE,
        PROCESS_MITIGATION_FONT_DISABLE_POLICY_ENABLE_NON_MICROSOFT_FONT_DISABLE
    )

    # Image load (block remote DLLs — prevents network-based DLL injection)
    _set_mitigation_policy_int(
        MITIGATION_IMAGE_LOAD,
        PROCESS_MITIGATION_IMAGE_LOAD_POLICY_NO_REMOTE_IMAGES
    )

    # Extension point disable (block hooks, AppInit DLLs — prevents injection)
    _set_mitigation_policy_int(
        MITIGATION_EXTENSION_POINT_DISABLE,
        PROCESS_MITIGATION_EXTENSION_POINT_DISABLE_POLICY_DISABLE_EXTENSION_POINTS
    )

    logger.debug("Applied enhanced mitigation policies (FontDisable, ImageLoad, ExtensionPoint)")


def apply_all_mitigations():
    """Apply all available mitigations to the current process.
    
    Call this inside the child process after forking/spawning.
    """
    remove_dangerous_privileges()
    apply_child_process_mitigation()
    apply_enhanced_mitigations()
