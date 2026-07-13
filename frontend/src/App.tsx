import { useState, useEffect, useCallback, useRef, lazy, Suspense, ReactNode } from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

function LoadingFallback({ children }: { children: ReactNode }) {
  return <Suspense fallback={<div className="p-8 text-center text-muted-foreground">Loading...</div>}>{children}</Suspense>
}
const ConnectionTab = lazy(() => import('@/pages/ConnectionTab'))
const RunBenchmarkTab = lazy(() => import('@/pages/RunBenchmarkTab'))
const HardwareTab = lazy(() => import('@/pages/HardwareTab'))
const HistoryResultsTab = lazy(() => import('@/pages/HistoryResultsTab'))
const LeaderboardTab = lazy(() => import('@/pages/LeaderboardTab'))
import Background from '@/components/ui/background'
import { Zap, Play, Activity, BarChart3, Trophy, Sun, Moon } from '@/components/ui/icons'
import * as api from '@/lib/api'
import { ToastProvider, useToast } from '@/components/ui/toast-provider'
import React from 'react'

class ErrorBoundary extends React.Component<{children: React.ReactNode}, {hasError: boolean}> {
  constructor(props: {children: React.ReactNode}) {
    super(props)
    this.state = {hasError: false}
  }
  static getDerivedStateFromError() { return {hasError: true} }
  componentDidCatch(error: Error) { console.warn('App crash:', error) }
  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-background text-foreground flex items-center justify-center p-8">
          <div className="text-center space-y-4">
            <h1 className="text-2xl font-bold">Something went wrong</h1>
            <p className="text-muted-foreground">The app encountered an unexpected error. Please refresh the page.</p>
            <button onClick={() => window.location.reload()} className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90">
              Refresh Page
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

export default function App() {
  return (
    <ToastProvider>
      <ErrorBoundary>
        <AppContent />
      </ErrorBoundary>
    </ToastProvider>
  )
}

function AppContent() {
  const { toast } = useToast()
  const [activeTab, setActiveTab] = useState('connection')
  const [activeRunId, setActiveRunId] = useState<number | null>(null)
  const [activeBatchId, setActiveBatchId] = useState<string | null>(null)
  const [connection, setConnection] = useState({
    apiUrl: 'http://127.0.0.1:1234/v1',
    apiKey: '',
    connected: false,
    models: [] as string[],
    selectedModel: '',
    metadata: {} as Record<string, any>,
  })
  const [runStatus, setRunStatus] = useState<any>(null)
  const [darkMode, setDarkMode] = useState(() => localStorage.getItem('benchmax-theme-dark') !== 'false')
  const [telemetryPaused, setTelemetryPaused] = useState(false)
  const userPausedRef = useRef(false)
  const [sparkData, setSparkData] = useState<{ cpu: number; gpu: number }[]>([])
  const [showShortcuts, setShowShortcuts] = useState(false)
  const [pendingRerun, setPendingRerun] = useState<{ model: string; benchmark: string; params: any } | null>(null)
  const pollMountedRef = useRef(true)
  const prevBatchIdRef = useRef<string | null>(null)
  const wasConnectedRef = useRef(false)
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0)
  const refreshHistory = useCallback(() => setHistoryRefreshKey(k => k + 1), [])

  useEffect(() => {
    const html = document.documentElement
    if (darkMode) {
      html.classList.add('dark')
    } else {
      html.classList.remove('dark')
    }
    localStorage.setItem('benchmax-theme-dark', String(darkMode))
  }, [darkMode])

  const handleConnect = useCallback(async () => {
    const result = await api.connectLMStudio(connection.apiUrl, connection.apiKey)
    if (result.status.startsWith('Connection failed')) {
      setConnection(prev => ({ ...prev, connected: false, models: [] }))
      toast({ title: "Connection Failed", description: result.status, variant: "error" })
      return
    }
    setConnection(prev => ({
      ...prev,
      connected: true,
      models: result.choices || [],
      selectedModel: result.selected || '',
      metadata: result.metadata || {},
    }))
    toast({ title: "Connected", description: `Successfully connected to ${connection.apiUrl}`, variant: "success" })
  }, [connection.apiUrl, connection.apiKey, toast])

  useEffect(() => {
    pollMountedRef.current = true
    return () => { pollMountedRef.current = false }
  }, [])

