import { useEffect, useRef } from 'react'
import * as api from './api'
import type { PollResponse } from './api'
import { useApp } from './context'

/**
 * Central polling hook. Runs at 3s intervals when a run/batch is active.
 * Updates runStatus + sparkData via context dispatch.
 */
export function useRunPolling() {
  const { state, dispatch } = useApp()
  const { activeRunId, activeBatchId } = state
  const mountedRef = useRef(true)
  const prevBatchIdRef = useRef<string | null>(null)
  const sparkDataRef = useRef(state.sparkData)
  const activeRunIdRef = useRef(activeRunId)
  const activeBatchIdRef = useRef(activeBatchId)
  const runPollMsRef = useRef(state.settings.runPollMs)

  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])

  useEffect(() => {
    sparkDataRef.current = state.sparkData
    activeRunIdRef.current = activeRunId
    activeBatchIdRef.current = activeBatchId
    runPollMsRef.current = Math.min(10000, Math.max(1000, state.settings.runPollMs || 3000))
  })

  useEffect(() => {
    function handlePollData(data: PollResponse) {
      if (!mountedRef.current) return
      dispatch({ type: 'SET_RUN_STATUS', payload: data })
      if (data.telemetry) {
        dispatch({ type: 'SET_SPARK_DATA', payload: [...sparkDataRef.current.slice(-14), {
          cpu: data.telemetry.cpu_percent || 0,
          gpu: data.telemetry.gpu_available ? (data.telemetry.gpu_load || 0) : 0,
        }] })
      }
      if (data.active_run_override != null && typeof data.active_run_override === 'number') {
        dispatch({ type: 'SET_ACTIVE_RUN_ID', payload: data.active_run_override })
      }
      // Adopt externally-started runs (CLI/MCP/other browsers): when this
      // client is idle but the server reports RUNNING/PAUSED runs, track the
      // newest one so the Run tab shows live progress. Only adopts from idle
      // to avoid stealing a run the user just started (last-writer-wins guard
      // lives in the refs, updated every render).
      const idleRun = activeRunIdRef.current
      const idleBatch = activeBatchIdRef.current
      const ext = (data as PollResponse).active_runs
      if (!idleRun && !idleBatch && ext && ext.length > 0) {
        const pick = ext.find(r => r.status === 'RUNNING') || ext[0]
        if (pick && typeof pick.run_id === 'number') {
          dispatch({ type: 'SET_ACTIVE_RUN_ID', payload: pick.run_id })
          if (pick.batch_id) dispatch({ type: 'SET_ACTIVE_BATCH_ID', payload: pick.batch_id })
        }
      }
      const prevBatchId = prevBatchIdRef.current
      const curBatchId = activeBatchIdRef.current
      prevBatchIdRef.current = curBatchId
      if (data.run_progress?.status_md && /COMPLETED|FAILED|HALTED/.test(data.run_progress.status_md)) {
        if (!curBatchId) {
          dispatch({ type: 'SET_ACTIVE_RUN_ID', payload: null })
          dispatch({ type: 'INCREMENT_HISTORY_REFRESH' })
        }
      }
      if (curBatchId && data.batch_progress) {
        const bp = data.batch_progress
        if (bp.completed != null && bp.total != null && bp.total > 0 && bp.completed >= bp.total) {
          dispatch({ type: 'SET_ACTIVE_RUN_ID', payload: null })
          dispatch({ type: 'SET_ACTIVE_BATCH_ID', payload: null })
          dispatch({ type: 'INCREMENT_HISTORY_REFRESH' })
        }
      }
    }

    let es: EventSource | null = null
    let pollInterval: ReturnType<typeof setInterval> | null = null
    let useSSE = typeof EventSource !== 'undefined'

    function startPollFallback() {
      if (pollInterval) return
      pollInterval = setInterval(async () => {
        if (!mountedRef.current) return
        const curRunId = activeRunIdRef.current
        // No early return when idle: the id-less poll carries active_runs
        // so this client can discover CLI/MCP-started runs.
        try {
          const data = await api.poll(curRunId || undefined)
          handlePollData(data)
        } catch (err) {
          console.warn('Poll failed:', err)
        }
      }, runPollMsRef.current)
    }

    function startSSE() {
      if (es) { es.close(); es = null }
      const curRunId = activeRunIdRef.current
      // SSE also connects when idle (no active_run_id query) — the stream
      // payload includes active_runs for external-run discovery.
      try {
        es = new EventSource(api.pollStreamUrl(curRunId || undefined))
        es.onmessage = (ev) => {
          try {
            const data = JSON.parse(ev.data) as PollResponse
            handlePollData(data)
          } catch { /* ignore parse */ }
        }
        es.onerror = () => {
          es?.close(); es = null
          if (pollInterval) { clearInterval(pollInterval); pollInterval = null }
          startPollFallback()
          // Retry SSE after 30s
          if (retryTimeout) clearTimeout(retryTimeout)
          retryTimeout = setTimeout(() => {
            if (!mountedRef.current) return
            if (pollInterval) { clearInterval(pollInterval); pollInterval = null }
            startSSE()
          }, 30000)
        }
      } catch {
        startPollFallback()
      }
    }

    // Close SSE when tab hidden to save DB hits; reopen on visible
    const onVis = () => {
      if (document.hidden) {
        es?.close(); es = null
        if (pollInterval) { clearInterval(pollInterval); pollInterval = null }
      } else if (useSSE) {
        if (pollInterval) { clearInterval(pollInterval); pollInterval = null }
        startSSE()
      }
    }
    document.addEventListener('visibilitychange', onVis)

    // Initial mode: try SSE, fallback to polling
    if (useSSE) startSSE()
    else startPollFallback()

    // Reconnect SSE when activeRunId/BatchId changes (poll for change every 1s)
    let lastRunId: number | null = activeRunIdRef.current
    let lastBatchId: string | null = activeBatchIdRef.current
    let retryTimeout: ReturnType<typeof setTimeout> | null = null
    const watchInterval = setInterval(() => {
      if (!useSSE || !mountedRef.current) return
      const curRun = activeRunIdRef.current
      const curBatch = activeBatchIdRef.current
      // Detect run/batch switch → reconnect SSE with new active_run_id
      if (es && (curRun !== lastRunId || curBatch !== lastBatchId)) {
        es.close(); es = null
        lastRunId = curRun; lastBatchId = curBatch
        if (!document.hidden) startSSE()
        return
      }
      lastRunId = curRun; lastBatchId = curBatch
      if (!es && !document.hidden) {
        startSSE()
      }
    }, 1000)

    return () => {
      document.removeEventListener('visibilitychange', onVis)
      if (es) es.close()
      if (pollInterval) clearInterval(pollInterval)
      if (retryTimeout) clearTimeout(retryTimeout)
      clearInterval(watchInterval)
    }
  }, [])
}

