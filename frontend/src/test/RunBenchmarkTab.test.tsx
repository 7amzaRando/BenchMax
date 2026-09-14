import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import RunBenchmarkTab from '@/pages/RunBenchmarkTab'
import { BenchMaxProvider } from '@/lib/context'
import { getBenchmarks } from '@/lib/api'

vi.mock('@/lib/api', () => ({
  getBenchmarks: vi.fn(() => Promise.resolve({ benchmarks: [] })),
  checkRunReadiness: vi.fn(() => Promise.resolve({ ok: true, issues: [] })),
  installAllDatasets: vi.fn(() => Promise.resolve({ status: 'ok' })),
  downloadRuntimes: vi.fn(() => Promise.resolve({ status: 'ok' })),
  startRun: vi.fn(() => Promise.resolve({ run_id: 1, message: 'started' })),
  startBatch: vi.fn(() => Promise.resolve({ run_id: 1, batch_id: 'b1', message: 'started', summary: [], batch_id_display: 'b1' })),
  startModelQueue: vi.fn(() => Promise.resolve({ queue_id: 'q1', message: 'queued' })),
  getRunStatus: vi.fn(() => Promise.resolve({ status: 'RUNNING', current_index: 0, total_samples: 0 })),
  pauseRun: vi.fn(() => Promise.resolve({ status: 'paused' })),
  resumeRun: vi.fn(() => Promise.resolve({ status: 'resumed' })),
  haltRun: vi.fn(() => Promise.resolve({ status: 'halted' })),
  getActiveModelQueue: vi.fn(() => Promise.resolve({ queue_id: null, status: 'idle' })),
  haltModelQueue: vi.fn(() => Promise.resolve({ status: 'halted' })),
  skipModelQueue: vi.fn(() => Promise.resolve({ status: 'skipped' })),
}))

vi.mock('@/components/ui/toast-provider', () => ({
  useToast: () => ({ toast: vi.fn() }),
  ToastProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

function renderWithProvider(ui: React.ReactElement) { return render(<BenchMaxProvider>{ui}</BenchMaxProvider>) }

describe('RunBenchmarkTab', () => {
  beforeEach(() => { localStorage.clear() })
  it('renders the single-run heading', () => {
    renderWithProvider(<RunBenchmarkTab />)
    expect(screen.getByText('Run a benchmark')).toBeInTheDocument()
  })
  it('renders the Start benchmark button', () => {
    renderWithProvider(<RunBenchmarkTab />)
    expect(screen.getByRole('button', { name: 'Start benchmark' })).toBeInTheDocument()
  })
  it('renders the benchmark search input', () => {
    renderWithProvider(<RunBenchmarkTab />)
    expect(screen.getByPlaceholderText('Search benchmarks…')).toBeInTheDocument()
  })
  it('shows Not connected when not connected', () => {
    renderWithProvider(<RunBenchmarkTab />)
    expect(screen.getByText('Not connected')).toBeInTheDocument()
  })
  it('shows a partial-Docker badge for LiveBench', async () => {
    vi.mocked(getBenchmarks).mockResolvedValueOnce({ benchmarks: [
      { label: 'LiveBench', name: 'LiveBench', category: 'Composite', docker: false, docker_partial: true, samples: 1436, short: 'Meta-benchmark' },
    ] } as any)
    renderWithProvider(<RunBenchmarkTab />)
    expect(await screen.findByText('Docker · coding only')).toBeInTheDocument()
    expect(await screen.findByText('◐ Docker for coding')).toBeInTheDocument()
  })
})
