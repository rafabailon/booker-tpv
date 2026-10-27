import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'

function mockFetch(response: Response | Promise<Response>) {
  const fetchMock = vi.fn().mockResolvedValue(response)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('api client', () => {
  it('joins validation details into a readable message', async () => {
    mockFetch(new Response(JSON.stringify({
      detail: [{ msg: 'Campo obligatorio' }, { msg: 'ISBN no válido' }],
    }), { status: 422, headers: { 'Content-Type': 'application/problem+json' } }))

    await expect(api.me()).rejects.toThrow('Campo obligatorio, ISBN no válido')
  })

  it('falls back to the status code when the error body is not JSON', async () => {
    mockFetch(new Response('gateway error', { status: 502 }))

    await expect(api.me()).rejects.toThrow('Error 502')
  })

  it('returns undefined for a successful no-content response', async () => {
    mockFetch(new Response(null, { status: 204 }))

    await expect(api.logout()).resolves.toBeUndefined()
  })

  it('translates network failures into a friendly message', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    await expect(api.me()).rejects.toThrow('No se pudo conectar con el servidor')
  })

  it('downloads the CSV with the filename sent by the server', async () => {
    mockFetch(new Response(new Blob(['ticket;total']), {
      status: 200,
      headers: {
        'Content-Type': 'text/csv; charset=utf-8',
        'Content-Disposition': 'attachment; filename="booker-ventas-2026-01-01.csv"',
      },
    }))

    const download = await api.dailySalesCsv('2026-01-01')

    expect(download.filename).toBe('booker-ventas-2026-01-01.csv')
    expect(download.blob.size).toBe(13)
    expect(download.blob.type).toBe('text/csv;charset=utf-8')
  })

  it('uses the report date in the CSV request and a fallback filename', async () => {
    const fetchMock = mockFetch(new Response(new Blob(['ok']), { status: 200 }))

    const download = await api.dailySalesCsv('2026-02-03')

    expect(fetchMock).toHaveBeenCalledWith('/api/v1/reports/daily-sales.csv?report_date=2026-02-03', { credentials: 'include' })
    expect(download.filename).toBe('booker-ventas.csv')
  })
})
