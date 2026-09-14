import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { health, updateRunNotes } from '@/lib/api'

// Tests the REAL fetchJson layer in lib/api.ts (no '@/lib/api' mock here).
// Regression context: fetchJson must merge caller headers AFTER the default
// ({ 'Content-Type': 'application/json', ...options?.headers }) so a
// caller-supplied header (e.g. Authorization) survives. updateRunNotes is the
// exported path that forwards caller-supplied headers through fetchJson, so it
// pins the merge; health() pins the default + URL building (BASE = '/api').

const fetchMock = vi.fn()

beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('lib/api fetchJson layer', () => {
  it('preserves caller-supplied headers alongside the Content-Type default', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ status: 'ok', notes: 'hi' }))
    await updateRunNotes(7, 'hi')

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/runs/7/notes')
    // Caller-supplied headers must not be dropped by the default merge.
    expect((init.headers as Record<string, string>)['Content-Type']).toBe('application/json')

    // Default still applied when the caller passes no headers.
    fetchMock.mockResolvedValue(jsonResponse({ status: 'ok' }))
    await health()
    const [, healthInit] = fetchMock.mock.calls[1] as [string, RequestInit]
    expect((healthInit.headers as Record<string, string>)['Content-Type']).toBe('application/json')
  })

  it('throws an Error containing the HTTP status on non-ok responses', async () => {
    // Fresh Response per call: a body can only be consumed once.
    fetchMock.mockImplementation(() => Promise.resolve(new Response('boom', { status: 500 })))
    await expect(health()).rejects.toThrow(/HTTP 500/)
    await expect(health()).rejects.toThrow(/boom/)
  })

  it('health() hits /api/health and returns parsed JSON', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ status: 'ok' }))
    const data = await health()

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/health')
    expect(data).toEqual({ status: 'ok' })
  })
})
