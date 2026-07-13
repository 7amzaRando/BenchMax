import { useState, useEffect, useRef } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import * as api from '@/lib/api'
import { useToast } from '@/components/ui/toast-provider'

const PROVIDERS: { label: string; url: string; needsKey: boolean }[] = [
  { label: 'LM Studio', url: 'http://127.0.0.1:1234/v1', needsKey: false },
  { label: 'Ollama', url: 'http://127.0.0.1:11434/v1', needsKey: false },
  { label: 'OpenAI', url: 'https://api.openai.com/v1', needsKey: true },
  { label: 'OpenRouter', url: 'https://openrouter.ai/api/v1', needsKey: true },
  { label: 'Groq', url: 'https://api.groq.com/openai/v1', needsKey: true },
  { label: 'DeepSeek', url: 'https://api.deepseek.com/v1', needsKey: true },
  { label: 'AIMLAPI', url: 'https://api.aimlapi.com/v1', needsKey: true },
  { label: 'SiliconFlow', url: 'https://api.siliconflow.cn/v1', needsKey: true },
]

interface Props {
  connection: {
    apiUrl: string
    apiKey: string
    connected: boolean
    models: string[]
    selectedModel: string
    metadata: Record<string, any>
  }
  setConnection: React.Dispatch<React.SetStateAction<Props['connection']>>
  onConnect: () => Promise<any>
}

