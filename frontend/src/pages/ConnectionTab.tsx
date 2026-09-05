import { useState, useEffect, useRef } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import * as api from '@/lib/api'
import { useToast } from '@/components/ui/toast-provider'
import { useApp } from '@/lib/context'

const PROVIDERS: { label: string; url: string; needsKey: boolean; desc: string }[] = [
  { label: 'LM Studio',  url: 'http://127.0.0.1:1234/v1',        needsKey: false, desc: 'Local · default' },
  { label: 'Ollama',     url: 'http://127.0.0.1:11434/v1',      needsKey: false, desc: 'Local' },
  { label: 'OpenAI',     url: 'https://api.openai.com/v1',      needsKey: true,  desc: 'Cloud' },
  { label: 'OpenRouter', url: 'https://openrouter.ai/api/v1',   needsKey: true,  desc: 'Cloud · 300+ models' },
  { label: 'Groq',       url: 'https://api.groq.com/openai/v1', needsKey: true,  desc: 'Cloud · fast' },
  { label: 'DeepSeek',   url: 'https://api.deepseek.com/v1',    needsKey: true,  desc: 'Cloud' },
  { label: 'AIMLAPI',    url: 'https://api.aimlapi.com/v1',     needsKey: true,  desc: 'Cloud' },
  { label: 'SiliconFlow',url: 'https://api.siliconflow.cn/v1',  needsKey: true,  desc: 'Cloud · CN' },
]

