import type { Metadata } from 'next'
import GradientText from '@/components/shared/GradientText'
import Badge from '@/components/shared/Badge'
import { endpointCategories, type Endpoint } from '@/lib/endpoints-data'

export const metadata: Metadata = {
  title: 'API Reference',
  description: 'Full REST API reference for BenchMax: 43 endpoints (45 including /health & /shutdown) across connection, runs, batch, model queue, export, leaderboard, datasets and telemetry.',
}

const METHOD_BADGES: Record<string, 'success' | 'primary' | 'danger' | 'warning'> = {
  GET: 'success',
  POST: 'primary',
  DELETE: 'danger',
  PATCH: 'warning',
  PUT: 'primary',
}

function EndpointRow({ endpoint }: { endpoint: Endpoint }) {
  return (
    <div className="rounded-xl border border-border bg-card p-4 hover:border-primary/15 transition-colors">
      <div className="flex items-center gap-3 mb-2 flex-wrap">
        <Badge variant={METHOD_BADGES[endpoint.method]} className="font-mono text-xs">{endpoint.method}</Badge>
        <code className="text-sm text-foreground font-mono font-medium break-all">{endpoint.path}</code>
      </div>
      <p className="text-sm text-muted-fg mb-2 leading-relaxed">{endpoint.description}</p>
      {endpoint.request && (
        <div className="mb-2">
          <span className="text-xs font-semibold tracking-widest uppercase text-muted-fg">Request</span>
          <div className="mt-1 rounded-lg bg-background border border-border px-3 py-2 font-mono text-xs text-muted-fg overflow-x-auto">{endpoint.request}</div>
        </div>
      )}
      <div>
        <span className="text-xs font-semibold tracking-widest uppercase text-muted-fg">Response</span>
        <div className="mt-1 rounded-lg bg-background border border-border px-3 py-2 font-mono text-xs text-muted-fg overflow-x-auto">{endpoint.response}</div>
      </div>
    </div>
  )
}

export default function ApiReferencePage() {
  const totalEndpoints = endpointCategories.reduce((sum, cat) => sum + cat.endpoints.length, 0)
  return (
    <div>
      <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight mb-4"><GradientText as="span">API Reference</GradientText></h1>
      <p className="text-lg text-muted-fg max-w-2xl">
        {totalEndpoints} REST endpoints (43 via <code className="text-foreground">api.py</code> + <code className="text-foreground">GET /api/health</code> & <code className="text-foreground">POST /api/shutdown</code> in <code className="text-foreground">main.py</code>). Served by FastAPI at <code className="text-primary">http://localhost:8000</code>. Swagger at <code className="text-primary">/docs</code>.
      </p>
      <p className="text-sm text-muted-fg mt-3 mb-10">Use the <Badge variant="primary">CLI</Badge> (<code className="text-foreground">cli.py</code>, 38 commands) or call the REST API directly.</p>
      <div className="space-y-10">
        {endpointCategories.map(cat => (
          <section key={cat.name}>
            <h2 className="text-xl font-bold tracking-tight">{cat.name}</h2>
            <p className="text-sm text-muted-fg mb-3">{cat.endpoints.length} endpoint{cat.endpoints.length !== 1 ? 's' : ''}</p>
            <div className="space-y-3">
              {cat.endpoints.map(ep => <EndpointRow key={`${ep.method}-${ep.path}`} endpoint={ep} />)}
            </div>
          </section>
        ))}
      </div>
    </div>
  )
}
