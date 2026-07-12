import { useState, useEffect, useCallback, useRef } from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import ConnectionTab from '@/pages/ConnectionTab'
import RunBenchmarkTab from '@/pages/RunBenchmarkTab'
import HardwareTab from '@/pages/HardwareTab'
import HistoryResultsTab from '@/pages/HistoryResultsTab'
import LeaderboardTab from '@/pages/LeaderboardTab'
import Background from '@/components/ui/background'
import { Zap, Play, Activity, BarChart3, Trophy, Sun, Moon } from '@/components/ui/icons'
import * as api from '@/lib/api'
import { ToastProvider, useToast } from '@/components/ui/toast-provider'
import { LineChart, Line, ResponsiveContainer } from 'recharts'

export default function App() {
  return (
    <ToastProvider>
      <AppContent />
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
    if (!result.status.startsWith('🟢')) {
      setConnection(prev => ({ ...prev, connected: false, models: [] }))
      toast({ title: "Connection Failed", description: result.status, variant: "error" })
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

  const pollInterval = 3000
  useEffect(() => {
    if (!activeRunId && !activeBatchId) return
    const interval = setInterval(async () => {
      try {
        const data = await api.poll(activeRunId || undefined)
        setRunStatus(data)

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

  useEffect(() => {
    if (telemetryPaused) return
    const interval = setInterval(async () => {
      try {
        const t = await api.getTelemetry()
        setSparkData(prev => [...prev.slice(-14), { cpu: t.cpu_percent || 0, gpu: t.gpu_available ? (t.gpu_load || 0) : 0 }])
      } catch { console.warn('Telemetry fetch failed') }
    }, 5000)
    return () => clearInterval(interval)
  }, [telemetryPaused])

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
      try {
        await api.poll()
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
            <p className="text-xs text-muted-foreground mt-0.5">Local LLM Benchmarker v2.0</p>
          </div>

          <div className="flex items-center gap-5">
            {!telemetryPaused && sparkData.length >= 3 && (
              <div className="flex items-center gap-4 text-[10px] text-muted-foreground font-mono">
                <div className="flex items-center gap-1.5 bg-card/40 px-2 py-1 rounded border border-border/40">
                  <span>CPU</span>
                  <div className="w-16 h-6">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={sparkData}>
                        <Line type="monotone" dataKey="cpu" stroke="#3B82F6" strokeWidth={1.5} dot={false} isAnimationActive={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                  <span>{Math.round(sparkData[sparkData.length - 1].cpu)}%</span>
                </div>
                <div className="flex items-center gap-1.5 bg-card/40 px-2 py-1 rounded border border-border/40">
                  <span>GPU</span>
                  <div className="w-16 h-6">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={sparkData}>
                        <Line type="monotone" dataKey="gpu" stroke="#fbbf24" strokeWidth={1.5} dot={false} isAnimationActive={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                  <span>{Math.round(sparkData[sparkData.length - 1].gpu)}%</span>
                </div>
              </div>
            )}

            {connection.connected && (
              <span className="inline-flex items-center gap-1.5 text-xs font-medium text-green-400">
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
          <TabsList className="grid grid-cols-5 mb-6 gap-1 px-2 py-1.5 backdrop-blur-2xl bg-card/95 border border-primary/10 rounded-lg">
            <TabsTrigger value="connection" icon={<Zap size={14} />}>Connection</TabsTrigger>
            <TabsTrigger value="run" icon={<Play size={14} />}>Run Benchmark</TabsTrigger>
            <TabsTrigger value="hardware" icon={<Activity size={14} />}>Hardware</TabsTrigger>
            <TabsTrigger value="history" icon={<BarChart3 size={14} />}>History & Results</TabsTrigger>
            <TabsTrigger value="leaderboard" icon={<Trophy size={14} />}>Leaderboard</TabsTrigger>
          </TabsList>

          <TabsContent forceMount value="connection">
            <ConnectionTab connection={connection} setConnection={setConnection} onConnect={handleConnect} />
          </TabsContent>

          <TabsContent forceMount value="run">
            <RunBenchmarkTab
              connection={connection} setConnection={setConnection}
              activeRunId={activeRunId} setActiveRunId={setActiveRunId}
              activeBatchId={activeBatchId} setActiveBatchId={setActiveBatchId}
              runStatus={runStatus}
              pendingRerun={pendingRerun}
              clearPendingRerun={() => setPendingRerun(null)}
            />
          </TabsContent>

          <TabsContent forceMount value="hardware">
            <HardwareTab telemetryPaused={telemetryPaused} setTelemetryPaused={handleSetTelemetryPaused} />
          </TabsContent>

          <TabsContent forceMount value="history">
            <HistoryResultsTab onRerun={handleRerun} activeTab={activeTab} historyRefreshKey={historyRefreshKey} />
          </TabsContent>

          <TabsContent forceMount value="leaderboard">
            <LeaderboardTab onDelete={refreshHistory} />
          </TabsContent>
        </Tabs>
      </main>

      {showShortcuts && (
        <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => setShowShortcuts(false)}>
          <div className="bg-card border border-border p-6 rounded-xl shadow-2xl max-w-sm w-full space-y-4 animate-fadeInUp" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-center">
              <h3 className="font-bold text-lg">Keyboard Shortcuts</h3>
              <button className="text-muted-foreground hover:text-foreground font-bold" onClick={() => setShowShortcuts(false)}>×</button>
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
                <span className="text-muted-foreground">Close diff panel</span>
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
