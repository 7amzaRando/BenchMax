import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import LanLoginGate from '@/components/LanLoginGate'
import { isLanUnauthorized } from '@/lib/api'

const fetchMock = vi.fn()

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
  localStorage.clear()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('LanLoginGate', () => {
  it('renders children when LAN login is not required', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ lan_required: false, password_set: true, authenticated: false }))
    render(<LanLoginGate><div>secret-child</div></LanLoginGate>)
    expect(await screen.findByText('secret-child')).toBeInTheDocument()
  })

  it('blocks with no-password message and Retry when no LAN password set', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ lan_required: true, password_set: false, authenticated: false }))
    render(<LanLoginGate><div>secret-child</div></LanLoginGate>)
    expect(await screen.findByText(/has no LAN password yet/)).toBeInTheDocument()
    expect(screen.queryByText('secret-child')).not.toBeInTheDocument()
    // Retry re-checks status
    fetchMock.mockResolvedValue(jsonResponse({ lan_required: false, password_set: false, authenticated: false }))
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByText('secret-child')).toBeInTheDocument()
  })

  it('shows login card and stores token on successful login', async () => {
    fetchMock.mockImplementation((url: string) => {
      if (String(url).endsWith('/auth/status')) {
        return Promise.resolve(jsonResponse({ lan_required: true, password_set: true, authenticated: false }))
      }
      return Promise.resolve(jsonResponse({ token: 'abc123' }))
    })
    render(<LanLoginGate><div>secret-child</div></LanLoginGate>)
    expect(await screen.findByText('BenchMax LAN Login')).toBeInTheDocument()
    expect(screen.queryByText('secret-child')).not.toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('LAN password'), { target: { value: 's3cret' } })
    fireEvent.click(screen.getByRole('button', { name: 'Unlock' }))
    expect(await screen.findByText('secret-child')).toBeInTheDocument()
    expect(localStorage.getItem('bm_lan_token')).toBe('abc123')
  })

  it('isLanUnauthorized detects LAN 401 errors only', () => {
    expect(isLanUnauthorized(new Error('HTTP 401: {"detail": "LAN login required."}'))).toBe(true)
    expect(isLanUnauthorized(new Error('HTTP 500: boom'))).toBe(false)
    expect(isLanUnauthorized(new Error('HTTP 401: wrong password'))).toBe(false)
  })

  it('shows wrong-password error on 401 login', async () => {
    fetchMock.mockImplementation((url: string) => {
      if (String(url).endsWith('/auth/status')) {
        return Promise.resolve(jsonResponse({ lan_required: true, password_set: true, authenticated: false }))
      }
      return Promise.resolve(new Response('wrong password', { status: 401 }))
    })
    render(<LanLoginGate><div>secret-child</div></LanLoginGate>)
    expect(await screen.findByText('BenchMax LAN Login')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('LAN password'), { target: { value: 'bad' } })
    fireEvent.click(screen.getByRole('button', { name: 'Unlock' }))
    expect(await screen.findByText(/Wrong password/)).toBeInTheDocument()
    expect(screen.queryByText('secret-child')).not.toBeInTheDocument()
    expect(localStorage.getItem('bm_lan_token')).toBeNull()
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
  })
})
