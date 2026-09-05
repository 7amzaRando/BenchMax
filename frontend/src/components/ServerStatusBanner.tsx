import { memo } from 'react'
import { useApp } from '@/lib/context'

export default memo(function ServerStatusBanner() {
  const { state } = useApp()
  if (state.serverOnline) return null

  return (
    <div className="fixed top-14 inset-x-0 z-[150] flex justify-center pointer-events-none" role="status" aria-live="polite">
      <div className="pointer-events-auto mt-2 px-4 py-2 rounded-lg bg-red-900/90 text-red-50 text-sm border border-red-500/50 shadow-lg">
        Server unreachable — reconnecting…
      </div>
    </div>
  )
})
