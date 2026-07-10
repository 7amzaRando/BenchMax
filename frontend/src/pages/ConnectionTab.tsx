import { useState, useEffect, useRef, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
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
  const [dockerAvailable, setDockerAvailable] = useState(false)
  const [dockerBuilding, setDockerBuilding] = useState(false)
  const [dockerBuildDone, setDockerBuildDone] = useState(false)
  const [dockerBuildMessage, setDockerBuildMessage] = useState('')
  const [dockerBuildLog, setDockerBuildLog] = useState('')
  const [dockerNotifs, setDockerNotifs] = useState<{ id: number; text: string; variant: 'ok' | 'skip' | 'failed' }[]>([])
  const notifId = useRef(0)
  const hfTokenRef = useRef('')
  const buildCleanupRef = useRef<(() => void) | null>(null)

  const addNotif = useCallback((text: string, variant: 'ok' | 'skip' | 'failed') => {
    const id = ++notifId.current
    setDockerNotifs(prev => [...prev.slice(-4), { id, text, variant }])
    setTimeout(() => setDockerNotifs(prev => prev.filter(n => n.id !== id)), 5000)
  }, [])
  const [datasets, setDatasets] = useState<api.DatasetEntry[]>([])
  const [datasetsLoading, setDatasetsLoading] = useState(false)
  const [installingAll, setInstallingAll] = useState(false)
  const [installingSingle, setInstallingSingle] = useState<Set<string>>(new Set())
  const [hfToken, setHfToken] = useState('')
  const [exitMsg, setExitMsg] = useState('')
  const mountedRef = useRef(true)

  useEffect(() => {
    return () => {
      mountedRef.current = false
      if (buildCleanupRef.current) {
        buildCleanupRef.current()
      }
    }
  }, [])

  useEffect(() => {
    api.getDockerStatus().then(r => {
      if (!mountedRef.current) return
      setDockerAvailable(r.available)
      if (r.built_count > 0) setDockerBuildDone(true)
    }).catch(() => {
      if (mountedRef.current) setDockerAvailable(false)
    })
    api.getHfToken().then(r => {
      if (mountedRef.current) setHfToken(r.token ?? '')
    }).catch(() => console.warn('Failed to load HF token'))
  }, [])

  async function handleConnect() {
    setConnecting(true)
    setConnectError('')
    try {
      await onConnect()
      api.getDockerStatus().then(r => {
        if (mountedRef.current) {
          setDockerAvailable(r.available)
          if (r.built_count > 0) setDockerBuildDone(true)
        }
      }).catch(() => console.warn('Failed to check Docker status'))
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
    } finally {
      if (mountedRef.current) setDatasetsLoading(false)
    }
  }

  async function handleInstallAll() {
    setInstallingAll(true)
    try {
      await api.installAllDatasets(hfToken)
      await handleScanDatasets()
    } catch {
      // silent
    } finally {
      if (mountedRef.current) setInstallingAll(false)
    }
  }

  const [dockerShowLog, setDockerShowLog] = useState(false)

  async function handleBuildDocker() {
    if (dockerBuildDone) {
      if (!dockerBuildLog) setDockerBuildLog('All images already built. Click again to show/hide log.')
      setDockerShowLog(prev => !prev)
      return
    }
    setDockerBuilding(true)
    setDockerBuildLog('')
    setDockerBuildMessage('')
    setDockerNotifs([])
    setDockerShowLog(true)
    try {
      const res = await api.buildDockerImages()
      if (res.message === 'Build already in progress') {
        setDockerBuildLog('Build already in progress from another tab.')
        setDockerBuilding(false)
        return
      }
      buildCleanupRef.current = api.connectBuildStream(
        (evt) => {
          if (!mountedRef.current) return
          if (evt.type === 'log') {
            setDockerBuildLog(prev => prev + evt.data.text + '\n')
          } else if (evt.type === 'image') {
            const txt = evt.data.text ?? ''
            if (txt.startsWith('[OK]')) {
              const img = txt.replace('[OK]', '').trim().split(' ')[0]
              addNotif(`Built ${img}`, 'ok')
              setDockerBuildMessage(`✓ Built ${img}`)
              toast({ title: "Docker Build", description: `Built ${img} successfully`, variant: "success" })
            } else if (txt.startsWith('[SKIP]')) {
              const img = txt.replace('[SKIP]', '').trim().split(' ')[0]
              addNotif(`${img} already exists`, 'skip')
              setDockerBuildMessage(`${img} already exists`)
            }
          } else if (evt.type === 'error') {
            addNotif('Build failed for an image', 'failed')
            setDockerBuildMessage('✗ Build failed for an image — check the log')
            toast({ title: "Docker Build Failed", description: "Check log for details", variant: "error" })
          } else if (evt.type === 'done') {
            api.getDockerStatus().then(s => {
              if (!mountedRef.current) return
              setDockerAvailable(s.available)
              if (s.built_count > 0) setDockerBuildDone(true)
            })
            setDockerBuilding(false)
            if (buildCleanupRef.current) {
              buildCleanupRef.current()
              buildCleanupRef.current = null
            }
            const code = evt.data?.exit_code
            if (code === 0) {
              setDockerBuildMessage('✓ All Docker images built successfully')
              toast({ title: "Docker Build Complete", description: "All images built successfully", variant: "success" })
            } else if (code === undefined || code === null) {
              setDockerBuildMessage('✓ Build complete')
              toast({ title: "Docker Build Complete", description: "Build complete", variant: "success" })
            } else {
              setDockerBuildMessage(`✗ Build finished with errors (exit code ${code})`)
              toast({ title: "Docker Build Finished", description: `Finished with code ${code}`, variant: "warning" })
            }
          }
        },
        () => {
          if (mountedRef.current) {
            setDockerBuilding(false)
            setDockerBuildDone(true)
          }
          buildCleanupRef.current = null
        },
      )
    } catch (e: any) {
      if (mountedRef.current) {
        setDockerBuildLog(e?.message ?? 'Build failed')
        setDockerBuilding(false)
      }
      buildCleanupRef.current = null
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
            <label className="text-sm font-medium">Provider</label>
            <select
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
            <label className="text-sm font-medium">Base URL</label>
            <Input
              placeholder="http://127.0.0.1:1234/v1"
              value={connection.apiUrl}
              onChange={e => setConnection(prev => ({ ...prev, apiUrl: e.target.value }))}
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">API Key</label>
            <Input
              type="password"
              placeholder="sk-..."
              value={connection.apiKey}
              onChange={e => setConnection(prev => ({ ...prev, apiKey: e.target.value }))}
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">HuggingFace Token</label>
            <Input
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
            {connection.connected && !connectError && <Badge variant="default">🟢 Connected</Badge>}
            {connectError && <div className="text-sm px-3 py-2 rounded-md bg-red-500/10 text-red-600 dark:text-red-300 border border-red-500/50">{connectError}</div>}
            {!connection.connected && !connectError && !connecting && <span className="text-sm text-muted-foreground">Not connected</span>}
          </div>
        </CardContent>
      </Card>

      <Card variant="glass">
        <CardHeader>
          <CardTitle>Docker</CardTitle>
          <CardDescription>Container runtime for code benchmarks</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-3">
            <Badge variant={dockerAvailable ? 'default' : 'destructive'}>
              {dockerAvailable ? 'Available' : 'Unavailable'}
            </Badge>
            <Button
              variant="outline"
              size="sm"
              onClick={handleBuildDocker}
              disabled={dockerBuilding}
            >
              {dockerBuilding ? 'Building...' : 'Build Local Images'}
            </Button>
          </div>
          {dockerNotifs.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {dockerNotifs.map(n => (
                <span key={n.id} className={
                  'text-xs px-2 py-1 rounded-full border ' +
                  (n.variant === 'ok' ? 'bg-emerald-900/40 text-emerald-300 border-emerald-700' :
                   n.variant === 'skip' ? 'bg-amber-900/40 text-amber-300 border-amber-700' :
                   'bg-red-900/40 text-red-300 border-red-700')
                }>
                  {n.variant === 'ok' ? '\u2713 ' : n.variant === 'skip' ? '\u2192 ' : '\u2717 '}
                  {n.text}
                </span>
              ))}
            </div>
          )}
          {dockerBuildMessage && (
            <div className={
              'text-sm px-3 py-2 rounded-md border ' +
              (dockerBuildMessage.startsWith('✓')
                ? 'bg-emerald-900/30 text-emerald-300 border-emerald-800 dark:text-emerald-300 text-emerald-700 dark:border-emerald-800 border-emerald-300'
                : 'bg-red-900/30 text-red-300 border-red-800 dark:text-red-300 text-red-700 dark:border-red-800 border-red-300')
            }>
              {dockerBuildMessage}
            </div>
          )}
          {dockerShowLog && (
            <pre className="text-xs text-muted-foreground bg-black/20 p-2 rounded max-h-48 overflow-y-auto whitespace-pre-wrap border border-border leading-relaxed">{dockerBuildLog || '(no log)'}</pre>
          )}
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
          </div>

          {datasets.length > 0 && (
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
                  {datasets.map((d, i) => (
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
                          onClick={async () => {
                            setInstallingSingle(prev => new Set(prev).add(d.Benchmark))
                            try {
                              await api.installDataset(d.Benchmark, hfToken)
                              await handleScanDatasets()
                            } catch { console.warn('Failed to install dataset') }
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
          <CardTitle>Server</CardTitle>
          <CardDescription>Shutdown the BenchMax server</CardDescription>
        </CardHeader>
        <CardContent className="flex items-center gap-3">
          <Button variant="destructive" onClick={handleExit}>
            Exit Server
          </Button>
          {exitMsg && <span className="text-sm text-muted-foreground">{exitMsg}</span>}
        </CardContent>
      </Card>
    </div>
  )
}
