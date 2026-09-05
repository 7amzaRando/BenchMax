import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { BenchMaxProvider, useApp } from '@/lib/context'

function TestConsumer() {
  const { state, dispatch } = useApp()
  return (
    <div>
      <span data-testid="tab">{state.activeTab}</span>
      <span data-testid="connected">{String(state.connection.connected)}</span>
      <button onClick={() => dispatch({ type: 'SET_ACTIVE_TAB', payload: 'run' })}>switch</button>
    </div>
  )
}

describe('BenchMaxProvider + useApp', () => {
  it('renders children', () => {
    render(
      <BenchMaxProvider>
        <div>child</div>
      </BenchMaxProvider>
    )
    expect(screen.getByText('child')).toBeInTheDocument()
  })

  it('useApp returns state and dispatch', () => {
    render(
      <BenchMaxProvider>
        <TestConsumer />
      </BenchMaxProvider>
    )
    expect(screen.getByTestId('tab')).toHaveTextContent('connection')
    expect(screen.getByTestId('connected')).toHaveTextContent('false')
  })

  it('dispatch updates state', () => {
    render(
      <BenchMaxProvider>
        <TestConsumer />
      </BenchMaxProvider>
    )
    expect(screen.getByTestId('tab')).toHaveTextContent('connection')
    fireEvent.click(screen.getByText('switch'))
    expect(screen.getByTestId('tab')).toHaveTextContent('run')
  })
})
