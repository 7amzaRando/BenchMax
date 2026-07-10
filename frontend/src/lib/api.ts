const BASE = '/api';

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.text().catch(() => 'Unknown error');
    throw new Error(`HTTP ${res.status}: ${err}`);
  }
  return res.json();
}

export interface ConnectResult {
  status: string;
  models: { id: string; Model: string }[];
  choices: string[];
  selected: string | null;
  metadata: Record<string, any>;
  docker_status: string;
}

export function connectLMStudio(apiUrl: string, apiKey: string = '') {
  return fetchJson<ConnectResult>('/connect', {
    method: 'POST',
    body: JSON.stringify({ api_url: apiUrl, api_key: apiKey }),
  });
}

export function getConnectionMetadata() {
  return fetchJson<{ providers: Record<string, any>; benchmarks: [string, string][]; bench_names: string[]; context_length?: number; max_context_length?: number }>('/connect/metadata');
}

export function getDockerStatus() {
  return fetchJson<{ available: boolean; images: Record<string, boolean>; built_count: number }>('/docker/status');
}

export function buildDockerImages() {
  return fetchJson<{ message: string }>('/docker/build', { method: 'POST' });
}

export type BuildEventType = 'log' | 'image' | 'error' | 'done' | 'summary';

export interface BuildEvent {
  type: BuildEventType;
  data: any;
}

export function connectBuildStream(
  onEvent: (evt: BuildEvent) => void,
  onDone: () => void,
): () => void {
  const es = new EventSource('/api/docker/build/stream');

  es.addEventListener('log', (e: MessageEvent) => onEvent({ type: 'log', data: JSON.parse(e.data) }));
  es.addEventListener('image', (e: MessageEvent) => onEvent({ type: 'image', data: JSON.parse(e.data) }));
  es.addEventListener('error', (e: MessageEvent) => onEvent({ type: 'error', data: JSON.parse(e.data) }));
  es.addEventListener('done', (e: MessageEvent) => {
    onEvent({ type: 'done', data: JSON.parse(e.data) });
    es.close();
    onDone();
  });
  es.addEventListener('summary', (e: MessageEvent) => onEvent({ type: 'summary', data: JSON.parse(e.data) }));

  es.onerror = () => {
    es.close();
    onDone();
  };

  return () => es.close();
}

export interface DatasetEntry {
  Benchmark: string;
  Installed: string;
  Samples: string;
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
  quantization?: string;
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
  quantization?: string;
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
  api_url: string;
  api_key?: string;
  temperature?: number;
  max_tokens?: number;
  system_prompt?: string;
  quick_test?: boolean;
}) {
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
  total_tokens: number;
  thinking_tokens: number;
  response_tokens: number;
  repetition_warnings: number;
  safety_metrics?: any;
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
    avg_tps: string;
    avg_ttft: string;
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
}

export function poll(activeRunId?: number) {
  const q = activeRunId ? `?active_run_id=${activeRunId}` : '';
  return fetchJson<PollResponse>(`/poll${q}`);
}

export interface HistoryEntry {
  'Run ID': number;
  Model: string;
  Benchmark: string;
  Status: string;
  Progress: string;
  Accuracy: string;
  'Avg TPS': string;
  'Avg TTFT': string;
  'Avg Tokens': number;
  Duration?: string;
  Batch?: string;
  Created: string;
}

export function loadHistory() {
  return fetchJson<{ runs: HistoryEntry[] }>('/runs');
}

export interface RunDetails {
  summary: string;
  samples: any[];
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

export function loadRecentRuns() {
  return fetchJson<{ runs: string[] }>('/recent-runs');
}

export function getDiff(runId: number, taskId: string) {
  return fetchJson<{ html: string }>(`/runs/${runId}/diff/${encodeURIComponent(taskId)}`);
}

export function analyzeRun(runId: number) {
  return fetchJson<RunDetails>(`/analyze/${runId}`);
}

export interface BatchSummary {
  summary: any[];
  chart: any[];
  latency_chart: any[];
}

export function loadBatchSummary(batchId: string) {
  return fetchJson<BatchSummary>(`/batch/${batchId}`);
}

export interface ActiveBatch {
  batch_id: string | null;
  active: boolean;
  completed: number;
  total: number;
  current_benchmark: string | null;
  eta: string;
  progress: number;
}

export function getActiveBatch() {
  return fetchJson<ActiveBatch>('/batch/active');
}

export function exportResults(runId: number, format: string = 'CSV') {
  return fetch(`${BASE}/export/runs/${runId}?format=${format}`);
}

export function exportBatch(batchId: string, format: string = 'CSV') {
  return fetch(`${BASE}/export/batch/${batchId}?format=${format}`);
}

export function exportTelemetryLink() {
  return `${BASE}/export/telemetry`;
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
  quantization?: string;
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
  'Avg TPS': string;
  'Avg TTFT': string;
  Passed: string;
  Tokens: number;
  Date: string;
  Quantization: string;
}

export function loadLeaderboard() {
  return fetchJson<{ leaderboard: LeaderboardEntry[] }>('/leaderboard');
}

export function deleteLeaderboardEntry(runId: number) {
  return fetchJson<{ leaderboard: LeaderboardEntry[]; status: string }>(`/leaderboard/${runId}`, {
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

export function getTelemetryHistory() {
  return fetchJson<{ history: any[] }>('/telemetry/history');
}

export function getProviders() {
  return fetchJson<{ providers: Record<string, { url: string; needs_key: boolean }> }>('/providers');
}

export function getBenchmarks() {
  return fetchJson<{ benchmarks: { label: string; name: string }[] }>('/benchmarks');
}

export interface StatsData {
  total_runs: number;
  completed_runs: number;
  total_tokens_generated: number;
  benchmarks_run: string[];
  models_tested: string[];
  best_accuracy: {
    model: string;
    benchmark: string;
    accuracy: number;
  };
}

export function getStats() {
  return fetchJson<StatsData>('/stats');
}
