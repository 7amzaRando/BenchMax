export interface Command {
  name: string
  description: string
  example: string
}

export type CommandCategory = {
  name: string
  commands: Command[]
}

export const commandCategories: CommandCategory[] = [
  {
    name: 'Connection',
    commands: [
      {
        name: 'health',
        description: 'Check if the BenchMax server is running.',
        example: 'py cli.py health',
      },
      {
        name: 'connect',
        description: 'Connect to LM Studio or an OpenAI-compatible endpoint.',
        example: 'py cli.py connect --url http://127.0.0.1:1234/v1',
      },
      {
        name: 'models',
        description: 'List currently loaded models in LM Studio.',
        example: 'py cli.py models',
      },
    ],
  },
  {
    name: 'Run Benchmarks',
    commands: [
      {
        name: 'run',
        description: 'Start a single benchmark run.',
        example: 'py cli.py run --model deepseek-r1 --benchmark HumanEval --quick-test --wait',
      },
      {
        name: 'batch',
        description: 'Run multiple benchmarks sequentially on one model.',
        example: 'py cli.py batch --model qwen-2.5-coder --benchmarks HumanEval MMLU-Pro AIME --wait',
      },
      {
        name: 'status',
        description: 'Get real-time status of a running benchmark.',
        example: 'py cli.py status --run-id 42',
      },
      {
        name: 'resume',
        description: 'Resume a paused, halted, or failed run.',
        example: 'py cli.py resume --run-id 42',
      },
    ],
  },
  {
    name: 'Run Control',
    commands: [
      {
        name: 'pause',
        description: 'Pause a running benchmark at the current sample.',
        example: 'py cli.py pause --run-id 42',
      },
      {
        name: 'halt',
        description: 'Halt a run permanently (can be resumed later).',
        example: 'py cli.py halt --run-id 42',
      },
    ],
  },
  {
    name: 'Model Queue',
    commands: [
      {
        name: 'model-queue',
        description: 'Start a multi-model queue (load, benchmark, unload cycle).',
        example: 'py cli.py model-queue --models model-a model-b --benchmarks HumanEval MMLU-Pro',
      },
      {
        name: 'model-queue-active',
        description: 'Get live status of the model queue.',
        example: 'py cli.py model-queue-active',
      },
      {
        name: 'model-queue-halt',
        description: 'Stop the model queue after the current model finishes.',
        example: 'py cli.py model-queue-halt',
      },
      {
        name: 'model-queue-skip',
        description: 'Skip the current model and move to the next one.',
        example: 'py cli.py model-queue-skip',
      },
    ],
  },
  {
    name: 'Polling & Progress',
    commands: [
      {
        name: 'poll',
        description: 'Get live telemetry + run progress.',
        example: 'py cli.py poll --wait',
      },
      {
        name: 'batch-status',
        description: 'Get status of a batch run.',
        example: 'py cli.py batch-status --batch-id abc123',
      },
    ],
  },
  {
    name: 'History & Results',
    commands: [
      {
        name: 'history',
        description: 'List all past benchmark runs.',
        example: 'py cli.py history --limit 20 --model deepseek',
      },
      {
        name: 'results',
        description: 'Get detailed results for a specific run.',
        example: 'py cli.py results --run-id 42',
      },
      {
        name: 'diff',
        description: 'Generate a diff for a code task.',
        example: 'py cli.py diff --run-id 42 --task-id HumanEval/0',
      },
      {
        name: 'comparison',
        description: 'Compare accuracy, latency, and tokens across multiple runs.',
        example: 'py cli.py comparison --run-ids 42,43,44',
      },
    ],
  },
  {
    name: 'Export',
    commands: [
      {
        name: 'export',
        description: 'Export a single run as CSV or JSON.',
        example: 'py cli.py export --run-id 42 --format JSON',
      },
      {
        name: 'export-batch',
        description: 'Export batch results.',
        example: 'py cli.py export-batch --batch-id abc123',
      },
      {
        name: 'export-history',
        description: 'Export the full run history.',
        example: 'py cli.py export-history --format CSV',
      },
    ],
  },
  {
    name: 'Leaderboard',
    commands: [
      {
        name: 'leaderboard',
        description: 'View the local leaderboard.',
        example: 'py cli.py leaderboard',
      },
      {
        name: 'leaderboard-sync',
        description: 'Sync the leaderboard to Supabase.',
        example: 'py cli.py leaderboard-sync',
      },
      {
        name: 'leaderboard-settings',
        description: 'View or update leaderboard sync settings.',
        example: 'py cli.py leaderboard-settings --api-key sk-xxx',
      },
      {
        name: 'leaderboard-delete',
        description: 'Remove an entry from the leaderboard.',
        example: 'py cli.py leaderboard-delete --run-id 42 --yes',
      },
      {
        name: 'leaderboard-clear',
        description: 'Clear the entire leaderboard.',
        example: 'py cli.py leaderboard-clear --yes',
      },
    ],
  },
  {
    name: 'Datasets',
    commands: [
      {
        name: 'datasets',
        description: 'Scan installed and missing datasets.',
        example: 'py cli.py datasets',
      },
      {
        name: 'install-dataset',
        description: 'Install a specific benchmark dataset.',
        example: 'py cli.py install-dataset humaneval',
      },
      {
        name: 'install-all',
        description: 'Install all missing datasets.',
        example: 'py cli.py install-all',
      },
    ],
  },
  {
    name: 'Telemetry',
    commands: [
      {
        name: 'telemetry',
        description: 'Get current system metrics (CPU, RAM, GPU).',
        example: 'py cli.py telemetry',
      },
    ],
  },
  {
    name: 'Configuration',
    commands: [
      {
        name: 'benchmarks',
        description: 'List all registered benchmarks.',
        example: 'py cli.py benchmarks',
      },
      {
        name: 'hf-token',
        description: 'Get or set the HuggingFace token.',
        example: 'py cli.py hf-token --token hf_xxx',
      },
      {
        name: 'download-runtimes',
        description: 'Download portable runtimes for Aider Polyglot (Go, Rust, GCC, Java, Node).',
        example: 'py cli.py download-runtimes',
      },
      {
        name: 'version',
        description: 'Show CLI version.',
        example: 'py cli.py version',
      },
    ],
  },
  {
    name: 'Server',
    commands: [
      {
        name: 'serve',
        description: 'Start the BenchMax server.',
        example: 'py cli.py serve --port 8000',
      },
      {
        name: 'shutdown',
        description: 'Shut down the running server.',
        example: 'py cli.py shutdown --yes',
      },
    ],
  },
]