export default function ConnectionTab({ onConnect }: { onConnect?: () => void }) {
  const { state, dispatch } = useApp()
  const { connection } = state
  const { toast } = useToast()
  const [connecting, setConnecting] = useState(false)
  const [connectError, setConnectError] = useState('')
  const hfTokenRef = useRef<string | null>(null)
  const [datasets, setDatasets] = useState<api.DatasetEntry[]>([])
  const [datasetsLoading, setDatasetsLoading] = useState(false)
  const [installingAll, setInstallingAll] = useState(false)
  const [installingSingle, setInstallingSingle] = useState<Set<string>>(new Set())
  const [hfToken, setHfToken] = useState('')
  const [hfTokenSet, setHfTokenSet] = useState(false)
  const [showExitConfirm, setShowExitConfirm] = useState(false)
  const [exitMsg, setExitMsg] = useState('')
  const [dockerLoading, setDockerLoading] = useState(false)
  const [dockerStatus, setDockerStatus] = useState<{ available: boolean; image_exists: boolean; message: string } | null>(null)
  const [datasetFilter, setDatasetFilter] = useState('')
  const mountedRef = useRef(true)

  useEffect(() => { return () => { mountedRef.current = false } }, [])

  useEffect(() => {
    api.getHfToken().then(r => {
      if (!mountedRef.current) return
      const t = r.token ?? ''
      if (t.includes('*')) { hfTokenRef.current = null; setHfToken(''); setHfTokenSet(true) }
      else { hfTokenRef.current = t || null; setHfToken(t); setHfTokenSet(!!t) }
    }).catch(() => {})
  }, [])

  async function handleConnect() {
    setConnecting(true); setConnectError('')
    try {
      const result = await api.connectLMStudio(connection.apiUrl, connection.apiKey)
      if (result.status.startsWith('Connection failed')) {
        dispatch({ type: 'SET_CONNECTION', payload: { connected: false, models: [] } })
        throw new Error(result.status)
      }
      dispatch({ type: 'SET_CONNECTION', payload: { connected: true, models: result.choices || [], selectedModel: result.selected || '', metadata: result.metadata || {} } })
      toast({ title: "Connected", description: `Connected to ${connection.apiUrl} · ${result.choices?.length ?? 0} models`, variant: "success" })
    } catch (e: any) {
      let msg = e?.message ?? 'Connection failed'
      if (!msg.startsWith('❌') && !msg.startsWith('Connection failed')) msg = '❌ ' + msg
      if (msg.includes('ConnectError') || msg.includes('Failed to fetch') || msg.includes('NetworkError')) msg = '❌ Could not reach provider — check URL and that the server is running'
      setConnectError(msg)
    } finally { if (mountedRef.current) setConnecting(false) }
  }

  async function handleScanDatasets() {
    setDatasetsLoading(true)
    try { const r = await api.scanDatasets(); if (mountedRef.current) setDatasets(r.datasets || []) }
    catch (e: any) { if (mountedRef.current) setDatasets([]); toast({ title: 'Scan failed', description: e?.message ?? 'Could not scan', variant: 'error' }) }
    finally { if (mountedRef.current) setDatasetsLoading(false) }
  }

  async function handleInstallAll() {
    setInstallingAll(true)
    try {
      const r = await api.installAllDatasets(hfTokenRef.current ?? hfToken)
      await handleScanDatasets()
      toast({ title: r.status === 'All datasets already installed.' ? 'All installed' : 'Install complete', description: r.status, variant: 'success' })
    } catch (e: any) { toast({ title: 'Install failed', description: e?.message ?? 'Could not install', variant: 'error' }) }
    finally { if (mountedRef.current) setInstallingAll(false) }
  }

  function onProviderChange(label: string) {
    const p = PROVIDERS.find(x => x.label === label)
    if (!p) return
    dispatch({ type: 'SET_CONNECTION', payload: { apiUrl: p.url, apiKey: p.needsKey ? connection.apiKey : '' } })
  }

  async function handleBuildDocker() {
    setDockerLoading(true)
    try { const r = await api.downloadRuntimes(); toast({ title: 'Docker', description: r.status }); const s = await api.getDockerStatus(); if (mountedRef.current) setDockerStatus(s) }
    catch (e: any) { toast({ title: 'Docker error', description: e?.message ?? 'Failed', variant: 'error' }) }
    finally { if (mountedRef.current) setDockerLoading(false) }
  }
  async function handleRefreshDockerStatus() {
    try { const s = await api.getDockerStatus(); if (mountedRef.current) setDockerStatus(s) } catch {}
  }
  async function handleExit() {
    setExitMsg('Shutting down server…')
    try {
      const res = await fetch('/api/shutdown', { method: 'POST' })
      if (res.ok) setExitMsg('Server shut down. You may close this window.')
      else if (res.status === 401) setExitMsg('Unauthorized — shutdown blocked.')
      else setExitMsg(`Shutdown failed: ${res.status} ${await res.text().catch(()=> '')}`)
    } catch { setExitMsg('Shutdown request failed — is the server still running?') }
  }

  const currentProvider = PROVIDERS.find(p => p.url === connection.apiUrl)
  const filteredDatasets = datasets.filter(d => !datasetFilter.trim() || d.Benchmark.toLowerCase().includes(datasetFilter.toLowerCase()))
  const installedCount = datasets.filter(d => d.Installed === '✅').length

  return (
    <div className="space-y-5 max-w-[1080px]">
      {/* hero */}
      <div className="rounded-xl border bg-gradient-to-br from-primary/10 via-secondary/5 to-transparent dark:from-primary/15 dark:via-secondary/10 p-5 flex flex-wrap gap-4 items-start">
        <div className="flex-1 min-w-[260px]">
          <h2 className="text-[18px] font-bold tracking-tight font-display">Connect your model</h2>
          <p className="text-[13px] text-muted-foreground leading-relaxed mt-1 max-w-[560px]">
            Connect to any OpenAI-compatible endpoint — local or cloud.
          </p>
        </div>
        <div className={`shrink-0 rounded-xl border px-4 py-3 min-w-[220px] ${connection.connected ? 'bg-emerald-50 border-emerald-200 dark:bg-emerald-950/30 dark:border-emerald-900' : 'bg-card border-border'}`}>
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${connection.connected ? 'bg-emerald-500 animate-pulse' : 'bg-zinc-400'}`} />
            <span className={`text-sm font-semibold ${connection.connected ? 'text-emerald-700 dark:text-emerald-300' : 'text-foreground'}`}>{connection.connected ? 'Connected' : 'Not connected'}</span>
            <span className="ml-auto text-[11px] font-mono px-1.5 py-0.5 rounded bg-black/5 dark:bg-white/10 border border-black/10 dark:border-white/10">{currentProvider?.label ?? 'Custom'}</span>
          </div>
          <div className="text-xs font-mono text-muted-foreground truncate mt-1.5">{connection.apiUrl}</div>
          {connection.connected && <div className="text-xs text-muted-foreground mt-1">{connection.models.length} models · {connection.selectedModel ? `selected: ${connection.selectedModel.slice(0,28)}` : 'no selection'}</div>}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1.15fr_0.85fr] gap-5">
        <Card>
          <CardHeader>
            <CardTitle>Provider & credentials</CardTitle>
            <CardDescription>Choose a preset or paste a custom OpenAI-compatible base URL (must end with <span className="font-mono">/v1</span>).</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {PROVIDERS.map(p => {
                const active = currentProvider?.label === p.label
                return (
                  <button
                    key={p.label}
                    onClick={() => onProviderChange(p.label)}
                    className={`text-left rounded-lg border px-3 py-2.5 transition-colors ${active ? 'bg-primary text-white border-primary shadow-sm' : 'bg-card hover:bg-muted border-border hover:border-[var(--border-strong)]'}`}
                  >
                    <div className={`text-xs font-semibold leading-none ${active ? 'text-white' : 'text-foreground'}`}>{p.label}</div>
                    <div className={`text-[11px] leading-none mt-1 font-mono ${active ? 'text-white/80' : 'text-muted-foreground'}`}>{p.desc}</div>
                  </button>
                )
              })}
            </div>

            <div className="space-y-3 pt-1">
              <div className="space-y-1.5">
                <label htmlFor="api-url" className="text-xs font-semibold tracking-wide uppercase text-muted-foreground">Base URL</label>
                <Input id="api-url" value={connection.apiUrl} onChange={e => dispatch({ type: 'SET_CONNECTION', payload: { apiUrl: e.target.value } })} placeholder="http://127.0.0.1:1234/v1" className="font-mono text-[13px]" />
                <p className="text-[11px] text-muted-foreground">LM Studio default is <span className="font-mono">http://127.0.0.1:1234/v1</span> · Ollama <span className="font-mono">http://127.0.0.1:11434/v1</span></p>
              </div>
              <div className="space-y-1.5">
                <label htmlFor="api-key" className="text-xs font-semibold tracking-wide uppercase text-muted-foreground">API key <span className="normal-case font-normal text-muted-foreground/70">(only for cloud providers)</span></label>
                <Input id="api-key" type="password" value={connection.apiKey} onChange={e => dispatch({ type: 'SET_CONNECTION', payload: { apiKey: e.target.value } })} placeholder="sk-…  (leave empty for local)" className="font-mono text-[13px]" />
              </div>
              <div className="space-y-1.5">
                <label htmlFor="hf-token" className="text-xs font-semibold tracking-wide uppercase text-muted-foreground flex items-center gap-2">
                  Hugging Face token <span className="normal-case font-normal text-muted-foreground/70">for gated datasets</span>
                  {hfTokenSet && <span className="text-[11px] px-1.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-950/30 dark:text-emerald-300 dark:border-emerald-800">✓ Saved</span>}
                </label>
                <Input
                  id="hf-token" type="password" value={hfToken}
                  placeholder={hfTokenSet ? 'Saved — type to replace' : 'hf_…'}
                  onChange={e => setHfToken(e.target.value)}
                  onBlur={() => {
                    const v = hfToken
                    if (v === (hfTokenRef.current ?? '') || v.includes('*')) return
                    hfTokenRef.current = v || null; setHfTokenSet(!!v)
                    api.setHfToken(v).catch(()=>{})
                  }}
                  className="font-mono text-[13px]"
                />
              </div>

              <div className="flex items-center gap-3 pt-1">
                <Button onClick={handleConnect} disabled={connecting} size="lg" className="min-w-[132px]">
                  {connecting ? 'Connecting…' : connection.connected ? 'Reconnect' : 'Connect'}
                </Button>
                {connection.connected && !connectError && <span className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">✓ Connected — {connection.models.length} models</span>}
                {connectError && <span className="text-xs px-3 py-2 rounded-lg bg-red-50 text-red-700 border border-red-200 dark:bg-red-950/30 dark:text-red-300 dark:border-red-900 max-w-[360px] leading-relaxed">{connectError}</span>}
                {!connection.connected && !connectError && !connecting && <span className="text-xs text-muted-foreground">Pick a provider above, then Connect.</span>}
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-5">
          <Card>
            <CardHeader>
              <CardTitle>Loaded models</CardTitle>
              <CardDescription>{connection.connected ? `${connection.models.length} models on this endpoint` : 'Connect to see models.'}</CardDescription>
            </CardHeader>
            <CardContent>
              {connection.connected && connection.models.length > 0 ? (
                <div className="rounded-lg border divide-y max-h-[220px] overflow-auto">
                  {connection.models.map((m: any, i: number) => {
                    const id = typeof m === 'string' ? m : m.id
                    const active = connection.selectedModel === id
                    return (
                      <div key={i} className={`flex items-center gap-2 px-3 py-2 text-xs font-mono ${active ? 'bg-primary/10 text-primary' : 'hover:bg-muted/60'}`}>
                        <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${active ? 'bg-primary' : 'bg-muted-foreground/40'}`} />
                        <span className="truncate">{id}</span>
                        {active && <Badge variant="soft" className="ml-auto text-[10px]">Selected</Badge>}
                      </div>
                    )
                  })}
                </div>
              ) : (
                <div className="rounded-lg border border-dashed p-6 text-center">
                  <div className="text-sm font-medium">No models yet</div>
                  <div className="text-xs text-muted-foreground mt-1">Connect to LM Studio/Ollama. For LM Studio, load a model first — then click Connect.</div>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Docker sandbox</CardTitle>
              <CardDescription>Required for 5 code benchmarks: HumanEval, BigCodeBench ×2, LiveCodeBench, Aider Polyglot. Image is <span className="font-mono">benchmax-sandbox</span>.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center gap-2 flex-wrap">
                {dockerStatus ? (
                  <Badge variant={dockerStatus.image_exists ? 'success' : dockerStatus.available ? 'warning' : 'danger'}>
                    {dockerStatus.image_exists ? '● Image ready' : dockerStatus.available ? '○ Docker available — image not built' : '✕ Docker unavailable'}
                  </Badge>
                ) : (
                  <Badge variant="outline">Unknown — click Refresh</Badge>
                )}
                <span className="text-xs text-muted-foreground">{dockerStatus?.message ?? ''}</span>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={handleRefreshDockerStatus}>Refresh</Button>
                <Button variant="soft" size="sm" onClick={handleBuildDocker} disabled={dockerLoading || !!dockerStatus?.image_exists}>
                  {dockerLoading ? 'Building…' : dockerStatus?.image_exists ? 'Image ready' : 'Build image'}
                </Button>
              </div>
              <p className="text-[11px] leading-relaxed text-muted-foreground">Build streams logs via SSE. 6 languages inside: Python 3.11, Node 20, GCC, Java 17, Go 1.22, Rust 1.75 — isolated with <span className="font-mono">--cap-drop ALL --network none</span>.</p>
            </CardContent>
          </Card>
        </div>
      </div>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle>Datasets</CardTitle>
              <CardDescription>
                {datasets.length ? `${installedCount}/${datasets.length} installed` : 'Scan to see install status for all 30 benchmarks. NIAHS needs 2 files (dataset + corpus).'} · Filter and install per-benchmark or all at once.
              </CardDescription>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={handleScanDatasets} disabled={datasetsLoading}>{datasetsLoading ? 'Scanning…' : 'Scan'}</Button>
              <Button size="sm" onClick={handleInstallAll} disabled={installingAll}>{installingAll ? 'Installing…' : 'Install all missing'}</Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <Input placeholder="Filter by benchmark name…" value={datasetFilter} onChange={e => setDatasetFilter(e.target.value)} className="max-w-[320px]" />
          {filteredDatasets.length > 0 ? (
            <div className="overflow-auto rounded-lg border">
              <table className="w-full text-sm">
                <thead className="bg-muted/70 text-[11px] tracking-widest uppercase text-muted-foreground">
                  <tr className="border-b">
                    <th className="text-left px-3 py-2.5 font-semibold">Benchmark</th>
                    <th className="text-left px-3 py-2.5 font-semibold hidden sm:table-cell">Category</th>
                    <th className="text-left px-3 py-2.5 font-semibold">Status</th>
                    <th className="text-left px-3 py-2.5 font-semibold hidden md:table-cell">Samples</th>
                    <th className="text-center px-3 py-2.5 font-semibold">Docker</th>
                    <th className="text-left px-3 py-2.5 font-semibold">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {filteredDatasets.map((d, i) => (
                    <tr key={i} className="hover:bg-muted/40">
                      <td className="px-3 py-2.5 font-medium text-[13px]">{d.Benchmark}</td>
                      <td className="px-3 py-2.5 hidden sm:table-cell"><Badge variant="outline" className="text-[11px]">{(d as any).Category || '—'}</Badge></td>
                      <td className="px-3 py-2.5">
                        <Badge variant={d.Installed === '✅' ? 'success' : 'danger'} className="font-mono text-[11px]">
                          {d.Installed === '✅' ? 'Installed' : 'Missing'}
                        </Badge>
                      </td>
                      <td className="px-3 py-2.5 font-mono text-xs text-muted-foreground hidden md:table-cell">{d.Samples}</td>
                      <td className="px-3 py-2.5 text-center text-xs">{(d as any).Docker ? '🐳' : '—'}</td>
                      <td className="px-3 py-2.5">
                        <Button
                          variant={d.Installed === '✅' ? 'outline' : 'soft'}
                          size="xs"
                          disabled={d.Installed === '✅' || installingAll || installingSingle.has(d.Benchmark)}
                          onClick={async () => {
                            setInstallingSingle(s => new Set(s).add(d.Benchmark))
                            try {
                              const r = await api.installDataset(d.Benchmark, hfTokenRef.current ?? hfToken)
                              await handleScanDatasets()
                              const fail = r.status.includes('failed') || r.status.includes('Error') || r.status.includes('timed out')
                              toast({ title: fail ? 'Install failed' : 'Installed', description: r.status, variant: fail ? 'error' : 'success' })
                            } catch (e: any) { toast({ title: 'Install failed', description: e?.message ?? `Could not install ${d.Benchmark}`, variant: 'error' }) }
                            setInstallingSingle(s => { const n = new Set(s); n.delete(d.Benchmark); return n })
                          }}
                        >
                          {installingSingle.has(d.Benchmark) ? '…' : d.Installed === '✅' ? 'Installed' : 'Install'}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="rounded-lg border border-dashed p-8 text-center">
              <div className="text-sm font-medium">{datasetsLoading ? 'Scanning…' : 'No datasets scanned yet'}</div>
              <div className="text-xs text-muted-foreground mt-1">Click <span className="font-mono">Scan</span> to check which of the 28 benchmark datasets are present in <span className="font-mono">data/</span>.</div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Server</CardTitle>
          <CardDescription>Shutdown is token-protected. The token is printed in the server logs at startup.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-3">
          <Button variant="destructive" size="sm" onClick={() => setShowExitConfirm(true)}>Shut down server</Button>
          {exitMsg && <span className="text-xs px-3 py-2 rounded-lg border bg-muted text-muted-foreground max-w-[560px]">{exitMsg}</span>}
          <span className="ml-auto text-xs text-muted-foreground hidden sm:inline">Tip: <kbd className="px-1 py-0.5 rounded border bg-muted font-mono text-[11px]">Ctrl+.</kbd> also halts the active run.</span>
          <ConfirmDialog open={showExitConfirm} onOpenChange={setShowExitConfirm} title="Shut down server?" description="This stops BenchMax. Any running benchmark will be interrupted. You will need to restart it manually." onConfirm={handleExit} />
        </CardContent>
      </Card>
    </div>
  )
}
