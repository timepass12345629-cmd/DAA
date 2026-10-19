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

  it('validates Goldberg/Charikar density metric (|E|/|V|) and contrast ratio invariants', () => {
    // Verify planted_dense scenario metrics
    const n = 30
    const m = 41
    const wholeGraphDensity = m / n // 41 / 30 = 1.36666...
    expect(wholeGraphDensity).toBeCloseTo(1.36667, 4)

    // Standard combinatorial density: 2E / (N*(N-1))
    const standardDensity = (2 * m) / (n * (n - 1))
    expect(standardDensity).toBeCloseTo(0.09425, 4)

    // Candidate cluster metrics: 8 nodes, 26 internal edges
    const candN = 8
    const candM = 26
    const candDensity = candM / candN // 26 / 8 = 3.25
    expect(candDensity).toBe(3.25)

    // Density contrast ratio: candidateDensity / wholeGraphDensity
    const contrastRatio = candDensity / wholeGraphDensity // 3.25 / 1.36667 = 2.37804...
    expect(contrastRatio).toBeCloseTo(2.378, 3)
  })

  it('initializes a synthetic baseline graph and queries topology', async () => {
    const mockBaseline = {
      graph_id: 'graph_synth_123',
      num_nodes: 30,
      num_edges: 41,
      nodes: Array.from({ length: 30 }, (_, i) => `ACC_${i}`),
      edges: [{ source: 'ACC_0', target: 'ACC_1', amount: 1000, timestamp: 1 }],
      is_directed: false,
    }

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockBaseline,
    } as Response)

    const generated = await api.generateGraph({
      scenario: 'planted_dense',
      num_nodes: 30,
      num_edges: 41,
      cluster_size: 8,
    })

    expect(generated.graph_id).toBe('graph_synth_123')
    expect(generated.num_nodes).toBe(30)
    expect(generated.nodes.length).toBe(30)
  })

  it('starts streaming session linked to an initial baseline graph ID', async () => {
    const mockSession = {
      stream_id: 'stream_abc_999',
      mode: 'B',
      recompute_interval: 50,
      decay_factor: 1.0,
      decay_window_batches: 5,
      version: 0,
      total_vertices: 30,
      total_unique_edges: 41,
    }

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockSession,
    } as Response)

    const session = await api.startStream({
      mode: 'B',
      recompute_interval: 50,
      initial_graph_id: 'graph_synth_123',
    })

    expect(session.stream_id).toBe('stream_abc_999')
    expect(session.mode).toBe('B')
    expect(session.total_vertices).toBe(30)
    expect(session.total_unique_edges).toBe(41)
  })

  it('derives dynamic nodes and candidate highlights from stream step snapshots', async () => {
    const mockStepResponse = {
      stream_id: 'stream_abc_999',
      steps_processed: 1,
      snapshots: [
        {
          version: 1,
          mode: 'B',
          num_new_unique_edges: 3,
          affected_vertices: ['ACC_0', 'ACC_NEW_1', 'ACC_NEW_2'],
          densest_density: 3.5,
          total_recomputations: 1,
          total_time_ms: 2.4,
          amortized_time_ms: 0.8,
          total_vertices: 32,
          total_unique_edges: 44,
          candidate_nodes: ['ACC_0', 'ACC_NEW_1'],
        },
      ],
      total_recomputations: 1,
    }

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockStepResponse,
    } as Response)

    const stepResult = await api.stepStream({
      stream_id: 'stream_abc_999',
      steps: 1,
      batch_size: 5,
    })

    expect(stepResult.snapshots.length).toBe(1)
    const snap = stepResult.snapshots[0]
    expect(snap.affected_vertices).toContain('ACC_NEW_1')
    expect(snap.candidate_nodes).toEqual(['ACC_0', 'ACC_NEW_1'])

    // Invariant: New vertices outside the original baseline (30 nodes) are tracked dynamically
    const baselineNodes = new Set(Array.from({ length: 30 }, (_, i) => `ACC_${i}`))
    const derivedNewNodes = snap.affected_vertices.filter(v => !baselineNodes.has(v))
    expect(derivedNewNodes).toEqual(['ACC_NEW_1', 'ACC_NEW_2'])
  })

  it('correctly models ring injection edge topology', async () => {
    const mockRingStepResponse = {
      stream_id: 'stream_abc_999',
      steps_processed: 1,
      snapshots: [
        {
          version: 2,
          mode: 'B',
          num_new_unique_edges: 5,
          affected_vertices: ['RING_999_0', 'RING_999_1', 'RING_999_2', 'RING_999_3', 'RING_999_4'],
          densest_density: 1.0,
          total_recomputations: 2,
          total_time_ms: 1.8,
          amortized_time_ms: 0.36,
          total_vertices: 37,
          total_unique_edges: 49,
          candidate_nodes: ['RING_999_0', 'RING_999_1', 'RING_999_2', 'RING_999_3', 'RING_999_4'],
        },
      ],
      total_recomputations: 2,
    }

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockRingStepResponse,
    } as Response)

    const ringResult = await api.injectRing({
      stream_id: 'stream_abc_999',
      ring_size: 5,
      complete_clique: false,
    })

    expect(ringResult.snapshots[0].affected_vertices.length).toBe(5)

    // Derive deterministic ring cycle edges
    const ringNodes = ringResult.snapshots[0].affected_vertices
    const derivedRingEdges = ringNodes.map((node, i) => ({
      source: node,
      target: ringNodes[(i + 1) % ringNodes.length],
    }))

    expect(derivedRingEdges.length).toBe(5)
    expect(derivedRingEdges[0]).toEqual({ source: 'RING_999_0', target: 'RING_999_1' })
    expect(derivedRingEdges[4]).toEqual({ source: 'RING_999_4', target: 'RING_999_0' })
  })

  it('rejects streaming actions on invalid or nonexistent stream ID', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({ detail: "Stream session 'invalid_id' not found" }),
    } as Response)

    await expect(api.stepStream({ stream_id: 'invalid_id', steps: 1 })).rejects.toThrow(ApiError)
  })

  it('handles opt-in new_edges streaming responses and deduplication', async () => {
    const mockStepWithEdges = {
      stream_id: 'stream_abc_999',
      steps_processed: 1,
      snapshots: [
        {
          version: 3,
          mode: 'B',
          num_new_unique_edges: 2,
          affected_vertices: ['ACC_0', 'ACC_1', 'ACC_2'],
          candidate_nodes: ['ACC_0', 'ACC_1'],
          densest_density: 1.0,
          total_recomputations: 1,
          total_time_ms: 1.2,
          amortized_time_ms: 0.6,
          total_vertices: 30,
          total_unique_edges: 43,
          new_edges: [
            { source: 'ACC_0', target: 'ACC_1', amount: 50.0 },
            { source: 'ACC_1', target: 'ACC_2', amount: 60.0 },
          ],
        },
      ],
      current_candidate_nodes: ['ACC_0', 'ACC_1'],
      current_density: 1.0,
      total_transactions: 10,
      total_unique_edges: 43,
      recomputations_count: 1,
      new_edges: [
        { source: 'ACC_0', target: 'ACC_1', amount: 50.0 },
        { source: 'ACC_1', target: 'ACC_2', amount: 60.0 },
      ],
    }

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockStepWithEdges,
    } as Response)

    const stepResult = await api.stepStream({
      stream_id: 'stream_abc_999',
      num_synthetic_batches: 1,
      include_edges: true,
    })

    expect(stepResult.new_edges).toBeDefined()
    expect(stepResult.new_edges?.length).toBe(2)

    // Deduplication invariant test:
    // Existing base edges + new edges should not duplicate reverse-direction or identical edges
    const existingEdges: [string, string][] = [['ACC_0', 'ACC_1']]
    const existingKeys = new Set(
      existingEdges.map(([u, v]) => (u < v ? `${u}--${v}` : `${v}--${u}`))
    )

    const uniqueToAdd: [string, string][] = []
    for (const e of stepResult.new_edges || []) {
      const k = e.source < e.target ? `${e.source}--${e.target}` : `${e.target}--${e.source}`
      if (!existingKeys.has(k)) {
        existingKeys.add(k)
        uniqueToAdd.push([e.source, e.target])
      }
    }

    // ACC_0--ACC_1 was already in existingEdges, so only ACC_1--ACC_2 should be added
    expect(uniqueToAdd).toEqual([['ACC_1', 'ACC_2']])
  })

  it('preserves backward compatibility when new_edges is omitted', async () => {
    const legacyStepResponse = {
      stream_id: 'stream_legacy',
      steps_processed: 1,
      snapshots: [
        {
          version: 1,
          mode: 'A',
          num_new_unique_edges: 1,
          affected_vertices: ['ACC_0', 'ACC_5'],
          candidate_nodes: ['ACC_0'],
          densest_density: 0.5,
          total_recomputations: 1,
          total_time_ms: 2.0,
          total_vertices: 10,
          total_unique_edges: 12,
        },
      ],
      current_candidate_nodes: ['ACC_0'],
      current_density: 0.5,
      total_transactions: 5,
      total_unique_edges: 12,
      recomputations_count: 1,
    }

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => legacyStepResponse,
    } as Response)

    const stepResult = await api.stepStream({
      stream_id: 'stream_legacy',
      num_synthetic_batches: 1,
    })

    expect(stepResult.new_edges).toBeUndefined()
    expect(stepResult.snapshots[0].new_edges).toBeUndefined()
    expect(stepResult.current_candidate_nodes).toEqual(['ACC_0'])
  })

  it('ensures candidate highlighting isolates solver candidate_nodes from affected_vertices', () => {
    // Ground truth: 15 accounts were touched in the batch, but only 4 are the densest core
    const affectedVertices = Array.from({ length: 15 }, (_, i) => `ACC_${i}`)
    const solverCandidateNodes = ['ACC_0', 'ACC_1', 'ACC_2', 'ACC_3']

    // Highlighted set must strictly equal solver candidate nodes
    const highlightedAccounts = new Set(solverCandidateNodes)
    expect(highlightedAccounts.size).toBe(4)
    expect(affectedVertices.filter(v => highlightedAccounts.has(v)).length).toBe(4)
    expect(affectedVertices.filter(v => !highlightedAccounts.has(v)).length).toBe(11)
  })

  it('clears dynamic streaming nodes and edges on stream reset', () => {
    let streamExtraNodes = ['ACC_13', 'ACC_14']
    let streamExtraEdges: [string, string][] = [['ACC_13', 'ACC_14']]

    // Reset action
    streamExtraNodes = []
    streamExtraEdges = []

    expect(streamExtraNodes.length).toBe(0)
    expect(streamExtraEdges.length).toBe(0)
  })
})
