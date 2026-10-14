/**
 * RingScope API v1 TypeScript Definitions
 * Directly aligned with Pydantic v2 schemas from ringscope.models_v1
 */

export interface HealthResponse {
  status: string
  version: string
  timestamp: number
  uptime_seconds: number
  active_graphs: number
  active_streams: number
  active_jobs: number
}

export interface DegreeStats {
  min: number
  avg: number
  max: number
}

export interface PlantedClusterInfo {
  nodes: string[]
  size: number
  internal_density: number
}

export interface GraphResponse {
  graph_id: string
  num_nodes: number
  num_edges: number
  density: number
  connected_components_count: number
  degree_stats: DegreeStats
  generator_type: string
  planted_cluster?: PlantedClusterInfo | null
  created_at: number
  nodes?: string[] | null
  edges?: [string, string][] | null
}

export interface GraphGenerateRequest {
  generator_type: 'planted_cluster' | 'random' | 'ring'
  num_nodes: number
  cluster_size?: number
  p_internal?: number
  p_external?: number
  seed?: number
  graph_id?: string
}

export interface GraphImportRequest {
  content: string
  format: 'csv' | 'snap'
  graph_id?: string
  source_col?: string
  target_col?: string
  delimiter?: string
}

export interface AnalysisRunRequest {
  graph_id: string
  analysis_type: 'densest_subgraph' | 'cycle_detection' | 'both'
  algorithm: 'goldberg' | 'greedy_peeling' | 'greedy_plus_plus' | 'all'
  params?: Record<string, any>
  async_execution?: boolean
}

export interface AnalysisJobResponse {
  analysis_id: string
  graph_id: string
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'
  analysis_type: string
  algorithm: string
  runtime_ms?: number | null
  results?: {
    densest_subgraph?: {
      goldberg?: {
        nodes: string[]
        density: number
        edge_count: number
        node_count: number
        flow_computations: number
        runtime_sec: number
        time_ms?: number
      }
      greedy_peeling?: {
        nodes: string[]
        density: number
        edge_count: number
        node_count: number
        approximation_factor: number
        runtime_sec: number
        time_ms?: number
      }
      greedy_plus_plus?: {
        nodes: string[]
        density: number
        edge_count: number
        node_count: number
        best_iteration: number
        total_iterations: number
        runtime_sec: number
        time_ms?: number
      }
    }
    cycle_detection?: {
      rings: Array<{
        nodes: string[]
        length: number
        total_amount: number
        min_amount: number
        edges: Array<{ source: string; target: string }>
      }>
      summary: {
        count: number
        avg_length: number
        max_length: number
        min_length: number
        total_volume: number
      }
    }
  } | null
  error?: string | null
  created_at: number
  completed_at?: number | null
}

export interface TransactionRecordIn {
  source: string
  target: string
  amount?: number
  timestamp?: number
  tx_id?: string
}

export interface StreamStartRequest {
  stream_id?: string
  mode: 'full_recomputation' | 'warm_started_recomputation' | 'incremental_heuristic'
  algorithm: 'goldberg' | 'greedy_peeling' | 'greedy_plus_plus'
  batch_size?: number
  initial_graph_id?: string
  config?: {
    recompute_interval?: number
    external_edge_threshold?: number
    external_degree_ratio?: number
    [key: string]: any
  }
}

export interface StreamSessionResponse {
  stream_id: string
  mode: string
  algorithm: string
  status: string
  current_version: number
  total_transactions: number
  total_unique_edges: number
  recomputations_count: number
  current_candidate_nodes: string[]
  current_density: number
}

export interface StreamStepSnapshot {
  batch_index: number
  version: number
  num_inserted_tx: number
  num_new_unique_edges: number
  total_vertices: number
  total_unique_edges: number
  affected_vertices: string[]
  candidate_nodes: string[]
  candidate_density: number
  batch_latency_ms: number
  cumulative_latency_ms: number
  recomputation_count: number
  mode: string
  recomputed_this_step: boolean
}

export interface StreamStepRequest {
  stream_id: string
  transactions?: TransactionRecordIn[]
  num_synthetic_batches?: number
}

export interface StreamStepResponse {
  stream_id: string
  snapshots: StreamStepSnapshot[]
  current_candidate_nodes: string[]
  current_density: number
  total_transactions: number
  total_unique_edges: number
  recomputations_count: number
}

export interface StreamInjectRingRequest {
  stream_id: string
  ring_size?: number
  ring_nodes?: string[]
  amount?: number
  complete_clique?: boolean
}

export interface StreamStopResponse {
  stream_id: string
  status: string
  total_batches: number
  total_transactions: number
  total_recomputations: number
  cumulative_latency_ms: number
}

export interface ExperimentRunRequest {
  experiment_name:
    | 'exp1_runtime_vs_size'
    | 'exp2_cluster_size_recovery'
    | 'exp3_cluster_sparsity'
    | 'exp4_background_connectivity'
    | 'exp5_exact_vs_approx'
    | 'exp6_streaming_modes'
    | 'exp7_clusters_and_hubs'
    | 'all'
  experiment_id?: string
  seed?: number
  params?: Record<string, any>
  async_execution?: boolean
}

export interface ExperimentJobResponse {
  experiment_id: string
  experiment_name: string
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'
  created_at: number
  completed_at?: number | null
  runtime_ms?: number | null
  output_files: string[]
  error?: string | null
}
