import type { Metadata } from 'next'
import GradientText from '@/components/shared/GradientText'
import Badge from '@/components/shared/Badge'

export const metadata: Metadata = {
  title: 'Configuration',
  description: 'Environment variables, provider presets, Docker sandbox and database for BenchMax.',
}

function CodeBlock({ children }: { children: string }) {
  return (
    <div className="code-surface rounded-xl p-4 font-mono text-sm leading-relaxed overflow-x-auto">
      <pre className="text-muted-fg whitespace-pre">{children}</pre>
    </div>
  )
}

function ConfigRow({ name, default: d, description }: { name: string; default?: string; description: string }) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-3 py-3 border-b border-border last:border-0">
      <code className="text-sm text-primary font-mono font-medium shrink-0 sm:w-52">{name}</code>
      {d !== undefined && <Badge variant="outline" className="w-fit text-xs font-mono shrink-0">default: {d}</Badge>}
      <p className="text-sm text-muted-fg">{description}</p>
    </div>
  )
}

export default function ConfigurationPage() {
  return (
    <div>
      <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight mb-4"><GradientText as="span">Configuration</GradientText></h1>
      <p className="text-lg text-muted-fg mb-10 max-w-2xl">Sensible defaults. Override what you need.</p>

      <section className="mb-10">
        <h2 className="text-2xl font-bold tracking-tight mb-4">Environment variables</h2>
        <p className="text-sm text-muted-fg mb-3">Shell env or <code className="text-foreground">.env</code> in project root. CLI also respects <code className="text-primary">.cli_config.json</code> written by <code className="text-foreground">py cli.py connect</code>.</p>
        <div className="rounded-xl bg-card border border-border p-4">
          <ConfigRow name="BENCHMAX_URL" default="http://127.0.0.1:8000" description="Server URL for CLI (overridden by --server)." />
          <ConfigRow name="BENCHMAX_HOST" default="127.0.0.1" description="Bind address for run.bat. Set to 0.0.0.0 to share on the LAN (then set a LAN password)." />
          <ConfigRow name="BENCHMAX_WORKERS" default="1" description="Single-process only — any other value logs a startup warning (run state lives in memory)." />
          <ConfigRow name="HF_HOME" description="Override HuggingFace cache directory." />
          <ConfigRow name="HF_TOKEN" description="HuggingFace token for gated datasets. Also available via POST /api/hf-token or cli hf-token." />
          <ConfigRow name="LOCALAPPDATA" description="Windows: %LOCALAPPDATA%\\BenchMax holds DB in .exe builds." />
          <ConfigRow name="XDG_CACHE_HOME" description="Linux/macOS fallback for DB cache dir." />
          <ConfigRow name="BENCHMAX_LOG_LEVEL" default="INFO" description="Log level (DEBUG / INFO / WARNING)." />
          <ConfigRow name="SUPABASE_URL / SUPABASE_KEY" description="Online leaderboard sync. Also available via POST /api/leaderboard/settings." />
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-2xl font-bold tracking-tight mb-4">LAN password</h2>
        <p className="text-sm text-muted-fg mb-4">
          Sharing the server on your network (<code className="text-foreground">py cli.py serve --host 0.0.0.0</code>) shows visitors an un-skippable login screen. Your own browser on the server machine keeps working with no login. Set the password once from the server machine (<code className="text-foreground">py cli.py set-password</code> or <code className="text-foreground">POST /api/auth/setup</code>); visitors sign in via <code className="text-foreground">POST /api/auth/login</code> and get a Bearer token valid for 30 days. Forgotten password: stop the server, delete <code className="text-foreground">records/.lan_password</code>, and set a new one.
        </p>
      </section>

      <section className="mb-10">
        <h2 className="text-2xl font-bold tracking-tight mb-4">MCP (AI tool access)</h2>
        <p className="text-sm text-muted-fg mb-4">
          BenchMax speaks the Model Context Protocol, so tools like Claude, OpenCode, Cursor, and VS Code can list benchmarks, start runs, and read results directly. The MCP server runs as a stdio process or via Streamable HTTP at <code className="text-foreground">/mcp</code> (LAN-gated like the REST API).
        </p>
        <div className="space-y-3">
          <div className="rounded-xl bg-card border border-border p-4">
            <h3 className="font-semibold text-sm mb-1">One-command install</h3>
            <CodeBlock>{`py cli.py install-mcp --client claude
py cli.py install-mcp --client opencode
py cli.py install-mcp --client cursor
py cli.py install-mcp --client vscode
py cli.py install-mcp --client all`}</CodeBlock>
          </div>
          <div className="rounded-xl bg-card border border-border p-4">
            <h3 className="font-semibold text-sm mb-1">What it provides</h3>
            <p className="text-sm text-muted-fg">16 tools: list benchmarks, start runs, check status, pause/halt/resume, get results, compare runs, view history, check telemetry, manage the provider endpoint, list models, check health, manage webhooks. The Settings tab shows live MCP status with copy-paste config snippets for each app.</p>
          </div>
          <div className="rounded-xl bg-card border border-border p-4">
            <h3 className="font-semibold text-sm mb-1">Manual stdio usage</h3>
            <CodeBlock>{`# Run directly via stdio:
python mcp_server.py

# Or via HTTP (server must be running):
# Connect to http://localhost:8000/mcp`}</CodeBlock>
          </div>
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-2xl font-bold tracking-tight mb-4">Provider presets</h2>
        <p className="text-sm text-muted-fg mb-4">8 built-ins (any OpenAI-compatible endpoint works; just set the URL).</p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
          {[
            { name: 'LM Studio', url: 'http://127.0.0.1:1234/v1', local: true },
            { name: 'Ollama', url: 'http://127.0.0.1:11434/v1', local: true },
            { name: 'OpenAI', url: 'https://api.openai.com/v1', local: false },
            { name: 'OpenRouter', url: 'https://openrouter.ai/api/v1', local: false },
            { name: 'Groq', url: 'https://api.groq.com/openai/v1', local: false },
            { name: 'DeepSeek', url: 'https://api.deepseek.com/v1', local: false },
            { name: 'AIMLAPI', url: 'https://api.aimlapi.com/v1', local: false },
            { name: 'SiliconFlow', url: 'https://api.siliconflow.cn/v1', local: false },
          ].map(p => (
            <div key={p.name} className="rounded-xl bg-card border border-border p-4">
              <div className="flex items-center gap-2 mb-1">
                <h3 className="font-semibold text-sm">{p.name}</h3>
                <Badge variant={p.local ? 'success' : 'outline'} className="text-[10px]">{p.local ? 'Local' : 'Cloud'}</Badge>
              </div>
              <code className="text-xs text-muted-fg font-mono break-all">{p.url}</code>
            </div>
          ))}
        </div>
        <div className="rounded-xl bg-card border border-border p-4">
          <h3 className="font-semibold text-sm mb-1">Custom endpoint</h3>
          <p className="text-xs text-muted-fg mb-3">Any OpenAI-compatible chat completions URL works. Set it in the Connection tab or:</p>
          <CodeBlock>{`py cli.py connect --url http://my-server:8080/v1`}</CodeBlock>
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-2xl font-bold tracking-tight mb-4">Docker sandbox</h2>
        <p className="text-sm text-muted-fg mb-4">
          5 benchmarks require Docker. 25 run without it. (LiveBench is mixed: only its coding subset needs the sandbox.) The image is <code className="text-foreground">benchmax-sandbox</code> (Python 3.11 + Node 20 + GCC + Java 17 + Go 1.22 + Rust 1.75, ~6.14 GB, <code className="text-foreground">--cap-drop ALL</code>, network blocked except Aider Polyglot which needs it for package downloads). Clear error if Docker is unavailable.
        </p>
        <div className="space-y-3">
          <div className="rounded-xl bg-card border border-border p-4">
            <h3 className="font-semibold text-sm mb-1">Which benchmarks need Docker?</h3>
            <p className="text-sm text-muted-fg">HumanEval, BigCodeBench, BigCodeBench-Hard, LiveCodeBench, Aider Polyglot. Everything else (MMLU-Pro, IFEval, BFCL, GAIA, …) is host-local.</p>
          </div>
          <div className="rounded-xl bg-card border border-border p-4">
            <h3 className="font-semibold text-sm mb-2">Build & check</h3>
            <CodeBlock>{`POST /api/docker/build   → builds benchmax-sandbox
GET  /api/docker/status  → { available, image_exists, message }
# or dashboard: Run tab → Build Docker Image`}</CodeBlock>
          </div>
          <div className="rounded-xl bg-card border border-border p-4">
            <h3 className="font-semibold text-sm mb-1">Config flags (backend/config.py)</h3>
            <p className="text-sm text-muted-fg"><code className="text-foreground">SANDBOX_USE_DOCKER=True</code> (Docker-only code execution in the benchmax-sandbox image; containers drop all capabilities, and every benchmark runs network-blocked except Aider Polyglot).</p>
          </div>
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-bold tracking-tight mb-4">Database</h2>
        <p className="text-sm text-muted-fg mb-3">SQLite + WAL, auto-created at <code className="text-foreground">records/benchmax.db</code> (or <code className="text-foreground">%LOCALAPPDATA%/BenchMax</code> in .exe). No migrations: SQLAlchemy creates the schema on startup.</p>
        <div className="rounded-xl bg-card border border-border p-4">
          <ul className="text-sm text-muted-fg space-y-1.5 list-disc list-inside">
            <li>WAL via <code className="text-foreground">engine.connect()</code> (autocommit).</li>
            <li>Adaptive write batching: every 5 samples (25 for 500+ sample suites); DB refresh at batch boundaries; in-memory halt check every sample.</li>
            <li>Live progress display updates every sample from in-memory rolling stats (accuracy, speed, token totals); the DB stays the source of truth.</li>
            <li>Dataset caching via <code className="text-foreground">BaseBenchmark._dataset_cache</code> (class-level).</li>
            <li>Run statuses: PENDING → RUNNING → PAUSED → COMPLETED / FAILED / HALTED.</li>
          </ul>
        </div>
      </section>
    </div>
  )
}
