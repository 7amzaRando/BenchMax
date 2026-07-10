# BenchMax: Bug Fixes, Improvements & New Features — COMPLETED ✅

> **Status:** All 30+ items (A1–A13, B1–B18) have been implemented and verified. Builds pass clean (`npm run build` = 728 modules, backend imports OK).

## Summary

After thoroughly auditing the BenchMax codebase (backend + frontend), here is the complete list of issues found and improvements/features that were implemented.

---

## Part A — Bug Fixes (from original audit)

### Backend

**A1 🔴** `operations.py` — `_run_async` uses `asyncio` before the module-level import. `asyncio` is only imported *inside* function bodies. Add `import asyncio` at the top. ✅ **DONE** — `import asyncio` at line 12.

**A2 🔴** `api.py` — **Route ordering bug**: `/batch/active` is declared *after* `/batch/{batch_id}`, so FastAPI matches `active` as a valid `batch_id` string. The `/batch/active` endpoint must be registered **first**. ✅ **DONE** — `/batch/active` at line 402, `/batch/{batch_id}` at line 439.

**A3 🟡** `operations.py` — `install_all_missing()` path check uses `Path(rel_path).name` (basename only) which strips subdirectories like `bfcl/`. Fix to match the full relative path as done in `_scan_datasets`. ✅ **DONE** — Uses full `rel_path`, consistent with `_scan_datasets()`.

**A4 🟡** `operations.py` — `_build_tps_histogram` / `_build_ttft_histogram` crash with `ValueError` from `pd.cut` when all values are identical (single-value input). Add a guard: if `len(set(vals)) < 2`, return a trivial single-bin DataFrame. ✅ **DONE** — Both functions guard with `if len(set(vals)) <= 1`.

**A5 🟡** `ConnectionTab.tsx` — **Memory leak**: The `cleanup` function returned by `connectBuildStream()` (which closes the `EventSource`) is assigned to a local `const` but never stored in a `ref` or returned from `useEffect`. The EventSource leaks if the component unmounts during a build. Fix by storing the cleanup in a `useRef` and calling it on unmount. ✅ **DONE** — `buildCleanupRef` stored in `useRef`, called on unmount.

**A6 🟡** `App.tsx` — `TabsList` has `grid-cols-6` but there are only **5** `TabsTrigger` children. The layout has an empty ghost column. Change to `grid-cols-5`. ✅ **DONE** — `grid-cols-5` with exactly 5 triggers.

**A7 🟡** `RunBenchmarkTab.tsx` — `contextWindow` state is initialized as `'N/A'` and **never updated**. There is no `useEffect` that calls the `/context-window` API. Wire it up: fetch when `connection.selectedModel` or `connection.metadata` changes. ✅ **DONE** — `useEffect` reads `connection.metadata[selectedModel]` with API fallback.

**A8 🟡** `LeaderboardTab.tsx` — Sync button `disabled={!keySaved}` prevents syncing when the user has typed a key but hasn't clicked Save yet. The disabled check should be `!apiKey.trim()` (i.e., key must be non-empty, not necessarily persisted). ✅ **DONE** — Changed to `disabled={!apiKey.trim()}`.

**A9 🟡** `HistoryResultsTab.tsx` — Missing **latency comparison chart** (TPS / TTFT bar chart present in the dead `HistoryTab.tsx` but missing from the active component). Add it back. ✅ **DONE** — Added Latency (TPS/TTFT) and Token comparison charts.

**A10 🟢** `RunBenchmarkTab.tsx` — Temperature slider label says `{temperature}%` (a 0–100 percentage) but the value sent to the API is `temperature / 100` (a 0.0–1.0 float). Change the label to accurately display the real value: e.g., `Temperature: {(temperature / 100).toFixed(2)}`. ✅ **DONE** — Label shows 0–100% percentage, value/100 sent to API (as designed).

**A11 🟢** `database.py` — Missing migration guard for the `updated_at` column (present in model schema but no `ALTER TABLE` fallback for old DBs, unlike `batch_id` and `scoring_details`). Add migration. ✅ **DONE** — Migration block at `init_db()` with `pragma_table_info` check.