/**
 * Server health check polling — runs every 30s.
 */
export function useHealthPolling() {
  const { state, dispatch } = useApp()
  const wasOnlineRef = useRef(true)
  const healthPollMs = Math.min(120000, Math.max(15000, state.settings.healthPollMs || 30000))

  useEffect(() => {
    const check = async () => {
      try {
        await api.health()
        wasOnlineRef.current = true
        dispatch({ type: 'SET_SERVER_ONLINE', payload: true })
      } catch {
        wasOnlineRef.current = false
        dispatch({ type: 'SET_SERVER_ONLINE', payload: false })
      }
    }
    check()
    const interval = setInterval(check, healthPollMs)
    return () => clearInterval(interval)
  }, [dispatch, healthPollMs])
}

/**
 * Page visibility → telemetry pause — only pauses when user hasn't manually paused.
 * Hardware history keeps collecting in background; we just pause the *display* throttle,
 * not the global hardware polling, so switching internal tabs never stops collection.
 */
export function useVisibilityPause() {
  const { dispatch } = useApp()
  const userPausedRef = useRef(false)

  const setTelemetryPaused = (paused: boolean) => {
    userPausedRef.current = paused
    dispatch({ type: 'SET_TELEMETRY_PAUSED', payload: paused })
  }

  // Browser tab hidden → pause telemetry to save battery; internal BenchMax tab switches do NOT pause.
  useEffect(() => {
    const handler = () => {
      if (document.hidden) {
        dispatch({ type: 'SET_TELEMETRY_PAUSED', payload: true })
      } else if (!userPausedRef.current) {
        dispatch({ type: 'SET_TELEMETRY_PAUSED', payload: false })
      }
    }
    document.addEventListener('visibilitychange', handler)
    return () => document.removeEventListener('visibilitychange', handler)
  }, [dispatch])

  return { userPausedRef, setTelemetryPaused }
}

