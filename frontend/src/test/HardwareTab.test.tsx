import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import HardwareTab from '@/pages/HardwareTab'
import { BenchMaxProvider } from '@/lib/context'

vi.mock('@/lib/api', () => ({
  getTelemetry: vi.fn(() => Promise.resolve({
    cpu_percent: 12.3, ram_used_gb: 8.1, ram_total_gb: 31.9, ram_percent: 25.4,
    gpu_available: true, gpu_name: 'AMD Radeon RX 7600 XT', gpu_load: 14.2, vram_total_mb: 16384, vram_used_mb: 4096, vram_percent: 25.0,
  })),
}))

function renderWithProvider(ui: React.ReactElement) { return render(<BenchMaxProvider>{ui}</BenchMaxProvider>) }

describe('HardwareTab', () => {
  it('renders the header', () => {
    renderWithProvider(<HardwareTab />)
    expect(screen.getByText('Real-time host telemetry')).toBeInTheDocument()
  })
  it('renders metric cards', () => {
    renderWithProvider(<HardwareTab />)
    expect(screen.getByText('CPU')).toBeInTheDocument()
    expect(screen.getByText('System RAM')).toBeInTheDocument()
    expect(screen.getByText('GPU')).toBeInTheDocument()
    expect(screen.getByText('VRAM')).toBeInTheDocument()
  })
  it('renders pause button', () => {
    renderWithProvider(<HardwareTab />)
    expect(screen.getByText('Pause')).toBeInTheDocument()
  })
  it('shows chart sections', () => {
    renderWithProvider(<HardwareTab />)
    expect(screen.getByText('CPU usage')).toBeInTheDocument()
    expect(screen.getByText('RAM usage')).toBeInTheDocument()
    expect(screen.getByText('GPU load')).toBeInTheDocument()
    expect(screen.getByText('VRAM usage')).toBeInTheDocument()
  })
})
