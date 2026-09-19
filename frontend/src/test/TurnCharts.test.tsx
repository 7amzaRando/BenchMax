import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { TurnCharts } from '@/components/TurnCharts'

// Recharts needs measured layout (ResizeObserver + SVG) that jsdom cannot
// provide, so stub the chart primitives and capture the mapped data payload.
// This still exercises TurnCharts' real logic: assistant-turn filtering,
// T{n+1} labels, and tps/ttft/token mapping.
vi.mock('recharts', () => ({
  BarChart: ({ data }: any) => <div data-testid="barchart">{JSON.stringify(data)}</div>,
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
  Cell: () => null,
}))

const turns = [
  { turn: -1, role: 'user', content: 'Solve step by step.' },
  { turn: 0, role: 'assistant', content: 'First attempt', tps: 40.4, ttft: 0.578, thinking_tokens: 100, response_tokens: 200 },
  { turn: 1, role: 'assistant', content: 'Second attempt', tps: 35.2, ttft: 0.611, thinking_tokens: 150, response_tokens: 250 },
] as any

describe('TurnCharts', () => {
  it('renders per-turn TPS/TTFT charts with turn labels and values', () => {
    render(<TurnCharts turns={turns} />)
    expect(screen.getByText('Per-Turn TPS')).toBeInTheDocument()
    expect(screen.getByText('Per-Turn TTFT')).toBeInTheDocument()
    const charts = screen.getAllByTestId('barchart')
    expect(charts).toHaveLength(2)
    // TPS chart carries per-turn TPS + summed tokens; TTFT chart per-turn TTFT.
    expect(JSON.parse(charts[0].textContent || '[]')).toEqual([
      { Turn: 'T1', TPS: 40.4, Tokens: 300 },
      { Turn: 'T2', TPS: 35.2, Tokens: 400 },
    ])
    expect(JSON.parse(charts[1].textContent || '[]')).toEqual([
      { Turn: 'T1', TTFT: 0.578 },
      { Turn: 'T2', TTFT: 0.611 },
    ])
  })
  it('renders nothing for a single assistant turn', () => {
    const { container } = render(<TurnCharts turns={[turns[1]]} />)
    expect(container.firstChild).toBeNull()
  })
})