  const pollInterval = 3000
  useEffect(() => {
    if (!activeRunId && !activeBatchId) return
    const interval = setInterval(async () => {
      if (!pollMountedRef.current) return
      try {
        const data = await api.poll(activeRunId || undefined)
        if (!pollMountedRef.current) return
        setRunStatus(data)
        if (data.telemetry) {
          setSparkData(prev => [...prev.slice(-14), {
            cpu: data.telemetry.cpu_percent || 0,
            gpu: data.telemetry.gpu_available ? (data.telemetry.gpu_load || 0) : 0,
          }])
        }

        // Batch run transition: follow the chain to the currently running run
        if (data.active_run_override != null && typeof data.active_run_override === 'number') {
          setActiveRunId(data.active_run_override)
        }

        const prevBatchId = prevBatchIdRef.current
        prevBatchIdRef.current = activeBatchId

        // Run completion notification (single-run mode only)
        if (data.run_progress?.status_md && /COMPLETED|FAILED|HALTED/.test(data.run_progress.status_md)) {
          if (!activeBatchId) {
            setActiveRunId(null)
            toast({
              title: "Benchmark Finished",
              description: `Evaluation finished with status: ${data.run_progress.status_md.replace(/\*\*|\*/g, '')}`,
              variant: data.run_progress.status_md.includes('COMPLETED') ? "success" : "warning"
            })
          }
        }

        // Batch completion notification
        if (activeBatchId && data.batch_progress) {
          const bp = data.batch_progress
          if (bp.completed != null && bp.total != null && bp.total > 0 && bp.completed >= bp.total) {
            setActiveRunId(null)
            setActiveBatchId(null)
            toast({
              title: "Batch Completed",
              description: `All ${bp.total} benchmarks finished`,
              variant: "success"
            })
          }
        }
      } catch { console.warn('Poll failed') }
    }, pollInterval)
    return () => clearInterval(interval)
  }, [activeRunId, activeBatchId, toast])

  // Wrapped setter: tracks user intent for visibility handler
  const handleSetTelemetryPaused = useCallback((paused: boolean) => {
    userPausedRef.current = paused
    setTelemetryPaused(paused)
  }, [])

  useEffect(() => {
    const handler = () => {
      if (document.hidden) {
        setTelemetryPaused(true)
      } else if (!userPausedRef.current) {
        setTelemetryPaused(false)
      }
    }
    document.addEventListener('visibilitychange', handler)
    return () => document.removeEventListener('visibilitychange', handler)
  }, [])

  useEffect(() => {
    const interval = setInterval(async () => {
      if (!pollMountedRef.current) return
      try {
        await api.poll()
        if (!pollMountedRef.current) return
        if (!connection.connected) {
          setConnection(prev => ({ ...prev, connected: true }))
          if (wasConnectedRef.current) {
            toast({ title: "Connection Restored", description: "Successfully reconnected to BenchMax server.", variant: "success" })
          }
          wasConnectedRef.current = true
        }
      } catch {
        if (connection.connected) {
          wasConnectedRef.current = true
          setConnection(prev => ({ ...prev, connected: false }))
          toast({ title: "Connection Lost", description: "Could not reach BenchMax server. Please check connection.", variant: "error" })
        }
      }
    }, 30000)
    return () => clearInterval(interval)
  }, [connection.connected, toast])

