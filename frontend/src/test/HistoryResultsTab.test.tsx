import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import HistoryResultsTab from '@/pages/HistoryResultsTab'
import { BenchMaxProvider } from '@/lib/context'

vi.mock('@/lib/api', () => ({
  loadHistory: vi.fn(() => Promise.resolve({ runs: [] })),
  loadRunDetails: vi.fn(() => Promise.resolve({
    summary: '', samples: [], failed_tasks: [], selected_failed: null,
    token_chart: [], ttft_histogram: [], tps_histogram: [], category_chart: [],
  })),
  loadDepthResults: vi.fn(() => Promise.resolve({ results: [] })),
  loadComparison: vi.fn(() => Promise.resolve({ accuracy: [], latency: [], tokens: [] })),
  loadTrustedCard: vi.fn(() => Promise.resolve({ text: 'card' })),
  loadBatchSummary: vi.fn(() => Promise.resolve({ summary: [], chart: [], latency_chart: [] })),
  resumeRun: vi.fn(() => Promise.resolve({ status: 'resumed' })),
  updateRunNotes: vi.fn(() => Promise.resolve({ status: 'ok', notes: '' })),
  getDiff: vi.fn(() => Promise.resolve({ html: '' })),
  clearAllHistory: vi.fn(() => Promise.resolve({ history: [], leaderboard: [], status: 'cleared' })),
  deleteLeaderboardEntry: vi.fn(() => Promise.resolve({ leaderboard: [], status: 'deleted' })),
  deleteRuns: vi.fn(() => Promise.resolve({ leaderboard: [], status: 'deleted' })),
}))

vi.mock('@/components/ui/toast-provider', () => ({
  useToast: () => ({ toast: vi.fn() }),
  ToastProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

function renderWithProvider(ui: React.ReactElement) { return render(<BenchMaxProvider>{ui}</BenchMaxProvider>) }

describe('HistoryResultsTab', () => {
  beforeEach(() => { localStorage.clear() })
  it('renders the All runs heading', () => {
    renderWithProvider(<HistoryResultsTab />)
    expect(screen.getByText('All runs')).toBeInTheDocument()
  })
  it('renders the history filter input', () => {
    renderWithProvider(<HistoryResultsTab />)
    expect(screen.getByPlaceholderText('Filter by model, benchmark or status…')).toBeInTheDocument()
  })
  it('shows the empty state when no runs exist', async () => {
    renderWithProvider(<HistoryResultsTab />)
    expect(await screen.findByText('No runs yet — start one from the Run tab.')).toBeInTheDocument()
  })
})