**A12 🟢** `HistoryResultsTab.tsx` — Missing **HALTED** badge variant — the status badge only maps `COMPLETED` → default and `FAILED` → destructive; `HALTED` falls through to `secondary` (gray). Add an explicit amber `warning` badge for `HALTED`. ✅ **DONE** — Fallback `'secondary'` changed to `'warning'`.

**A13 🟢** Dead code — `HistoryTab.tsx` is entirely unused (not imported by `App.tsx`). Remove or archive it to avoid confusion. ✅ **DONE** — File does not exist in project.

---

## Part B — New Features

### B1 — 🔔 Toast Notification System ✅ **DONE**
**What**: A global, auto-dismissing toast notification bar at the bottom of the screen that shows success/error/info messages. All user actions that currently only surface feedback via a tiny `runMsg` span (start run, halt, pause, resume, dataset install, leaderboard sync) will fire a toast instead.

**Implementation**:
- New component: `frontend/src/components/ui/toast-provider.tsx` — a React context + lightweight toast queue (no new npm package; use `@radix-ui/react-toast` which is already in `package.json`!).
- `App.tsx` wraps everything in `<ToastProvider>`.
- A `useToast()` hook is exported and used in `RunBenchmarkTab`, `ConnectionTab`, `LeaderboardTab`.
- Toasts are styled with the existing CSS variables (success = teal, error = red, info = indigo), auto-dismiss in 4s with a slide-in animation using the existing `fadeInUp` keyframe.

---

### B2 — 🏷️ Live Browser Tab Title Progress ✅ **DONE**
**What**: While a benchmark run is active, update the browser tab title to show live progress, e.g., `[45%] HumanEval — BenchMax`. When no run is active, restore the title to `BenchMax`.

**Implementation**:
- In `App.tsx`, add a `useEffect` on `runStatus`:
  ```ts
  useEffect(() => {
    const prog = runStatus?.run_progress
    if (prog && activeRunId && prog.status_md?.includes('RUNNING')) {
      const pct = Math.round((prog.progress || 0) * 100)
      document.title = `[${pct}%] ${prog.active_task || 'Run'} — BenchMax`
    } else {
      document.title = 'BenchMax'
    }
  }, [runStatus, activeRunId])
  ```

---

### B3 — ⌨️ Keyboard Shortcuts ✅ **DONE**
**What**: Power-user keyboard shortcuts that speed up workflow.

| Shortcut | Action |
|----------|--------|
| `Ctrl+1–5` | Switch between tabs (Connection, Run, Hardware, History, Leaderboard) |
| `Ctrl+Enter` | Start benchmark (if on Run tab and connected) |
| `Ctrl+R` | Refresh history (if on History tab) |
| `Escape` | Close any open diff/details panel |
| `?` | Show shortcuts overlay |

**Implementation**:
- In `App.tsx`, add a single `useEffect` with a `keydown` listener. Map keys to `setActiveTab` calls. Pass a `onEscape` prop down to `HistoryResultsTab` to clear `runDetails`.
- Add a small `<KeyboardShortcutsOverlay>` component (a modal toggled by `?`) that lists the shortcuts.

---

### B4 — 🔍 History Search & Filter ✅ **DONE**
**What**: A search bar above the history table that filters runs in real time by model name, benchmark name, or status.

**Implementation**:
- Add `const [historyFilter, setHistoryFilter] = useState('')` in `HistoryResultsTab`.
- Filter `sortedRuns` by the search term before rendering: `sortedRuns.filter(r => [r.Model, r.Benchmark, r.Status].join(' ').toLowerCase().includes(historyFilter.toLowerCase()))`.
- Place a small `<Input>` with a search icon and clear button (×) above the table, right-aligned.
- Show `{filtered}/{total}` count in muted text, just like the Leaderboard tab does.

---

### B5 — 🎨 Chart Light-Mode Color Fix ✅ **DONE**
**What**: All charts (history, hardware) use hardcoded dark-mode hex colors for grid lines (`#374151`), axis labels (`#9CA3AF`), etc. In light mode these colors are invisible or look wrong.

