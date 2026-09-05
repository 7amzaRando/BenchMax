import { memo } from 'react'
import { useApp } from '@/lib/context'

export default memo(function ShortcutsDialog() {
  const { state, dispatch } = useApp()
  if (!state.showShortcuts) return null

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => dispatch({ type: 'SET_SHOW_SHORTCUTS', payload: false })} role="dialog" aria-modal="true" aria-label="Keyboard shortcuts" onKeyDown={(e) => { if (e.key === 'Escape') dispatch({ type: 'SET_SHOW_SHORTCUTS', payload: false }) }}>
      <div className="bg-card border border-border p-6 rounded-xl shadow-2xl max-w-sm w-full space-y-4 animate-fadeInUp" onClick={e => e.stopPropagation()}>
        <div className="flex justify-between items-center">
          <h3 className="font-bold text-lg">Keyboard Shortcuts</h3>
          <button className="text-muted-foreground hover:text-foreground font-bold" aria-label="Close shortcuts" onClick={() => dispatch({ type: 'SET_SHOW_SHORTCUTS', payload: false })}>×</button>
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
  )
})
