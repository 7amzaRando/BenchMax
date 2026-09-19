const BASE = '/api';

const LAN_TOKEN_KEY = 'bm_lan_token';

export function getLanToken(): string | null {
  try {
    if (typeof localStorage === 'undefined') return null;
    return localStorage.getItem(LAN_TOKEN_KEY);
  } catch {
    return null;
  }
}

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const token = getLanToken();
  const res = await fetch(`${BASE}${url}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const err = await res.text().catch(() => 'Unknown error');
    throw new Error(`HTTP ${res.status}: ${err}`);
  }
  return res.json();
}

export function isLanUnauthorized(err: unknown): boolean {
  if (!(err instanceof Error)) return false;
  return err.message.includes('HTTP 401') && err.message.includes('LAN login required');
}

export interface AuthStatus {
  lan_required: boolean;
  password_set: boolean;
  authenticated: boolean;
}

export function authStatus() {
  return fetchJson<AuthStatus>('/auth/status');
}

export function authLogin(password: string) {
  return fetchJson<{ token: string }>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ password }),
  });
}

export function authSetup(password: string) {
  return fetchJson<{ status: string }>('/auth/setup', {
    method: 'POST',
    body: JSON.stringify({ password }),
  });
}

export interface ModelMetadata {
  context_length?: number | string;
  max_context_length?: number | string;
  context_window?: number | string;
  [key: string]: any;
}

export interface ConnectResult {
  status: string;
  models: { id: string; Model: string }[];
  choices: string[];
  selected: string | null;
  metadata: Record<string, ModelMetadata>;
}

export function health() {
  return fetchJson<{ status: string }>('/health');
}

export function connectLMStudio(apiUrl: string, apiKey: string = '') {
  return fetchJson<ConnectResult>('/connect', {
    method: 'POST',
    body: JSON.stringify({ api_url: apiUrl, api_key: apiKey }),
  });
}

export interface DatasetEntry {
  Benchmark: string;
  Installed: string;
  Samples: string;
  Category?: string;
  Docker?: string;
  Short?: string;
  'Full Dataset'?: string;
  Status?: string;
}

export function scanDatasets() {
  return fetchJson<{ datasets: DatasetEntry[] }>('/datasets');
}

export function installDataset(name: string, hfToken: string = '') {
  return fetchJson<{ status: string }>(`/datasets/install/${encodeURIComponent(name)}`, {
    method: 'POST',
    body: JSON.stringify({ hf_token: hfToken }),
  });
}

export function installAllDatasets(hfToken: string = '') {
  return fetchJson<{ status: string }>('/datasets/install-all', {
    method: 'POST',
    body: JSON.stringify({ hf_token: hfToken }),
  });
}

export function getHfToken() {
  return fetchJson<{ token: string }>('/hf-token');
}

export function setHfToken(token: string) {
  return fetchJson<{ status: string }>('/hf-token', {
    method: 'POST',
    body: JSON.stringify({ token }),
  });
}

export interface RunResponse {
  run_id: number | null;
  message: string;
}

export interface BatchResponse {
  run_id: number | null;
  batch_id: string | null;
  message: string;
  summary: any[];
  batch_id_display: string;
}

export function startRun(params: {
  model: string;
  benchmark: string;
  api_url: string;
  api_key?: string;
  temperature?: number;
  max_tokens?: number;
  system_prompt?: string;
  quick_test?: boolean;
  disable_repetition_detection?: boolean;
  context_length?: number;
}) {
  return fetchJson<RunResponse>('/run/start', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

export function startBatch(params: {
  model: string;
  benchmarks: string[];
  api_url: string;
  api_key?: string;
  temperature?: number;
  max_tokens?: number;
  system_prompt?: string;
  quick_test?: boolean;
  disable_repetition_detection?: boolean;
  context_length?: number;
}) {
  return fetchJson<BatchResponse>('/batch/start', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

export function pauseRun(runId: number) {
  return fetchJson<{ status: string }>(`/run/${runId}/pause`, { method: 'POST' });
}

export function resumeRun(runId: number, params: {
  api_url?: string;
  api_key?: string;
  temperature?: number;
  max_tokens?: number;
  system_prompt?: string;
  quick_test?: boolean;
  disable_repetition_detection?: boolean;
  context_length?: number;
} = {}) {
  return fetchJson<{ status: string }>(`/run/${runId}/resume`, {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

export function haltRun(runId: number) {
  return fetchJson<{ status: string }>(`/run/${runId}/halt`, { method: 'POST' });
}

export interface RunStatus {
  run_id: number;
  model_name: string;
  benchmark_name: string;
  status: string;
  current_index: number;
  total_samples: number;
  samples_completed: number;
  samples_correct: number;
  accuracy: number;
  accuracy_display: string;
  avg_tps: number;
  avg_ttft: number;
  avg_prompt_tps: number;
  total_tokens: number;
  thinking_tokens: number;
  response_tokens: number;
  repetition_warnings: number;
  safety_metrics?: any;
  notes?: string;
  created_at?: string;
}

export function getRunStatus(runId: number) {
  return fetchJson<RunStatus>(`/run/${runId}/status`);
}

export interface PollResponse {
  telemetry: {
    cpu_percent: number;
    ram_used_gb: number;
    ram_total_gb: number;
    ram_percent: number;
    gpu_available: boolean;
    gpu_name: string | null;
    gpu_load: number;
    vram_total_mb: number;
    vram_used_mb: number;
    vram_percent: number;
  };
  run_progress: {
    progress: number;
    status_md: string;
    active_task: string;
    avg_tps: number | string;
    avg_ttft: number | string;
    accuracy: string;
    token_stats: string;
  };
  batch_progress: {
    progress: number;
    status_md: string;
    eta: string;
    summary: any[];
    batch_id: string;
    completed: number;
    total: number;
    current_benchmark: string;
  };
  active_run_override?: number | null;
  live_turn?: { run_id: number; turn: number; max_turns: number; elapsed: number; ts: number } | null;
  active_runs?: { run_id: number; model_name: string; benchmark_name: string; status: string; batch_id: string | null; current_index: number; total_samples: number }[];
}

export function poll(activeRunId?: number) {
  const q = activeRunId ? `?active_run_id=${activeRunId}` : '';
  return fetchJson<PollResponse>(`/poll${q}`);
}

export function pollStreamUrl(activeRunId?: number) {
  const q = activeRunId ? `?active_run_id=${activeRunId}` : '';
  return `${BASE}/poll/stream${q}`;
}

export interface HistoryEntry {
  'Run ID': number;
  Model: string;
  Benchmark: string;
  Status: string;
  Progress: string;
  Accuracy: string;
  Needles?: string;
  'Needles Raw'?: string;
  'Avg TPS': string;
  'Avg TTFT': string;
  'Avg Prompt TPS': number;
  'Avg Tokens': number;
  'Total Tokens': number;
  'Context Length'?: string;
  'Context Length Raw'?: number | string;
  'Context K'?: string;
  Duration?: string;
  Batch?: string;
  Notes?: string;
  Created: string;
}

export function loadHistory() {
  return fetchJson<{ runs: HistoryEntry[] }>('/runs');
}

export interface RunDetails {
  summary: string;
  benchmark_name?: string;
  context_length?: number | null;
  samples: any[];
  samples_total?: number;
  sample_offset?: number;
  sample_limit?: number;
  failed_tasks: string[];
  selected_failed: string | null;
  token_chart: any[];
  ttft_histogram: any[];
  tps_histogram: any[];
  category_chart: any[];
}

export function loadRunDetails(runId: number) {
  return fetchJson<RunDetails>(`/runs/${runId}`);
}

export function getDiff(runId: number, taskId: string) {
  return fetchJson<{ html: string }>(`/runs/${runId}/diff/${encodeURIComponent(taskId)}`);
}

export interface TrustedCard {
  run_id: number;
  text: string;
  display_name: string;
  publisher: string;
  model_id: string;
  arch: string;
  quant: string;
  size_gb: string;
  max_context: number | null;
  loaded_context: number | null;
  hardware: string;
  date: string;
  benchmark: string;
  accuracy: number;
  correct: number;
  total: number;
  status: string;
  quick_test: boolean;
  avg_tps: number;
  avg_prompt_tps: number;
  avg_tokens: number;
  think_pct: number;
  resp_pct: number;
  avg_ttft: number;
}

export function loadTrustedCard(runId: number) {
  return fetchJson<TrustedCard>(`/runs/${runId}/card`);
}

export function updateRunNotes(runId: number, notes: string) {
  return fetchJson<{ status: string; notes: string }>(`/runs/${runId}/notes`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ notes }),
  });
}

export interface DepthResult {
  task_id: string;
  correct: boolean;
  depth: number;
  context_length: number;
}

export function loadDepthResults(runId: number) {
  return fetchJson<{ results: DepthResult[] }>(`/runs/${runId}/depth-results`);
}

export interface BatchSummary {
  summary: any[];
  chart: any[];
  latency_chart: any[];
}

export function loadBatchSummary(batchId: string) {
  return fetchJson<BatchSummary>(`/batch/${batchId}`);
}

export function exportBatch(batchId: string, format: string = 'CSV') {
  return fetch(`${BASE}/export/batch/${batchId}?format=${format}`);
}

export function exportHistoryLink() {
  return `${BASE}/export/history`;
}

export interface ModelQueueResponse {
  queue_id: string;
  message: string;
}

export function startModelQueue(params: {
  models: string[];
  benchmarks: string[];
  api_url: string;
  api_key?: string;
  temperature?: number;
  max_tokens?: number;
  system_prompt?: string;
  quick_test?: boolean;
  disable_repetition_detection?: boolean;
  context_length?: number;
}) {
  return fetchJson<ModelQueueResponse>('/model-queue/start', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

export function getActiveModelQueue() {
  return fetchJson<{
    queue_id: string | null;
    models: string[];
    current_model_index: number;
    total_models: number;
    current_benchmark: string;
    status: string;
    message: string;
    sample_progress?: number;
    total_samples?: number;
    accuracy?: string;
    avg_tps?: number;
    avg_ttft?: number;
    token_stats?: string;
  }>('/model-queue/active');
}

export function haltModelQueue() {
  return fetchJson<{ status: string }>('/model-queue/halt', { method: 'POST' });
}

export function skipModelQueue() {
  return fetchJson<{ status: string }>('/model-queue/skip', { method: 'POST' });
}

export interface ComparisonResult {
  accuracy: any[];
  latency: any[];
  tokens: any[];
}

export function loadComparison(runIds: string) {
  return fetchJson<ComparisonResult>(`/comparison?run_ids=${encodeURIComponent(runIds)}`);
}

export interface LeaderboardEntry {
  'Run ID': number;
  Model: string;
  Benchmark: string;
  Accuracy: string;
  Needles?: string;
  'Avg TPS': string;
  'Avg TTFT': string;
  Passed: string;
  Tokens: number;
  'Context Length'?: string;
  'Context Length Raw'?: number | string;
  'Context K'?: string;
  Date: string;
  QuickTest?: boolean;
}

export function loadLeaderboard() {
  return fetchJson<{ leaderboard: LeaderboardEntry[] }>('/leaderboard');
}

export function deleteLeaderboardEntry(runId: number) {
  return fetchJson<{ leaderboard: LeaderboardEntry[]; status: string }>(`/leaderboard/${runId}`, {
    method: 'DELETE',
  });
}

export function deleteRuns(runIds: number[]) {
  const ids = [...runIds].sort((a, b) => a - b).join(',');
  return fetchJson<{ leaderboard: LeaderboardEntry[]; status: string }>(`/runs?run_ids=${encodeURIComponent(ids)}`, {
    method: 'DELETE',
  });
}

export function clearAllHistory(confirmText: string) {
  return fetchJson<{ history: any[]; leaderboard: LeaderboardEntry[]; status: string }>('/leaderboard/clear', {
    method: 'POST',
    body: JSON.stringify({ confirm_text: confirmText }),
  });
}

export function getLeaderboardSettings() {
  return fetchJson<{ api_key: string }>('/leaderboard/settings');
}

export function saveLeaderboardSettings(apiKey: string) {
  return fetchJson<{ status: string }>('/leaderboard/settings', {
    method: 'POST',
    body: JSON.stringify({ api_key: apiKey }),
  });
}

export function syncLeaderboard(apiKey?: string) {
  return fetchJson<{ status: string }>('/leaderboard/sync', {
    method: 'POST',
    body: JSON.stringify({ api_key: apiKey || '' }),
  });
}

export interface TelemetryData {
  cpu_percent: number;
  ram_total_gb: number;
  ram_used_gb: number;
  ram_percent: number;
  gpu_available: boolean;
  gpu_name: string | null;
  vram_total_mb: number;
  vram_used_mb: number;
  vram_percent: number;
  gpu_load: number;
}

export function getTelemetry() {
  return fetchJson<TelemetryData>('/telemetry');
}

let _benchmarksCache: { data: { benchmarks: { label: string; name: string }[] }; ts: number } | null = null
const BENCHMARKS_CACHE_TTL = 5 * 60 * 1000

export function getBenchmarks() {
  if (_benchmarksCache && Date.now() - _benchmarksCache.ts < BENCHMARKS_CACHE_TTL) {
    return Promise.resolve(_benchmarksCache.data)
  }
  return fetchJson<{ benchmarks: { label: string; name: string; docker?: boolean; docker_partial?: boolean }[] }>('/benchmarks').then(data => {
    _benchmarksCache = { data, ts: Date.now() }
    return data
  })
}

export function invalidateBenchmarksCache() {
  _benchmarksCache = null
}

export function downloadRuntimes() {
  return fetchJson<{ status: string }>('/docker/build', { method: 'POST' });
}

export function getDockerStatus() {
  return fetchJson<{ available: boolean; image_exists: boolean; message: string }>('/docker/status');
}

export interface ReadinessIssue {
  benchmark: string
  kind: 'dataset' | 'runtime'
  severity?: 'blocking' | 'warning'
  message: string
  action: 'install_dataset' | 'download_runtime'
}

export function checkRunReadiness(params: { benchmarks: string[]; quick_test?: boolean }) {
  return fetchJson<{ ok: boolean; issues: ReadinessIssue[]; warnings?: ReadinessIssue[] }>('/run/check', {
    method: 'POST',
    body: JSON.stringify({ benchmarks: params.benchmarks, quick_test: params.quick_test }),
  })
}

export interface VersionInfo {
  current: string
  latest: string | null
  update_available: boolean
  html_url: string | null
  published_at: string | null
  name: string | null
  notes_excerpt: string | null
  download_url: string | null
  asset_name: string | null
  asset_size: number | null
  checked_at: number
}

export function getVersion(refresh = false) {
  return fetchJson<VersionInfo>(refresh ? '/version?refresh=true' : '/version');
}

export interface McpInfo {
  mounted: boolean
  endpoint: string
  tools: string[]
  stdio_command: string[]
  install_command: string
}

export function getMcpInfo() {
  return fetchJson<McpInfo>('/mcp/info');
}

export function installMcp(body: { clients?: string[]; url?: string; remote?: boolean; uninstall?: boolean }) {
  return fetchJson<{ status: string; action: string; configs: Record<string, string> }>('/mcp/install', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}


