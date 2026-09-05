import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

function jsonResponse(data: unknown, ok = true) {
  return {
    ok,
    status: ok ? 200 : 404,
    text: async () => JSON.stringify(data),
    json: async () => data,
  } as Response
}

describe('public API client', () => {
  beforeEach(() => {
    ;(globalThis as any).document = { cookie: '' }
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('fetches current week', async () => {
    const mod = await import('../public')
    const mock = vi.fn().mockResolvedValue(jsonResponse({ id: 1, week: 12, title: '第十二周', problems: [] }))
    vi.stubGlobal('fetch', mock)
    const week = await mod.fetchCurrentWeek()
    expect(week?.week).toBe(12)
    expect(mock.mock.calls[0][0]).toBe('/api/public/weeks/current')
  })

  it('fetches the published week list', async () => {
    const mod = await import('../public')
    const mock = vi.fn().mockResolvedValue(jsonResponse([{ id: 2, week: 10, title: '第十周', problem_count: 2 }]))
    vi.stubGlobal('fetch', mock)
    const weeks = await mod.fetchPublishedWeeks()
    expect(weeks[0].week).toBe(10)
    expect(mock.mock.calls[0][0]).toBe('/api/public/weeks')
  })

  it('run sample posts code and sample_index', async () => {
    const mod = await import('../public')
    const mock = vi.fn().mockResolvedValue(jsonResponse({ mode: 'sample', status: 'ACCEPTED', results: [] }))
    vi.stubGlobal('fetch', mock)
    await mod.runSample(1, 2, 'int main(){}', 0)
    const [url, init] = mock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/public/run/sample')
    expect(init.method).toBe('POST')
    const body = JSON.parse(init.body as string)
    expect(body.code).toBe('int main(){}')
    expect(body.sample_index).toBe(0)
  })

  it('run custom posts input', async () => {
    const mod = await import('../public')
    const mock = vi.fn().mockResolvedValue(jsonResponse({ mode: 'custom', status: 'ACCEPTED', results: [] }))
    vi.stubGlobal('fetch', mock)
    await mod.runCustom(1, 2, 'int main(){}', '1 2')
    const [url] = mock.mock.calls[0] as [string]
    expect(url).toBe('/api/public/run/custom')
  })

  it('run all posts to all endpoint', async () => {
    const mod = await import('../public')
    const mock = vi.fn().mockResolvedValue(jsonResponse({ mode: 'all', status: 'ACCEPTED', results: [] }))
    vi.stubGlobal('fetch', mock)
    await mod.runAll(1, 2, 'int main(){}')
    const [url] = mock.mock.calls[0] as [string]
    expect(url).toBe('/api/public/run/all')
  })
})
