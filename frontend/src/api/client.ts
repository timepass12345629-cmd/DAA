/**
 * RingScope Typed API Client
 * Targets /api/v1 endpoints via Vite proxy to the FastAPI backend.
 */

import {
  AnalysisJobResponse,
  AnalysisRunRequest,
  ExperimentJobResponse,
  ExperimentRunRequest,
  GraphGenerateRequest,
  GraphImportRequest,
  GraphResponse,
  HealthResponse,
  StreamInjectRingRequest,
  StreamSessionResponse,
  StreamStartRequest,
  StreamStepRequest,
  StreamStepResponse,
  StreamStopResponse,
} from './types'

const API_BASE = '/api/v1'

export class ApiError extends Error {
  status: number
  detail: string

  constructor(status: number, detail: string) {
    super(`API Error ${status}: ${detail}`)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

async function request<T>(
  method: 'GET' | 'POST' | 'DELETE',
  path: string,
  body?: any,
  signal?: AbortSignal
): Promise<T> {
  const headers: Record<string, string> = {
    'Accept': 'application/json',
  }
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal,
  })

  if (!res.ok) {
    let detail = `HTTP ${res.status} ${res.statusText}`
    try {
      const errJson = await res.json()
      if (errJson.detail) {
        detail = typeof errJson.detail === 'string'
          ? errJson.detail
          : JSON.stringify(errJson.detail)
      }
    } catch {
      // ignore json parse error on non-json body
    }
    throw new ApiError(res.status, detail)
  }

  return res.json() as Promise<T>
}

export const api = {
  // System Health
  getHealth: (signal?: AbortSignal): Promise<HealthResponse> =>
    request<HealthResponse>('GET', '/health', undefined, signal),

  // Graphs
  generateGraph: (req: GraphGenerateRequest): Promise<GraphResponse> =>
    request<GraphResponse>('POST', '/graphs/generate', req),

  importGraph: (req: GraphImportRequest): Promise<GraphResponse> =>
    request<GraphResponse>('POST', '/graphs/import', req),

  getGraph: (graphId: string, includeElements = false): Promise<GraphResponse> =>
    request<GraphResponse>(
      'GET',
      `/graphs/${encodeURIComponent(graphId)}?include_elements=${includeElements}`
    ),

  // Algorithms & Analysis
  runAnalysis: (req: AnalysisRunRequest): Promise<AnalysisJobResponse> =>
    request<AnalysisJobResponse>('POST', '/analysis/run', req),

  getAnalysis: (analysisId: string): Promise<AnalysisJobResponse> =>
    request<AnalysisJobResponse>('GET', `/analysis/${encodeURIComponent(analysisId)}`),

  // Streaming Simulator
  startStream: (req: StreamStartRequest): Promise<StreamSessionResponse> =>
    request<StreamSessionResponse>('POST', '/stream/start', req),

  stepStream: (req: StreamStepRequest): Promise<StreamStepResponse> =>
    request<StreamStepResponse>('POST', '/stream/step', req),

  injectRing: (req: StreamInjectRingRequest): Promise<StreamStepResponse> =>
    request<StreamStepResponse>('POST', '/stream/inject-ring', req),

  stopStream: (streamId: string): Promise<StreamStopResponse> =>
    request<StreamStopResponse>('POST', '/stream/stop', { stream_id: streamId }),

  // Experiments & Benchmark Harness
  runExperiment: (req: ExperimentRunRequest): Promise<ExperimentJobResponse> =>
    request<ExperimentJobResponse>('POST', '/experiments/run', req),

  getExperiment: (experimentId: string): Promise<ExperimentJobResponse> =>
    request<ExperimentJobResponse>('GET', `/experiments/${encodeURIComponent(experimentId)}`),

  getExperimentResults: (experimentId: string): Promise<any[]> =>
    request<any[]>('GET', `/experiments/${encodeURIComponent(experimentId)}/results`),

  getExportUrl: (experimentId: string, format: 'json' | 'csv'): string =>
    `${API_BASE}/experiments/${encodeURIComponent(experimentId)}/export?format=${format}`,
}
