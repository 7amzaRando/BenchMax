import { useCallback, useState, lazy, Suspense, type ReactNode } from 'react'
import { BenchMaxProvider, useApp } from '@/lib/context'
import { useRunPolling, useHealthPolling, useVisibilityPause, useHardwarePolling, useDarkModeSync, useTitleSync, useKeyboardShortcuts } from '@/lib/hooks'
import Sidebar from '@/components/Sidebar'
import TopBar from '@/components/TopBar'
import ShortcutsDialog from '@/components/ShortcutsDialog'
import ServerStatusBanner from '@/components/ServerStatusBanner'
import Background from '@/components/ui/background'
import * as api from '@/lib/api'
import { ToastProvider, useToast } from '@/components/ui/toast-provider'
import React from 'react'

class ErrorBoundary extends React.Component<{children: React.ReactNode}, {hasError: boolean}> {
  constructor(props: {children: React.ReactNode}) { super(props); this.state = {hasError: false} }
  static getDerivedStateFromError() { return {hasError: true} }
  componentDidCatch(error: Error) { console.warn('App crash:', error) }
  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-background text-foreground flex items-center justify-center p-8">
          <div className="text-center space-y-4 max-w-md">
            <h1 className="text-xl font-bold font-display">Something went wrong</h1>
            <p className="text-sm text-muted-foreground">The app hit an unexpected error. Your runs are safe — just refresh.</p>
            <button onClick={() => window.location.reload()} className="px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-[var(--primary-dark)]">Refresh Page</button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

class TabErrorBoundary extends React.Component<{children: React.ReactNode; name: string}, {hasError: boolean}> {
  constructor(props: {children: React.ReactNode; name: string}) { super(props); this.state = {hasError: false} }
  static getDerivedStateFromError() { return {hasError: true} }
  componentDidCatch(error: Error) { console.warn(`Tab ${this.props.name} crash:`, error) }
  render() {
    if (this.state.hasError) {
      return (
        <div className="rounded-xl border border-border bg-card p-8 text-center">
          <p className="text-sm font-medium">This tab crashed</p>
          <p className="text-xs text-muted-foreground mt-1">Try again — your data is still there.</p>
          <button onClick={() => this.setState({hasError: false})} className="mt-3 px-3 py-1.5 text-xs bg-muted hover:bg-muted/80 rounded-lg border border-border">Try again</button>
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
        <BenchMaxProvider>
          <AppContent />
        </BenchMaxProvider>
      </ErrorBoundary>
    </ToastProvider>
  )
}

const ConnectionTab = lazy(() => import('@/pages/ConnectionTab'))
const RunBenchmarkTab = lazy(() => import('@/pages/RunBenchmarkTab'))
const HardwareTab = lazy(() => import('@/pages/HardwareTab'))
const HistoryResultsTab = lazy(() => import('@/pages/HistoryResultsTab'))
const LeaderboardTab = lazy(() => import('@/pages/LeaderboardTab'))

function LoadingFallback({ children }: { children: ReactNode }) {
  return <Suspense fallback={<div className="p-8 text-center text-sm text-muted-foreground">Loading…</div>}>{children}</Suspense>
}

function AppContent() {
  const { state, dispatch } = useApp()
  const { toast } = useToast()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  useRunPolling()
  useHealthPolling()
  useHardwarePolling()
  useDarkModeSync()
  useTitleSync()
  useKeyboardShortcuts()
  useVisibilityPause()

  const handleConnect = useCallback(async () => {
    const result = await api.connectLMStudio(state.connection.apiUrl, state.connection.apiKey)
    if (result.status.startsWith('Connection failed')) {
      dispatch({ type: 'SET_CONNECTION', payload: { connected: false, models: [] } })
      toast({ title: "Connection Failed", description: result.status, variant: "error" })
      return
    }
    dispatch({ type: 'SET_CONNECTION', payload: {
      connected: true,
      models: result.choices || [],
      selectedModel: result.selected || '',
      metadata: result.metadata || {},
    }})
    toast({ title: "Connected", description: `Connected to ${state.connection.apiUrl}`, variant: "success" })
  }, [state.connection.apiUrl, state.connection.apiKey, toast, dispatch])

  const handleRerun = useCallback((model: string, benchmark: string, params: Record<string, unknown>) => {
    dispatch({ type: 'SET_PENDING_RERUN', payload: { model, benchmark, params } })
    dispatch({ type: 'SET_ACTIVE_TAB', payload: 'run' })
  }, [dispatch])

  return (
    <div className={`min-h-screen bg-background text-foreground font-sans ${state.darkMode ? 'dark' : ''}`}>
      <Background />

      <div className="relative z-10 min-h-screen flex">
        <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

        <div className="flex-1 min-w-0 lg:pl-[272px] flex flex-col min-h-screen">
          <TopBar onMenu={() => setSidebarOpen(v => !v)} />

          <main className="flex-1 w-full max-w-[1280px] mx-auto px-4 lg:px-6 py-6">
            {/* quick status strip when running */}
            {state.activeRunId && state.runStatus?.run_progress && (
              <div className="mb-5 rounded-xl border bg-card shadow-sm px-4 py-3 flex items-center gap-3 text-xs">
                <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse shrink-0" />
                <span className="font-mono font-medium truncate">{state.runStatus.run_progress.active_task || `Run #${state.activeRunId}`}</span>
                <span className="text-muted-foreground hidden sm:inline truncate">{state.runStatus.run_progress.status_md}</span>
                <span className="ml-auto font-mono text-muted-foreground hidden md:inline">
                  {state.runStatus.run_progress.accuracy} · {state.runStatus.run_progress.avg_tps} · {state.runStatus.run_progress.token_stats}
                </span>
              </div>
            )}

            {state.activeTab === 'connection' && (
              <TabErrorBoundary name="Connection"><LoadingFallback><ConnectionTab onConnect={handleConnect} /></LoadingFallback></TabErrorBoundary>
            )}
            {state.activeTab === 'run' && (
              <TabErrorBoundary name="Run"><LoadingFallback><RunBenchmarkTab /></LoadingFallback></TabErrorBoundary>
            )}
            {state.activeTab === 'hardware' && (
              <TabErrorBoundary name="Hardware"><LoadingFallback><HardwareTab /></LoadingFallback></TabErrorBoundary>
            )}
            {state.activeTab === 'history' && (
              <TabErrorBoundary name="History"><LoadingFallback><HistoryResultsTab onRerun={handleRerun} /></LoadingFallback></TabErrorBoundary>
            )}
            {state.activeTab === 'leaderboard' && (
              <TabErrorBoundary name="Leaderboard"><LoadingFallback><LeaderboardTab onDelete={() => dispatch({ type: 'INCREMENT_HISTORY_REFRESH' })} /></LoadingFallback></TabErrorBoundary>
            )}
          </main>

          <footer className="border-t border-border/40 bg-card/30 backdrop-blur">
            <div className="max-w-[1280px] mx-auto px-4 lg:px-6 py-3 flex flex-wrap items-center gap-2.5 text-[11px] text-muted-foreground">
              <span className="font-mono font-medium tracking-tight">BenchMax <span className="text-foreground">v2.0</span></span>
              <span className="hidden sm:inline-flex items-center gap-2">
                <span className="w-px h-3 bg-border hidden sm:block" />
                <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-muted/50 px-2.5 py-0.5 font-medium">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                  30 benchmarks
                </span>
                <span className="hidden md:inline">Fully local</span>
                <span className="opacity-30 hidden md:inline">·</span>
                <span className="hidden md:inline">Private by design</span>
              </span>
              <span className="ml-auto flex items-center gap-2.5">
                <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium ${state.serverOnline ? 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/30 dark:text-emerald-300 dark:border-emerald-900' : 'bg-red-50 text-red-700 border-red-200 dark:bg-red-950/30 dark:text-red-300 dark:border-red-900'}`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${state.serverOnline ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'}`} />
                  {state.serverOnline ? 'Online' : 'Offline'}
                </span>
                <span className="hidden sm:inline-flex items-center gap-1">
                  Press <kbd className="px-1.5 py-0.5 rounded border bg-muted font-mono text-[10px] leading-none">?</kbd>
                </span>
              </span>
            </div>
          </footer>
        </div>
      </div>

      <ServerStatusBanner />
      <ShortcutsDialog />
    </div>
  )
}
