import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import SettingsTab from '@/pages/SettingsTab'
import { BenchMaxProvider } from '@/lib/context'
import { useSettingsSync, useDarkModeSync } from '@/lib/hooks'

vi.mock('@/lib/api', () => ({
  authStatus: vi.fn(() => Promise.resolve({ password_set: false })),
  authSetup: vi.fn(() => Promise.resolve({ status: 'ok' })),
  getHfToken: vi.fn(() => Promise.resolve({ token: '', set: false })),
  setHfToken: vi.fn(() => Promise.resolve({ status: 'saved' })),
  getLeaderboardSettings: vi.fn(() => Promise.resolve({ api_key: '', supabase_url: '', auto_sync: false })),
  saveLeaderboardSettings: vi.fn(() => Promise.resolve({ status: 'saved' })),
  exportHistoryLink: vi.fn(() => '/api/export/history'),
  getMcpInfo: vi.fn(() => Promise.resolve({
    mounted: true, endpoint: '/mcp', tools: ['list_benchmarks', 'run_benchmark'],
    stdio_command: ['py', 'mcp_server.py'], install_command: 'py cli.py install-mcp --client all',
  })),
  installMcp: vi.fn(() => Promise.resolve({ status: 'ok', action: 'written to', configs: { claude: 'c.json' } })),
}))

vi.mock('@/components/ui/toast-provider', () => ({
  useToast: () => ({ toast: vi.fn() }),
  ToastProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

// Mount the same persistence hooks AppContent uses — settings/theme only
// reach localStorage through them.
function renderSettings() {
  function Boot() {
    useSettingsSync()
    useDarkModeSync()
    return <SettingsTab />
  }
  return render(<BenchMaxProvider><Boot /></BenchMaxProvider>)
}

describe('SettingsTab', () => {
  beforeEach(() => { localStorage.clear() })

  it('renders all sections', () => {
    renderSettings()
    expect(screen.getByText('Run defaults')).toBeInTheDocument()
    expect(screen.getByText('Live updates')).toBeInTheDocument()
    expect(screen.getByText('Appearance')).toBeInTheDocument()
    expect(screen.getByText('Access & secrets')).toBeInTheDocument()
    expect(screen.getByText('Data')).toBeInTheDocument()
    expect(screen.getByText('About')).toBeInTheDocument()
  })

  it('shows MCP status and copyable endpoint once info loads', async () => {
    renderSettings()
    expect(await screen.findByText('AI access (MCP)')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByText(/Live — 2 tools/)).toBeInTheDocument()
    })
    // Manual config lives behind a disclosure until asked for.
    fireEvent.click(screen.getByText(/Manual setup/))
    expect(await screen.findByLabelText('MCP endpoint URL')).toBeInTheDocument()
  })

  it('one-click install calls the endpoint and confirms', async () => {
    const api = await import('@/lib/api')
    renderSettings()
    fireEvent.click(await screen.findByText('Connect all my apps'))
    await waitFor(() => {
      expect(api.installMcp).toHaveBeenCalledWith({ clients: ['all'], url: window.location.origin })
      expect(screen.getByText(/Connected claude/)).toBeInTheDocument()
    })
  })

  it('persists a changed default to localStorage', async () => {
    renderSettings()
    const maxTokens = screen.getByLabelText('Default max tokens') as HTMLInputElement
    fireEvent.change(maxTokens, { target: { value: '4096' } })
    await waitFor(() => {
      const raw = localStorage.getItem('benchmax-settings')
      expect(raw).toContain('4096')
    })
  })

  it('toggles theme and resets all settings', async () => {    renderSettings()
    fireEvent.click(screen.getByText('Switch to light mode'))
    await waitFor(() => {
      expect(localStorage.getItem('benchmax-theme-dark')).toBe('false')
    })
    fireEvent.click(screen.getByText('Reset all settings'))
    await waitFor(() => {
      const raw = localStorage.getItem('benchmax-settings')
      expect(raw).toContain('8192')
    })
  })

  it('saves provider default and telemetry-paused default', async () => {
    renderSettings()
    const url = screen.getByLabelText('Default provider URL') as HTMLInputElement
    fireEvent.change(url, { target: { value: 'http://mybox:11434/v1' } })
    const boxes = screen.getAllByRole('checkbox')
    const pauseBox = boxes.find(b => b.parentElement?.textContent?.includes('Pause hardware telemetry')) as HTMLInputElement
    fireEvent.click(pauseBox)
    await waitFor(() => {
      const raw = localStorage.getItem('benchmax-settings') || ''
      expect(raw).toContain('mybox:11434')
      expect(raw).toContain('telemetryPausedByDefault')
    })
  })
})