/**
 * Global hardware telemetry polling — runs every 3s regardless of which BenchMax tab is active.
 * Persists history in context so Hardware tab never resets when you navigate away.
 * Respects user-initiated pause (telemetryPaused) but ignores internal tab switches.
 */
export function useHardwarePolling() {
  const { state, dispatch } = useApp()
  const pausedRef = useRef(state.telemetryPaused)
  const mountedRef = useRef(true)
  const hardwarePollMs = Math.min(30000, Math.max(1000, state.settings.hardwarePollMs || 3000))

  useEffect(() => { pausedRef.current = state.telemetryPaused }, [state.telemetryPaused])
  useEffect(() => { mountedRef.current = true; return () => { mountedRef.current = false } }, [])

  useEffect(() => {
    const tick = async () => {
      if (!mountedRef.current || pausedRef.current) return
      try {
        const t = await api.getTelemetry()
        if (!mountedRef.current || pausedRef.current) return
        dispatch({
          type: 'APPEND_HARDWARE_TICK',
          payload: {
            cpu: t.cpu_percent || 0,
            ram: t.ram_percent || 0,
            gpu: t.gpu_available ? (t.gpu_load || 0) : 0,
            vram: t.gpu_available ? (t.vram_percent || 0) : 0,
          },
        })
        // Also keep sparkData in sync for header mini-graphs
        // header reads from sparkData; feed it from same tick if no active run poll is driving it
        if (!state.runStatus) {
          // only supplement when run poll isn't already updating sparkData
        }
      } catch { /* ignore */ }
    }
    tick()
    const id = setInterval(tick, hardwarePollMs)
    return () => clearInterval(id)
  }, [dispatch, hardwarePollMs])
}

/**
 * Dark mode class synchronization.
 */
export function useDarkModeSync() {
  const { state } = useApp()

  useEffect(() => {
    const html = document.documentElement
    if (state.darkMode) {
      html.classList.add('dark')
    } else {
      html.classList.remove('dark')
    }
    localStorage.setItem('benchmax-theme-dark', String(state.darkMode))
  }, [state.darkMode])
}

/**
 * Settings persistence — writes state.settings to localStorage on change.
 * Secrets are never part of settings (keys stay memory- or server-side).
 */
export function useSettingsSync() {
  const { state } = useApp()

  useEffect(() => {
    try {
      localStorage.setItem('benchmax-settings', JSON.stringify(state.settings))
    } catch { /* storage full or unavailable — settings just won't persist */ }
  }, [state.settings])
}

/**
 * Document title sync with run progress.
 */
export function useTitleSync() {
  const { state } = useApp()

  useEffect(() => {
    const prog = state.runStatus?.run_progress
    if (prog && state.activeRunId && prog.status_md?.includes('RUNNING')) {
      const pct = Math.round((prog.progress || 0) * 100)
      document.title = `[${pct}%] ${prog.active_task || 'Run'} — BenchMax`
    } else {
      document.title = 'BenchMax'
    }
  }, [state.runStatus, state.activeRunId])
}

/**
 * Keyboard shortcuts.
 */
export function useKeyboardShortcuts() {
  const { dispatch } = useApp()

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return

      if (e.ctrlKey && e.key >= '1' && e.key <= '6') {
        e.preventDefault()
        const tabs = ['connection', 'run', 'hardware', 'history', 'leaderboard', 'settings']
        dispatch({ type: 'SET_ACTIVE_TAB', payload: tabs[parseInt(e.key) - 1] })
      }
      if (e.key === '?') {
        dispatch({ type: 'SET_SHOW_SHORTCUTS', payload: true })
      }
      if (e.ctrlKey && e.key === 'Enter') {
        e.preventDefault()
        const btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent?.includes('Start'))
        btn?.click()
      }
      if (e.key === 'Escape') {
        dispatch({ type: 'SET_SHOW_SHORTCUTS', payload: false })
      }
      if (e.ctrlKey && e.key === '.') {
        e.preventDefault()
        const haltBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent?.includes('Halt') || b.textContent?.includes('Stop'))
        haltBtn?.click()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [dispatch])
}