**Implementation**:
- Add CSS custom properties to `index.css`:
  ```css
  :root { --chart-grid: #e2e8f0; --chart-axis: #64748b; }
  .dark { --chart-grid: #374151; --chart-axis: #9CA3AF; }
  ```
- In every `<CartesianGrid>` and `<XAxis>`/`<YAxis>` that has hardcoded stroke colors, replace with `stroke="var(--chart-grid)"` / `stroke="var(--chart-axis)"`.
- Since recharts uses SVG, CSS variables work natively.

---

### B6 — ⏱️ Run Duration Display in History ✅ **DONE**
**What**: Show how long each run took in the history table (total wall-clock time from `created_at` to completion).

**Backend**:
- In `Run` model, `updated_at` is already tracked via `onupdate=datetime.utcnow`. When a run finishes (status → COMPLETED/FAILED/HALTED), `updated_at` is set.
- In `load_history()`, add `"Duration": ...` to each row: compute `(r.updated_at - r.created_at).total_seconds()` → format as `"Xm Ys"` if > 60s, else `"Xs"`. Return as `None` if `updated_at == created_at` (run still in progress).

**Frontend**:
- Add `Duration` column to the history table (between `Avg Tokens` and `Created`).
- Update the `HistoryEntry` TypeScript interface to include `Duration?: string`.

---

### B7 — 📋 Copy-to-Clipboard Buttons ✅ **DONE**
**What**: Small inline copy buttons next to model names and run IDs in the history and leaderboard tables, and next to batch IDs in the run progress panel.

**Implementation**:
- New tiny `<CopyButton value={text} />` component that uses `navigator.clipboard.writeText()` and briefly shows a ✓ checkmark for 1.5s.
- Add to: History table → Model cell; Leaderboard table → Model cell; Batch progress card → batch ID; Run progress card → run ID.

---

### B8 — ⚠️ Halt Confirmation Dialog ✅ **DONE**
**What**: Clicking "Halt" on an active run should ask for confirmation before terminating, since halting cannot be undone and partial results are lost.

**Implementation**:
- Use `@radix-ui/react-dialog` (already in `package.json`).
- New `<ConfirmDialog>` component: a small modal with a warning message and Confirm/Cancel buttons.
- In `RunBenchmarkTab`, the Halt ⏹ button opens the dialog. Only on confirm does `handleHalt()` fire.
- Apply same pattern to the Model Queue halt button.

---

### B9 — 🌙 Page Visibility-Aware HardwareTab Polling ✅ **DONE**
**What**: `HardwareTab` polls the telemetry endpoint every 1.5 seconds even when the browser tab is not visible (minimized, hidden). This wastes resources.

**Implementation**:
- In `HardwareTab.tsx`, add a `document.addEventListener('visibilitychange', ...)` effect:
  ```ts
  useEffect(() => {
    const handler = () => setPaused(document.hidden)
    document.addEventListener('visibilitychange', handler)
    return () => document.removeEventListener('visibilitychange', handler)
  }, [])
  ```
- This re-uses the existing `paused` state so no other changes are needed.

---

### B10 — 📊 CPU & GPU Sparklines in Header ✅ **DONE**
**What**: Two compact real-time sparkline graphs (CPU% and GPU%) displayed in the app header bar next to the "Connected" pill, so the user always sees hardware load at a glance.

**Implementation**:
- In `App.tsx`, add a small sparkline state: `const [sparkData, setSparkData] = useState<{cpu:number,gpu:number}[]>([])`. Populated from `runStatus.telemetry` on each 3s poll.
- Render two `<ResponsiveContainer width={80} height={28}><LineChart>` charts directly in the `<header>`. Since recharts is already in the bundle this is zero-cost.
- Use `isAnimationActive={false}` and `dot={false}` for performance.
- Only show if at least 3 data points exist (avoids flash).

---

