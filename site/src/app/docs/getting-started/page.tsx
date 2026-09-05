import type { Metadata } from 'next'
import GradientText from '@/components/shared/GradientText'
import Badge from '@/components/shared/Badge'

export const metadata: Metadata = {
  title: 'Getting Started',
  description: 'Install BenchMax and run your first benchmark in under 5 minutes.',
}

function CodeBlock({ children }: { children: string }) {
  return (
    <div className="code-surface rounded-xl p-4 font-mono text-sm leading-relaxed overflow-x-auto">
      <pre className="text-muted-fg whitespace-pre">{children}</pre>
    </div>
  )
}

function Step({ number, title, children }: { number: number; title: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-4">
      <div className="shrink-0 w-8 h-8 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center">
        <span className="text-sm font-bold text-primary">{number}</span>
      </div>
      <div className="flex-1 min-w-0">
        <h3 className="text-lg font-semibold tracking-tight mb-3">{title}</h3>
        {children}
      </div>
    </div>
  )
}

export default function GettingStartedPage() {
  return (
    <div>
      <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight mb-4">
        <GradientText as="span">Getting Started</GradientText>
      </h1>
      <p className="text-lg text-muted-fg mb-8 max-w-2xl">Install BenchMax and run your first benchmark in under 5 minutes. Windows, macOS, or Linux.</p>

      <div className="mb-10">
        <h2 className="text-2xl font-bold tracking-tight mb-4">Requirements</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {[
            { k: 'Python 3.11+', v: 'Backend runtime' },
            { k: 'Node.js 18+', v: 'Frontend build' },
            { k: 'Docker Desktop', v: 'For 5 code benchmarks (benchmax-sandbox)' },
            { k: 'API endpoint', v: 'LM Studio / Ollama / OpenAI / any OpenAI-compatible' },
          ].map(r => (
            <div key={r.k} className="rounded-xl bg-card border border-border p-4">
              <p className="font-semibold text-sm">{r.k}</p>
              <p className="text-xs text-muted-fg mt-1">{r.v}</p>
            </div>
          ))}
        </div>
        <p className="text-xs text-muted-fg mt-3">Without Docker, 23 benchmarks run fully. The 5 code benchmarks (HumanEval, BigCodeBench ×2, LiveCodeBench, Aider Polyglot) return a clear error with build instructions.</p>
      </div>

      <div className="space-y-8 mb-10">
        <h2 className="text-2xl font-bold tracking-tight">Installation</h2>

        <Step number={1} title="Clone the repository">
          <CodeBlock>{`git clone https://github.com/7amzaRando/BenchMax.git
cd BenchMax`}</CodeBlock>
        </Step>

        <Step number={2} title="Create a virtual environment & install Python deps">
          <CodeBlock>{`python -m venv .venv
.venv\\Scripts\\activate          # Windows
# source .venv/bin/activate       # macOS / Linux
.venv\\Scripts\\pip install -r backend/requirements.txt`}</CodeBlock>
        </Step>

        <Step number={3} title="Build the frontend">
          <CodeBlock>{`cd frontend
npm install
npm run build
cd ..`}</CodeBlock>
          <p className="text-xs text-muted-fg mt-2">Without this, the API works but the dashboard at <code className="text-foreground">/</code> shows a 404.</p>
        </Step>

        <Step number={4} title="Optional: build the Docker sandbox (for code benchmarks)">
          <CodeBlock>{`# From the dashboard: Run tab → Build Docker Image
# Or via API:  POST http://localhost:8000/api/docker/build
# Check:       GET  http://localhost:8000/api/docker/status`}</CodeBlock>
        </Step>

        <Step number={5} title="Optional: install datasets">
          <CodeBlock>{`# Via the dashboard: Connection tab → Datasets → Install All
# Or individually:
.venv\\Scripts\\python scripts/fetch_humaneval.py
.venv\\Scripts\\python scripts/fetch_mmlu_pro.py
# …or:  POST /api/datasets/install-all`}</CodeBlock>
        </Step>
      </div>

      <div className="mb-10">
        <h2 className="text-2xl font-bold tracking-tight mb-4">First run</h2>
        <div className="space-y-6">
          <Step number={6} title="Start LM Studio (or your provider) and load a model">
            <p className="text-sm text-muted-fg leading-relaxed">
              Open LM Studio, download any model and click Load. The OpenAI-compatible server starts at <Badge variant="primary">http://127.0.0.1:1234/v1</Badge>. Ollama, OpenAI, Groq, and others work the same way; just change the URL.
            </p>
          </Step>
          <Step number={7} title="Start BenchMax">
            <CodeBlock>{`.venv\\Scripts\\uvicorn backend.main:app --port 8000
# → http://localhost:8000  (or run.bat on Windows)`}</CodeBlock>
          </Step>
          <Step number={8} title="Run a benchmark">
            <p className="text-sm text-muted-fg leading-relaxed">
              Open <Badge variant="primary">http://localhost:8000</Badge> → <strong className="text-foreground">Run Benchmark</strong> → pick e.g. HumanEval → Start. Live accuracy, TPS and TTFT stream in. Or via CLI:
            </p>
            <div className="mt-3"><CodeBlock>{`py cli.py run --benchmark HumanEval --model <model-id> --wait`}</CodeBlock></div>
          </Step>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="rounded-xl bg-card border border-border p-5">
          <h3 className="font-semibold">Quick Test mode</h3>
          <p className="text-sm text-muted-fg mt-1 leading-relaxed">Every benchmark has a <code className="text-primary">quick_test</code> toggle that loads a 5-sample mini dataset. Use it to validate the pipeline before burning through 12k MMLU-Pro items.</p>
        </div>
        <div className="rounded-xl bg-card border border-border p-5">
          <h3 className="font-semibold">Standalone .exe</h3>
          <p className="text-sm text-muted-fg mt-1 leading-relaxed"><code className="text-foreground">build.bat</code> produces <code className="text-foreground">dist/BenchMax.exe</code> via PyInstaller (frontend + mini datasets bundled; DB in %LOCALAPPDATA%).</p>
        </div>
      </div>
    </div>
  )
}
