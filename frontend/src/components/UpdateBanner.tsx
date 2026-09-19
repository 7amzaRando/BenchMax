import { memo, useCallback, useEffect, useState } from 'react'
import { useApp } from '@/lib/context'
import * as api from '@/lib/api'
import type { VersionInfo } from '@/lib/api'

const LAST_CHECK_KEY = 'bm_update_last_check'
const SKIPPED_KEY = 'bm_update_skipped_version'
const CHECK_INTERVAL_MS = 24 * 3600 * 1000

function loadSkipped(): string | null {
  try { return localStorage.getItem(SKIPPED_KEY) } catch { return null }
}

/** Slim update banner: daily-cached GitHub release check, dismissible per version. */
export default memo(function UpdateBanner() {
  const { state } = useApp()
  const [info, setInfo] = useState<VersionInfo | null>(null)
  const [dismissed, setDismissed] = useState(false)

  const check = useCallback(async (refresh: boolean) => {
    try {
      const data = await api.getVersion(refresh)
      setInfo(data)
      try { localStorage.setItem(LAST_CHECK_KEY, String(Date.now())) } catch { /* ignore */ }
    } catch {
      /* offline — fail silent */
    }
  }, [])

  useEffect(() => {
    if (!state.settings.updateCheckEnabled) return
    let last = 0
    try { last = parseInt(localStorage.getItem(LAST_CHECK_KEY) || '0', 10) || 0 } catch { /* ignore */ }
    if (Date.now() - last > CHECK_INTERVAL_MS) check(false)
  }, [state.settings.updateCheckEnabled, check])

  if (!state.settings.updateCheckEnabled || !info?.update_available || dismissed) return null
  if (info.latest && loadSkipped() === info.latest) return null

  const dismiss = () => {
    try { if (info.latest) localStorage.setItem(SKIPPED_KEY, info.latest) } catch { /* ignore */ }
    setDismissed(true)
  }

  return (
    <div className="mb-5 rounded-xl border border-sky-200 dark:border-sky-900 bg-sky-50/80 dark:bg-sky-950/30 px-4 py-3 flex flex-wrap items-center gap-3 text-xs shadow-sm" role="status" aria-live="polite">
      <span className="w-2 h-2 rounded-full bg-sky-500 shrink-0" />
      <span className="font-semibold">BenchMax v{info.latest} is out</span>
      <span className="text-muted-foreground truncate max-w-[420px] hidden sm:inline">
        {info.notes_excerpt || 'A newer release is available on GitHub.'}
      </span>
      <span className="ml-auto flex items-center gap-2">
        {info.download_url && (
          <a href={info.download_url} className="px-3 py-1.5 rounded-lg bg-primary text-white font-medium hover:bg-[var(--primary-dark)]">
            Download
          </a>
        )}
        {info.html_url && (
          <a href={info.html_url} target="_blank" rel="noreferrer" className="px-3 py-1.5 rounded-lg border border-border bg-card hover:bg-muted font-medium">
            Release notes
          </a>
        )}
        <button onClick={dismiss} className="px-2 py-1.5 text-muted-foreground hover:text-foreground" aria-label="Dismiss this version">
          Dismiss
        </button>
      </span>
    </div>
  )
})