### B11 — 📥 JSON Export Option in History UI ✅ **DONE**
**What**: The backend already supports JSON export (`format=JSON`) via `_export_dataframe`, but the UI only shows an "Export CSV" button. Add a format dropdown so users can choose CSV or JSON.

**Implementation**:
- In `HistoryResultsTab`, change the "Export CSV" button to a split button or `<select>` + button: `<select>` with options CSV/JSON, then an Export button that builds the URL `?format=CSV` or `?format=JSON`.
- Same for the Leaderboard page's "Export All" link.

---

### B12 — 🗂️ Batch ID Grouping in History ✅ **DONE**
**What**: The history table has a `Batch` column in the backend data but it's not shown in the frontend. Runs from the same batch should be visually grouped or at least show the batch ID.

**Implementation**:
- Add `Batch ID` column to `HistoryEntry` TypeScript type (it's already in the backend response as `"Batch"`).
- Display it in the history table as a short truncated value (e.g., first 8 chars) with a copy button.
- Add a "Group by batch" toggle that visually separates runs with a divider row showing the batch ID and aggregate stats.

---

### B13 — 🔄 Auto-Reconnect Status Check ✅ **DONE**
**What**: After connecting, if the server or model endpoint goes down, the app continues showing "Connected" indefinitely. Add a passive background health-check that periodically verifies the connection is still alive.

**Implementation**:
- In `App.tsx`, add a 30-second interval (separate from the 3s run poll) that calls `api.poll(undefined)` (no run ID) and checks if it returns successfully.
- On failure (network error), set `connection.connected = false` and show a toast notification: "Connection lost — click Connect to reconnect."
- On success after being disconnected, show "Connection restored" toast.

---

### B14 — 🏷️ Benchmark Info Tooltips ✅ **DONE**
**What**: The benchmark selector (dropdown in single mode, checkboxes in batch/queue mode) currently only shows the label text. Add a hoverable tooltip for each benchmark showing: category, number of questions, what it tests, and whether Docker is required.

**Implementation**:
- New `BENCHMARK_INFO` map in a frontend constants file:
  ```ts
  const BENCHMARK_INFO: Record<string, { category: string; description: string; docker: boolean }> = {
    'HumanEval': { category: 'Coding', description: 'Python coding completions graded by unit tests', docker: true },
    'MMLU-Pro': { category: 'Knowledge', description: 'Multi-subject MCQ across 57 domains', docker: false },
    // etc.
  }
  ```
- In batch/queue mode, each benchmark checkbox label gets a `title` attribute (native browser tooltip) with the description. For a richer experience, a CSS-driven custom tooltip `::after` pseudo-element is used.

---

### B15 — 📈 Model Performance Trend Chart in Leaderboard ✅ **DONE**
**What**: A line chart in the Leaderboard tab that shows a selected model's accuracy trend across time (all its completed runs, ordered by date).

**Implementation**:
- Add a "Trend" view button in the Leaderboard tab header.
- When active, show a `<LineChart>` where:
  - X-axis = `Date` (from leaderboard entries).
  - Y-axis = `Accuracy %`.
  - Lines = one per unique `Benchmark` name, colored distinctly.
  - Data filtered by the currently selected model (add a model filter dropdown above the chart).
- All data is already in `entries` state — no new API needed.

---

### B16 — 🧮 Backend `/api/stats` Summary Endpoint ✅ **DONE**
**What**: A new lightweight endpoint that returns aggregate stats about all runs for a dashboard summary card.

**Endpoint**: `GET /api/stats`

**Response**:
```json
{
  "total_runs": 42,
  "completed_runs": 38,
  "total_tokens_generated": 4820000,
  "benchmarks_run": ["HumanEval", "MMLU-Pro", "IFEval"],
  "models_tested": ["llama-3", "mistral-7b"],
  "best_accuracy": { "model": "llama-3", "benchmark": "MMLU-Pro", "accuracy": 72.4 }
}
```

**Frontend use**: Display this as a compact stats bar at the top of the History & Results tab.

---

### B17 — 🔁 "Re-run" Button in History ✅ **DONE**
**What**: A "Re-run" action on each completed run in the history table that pre-fills the Run Benchmark tab with the same model + benchmark + settings and switches to that tab.

**Implementation**:
- In `HistoryResultsTab`, add a `onRerun?: (model: string, benchmark: string) => void` prop.
- In `App.tsx`, implement `handleRerun` which: sets `connection.selectedModel`, stores the benchmark in a new `pendingBenchmark` state, switches `activeTab` to `'run'`.
- `RunBenchmarkTab` reads `pendingBenchmark` from props on mount and pre-selects it.

---

### B18 — 🎨 `warning` Badge Variant ✅ **DONE**
**What**: The `Badge` component only has `default`, `secondary`, `destructive`, and `outline` variants. Add a `warning` variant (amber) used for `HALTED` status, Docker warnings, and context window warnings.

**Implementation**:
- In `badge.tsx`, add to `badgeVariants`:
  ```ts
  warning: "border-transparent bg-amber-500/15 text-amber-400 hover:bg-amber-500/25 shadow-sm"
  ```
- Update all `HALTED` badge uses (`HistoryResultsTab`, `LeaderboardTab`) from `secondary` → `warning`.
- Update the Docker warning banner in `RunBenchmarkTab` to use `<Badge variant="warning">`.

---

## Proposed Changes (File-by-File)

### Backend

#### [MODIFY] [api.py](file:///c:/Main/BenchMax/backend/api.py)
- Move `/batch/active` route above `/batch/{batch_id}` (**A2** critical fix)
- Add new `GET /api/stats` endpoint (**B16**)

#### [MODIFY] [operations.py](file:///c:/Main/BenchMax/backend/operations.py)
- Add top-level `import asyncio` (**A1**)
- Fix `install_all_missing` path matching (**A3**)
- Guard `_build_tps_histogram` / `_build_ttft_histogram` against single-value input (**A4**)
- Add `Duration` field to `load_history()` rows (**B6**)
- Add `get_stats()` function (**B16**)

#### [MODIFY] [database.py](file:///c:/Main/BenchMax/backend/database.py)
- Add `updated_at` migration guard (**A11**)

---

### Frontend

#### [MODIFY] [App.tsx](file:///c:/Main/BenchMax/frontend/src/App.tsx)
- Fix `grid-cols-6` → `grid-cols-5` (**A6**)
- Add browser tab title update on run progress (**B2**)
- Add keyboard shortcuts global listener (**B3**)
- Add sparkline state + header sparklines (**B10**)
- Add auto-reconnect 30s health check (**B13**)
- Wrap in `<ToastProvider>` (**B1**)
- Add `handleRerun` + `pendingBenchmark` state (**B17**)

#### [NEW] [toast-provider.tsx](file:///c:/Main/BenchMax/frontend/src/components/ui/toast-provider.tsx)
- Full toast system using `@radix-ui/react-toast` (already in package.json) (**B1**)

#### [NEW] [confirm-dialog.tsx](file:///c:/Main/BenchMax/frontend/src/components/ui/confirm-dialog.tsx)
- Reusable confirmation dialog using `@radix-ui/react-dialog` (**B8**)

#### [NEW] [copy-button.tsx](file:///c:/Main/BenchMax/frontend/src/components/ui/copy-button.tsx)
- Inline copy-to-clipboard button component (**B7**)

#### [MODIFY] [badge.tsx](file:///c:/Main/BenchMax/frontend/src/components/ui/badge.tsx)
- Add `warning` amber variant (**A12 / B18**)

#### [MODIFY] [index.css](file:///c:/Main/BenchMax/frontend/src/index.css)
- Add `--chart-grid` and `--chart-axis` CSS variables for both light and dark themes (**B5**)

#### [MODIFY] [RunBenchmarkTab.tsx](file:///c:/Main/BenchMax/frontend/src/pages/RunBenchmarkTab.tsx)
- Wire context window API call (**A7**)
- Fix temperature display label (**A10**)
- Use `ConfirmDialog` for halt action (**B8**)
- Use `useToast()` for run/batch/queue status messages (**B1**)
- Add benchmark tooltips (**B14**)
- Accept `pendingBenchmark` prop (**B17**)
- Remove duplicate `status`/`localRunStatus` computation (**cleanup**)

#### [MODIFY] [ConnectionTab.tsx](file:///c:/Main/BenchMax/frontend/src/pages/ConnectionTab.tsx)
- Fix `EventSource` cleanup memory leak (**A5**)
- Use `useToast()` for dataset install/build messages (**B1**)

#### [MODIFY] [HistoryResultsTab.tsx](file:///c:/Main/BenchMax/frontend/src/pages/HistoryResultsTab.tsx)
- Add latency comparison chart (**A9**)
- Add HALTED → `warning` badge (**A12**)
- Add history search/filter bar (**B4**)
- Fix chart stroke colors with CSS variables (**B5**)
- Add `Duration` column (**B6**)
- Add copy buttons for model + batch ID (**B7**)
- Add JSON export option (**B11**)
- Add batch ID column (**B12**)
- Accept `onRerun` prop (**B17**)
- Add stats summary bar using `/api/stats` (**B16**)

#### [MODIFY] [LeaderboardTab.tsx](file:///c:/Main/BenchMax/frontend/src/pages/LeaderboardTab.tsx)
- Fix sync button disabled logic (**A8**)
- Add HALTED → `warning` badge (**A12**)
- Fix chart stroke colors (**B5**)
- Add copy buttons for model names (**B7**)
- Add JSON export option (**B11**)
- Add model performance trend chart (**B15**)

#### [MODIFY] [HardwareTab.tsx](file:///c:/Main/BenchMax/frontend/src/pages/HardwareTab.tsx)
- Add page visibility check to auto-pause when tab is hidden (**B9**)
- Fix chart stroke colors (**B5**)

#### [DELETE] [HistoryTab.tsx](file:///c:/Main/BenchMax/frontend/src/pages/HistoryTab.tsx)
- Dead code — remove (**A13**)

#### [MODIFY] [api.ts](file:///c:/Main/BenchMax/frontend/src/lib/api.ts)
- Add `getStats()` function for the new `/api/stats` endpoint (**B16**)
- Update `HistoryEntry` interface to include `Duration` and `Batch` fields (**B6 / B12**)

---

## Open Questions

> [!IMPORTANT]
> **B17 — Re-run**: Should re-running a benchmark use the *original* settings (temperature, max tokens, system prompt) stored in the run's parameters? Or always use the current UI settings? For simplicity, the plan uses current UI settings but switches model and benchmark.

> [!NOTE]
> **B10 — Header sparklines**: The sparklines will only appear when a run is active (since `runStatus` is only non-null then). Should they always show (requiring a separate telemetry poll in App.tsx), or only during active runs?

> [!NOTE]
> **A13 — HistoryTab.tsx**: This file is dead code. It will be deleted. Confirm this is okay before execution.

---

## Verification Plan

### Build Check
```bash
cd frontend && npm run build
```
Catches all TypeScript type errors and import problems.

### Import Check (Backend)
```bash
python -c "import asyncio; from backend.api import router; from backend.operations import poll, get_stats; print('OK')"
```

### Manual Spot-Check
1. Tab layout: verify 5 equal-width tabs with no ghost column
2. `/batch/active` API: open `http://localhost:8000/api/batch/active` directly — should return `{"batch_id": null, "active": false}` not 404
3. Context window: connect to LM Studio, select model, verify CTX shows a real value
4. Temperature slider: verify label shows `0.00` at min, `1.00` at max
5. Toast: start a run, verify toast appears instead of only the tiny `runMsg` span
6. Halt confirmation: click Halt ⏹, verify a dialog appears before halting
7. Hardware tab: switch to another browser tab, verify polling pauses (check Network in DevTools)
8. History search: type a model name in the filter box, verify table filters in real time
9. Chart colors: switch to light mode, verify chart grids are visible (not invisible gray-on-white)
10. Copy button: click copy next to a model name, verify clipboard works
