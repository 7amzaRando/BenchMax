import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import HistoryResultsTab from '@/pages/HistoryResultsTab'
import { BenchMaxProvider } from '@/lib/context'
import { loadHistory, loadRunDetails } from '@/lib/api'

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
  it('selecting a run enables Compare/Delete and loads run details', async () => {
    const seedRuns = [
      { 'Run ID': 1, Model: 'test-model', Benchmark: 'AIME', Status: 'COMPLETED', Progress: '5/5', Accuracy: '80%', 'Avg TPS': '10.0', 'Avg TTFT': '0.2', 'Avg Tokens': 100, 'Total Tokens': 500, Created: '2026-09-18' },
      { 'Run ID': 2, Model: 'test-model', Benchmark: 'ARC', Status: 'COMPLETED', Progress: '5/5', Accuracy: '60%', 'Avg TPS': '11.0', 'Avg TTFT': '0.3', 'Avg Tokens': 110, 'Total Tokens': 550, Created: '2026-09-18' },
    ] as any
    vi.mocked(loadHistory).mockResolvedValueOnce({ runs: seedRuns })
    vi.mocked(loadRunDetails).mockClear()
    renderWithProvider(<HistoryResultsTab />)
    // Checkbox select surfaces the bulk-action bar with actions enabled.
    const checkbox = await screen.findByRole('checkbox', { name: 'Select run 1' })
    fireEvent.click(checkbox)
    expect(await screen.findByText('1 selected')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Compare selected' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Delete' })).toBeEnabled()
    // Row click loads the run detail panel.
    fireEvent.click(checkbox.closest('tr')!)
    await waitFor(() => expect(vi.mocked(loadRunDetails)).toHaveBeenCalledWith(1))
    expect(await screen.findByText('Run #1')).toBeInTheDocument()
  })
})