export default function ConnectionTab({ connection, setConnection, onConnect }: Props) {
  const { toast } = useToast()
  const [connecting, setConnecting] = useState(false)
  const [connectError, setConnectError] = useState('')
  const hfTokenRef = useRef('')
  const [datasets, setDatasets] = useState<api.DatasetEntry[]>([])
  const [datasetsLoading, setDatasetsLoading] = useState(false)
  const [installingAll, setInstallingAll] = useState(false)
  const [installingSingle, setInstallingSingle] = useState<Set<string>>(new Set())
  const [hfToken, setHfToken] = useState('')
  const [showExitConfirm, setShowExitConfirm] = useState(false)
  const [exitMsg, setExitMsg] = useState('')
  const [runtimesLoading, setRuntimesLoading] = useState(false)
  const [datasetFilter, setDatasetFilter] = useState('')
  const mountedRef = useRef(true)

  useEffect(() => {
    return () => {
      mountedRef.current = false
    }
  }, [])

  useEffect(() => {
    api.getHfToken().then(r => {
      if (mountedRef.current) setHfToken(r.token ?? '')
    }).catch(() => console.warn('Failed to load HF token'))
  }, [])

  async function handleConnect() {
    setConnecting(true)
    setConnectError('')
    try {
      await onConnect()
    } catch (e: any) {
      let msg = e?.message ?? 'Connection failed'
      if (!msg.startsWith('❌')) msg = '❌ ' + msg
      if (msg.includes('ConnectError') || msg.includes('fetch') || msg.includes('Failed to fetch') || msg.includes('NetworkError')) msg = '❌ Could not reach provider — check URL and ensure the server is running'
      setConnectError(msg)
    } finally {
      if (mountedRef.current) setConnecting(false)
    }
  }

  async function handleScanDatasets() {
    setDatasetsLoading(true)
    try {
      const r = await api.scanDatasets()
      if (mountedRef.current) setDatasets(r.datasets || [])
    } catch (e: any) {
      if (mountedRef.current) setDatasets([])
      toast({ title: 'Scan Failed', description: e?.message ?? 'Could not scan datasets', variant: 'error' })
    } finally {
      if (mountedRef.current) setDatasetsLoading(false)
    }
  }

  async function handleInstallAll() {
    setInstallingAll(true)
    try {
      await api.installAllDatasets(hfToken)
      await handleScanDatasets()
    } catch (e: any) {
      toast({ title: 'Install All Failed', description: e?.message ?? 'Could not install datasets', variant: 'error' })
    } finally {
      if (mountedRef.current) setInstallingAll(false)
    }
  }

  function onProviderChange(label: string) {
    const p = PROVIDERS.find(x => x.label === label)
    if (!p) return
    setConnection(prev => ({
      ...prev,
      apiUrl: p.url,
      apiKey: p.needsKey ? prev.apiKey : '',
    }))
  }

  async function handleDownloadRuntimes() {
    setRuntimesLoading(true)
    try {
      const result = await api.downloadRuntimes()
      toast({ title: 'Runtimes', description: result.status })
    } catch (e: any) {
      toast({ title: 'Runtimes Error', description: e?.message ?? 'Failed', variant: 'error' })
    } finally {
      if (mountedRef.current) setRuntimesLoading(false)
    }
  }

  async function handleExit() {
    setExitMsg('Shutting down server...')
    try {
      await fetch('/api/shutdown')
      setExitMsg('Server shut down. You may close this window.')
    } catch {
      setExitMsg('Shutdown request sent.')
    }
  }

  const currentProvider = PROVIDERS.find(p => p.url === connection.apiUrl)

  return (
    <div className="space-y-6">
      <Card variant="glow">
        <CardHeader>
          <CardTitle>Connection</CardTitle>
          <CardDescription>Configure provider and connect to a model server</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <label htmlFor="provider-select" className="text-sm font-medium">Provider</label>
            <select
              id="provider-select"
              className="flex h-10 w-full rounded-md border border-border bg-card px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              value={currentProvider?.label ?? ''}
              onChange={e => onProviderChange(e.target.value)}
            >
              <option value="" disabled>Select provider...</option>
              {PROVIDERS.map(p => (
                <option key={p.label} value={p.label}>{p.label}</option>
              ))}
            </select>
          </div>

          <div className="space-y-2">
            <label htmlFor="api-url" className="text-sm font-medium">Base URL</label>
            <Input
              id="api-url"
              placeholder="http://127.0.0.1:1234/v1"
              value={connection.apiUrl}
              onChange={e => setConnection(prev => ({ ...prev, apiUrl: e.target.value }))}
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="api-key" className="text-sm font-medium">API Key</label>
            <Input
              id="api-key"
              type="password"
              placeholder="sk-..."
              value={connection.apiKey}
              onChange={e => setConnection(prev => ({ ...prev, apiKey: e.target.value }))}
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="hf-token" className="text-sm font-medium">HuggingFace Token</label>
            <Input
              id="hf-token"
              type="password"
              placeholder="hf_..."
              value={hfToken}
              onChange={e => setHfToken(e.target.value)}
              onBlur={() => {
                if (hfToken !== hfTokenRef.current) {
                  hfTokenRef.current = hfToken
                  api.setHfToken(hfToken).catch(() => console.warn('setHfToken failed'))
                }
              }}
            />
          </div>

          <div className="flex items-center gap-3">
            <Button variant="glow" onClick={handleConnect} disabled={connecting}>
              {connecting ? 'Connecting...' : 'Connect'}
            </Button>
            <div aria-live="polite" className="inline-flex items-center gap-3">
              {connection.connected && !connectError && <Badge variant="default">🟢 Connected</Badge>}
              {connectError && <div className="text-sm px-3 py-2 rounded-md bg-red-500/10 text-red-600 dark:text-red-300 border border-red-500/50">{connectError}</div>}
              {!connection.connected && !connectError && !connecting && <span className="text-sm text-muted-foreground">Not connected</span>}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Models Table */}
      {connection.connected && connection.models.length > 0 && (
        <Card variant="glass">
          <CardHeader>
            <CardTitle>Loaded Models ({connection.models.length})</CardTitle>
            <CardDescription>Available models on the connected server</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-2 px-3 font-medium">Model ID</th>
                  </tr>
                </thead>
                <tbody>
                  {connection.models.map((m: any, i: number) => {
                    const row = typeof m === 'string' ? { id: m } : m
                    return (
                      <tr key={i} className="border-b border-border hover:bg-accent/50">
                        <td className="py-2 px-3 font-mono text-xs">{row.id}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      <Card variant="glass">
        <CardHeader>
          <CardTitle>Datasets</CardTitle>
          <CardDescription>Manage benchmark datasets</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-3">
            <Button variant="outline" size="sm" onClick={handleScanDatasets} disabled={datasetsLoading}>
              {datasetsLoading ? 'Scanning...' : 'Refresh Status'}
            </Button>
            <Button size="sm" onClick={handleInstallAll} disabled={installingAll}>
              {installingAll ? 'Installing...' : 'Install All Missing'}
            </Button>
            <Input
              id="dataset-filter"
              placeholder="Filter datasets..."
              value={datasetFilter}
              onChange={e => setDatasetFilter(e.target.value)}
              className="max-w-[220px]"
            />
          </div>

          {datasets.filter(d => d.Benchmark.toLowerCase().includes(datasetFilter.toLowerCase())).length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-2 px-3 font-medium">Benchmark</th>
                    <th className="text-left py-2 px-3 font-medium">Installed</th>
                    <th className="text-left py-2 px-3 font-medium">Samples</th>
                    <th className="text-left py-2 px-3 font-medium">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {datasets
                    .filter(d => d.Benchmark.toLowerCase().includes(datasetFilter.toLowerCase()))
                    .map((d, i) => (
                    <tr key={i} className="border-b border-border hover:bg-accent/50">
                      <td className="py-2 px-3">{d.Benchmark}</td>
                      <td className="py-2 px-3">
                        <Badge variant={d.Installed === '✅' ? 'default' : 'destructive'}>
                          {d.Installed}
                        </Badge>
                      </td>
                      <td className="py-2 px-3 text-muted-foreground">{d.Samples}</td>
                      <td className="py-2 px-3">
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={d.Installed === '✅' || installingAll || installingSingle.has(d.Benchmark)}
                          aria-label={`Install ${d.Benchmark}`}
                          onClick={async () => {
                            setInstallingSingle(prev => new Set(prev).add(d.Benchmark))
                            try {
                              await api.installDataset(d.Benchmark, hfToken)
                              await handleScanDatasets()
                            } catch (e: any) {
                              toast({ title: 'Install Failed', description: e?.message ?? `Could not install ${d.Benchmark}`, variant: 'error' })
                            }
                            setInstallingSingle(prev => { const next = new Set(prev); next.delete(d.Benchmark); return next })
                          }}
                        >
                          {installingSingle.has(d.Benchmark) ? '...' : 'Install'}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {!datasetsLoading && datasets.length === 0 && (
            <p className="text-sm text-muted-foreground">Click "Refresh Status" to view dataset status.</p>
          )}
        </CardContent>
      </Card>

      <Card variant="glass">
        <CardHeader>
          <CardTitle>Runtimes</CardTitle>
          <CardDescription>Download portable runtimes for Aider Polyglot (Go, Rust, GCC, Java, Node)</CardDescription>
        </CardHeader>
        <CardContent className="flex items-center gap-3">
          <Button variant="outline" onClick={handleDownloadRuntimes} disabled={runtimesLoading}>
            {runtimesLoading ? 'Downloading...' : 'Download Runtimes'}
          </Button>
        </CardContent>
      </Card>

      <Card variant="glass">
        <CardHeader>
          <CardTitle>Server</CardTitle>
          <CardDescription>Shutdown the BenchMax server</CardDescription>
        </CardHeader>
        <CardContent className="flex items-center gap-3">
          <Button variant="destructive" onClick={() => setShowExitConfirm(true)}>
            Exit Server
          </Button>
          {exitMsg && <span className="text-sm text-muted-foreground">{exitMsg}</span>}
          <ConfirmDialog
            open={showExitConfirm}
            onOpenChange={setShowExitConfirm}
            title="Shut Down Server?"
            description="This will stop the BenchMax server. Any running benchmarks will be interrupted."
            onConfirm={handleExit}
          />
        </CardContent>
      </Card>
    </div>
  )
}
