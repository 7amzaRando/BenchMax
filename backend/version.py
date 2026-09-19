"""Single source of truth for the BenchMax version.

Why: the version string was hardcoded in 5+ places (main.py, cli.py,
frontend/package.json, App.tsx footer, Sidebar) and they drifted. Backend
code imports from here; the frontend reads it at runtime via GET /api/version
(falling back to its build-time string when the server is unreachable).
"""

__version__ = "2.0.3"
