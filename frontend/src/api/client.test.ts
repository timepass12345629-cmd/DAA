import { describe, it, expect, vi, beforeEach } from 'vitest'
import { api, ApiError } from './client'

describe('RingScope API Client', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('correctly constructs export URLs with format query parameters', () => {
    const csvUrl = api.getExportUrl('exp_123', 'csv')
    const jsonUrl = api.getExportUrl('exp_123', 'json')

    expect(csvUrl).toBe('/api/v1/experiments/exp_123/export?format=csv')
    expect(jsonUrl).toBe('/api/v1/experiments/exp_123/export?format=json')
  })

  it('handles ApiError with status and error payload', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({ detail: 'Graph not found' }),
    } as Response)

    await expect(api.getGraph('nonexistent_id')).rejects.toThrow(ApiError)
  })

  it('successfully fetches health check payload', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        status: 'ok',
        version: '1.0.0',
        algorithms: ['goldberg', 'greedy_peeling', 'greedy_plus_plus'],
        active_graphs: 1,
        active_streams: 0,
        active_experiments: 0,
      }),
    } as Response)

    const health = await api.getHealth()
    expect(health.status).toBe('ok')
    expect(health.version).toBe('1.0.0')
    expect(health.active_graphs).toBe(1)
  })
})