  useEffect(() => {
    const prog = runStatus?.run_progress
    if (prog && activeRunId && prog.status_md?.includes('RUNNING')) {
      const pct = Math.round((prog.progress || 0) * 100)
      document.title = `[${pct}%] ${prog.active_task || 'Run'} — BenchMax`
    } else {
      document.title = 'BenchMax'
    }
  }, [runStatus, activeRunId])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return
      }
      if (e.ctrlKey && e.key >= '1' && e.key <= '5') {
        e.preventDefault()
        const tabs = ['connection', 'run', 'hardware', 'history', 'leaderboard']
        setActiveTab(tabs[parseInt(e.key) - 1])
      }
      if (e.key === '?') {
        setShowShortcuts(prev => !prev)
      }
      if (e.ctrlKey && e.key === 'Enter') {
        e.preventDefault()
        const btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent?.includes('Start'))
        btn?.click()
      }
      if (e.key === 'Escape') {
        setShowShortcuts(false)
      }
      if (e.ctrlKey && e.key === '.') {
        e.preventDefault()
        const haltBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent?.includes('Halt') || b.textContent?.includes('Stop'))
        haltBtn?.click()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  const handleRerun = useCallback((model: string, benchmark: string, params: any) => {
    setPendingRerun({ model, benchmark, params })
    setActiveTab('run')
  }, [])

  return (
    <div className={`min-h-screen bg-background text-foreground font-sans ${darkMode ? 'dark' : ''}`}>
      <Background intensity="subtle" />

      <header className="backdrop-blur-2xl bg-white/5 dark:bg-primary/[0.02] border-b border-primary/10 sticky top-0 z-50">
        <div className="max-w-[1600px] mx-auto px-6 py-3 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold tracking-tight gradient-text">BenchMax</h1>
            <p className="text-xs text-muted-foreground mt-0.5">Local LLM Benchmarker alpha 1.0.1</p>
          </div>

          <div className="flex items-center gap-5">
            {!telemetryPaused && sparkData.length >= 3 && (
              <div className="flex items-center gap-4 text-[10px] text-muted-foreground font-mono">
                <div className="flex items-center gap-1.5 bg-card/40 px-2 py-1 rounded border border-border/40">
                  <span>CPU</span>
                  <div className="flex gap-px items-end h-6 w-16">
                    {sparkData.slice(-16).map((d, i) => (
                      <div key={i} className="w-1 rounded-t" style={{ height: `${Math.max(d.cpu, 2)}%`, background: '#3B82F6', opacity: 0.4 + 0.6 * (i / Math.max(sparkData.slice(-16).length - 1, 1)) }} />
                    ))}
                  </div>
                  <span>{Math.round(sparkData[sparkData.length - 1].cpu)}%</span>
                </div>
                <div className="flex items-center gap-1.5 bg-card/40 px-2 py-1 rounded border border-border/40">
                  <span>GPU</span>
                  <div className="flex gap-px items-end h-6 w-16">
                    {sparkData.slice(-16).map((d, i) => (
                      <div key={i} className="w-1 rounded-t" style={{ height: `${Math.max(d.gpu, 2)}%`, background: '#fbbf24', opacity: 0.4 + 0.6 * (i / Math.max(sparkData.slice(-16).length - 1, 1)) }} />
                    ))}
                  </div>
                  <span>{Math.round(sparkData[sparkData.length - 1].gpu)}%</span>
                </div>
              </div>
            )}

            {connection.connected && (
              <span className="inline-flex items-center gap-1.5 text-xs font-medium text-green-400" aria-live="polite">
                <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
                Connected
              </span>
            )}

            <button
              onClick={() => setDarkMode(!darkMode)}
              className={`p-2 rounded-lg transition-all duration-300 ${darkMode ? 'bg-primary/15 text-primary' : 'hover:bg-accent/10 text-muted-foreground'}`}
              aria-label="Toggle dark mode"
            >
              {darkMode ? <Sun size={18} /> : <Moon size={18} />}
            </button>
          </div>
        </div>
      </header>

      <main className="relative z-10 p-4 max-w-[1600px] mx-auto">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="flex flex-wrap mb-6 gap-1 px-2 py-1.5 backdrop-blur-2xl bg-card/95 border border-primary/10 rounded-lg">
            <TabsTrigger value="connection" icon={<Zap size={14} />}>Connection</TabsTrigger>
            <TabsTrigger value="run" icon={<Play size={14} />}>Run Benchmark</TabsTrigger>
            <TabsTrigger value="hardware" icon={<Activity size={14} />}>Hardware</TabsTrigger>
            <TabsTrigger value="history" icon={<BarChart3 size={14} />}>History & Results</TabsTrigger>
            <TabsTrigger value="leaderboard" icon={<Trophy size={14} />}>Leaderboard</TabsTrigger>
          </TabsList>

          <TabsContent forceMount value="connection">
            <LoadingFallback><ConnectionTab connection={connection} setConnection={setConnection} onConnect={handleConnect} /></LoadingFallback>
          </TabsContent>

          <TabsContent forceMount value="run">
            <LoadingFallback><RunBenchmarkTab
                connection={connection} setConnection={setConnection}
                activeRunId={activeRunId} setActiveRunId={setActiveRunId}
                activeBatchId={activeBatchId} setActiveBatchId={setActiveBatchId}
                runStatus={runStatus}
                pendingRerun={pendingRerun}
                clearPendingRerun={() => setPendingRerun(null)}
              />
            </LoadingFallback>
          </TabsContent>

          <TabsContent forceMount value="hardware">
            <LoadingFallback><HardwareTab telemetryPaused={telemetryPaused} setTelemetryPaused={handleSetTelemetryPaused} /></LoadingFallback>
          </TabsContent>

          <TabsContent forceMount value="history">
            <LoadingFallback><HistoryResultsTab onRerun={handleRerun} activeTab={activeTab} historyRefreshKey={historyRefreshKey} /></LoadingFallback>
          </TabsContent>

          <TabsContent forceMount value="leaderboard">
            <LoadingFallback><LeaderboardTab onDelete={refreshHistory} /></LoadingFallback>
          </TabsContent>
        </Tabs>
      </main>

      {showShortcuts && (
        <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => setShowShortcuts(false)} role="dialog" aria-modal="true" aria-label="Keyboard shortcuts" onKeyDown={(e) => { if (e.key === 'Escape') setShowShortcuts(false) }}>
          <div className="bg-card border border-border p-6 rounded-xl shadow-2xl max-w-sm w-full space-y-4 animate-fadeInUp" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-center">
              <h3 className="font-bold text-lg">Keyboard Shortcuts</h3>
              <button className="text-muted-foreground hover:text-foreground font-bold" aria-label="Close shortcuts" onClick={() => setShowShortcuts(false)}>×</button>
            </div>
            <div className="space-y-2 text-sm font-mono">
              <div className="flex justify-between border-b border-border/40 pb-1">
                <span>Ctrl + 1..5</span>
                <span className="text-muted-foreground">Switch tabs</span>
              </div>
              <div className="flex justify-between border-b border-border/40 pb-1">
                <span>Ctrl + Enter</span>
                <span className="text-muted-foreground">Start Benchmark</span>
              </div>
              <div className="flex justify-between border-b border-border/40 pb-1">
                <span>Escape</span>
                <span className="text-muted-foreground">Close this dialog</span>
              </div>
              <div className="flex justify-between">
                <span>?</span>
                <span className="text-muted-foreground">Toggle shortcuts helper</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
