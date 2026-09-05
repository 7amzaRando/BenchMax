import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import LeaderboardTab from '@/pages/LeaderboardTab'
import { BenchMaxProvider } from '@/lib/context'

vi.mock('@/lib/api', () => ({
  loadLeaderboard: vi.fn(() => Promise.resolve({ leaderboard: [] })),
  deleteLeaderboardEntry: vi.fn(() => Promise.resolve({ leaderboard: [], status: 'deleted' })),
  getLeaderboardSettings: vi.fn(() => Promise.resolve({ api_key: '' })),
  saveLeaderboardSettings: vi.fn(() => Promise.resolve({ status: 'ok' })),
  syncLeaderboard: vi.fn(() => Promise.resolve({ status: 'ok' })),
}))

function renderWithProvider(ui: React.ReactElement) { return render(<BenchMaxProvider>{ui}</BenchMaxProvider>) }

describe('LeaderboardTab', () => {
  beforeEach(() => { localStorage.clear() })
  it('renders header Leaderboard', () => {
    renderWithProvider(<LeaderboardTab />)
    expect(screen.getByText('Leaderboard')).toBeInTheDocument()
  })
  it('renders filter input', () => {
    renderWithProvider(<LeaderboardTab />)
    expect(screen.getByPlaceholderText('Filter by model, benchmark or ID…')).toBeInTheDocument()
  })
  it('shows No completed runs yet when empty', async () => {
    renderWithProvider(<LeaderboardTab />)
    expect(await screen.findByText(/No completed runs yet/)).toBeInTheDocument()
  })
})
