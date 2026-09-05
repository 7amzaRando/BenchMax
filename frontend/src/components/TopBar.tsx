import { memo } from 'react'
import { useApp } from '@/lib/context'
import { Sun, Moon } from '@/components/ui/icons'

const TITLES: Record<string, { title: string; desc: string }> = {
  connection: { title: 'Connection', desc: 'Providers, models, datasets & Docker sandbox' },
  run: { title: 'Run', desc: 'Start single, batch or model-queue benchmarks' },
  hardware: { title: 'Hardware', desc: 'Live CPU · RAM · GPU · VRAM at 3s intervals' },
  history: { title: 'History & Results', desc: 'Runs, per-sample analysis, diffs & exports' },
  leaderboard: { title: 'Leaderboard', desc: 'Rankings, trends & online sync' },
}

export default memo(function TopBar({ onMenu }: { onMenu: () => void }) {
  const { state, dispatch } = useApp()
  const meta = TITLES[state.activeTab] ?? TITLES.connection
  const spark = state.sparkData
  const telemetryPaused = state.telemetryPaused

  return (
    <header className="sticky top-0 z-30 backdrop-blur-xl border-b bg-[var(--topbar-bg)] border-border/60">
      <div className="h-[64px] px-4 lg:px-6 flex items-center gap-4 max-w-[1280px] mx-auto w-full">
        <button
          onClick={onMenu}
          className="lg:hidden p-2 -ml-2 rounded-lg hover:bg-muted border border-transparent hover:border-border"
          aria-label="Open navigation"
        >
          <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><path d="M4 6h16M4 12h16M4 18h16" /></svg>
        </button>

        <div className="min-w-0">
          <h1 className="text-[15px] font-semibold tracking-tight leading-none">{meta.title}</h1>
          <p className="hidden sm:block text-xs text-muted-foreground leading-none mt-1">{meta.desc}</p>
        </div>

        <div className="ml-auto flex items-center gap-2">
          {/* mini sparkline */}
          {!telemetryPaused && spark.length >= 3 && (
            <div className="hidden md:flex items-center gap-2 text-[11px] font-mono">
              <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-full border bg-card shadow-sm">
                <span className="text-muted-foreground">CPU</span>
                <span className="flex gap-px items-end h-4">
                  {spark.slice(-12).map((d, i) => (
                    <span key={i} className="w-0.5 rounded-full" style={{ height: `${Math.max(4, Math.min(16, (d.cpu/100)*16))}px`, background: 'var(--chart-cpu)', opacity: 0.45 + 0.55*(i/12) }} />
                  ))}
                </span>
                <span className="font-semibold">{Math.round(spark[spark.length-1].cpu)}%</span>
              </div>
              <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1.5 rounded-full border bg-card shadow-sm">
                <span className="text-muted-foreground">GPU</span>
                <span className="flex gap-px items-end h-4">
                  {spark.slice(-12).map((d, i) => (
                    <span key={i} className="w-0.5 rounded-full" style={{ height: `${Math.max(4, Math.min(16, (Math.min(d.gpu,100)/100)*16))}px`, background: 'var(--chart-gpu)', opacity: 0.45 + 0.55*(i/12) }} />
                  ))}
                </span>
                <span className="font-semibold">{Math.round(spark[spark.length-1].gpu)}%</span>
              </div>
            </div>
          )}

          <div className="hidden sm:flex items-center gap-1.5 pl-2 ml-1 border-l border-border">
            <span className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-full border font-medium ${state.connection.connected ? 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/30 dark:text-emerald-300 dark:border-emerald-900' : 'bg-muted text-muted-foreground border-border'}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${state.connection.connected ? 'bg-emerald-500 animate-pulse' : 'bg-zinc-400'}`} />
              {state.connection.connected ? 'Connected' : 'Offline'}
            </span>
          </div>

          <button
            onClick={() => dispatch({ type: 'SET_SHOW_SHORTCUTS', payload: true })}
            className="hidden sm:inline-flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg border border-border bg-card hover:bg-muted font-mono"
            title="Shortcuts (?)"
          >
            <span className="text-muted-foreground">?</span>
            <span className="hidden lg:inline text-muted-foreground">Shortcuts</span>
          </button>

          <button
            onClick={() => dispatch({ type: 'SET_DARK_MODE', payload: !state.darkMode })}
            className="p-2 rounded-lg border border-border bg-card hover:bg-muted transition-colors"
            aria-label="Toggle theme"
            title="Toggle dark mode"
          >
            {state.darkMode ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        </div>
      </div>
    </header>
  )
})
