import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import HardwareTab from '@/pages/HardwareTab'

vi.mock('@/lib/api', () => ({
  getTelemetry: vi.fn(() => Promise.resolve({
    cpu_percent: 12.3,
    ram_used_gb: 8.1,
    ram_total_gb: 31.9,
    ram_percent: 25.4,
    gpu_available: true,
    gpu_name: 'AMD Radeon RX 7600 XT',
    gpu_load: 14.2,
    vram_total_mb: 16384,
    vram_used_mb: 4096,
    vram_percent: 25.0,
  })),
}))

describe('HardwareTab', () => {
  it('renders the header', () => {
    render(<HardwareTab />)
    expect(screen.getByText('Real-Time Host Telemetry')).toBeInTheDocument()
  })

  it('renders metric cards', () => {
    render(<HardwareTab />)
    expect(screen.getByText('CPU')).toBeInTheDocument()
    expect(screen.getByText('System RAM')).toBeInTheDocument()
    expect(screen.getByText('GPU Load')).toBeInTheDocument()
    expect(screen.getByText('VRAM')).toBeInTheDocument()
  })

  it('renders pause button', () => {
    render(<HardwareTab />)
    expect(screen.getByText('⏸ Pause')).toBeInTheDocument()
  })

  it('shows chart sections', () => {
    render(<HardwareTab />)
    expect(screen.getByText('CPU %')).toBeInTheDocument()
    expect(screen.getByText('RAM %')).toBeInTheDocument()
    expect(screen.getByText('GPU Load %')).toBeInTheDocument()
    expect(screen.getByText('VRAM %')).toBeInTheDocument()
  })
})
