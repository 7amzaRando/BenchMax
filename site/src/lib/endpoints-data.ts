export interface Endpoint {
  method: 'GET' | 'POST' | 'DELETE' | 'PATCH' | 'PUT'
  path: string
  description: string
  request?: string
  response: string
}

export type EndpointCategory = {
  name: string
  endpoints: Endpoint[]
}

export const endpointCategories: EndpointCategory[] = [
  {
    name: 'Connection',
    endpoints: [
      {
        method: 'POST',
        path: '/api/connect',
        description: 'Connect to LM Studio or an OpenAI-compatible endpoint and list available models.',
        request: '{ "api_url": "http://127.0.0.1:1234/v1", "api_key?" }',
        response: '{ status, models, choices, selected, metadata }',
      },
    ],
  },
  {
    name: 'Run Lifecycle',
    endpoints: [
      {
        method: 'POST',
        path: '/api/run/start',
        description: 'Start a single benchmark run.',
        request: '{ model, benchmark, temperature?, max_tokens?, system_prompt?, api_url?, api_key?, quick_test?, disable_repetition_detection?, context_length? }',
        response: '{ run_id, message }',
      },
      {
        method: 'GET',
        path: '/api/run/{id}/status',
        description: 'Get real-time status of a running benchmark.',
        response: '{ run_id, model_name, benchmark_name, status, current_index, total_samples, accuracy, avg_tps, avg_ttft, ... }',
      },
      {
        method: 'POST',
        path: '/api/run/{id}/pause',
        description: 'Pause a running benchmark. Resume from the exact sample later.',
        response: '{ status }',
      },
      {
        method: 'POST',
        path: '/api/run/{id}/resume',
        description: 'Resume a paused, halted, or failed run.',
        response: '{ status }',
      },
      {
        method: 'POST',
        path: '/api/run/{id}/halt',
        description: 'Halt a run permanently. Can be resumed from the last completed sample.',
        response: '{ status }',
      },
      {
        method: 'POST',
        path: '/api/run/check',
        description: 'Pre-flight check for missing datasets or runtimes before starting a run.',
        request: '{ benchmarks: string[], ... }',
        response: '{ ok, issues[] }',
      },
      {
        method: 'PATCH',
        path: '/api/runs/{id}/notes',
        description: 'Add or update user annotations on a completed run.',
        request: '{ notes }',
        response: '{ status, notes }',
      },
    ],
  },
  {
    name: 'Batch Runs',
    endpoints: [
      {
        method: 'POST',
        path: '/api/batch/start',
        description: 'Start multiple benchmarks sequentially for a single model.',
        request: '{ model, benchmarks[], temperature?, max_tokens?, ... }',
        response: '{ run_id, batch_id, message, summary, batch_id_display }',
      },
      {
        method: 'GET',
        path: '/api/batch/{batch_id}',
        description: 'Get summary and comparison chart for a batch run.',
        response: '{ summary, chart, latency_chart }',
      },
    ],
  },
  {
    name: 'Model Queue',
    endpoints: [
      {
        method: 'POST',
        path: '/api/model-queue/start',
        description: 'Load, benchmark, and unload multiple models sequentially.',
        request: '{ models[], benchmarks[], temperature?, max_tokens?, ... }',
        response: '{ queue_id, message }',
      },
      {
        method: 'GET',
        path: '/api/model-queue/active',
        description: 'Get live status of the model queue.',
        response: '{ queue_id, models, current_model_index, total_models, status, message }',
      },
      {
        method: 'POST',
        path: '/api/model-queue/halt',
        description: 'Stop the model queue after the current benchmark finishes.',
        response: '{ status }',
      },
      {
        method: 'POST',
        path: '/api/model-queue/skip',
        description: 'Skip the current model and move to the next one.',
        response: '{ status }',
      },
    ],
  },
  {
    name: 'History & Results',
    endpoints: [
      {
        method: 'GET',
        path: '/api/runs',
        description: 'List all benchmark runs with optional filtering.',
        response: '{ runs[], total, offset, limit }',
      },
      {
        method: 'GET',
        path: '/api/runs/{id}',
        description: 'Get detailed results for a single run.',
        response: '{ summary, samples[], token_chart, ttft_histogram, tps_histogram, category_chart, failed_tasks, selected_failed }',
      },
      {
        method: 'GET',
        path: '/api/runs/{id}/diff/{task_id}',
        description: 'Generate a diff between expected and actual code output.',
        response: '{ html }',
      },
      {
        method: 'GET',
        path: '/api/runs/{id}/depth-results',
        description: 'Get depth-based results for NIAHS (Needle-in-a-Haystack) benchmarks.',
        response: '{ results[] }',
      },
      {
        method: 'GET',
        path: '/api/comparison',
        description: 'Compare accuracy, latency, and token metrics across multiple runs.',
        response: '{ accuracy, latency, tokens }',
      },
      {
        method: 'GET',
        path: '/api/poll',
        description: 'Lightweight polling endpoint for live progress + telemetry.',
        response: '{ telemetry, run_progress, batch_progress, active_run_override }',
      },
    ],
  },
  {
    name: 'Export',
    endpoints: [
      {
        method: 'GET',
        path: '/api/export/runs/{id}',
        description: 'Export a single run as a file download.',
        response: 'File download (JSON)',
      },
      {
        method: 'GET',
        path: '/api/export/runs/{id}/markdown',
        description: 'Export a single run as a Markdown report.',
        response: 'Markdown file',
      },
      {
        method: 'GET',
        path: '/api/export/batch/{batch_id}',
        description: 'Export batch results as a file download.',
        response: 'File download (JSON)',
      },
      {
        method: 'GET',
        path: '/api/export/history',
        description: 'Export the full run history.',
        response: 'File download (JSON)',
      },
      {
        method: 'GET',
        path: '/api/export/history/markdown',
        description: 'Export the full history as a Markdown report.',
        response: 'Markdown file',
      },
      {
        method: 'GET',
        path: '/api/export/leaderboard',
        description: 'Export the leaderboard as a file.',
        response: 'File download',
      },
      {
        method: 'GET',
        path: '/api/export/comparison',
        description: 'Export a comparison report.',
        response: 'File download',
      },
    ],
  },
  {
    name: 'Leaderboard',
    endpoints: [
      {
        method: 'GET',
        path: '/api/leaderboard',
        description: 'Get the local leaderboard.',
        response: '{ leaderboard[] }',
      },
      {
        method: 'DELETE',
        path: '/api/leaderboard/{id}',
        description: 'Remove an entry from the leaderboard.',
        response: '{ leaderboard[], status }',
      },
      {
        method: 'POST',
        path: '/api/leaderboard/clear',
        description: 'Clear the entire leaderboard.',
        request: '{ confirm_text }',
        response: '{ history, leaderboard, status }',
      },
      {
        method: 'POST',
        path: '/api/leaderboard/sync',
        description: 'Sync local leaderboard to Supabase.',
        response: '{ status }',
      },
      {
        method: 'GET',
        path: '/api/leaderboard/settings',
        description: 'Get leaderboard sync settings.',
        response: '{ api_key }',
      },
      {
        method: 'POST',
        path: '/api/leaderboard/settings',
        description: 'Update leaderboard sync settings.',
        request: '{ api_key }',
        response: '{ status }',
      },
    ],
  },
  {
    name: 'Datasets',
    endpoints: [
      {
        method: 'GET',
        path: '/api/datasets',
        description: 'Scan installed and missing datasets.',
        response: '{ datasets[] }',
      },
      {
        method: 'POST',
        path: '/api/datasets/install/{name}',
        description: 'Install a specific benchmark dataset.',
        request: '{ hf_token? }',
        response: '{ status }',
      },
      {
        method: 'POST',
        path: '/api/datasets/install-all',
        description: 'Install all missing datasets.',
        request: '{ hf_token? }',
        response: '{ status }',
      },
      {
        method: 'POST',
        path: '/api/runtimes/download',
        description: 'Download portable runtimes for Aider Polyglot (Go, Rust, GCC, Java, Node).',
        response: '{ status }',
      },
    ],
  },
  {
    name: 'Telemetry',
    endpoints: [
      {
        method: 'GET',
        path: '/api/telemetry',
        description: 'Get current system metrics (CPU, RAM, GPU, VRAM).',
        response: '{ cpu_percent, ram_used_gb, ram_total_gb, gpu_name, gpu_load, gpu_temp, vram_used, vram_total }',
      },
    ],
  },
  {
    name: 'Configuration',
    endpoints: [
      {
        method: 'GET',
        path: '/api/benchmarks',
        description: 'List all registered benchmarks and their sample counts.',
        response: '{ benchmarks[] }',
      },
      {
        method: 'GET',
        path: '/api/hf-token',
        description: 'Get the stored HuggingFace token.',
        response: '{ token, set }',
      },
      {
        method: 'POST',
        path: '/api/hf-token',
        description: 'Set the HuggingFace token for gated datasets.',
        request: '{ token }',
        response: '{ status }',
      },
      {
        method: 'GET',
        path: '/api/health',
        description: 'Health check endpoint.',
        response: '{ status: "healthy", app: "BenchMax", database: "connected" }',
      },
    ],
  },
]
