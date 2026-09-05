import { memo } from 'react'
import { useApp } from '@/lib/context'
import { Zap, Play, Activity, BarChart3, Trophy } from '@/components/ui/icons'

type NavItem = { id: string; label: string; desc: string; icon: React.ReactNode; kbd: string }

const NAV: NavItem[] = [
  { id: 'connection', label: 'Connection', desc: 'Providers & datasets', icon: <Zap size={16} />, kbd: '1' },
  { id: 'run',        label: 'Run',        desc: 'Benchmarks & queues', icon: <Play size={16} />, kbd: '2' },
  { id: 'hardware',   label: 'Hardware',   desc: 'Live telemetry',      icon: <Activity size={16} />, kbd: '3' },
  { id: 'history',    label: 'History',    desc: 'Results & analysis',  icon: <BarChart3 size={16} />, kbd: '4' },
  { id: 'leaderboard',label: 'Leaderboard',desc: 'Rankings & sync',     icon: <Trophy size={16} />, kbd: '5' },
]

export default memo(function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { state, dispatch } = useApp()
  const { activeTab, connection, runStatus } = state
  const isRunning = !!runStatus?.run_progress?.status_md?.includes('RUNNING') || state.activeRunId !== null || state.activeBatchId !== null

  return (
    <>
      {/* overlay mobile */}
      {open && <div className="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm lg:hidden" onClick={onClose} aria-hidden />}

      <aside
        className={[
          "fixed top-0 left-0 z-50 h-dvh w-[272px] shrink-0 border-r flex flex-col",
          "bg-[var(--sidebar-bg)] border-[var(--sidebar-border)]",
          "transition-transform duration-200 ease-out",
          open ? "translate-x-0" : "-translate-x-full lg:translate-x-0",
        ].join(" ")}
        aria-label="Primary"
      >
        {/* brand */}
        <div className="h-[64px] px-5 flex items-center gap-3 border-b border-[var(--sidebar-border)] shrink-0">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[var(--primary)] to-[var(--secondary)] flex items-center justify-center text-white font-display font-bold text-[13px] tracking-tight shadow-sm">
            BM
          </div>
          <div className="min-w-0">
            <div className="font-display font-bold text-[15px] leading-none tracking-tight">BenchMax</div>
            <div className="text-[11px] text-muted-foreground font-mono leading-none mt-1">v2.0 · 30 benchmarks</div>
          </div>
          <span className="ml-auto hidden lg:inline-flex text-[10px] font-mono px-1.5 py-0.5 rounded border border-border bg-muted text-muted-foreground">LOCAL</span>
          <button
            onClick={onClose}
            className="lg:hidden ml-auto p-1.5 rounded-md hover:bg-muted text-muted-foreground"
            aria-label="Close navigation"
          >
            <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><path d="M18 6L6 18M6 6l12 12" /></svg>
          </button>
        </div>

        {/* connection summary */}
        <div className="px-3 py-3 border-b border-[var(--sidebar-border)]">
          <div className={`flex items-center gap-2.5 rounded-lg border px-3 py-2.5 ${connection.connected ? 'bg-emerald-50/70 dark:bg-emerald-950/20 border-emerald-200/60 dark:border-emerald-900/40' : 'bg-muted/60 border-border'}`}>
            <span className={`w-2 h-2 rounded-full shrink-0 ${connection.connected ? 'bg-emerald-500 shadow-[0_0_0_4px_rgba(16,185,129,0.18)]' : 'bg-zinc-400'}`} />
            <div className="min-w-0">
              <div className={`text-xs font-semibold leading-none ${connection.connected ? 'text-emerald-700 dark:text-emerald-300' : 'text-muted-foreground'}`}>
                {connection.connected ? 'Connected' : 'Not connected'}
              </div>
              <div className="text-[11px] font-mono text-muted-foreground truncate max-w-[170px] leading-none mt-1">
                {connection.connected
                  ? (connection.selectedModel || `${connection.models.length} models`)
                  : 'Select a provider to begin'}
              </div>
            </div>
            {isRunning && (
              <span className="ml-auto inline-flex items-center gap-1 text-[10px] font-semibold px-1.5 py-1 rounded-full bg-amber-500 text-white animate-pulse">
                RUN
              </span>
            )}
          </div>
          {connection.connected && connection.models.length > 0 && (
            <div className="mt-2 text-[11px] text-muted-foreground font-mono px-1">
              {connection.models.length} model{connection.models.length !== 1 ? 's' : ''} available
            </div>
          )}
        </div>

        {/* nav */}
        <nav className="flex-1 overflow-y-auto p-3 space-y-1">
          <div className="text-[10px] font-semibold tracking-widest text-muted-foreground px-2 pt-1 pb-2 uppercase">Navigate</div>
          {NAV.map(item => {
            const active = activeTab === item.id
            return (
              <button
                key={item.id}
                onClick={() => { dispatch({ type: 'SET_ACTIVE_TAB', payload: item.id }); onClose() }}
                className={[
                  "w-full flex items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors border",
                  active
                    ? "nav-active border-transparent"
                    : "border-transparent text-muted-foreground hover:text-foreground hover:bg-muted hover:border-border",
                ].join(" ")}
              >
                <span className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${active ? 'bg-white/90 dark:bg-white text-[var(--primary)] shadow-sm' : 'bg-muted text-muted-foreground'}`}>
                  {item.icon}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-[13px] leading-none">{item.label}</span>
                  <span className={`block text-[11px] leading-none mt-1 ${active ? 'text-[var(--primary)]/70 dark:text-white/70' : 'text-muted-foreground'}`}>{item.desc}</span>
                </span>
                <span className={`hidden xl:inline-flex text-[10px] font-mono px-1.5 py-0.5 rounded border ${active ? 'bg-white/80 dark:bg-white/15 border-transparent' : 'bg-card border-border text-muted-foreground'}`}>
                  ⌘{item.kbd}
                </span>
              </button>
            )
          })}


        </nav>

        {/* footer */}
        <div className="p-3 border-t border-[var(--sidebar-border)]">
          <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
            <span className="font-mono">AGPL-3.0</span>
            <span className="opacity-40">·</span>
            <a href="https://github.com/7amzaRando/BenchMax" target="_blank" rel="noreferrer" className="hover:text-foreground underline-offset-4 hover:underline">GitHub</a>
            <span className="ml-auto font-mono text-[10px] px-1.5 py-0.5 rounded bg-muted border border-border">Press ?</span>
          </div>
        </div>
      </aside>
    </>
  )
})
