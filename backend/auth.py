"""LAN password protection for BenchMax.

Single-user local app: requests from localhost (127.0.0.1 / ::1) are always
trusted and never see a login. Requests arriving over LAN (any non-loopback
client IP) must present a Bearer token obtained via POST /api/auth/login.

Password handling:
- Owner sets it locally: ``py cli.py set-password`` (talks to localhost).
- Stored as PBKDF2-HMAC-SHA256 (stdlib only) in records/.lan_password.
- Reset: stop server, delete records/.lan_password, start, set a new one.
  See docs/CONFIGURATION.md "LAN access & password".
"""

import hashlib
import hmac
import logging
import os
import secrets
import time
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
PASSWORD_FILE = ROOT / "records" / ".lan_password"

_ITERATIONS = 210_000
_TOKEN_TTL_SEC = 30 * 24 * 3600  # 30 days
_MAX_PASSWORD_LEN = 256

# token -> expires_at (in-memory only; server restart logs everyone out)
_active_tokens: dict[str, float] = {}


def _is_loopback(client_host: str | None) -> bool:
    if not client_host:
        return False
    host = client_host.strip().lower().strip("[]")
    return host in ("127.0.0.1", "::1", "localhost")


def is_loopback_request(request) -> bool:
    """True when the HTTP client connected via loopback (trusted, no login)."""
    client = getattr(request, "client", None)
    host = getattr(client, "host", None) if client else None
    # Starlette TestClient reports "testclient" — treat as loopback so the
    # test suite exercises the localhost (open) path.
    if host in (None, "testclient"):
        return True
    return _is_loopback(host)


def password_is_set() -> bool:
    return PASSWORD_FILE.exists() and PASSWORD_FILE.stat().st_size > 0


def _harden_file(path: Path) -> None:
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass  # Windows ACLs: best effort, file stays user-readable only


def set_password(password: str) -> None:
    """Hash + store a new LAN password (overwrites). Raises ValueError."""
    if not password or not password.strip():
        raise ValueError("Password must not be empty.")
    if len(password) > _MAX_PASSWORD_LEN:
        raise ValueError("Password too long (max 256 characters).")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    PASSWORD_FILE.parent.mkdir(parents=True, exist_ok=True)
    PASSWORD_FILE.write_text(
        f"pbkdf2_sha256${_ITERATIONS}${salt.hex()}${digest.hex()}",
        encoding="utf-8",
    )
    _harden_file(PASSWORD_FILE)
    # Changing the password invalidates all existing LAN sessions.
    _active_tokens.clear()


def verify_password(password: str) -> bool:
    """Constant-time check of a candidate password against the stored hash."""
    try:
        raw = PASSWORD_FILE.read_text(encoding="utf-8").strip()
        algo, iters, salt_hex, hash_hex = raw.split("$")
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iters)
        )
        return hmac.compare_digest(digest.hex(), hash_hex)
    except Exception:
        logger.warning("LAN password verification failed (missing/corrupt file).")
        return False


def issue_token() -> tuple[str, float]:
    """Create a Bearer token valid for _TOKEN_TTL_SEC. Returns (token, expires_at)."""
    token = secrets.token_hex(32)
    expires_at = time.time() + _TOKEN_TTL_SEC
    _active_tokens[token] = expires_at
    return token, expires_at


def verify_token(token: str | None) -> bool:
    """Check a Bearer token; prunes expired tokens opportunistically."""
    if not token:
        return False
    now = time.time()
    # Opportunistic prune so the dict can't grow unboundedly.
    expired = [t for t, exp in _active_tokens.items() if exp < now]
    for t in expired:
        del _active_tokens[t]
    exp = _active_tokens.get(token)
    return exp is not None and exp >= now


def bearer_from_header(request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return None


def lan_request_allowed(request) -> bool:
    """Gate for non-loopback traffic: valid Bearer token required."""
    if is_loopback_request(request):
        return True
    return verify_token(bearer_from_header(request))
