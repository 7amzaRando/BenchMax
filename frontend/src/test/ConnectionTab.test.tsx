import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ConnectionTab from '@/pages/ConnectionTab'
import { BenchMaxProvider } from '@/lib/context'

vi.mock('@/lib/api', () => ({
  connectLMStudio: vi.fn(() => Promise.resolve({ status: 'Connection failed', models: [], choices: [], selected: null, metadata: {} })),
  getHfToken: vi.fn(() => Promise.resolve({ token: '' })),
  setHfToken: vi.fn(() => Promise.resolve({ status: 'ok' })),
  scanDatasets: vi.fn(() => Promise.resolve({ datasets: [] })),
  installAllDatasets: vi.fn(() => Promise.resolve({ status: 'ok' })),
  installDataset: vi.fn(() => Promise.resolve({ status: 'ok' })),
  downloadRuntimes: vi.fn(() => Promise.resolve({ status: 'ok' })),
  getDockerStatus: vi.fn(() => Promise.resolve({ available: false, image_exists: false, message: '' })),
}))

vi.mock('@/components/ui/toast-provider', () => ({
  useToast: () => ({ toast: vi.fn() }),
  ToastProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

function renderWithProvider(ui: React.ReactElement) { return render(<BenchMaxProvider>{ui}</BenchMaxProvider>) }

describe('ConnectionTab', () => {
  beforeEach(() => { localStorage.clear() })
  it('renders provider presets', () => {
    renderWithProvider(<ConnectionTab />)
    expect(screen.getAllByText('LM Studio').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Ollama').length).toBeGreaterThan(0)
  })
  it('renders API URL input', () => {
    renderWithProvider(<ConnectionTab />)
    expect(screen.getByLabelText('Base URL')).toBeInTheDocument()
  })
  it('renders Connect button', () => {
    renderWithProvider(<ConnectionTab />)
    expect(screen.getByText('Connect')).toBeInTheDocument()
  })
  it('shows Not connected when not connected', () => {
    renderWithProvider(<ConnectionTab />)
    expect(screen.getByText('Not connected')).toBeInTheDocument()
  })
})
