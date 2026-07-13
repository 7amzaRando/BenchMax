import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import App from '@/App'

vi.mock('@/lib/api', () => {
  const fn = <T,>(v: T) => () => Promise.resolve(v)
  return {
    connectLMStudio: fn({ status: '🟢 Connected', models: [], choices: [], selected: null, metadata: {} }),
    getHfToken: fn({ token: '' }),
    setHfToken: fn({ status: 'ok' }),
    poll: fn({
      telemetry: { cpu_percent: 0, ram_used_gb: 0, ram_total_gb: 0, ram_percent: 0, gpu_available: false, gpu_name: null, gpu_load: 0, vram_total_mb: 0, vram_used_mb: 0, vram_percent: 0 },
      run_progress: { progress: 0, status_md: 'IDLE', active_task: '', avg_tps: '0', avg_ttft: '0', accuracy: '0%', token_stats: '0 | 0 | 0' },
      batch_progress: { progress: 0, status_md: '', eta: '', summary: [], batch_id: '', completed: 0, total: 0, current_benchmark: '' },
    }),
    getTelemetry: fn({ cpu_percent: 0, ram_used_gb: 0, ram_total_gb: 0, ram_percent: 0, gpu_available: false, gpu_name: null, gpu_load: 0, vram_total_mb: 0, vram_used_mb: 0, vram_percent: 0 }),
    loadHistory: fn({ runs: [] }),
    loadLeaderboard: fn({ leaderboard: [] }),
    getBenchmarks: fn({ benchmarks: [] }),
    getLeaderboardSettings: fn({ api_key: '' }),
    scanDatasets: fn({ datasets: [] }),
  }
})

describe('App', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('renders the header', () => {
    render(<App />)
    expect(screen.getByText('BenchMax')).toBeInTheDocument()
  })

  it('renders all tab triggers', () => {
    render(<App />)
    const tabs = screen.getAllByRole('tab')
    expect(tabs.map(t => t.textContent)).toEqual(
      expect.arrayContaining(['Connection', 'Run Benchmark', 'Hardware', 'History & Results', 'Leaderboard'])
    )
    expect(tabs).toHaveLength(5)
  })

  it('renders dark mode toggle', () => {
    render(<App />)
    const toggle = screen.getByLabelText('Toggle dark mode')
    expect(toggle).toBeInTheDocument()
  })
})
