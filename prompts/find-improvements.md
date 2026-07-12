Scan the entire BenchMax project for improvement opportunities. Do NOT implement anything — just find and document.

Search across all `.py`, `.tsx`, `.ts`, `.json`, `.md`, `.bat`, and `.ps1` files for these categories:

### 1. Performance
- N+1 queries in DB access patterns (queries inside loops)
- Synchronous I/O in hot paths (blocking calls during request handling)
- Repeated computation that could be cached (same data transformed multiple times)
- Large JSON files parsed repeatedly (could use persistent cache)
- Frontend bundle size issues (large imports, missing code splitting)
- Polling frequency vs data change rate mismatch

### 2. Missing Features
- Benchmark gaps (popular eval benchmarks not yet integrated)
- UI polish (missing keyboard shortcuts, no bulk actions, no search/filter where expected)
- Export gaps (missing format, missing data fields in exports)
- Monitoring (no alerting on run failure, no run duration tracking)
- Configuration (hardcoded values that should be configurable)

### 3. Dead / Redundant Code
- Unused imports, variables, functions, or classes
- Dead endpoints or frontend routes
- Duplicate utility code that could be shared
- Orphaned data files or templates
- TODO/FIXME/HACK comments that are stale

### 4. Error Handling & Resilience
- Bare `except:` clauses without specific exception types
- Silent `catch {}` / `except: pass` blocks
- Unhandled edge cases (empty datasets, missing files, network timeouts)
- Unclosed resources (file handles, DB sessions, HTTP clients)
- Race conditions (shared mutable state without locks)

### 5. UX & Polish
- Inconsistent UI patterns (different button styles for same action)
- Missing loading/empty/error states
- Confusing labels or missing tooltips
- Accessibility gaps (missing aria labels, keyboard navigation)
- Mobile/responsive layout issues

For each finding, write one line: `{file}:{line} | {category} | {severity (low/med/high)} | {one-sentence description}`

Return: sorted list grouped by category. Do not implement anything.
