import React from 'react'
import {
  Activity,
  Layers,
  Zap,
  Radio,
  Clock,
  Sparkles,
  Server,
  ArrowRight,
  Database,
} from 'lucide-react'
import { GraphResponse, HealthResponse, AnalysisJobResponse, StreamSessionResponse } from '../api/types'
import { CytoscapeGraph } from '../components/CytoscapeGraph'

interface OverviewScreenProps {
  graph: GraphResponse | null
  health: HealthResponse | null
  analysis: AnalysisJobResponse | null
  stream: StreamSessionResponse | null
  onNavigate: (screen: string) => void
  onQuickGenerate: () => void
  onQuickAnalyze: () => void
  candidateNodes: string[]
}

export const OverviewScreen: React.FC<OverviewScreenProps> = ({
  graph,
  health,
  analysis,
  stream,
  onNavigate,
  onQuickGenerate,
  onQuickAnalyze,
  candidateNodes,
}) => {
  const densestResults = analysis?.results?.densest_subgraph
  const bestDensity = densestResults?.goldberg?.density ??
    densestResults?.greedy_peeling?.density ??
    densestResults?.greedy_plus_plus?.density ??
    graph?.density ?? 0

  const lastRuntime = densestResults?.goldberg?.time_ms ??
    densestResults?.greedy_peeling?.time_ms ??
    analysis?.runtime_ms ?? 0

  const activeAlgo = analysis?.algorithm || 'goldberg'
  const isImported = graph?.generator_type?.startsWith('import_')

  return (
    <div className="space-y-6">
      {/* Top Banner: Status & Connectivity */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-4 rounded-xl bg-navy-900 border border-navy-700/80 shadow-md">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-accent-blue/10 border border-accent-blue/30 flex items-center justify-center text-accent-blue">
            <Activity className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-semibold text-slate-100">RingScope Research System</h2>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                v{health?.version || '0.4.0'} ONLINE
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Graph Engine • Exact Flow Reductions • Streaming Maintenance • Empirical Harness
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4 text-xs font-mono text-slate-400">
          <div className="flex items-center gap-1.5">
            <Server className="w-3.5 h-3.5 text-slate-500" />
            <span>Active Graphs: {health?.active_graphs ?? 0}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Radio className="w-3.5 h-3.5 text-accent-emerald" />
            <span>Streams: {health?.active_streams ?? 0}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 text-slate-500" />
            <span>Uptime: {health?.uptime_seconds ? `${Math.round(health.uptime_seconds)}s` : '—'}</span>
          </div>
        </div>
      </div>

      {/* Metric Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Graph Topology */}
        <div className="p-4 rounded-xl bg-navy-900/90 border border-navy-700/80 shadow">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
            <span>Graph Topology</span>
            <Database className="w-4 h-4 text-accent-blue" />
          </div>
          <div className="text-2xl font-bold font-mono text-slate-100">
            {graph ? `${graph.num_nodes} accounts` : '0 accounts'}
          </div>
          <div className="text-xs text-slate-400 mt-1 flex items-center gap-2">
            <span>{graph ? `${graph.num_edges} unique edges` : '0 edges'}</span>
            <span>•</span>
            <span>{graph?.connected_components_count ?? 0} comp</span>
          </div>
          <div className="mt-2 text-[11px]">
            <span
              className={`px-2 py-0.5 rounded font-mono ${
                isImported
                  ? 'bg-purple-950 text-purple-300 border border-purple-700/50'
                  : 'bg-blue-950 text-blue-300 border border-blue-700/50'
              }`}
            >
              {isImported ? 'Imported SNAP / CSV' : 'Planted Synthetic'}
            </span>
          </div>
        </div>

        {/* Card 2: Subgraph Density */}
        <div className="p-4 rounded-xl bg-navy-900/90 border border-navy-700/80 shadow">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
            <span>Peak Density (λ*)</span>
            <Zap className="w-4 h-4 text-cluster-node" />
          </div>
          <div className="text-2xl font-bold font-mono text-red-400">
            {Number(bestDensity).toFixed(4)}
          </div>
          <div className="text-xs text-slate-400 mt-1">
            Global: <span className="font-mono">{Number(graph?.density ?? 0).toFixed(4)}</span> | |E(S)|/|S|
          </div>
          <div className="mt-2 text-[11px] text-slate-400">
            Cluster Size: <span className="font-mono text-red-300 font-bold">{candidateNodes.length}</span> nodes
          </div>
        </div>

        {/* Card 3: Selected Algorithm & Latency */}
        <div className="p-4 rounded-xl bg-navy-900/90 border border-navy-700/80 shadow">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
            <span>Solver Engine</span>
            <Layers className="w-4 h-4 text-accent-emerald" />
          </div>
          <div className="text-lg font-bold text-slate-100 capitalize">
            {activeAlgo.replace(/_/g, ' ')}
          </div>
          <div className="text-xs text-slate-400 mt-1">
            Latency:{' '}
            <span className="font-mono text-emerald-400 font-semibold">
              {Number(lastRuntime).toFixed(3)} ms
            </span>
          </div>
          <div className="mt-2 text-[11px] text-slate-400">
            Status:{' '}
            <span className="font-mono text-slate-200">
              {analysis?.status || 'IDLE'}
            </span>
          </div>
        </div>

        {/* Card 4: Streaming Status */}
        <div className="p-4 rounded-xl bg-navy-900/90 border border-navy-700/80 shadow">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
            <span>Streaming Session</span>
            <Radio className="w-4 h-4 text-accent-amber" />
          </div>
          <div className="text-lg font-bold text-slate-100 capitalize">
            {stream ? stream.mode.replace(/_/g, ' ') : 'Inactive'}
          </div>
          <div className="text-xs text-slate-400 mt-1">
            Tx Ingested:{' '}
            <span className="font-mono text-amber-300 font-semibold">
              {stream?.total_transactions ?? 0}
            </span>
          </div>
          <div className="mt-2 text-[11px] text-slate-400">
            Recomputations:{' '}
            <span className="font-mono text-amber-400 font-semibold">
              {stream?.recomputations_count ?? 0}
            </span>
          </div>
        </div>
      </div>

      {/* Main Body: Graph Visual Preview & Quick Launch Panels */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Interactive Graph Canvas Preview */}
        <div className="lg:col-span-2 space-y-2">
          <div className="flex items-center justify-between px-1">
            <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-cluster-node animate-pulse" />
              Active Graph Topology & Candidate Cluster Preview
            </h3>
            <button
              onClick={() => onNavigate('explorer')}
              className="text-xs text-accent-blue hover:text-white flex items-center gap-1 transition"
            >
              <span>Open in Full Explorer</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="h-[460px]">
            <CytoscapeGraph
              nodes={graph?.nodes}
              edges={graph?.edges}
              candidateNodes={candidateNodes}
              plantedNodes={graph?.planted_cluster?.nodes}
            />
          </div>
        </div>

        {/* Quick Research Actions & Specifications */}
        <div className="space-y-4">
          <div className="p-4 rounded-xl bg-navy-900 border border-navy-700/80 shadow space-y-3">
            <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-accent-amber" />
              <span>Quick Research Actions</span>
            </h3>

            <p className="text-xs text-slate-400 leading-relaxed">
              Synthesize benchmark topologies, trigger exact max-flow densest subgraph reductions, or enter the streaming simulator.
            </p>

            <div className="space-y-2 pt-1">
              <button
                onClick={onQuickGenerate}
                className="w-full flex items-center justify-between p-2.5 rounded-lg bg-navy-800 hover:bg-navy-700 border border-navy-600/70 text-xs text-slate-200 transition"
              >
                <div className="flex items-center gap-2">
                  <Database className="w-4 h-4 text-accent-blue" />
                  <span>Generate Planted Benchmark</span>
                </div>
                <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
              </button>

              <button
                onClick={onQuickAnalyze}
                className="w-full flex items-center justify-between p-2.5 rounded-lg bg-navy-800 hover:bg-navy-700 border border-navy-600/70 text-xs text-slate-200 transition"
              >
                <div className="flex items-center gap-2">
                  <Zap className="w-4 h-4 text-cluster-node" />
                  <span>Execute Goldberg Max-Flow</span>
                </div>
                <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
              </button>

              <button
                onClick={() => onNavigate('streaming')}
                className="w-full flex items-center justify-between p-2.5 rounded-lg bg-navy-800 hover:bg-navy-700 border border-navy-600/70 text-xs text-slate-200 transition"
              >
                <div className="flex items-center gap-2">
                  <Radio className="w-4 h-4 text-accent-emerald" />
                  <span>Open Streaming Simulator</span>
                </div>
                <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
              </button>

              <button
                onClick={() => onNavigate('experiments')}
                className="w-full flex items-center justify-between p-2.5 rounded-lg bg-navy-800 hover:bg-navy-700 border border-navy-600/70 text-xs text-slate-200 transition"
              >
                <div className="flex items-center gap-2">
                  <Activity className="w-4 h-4 text-purple-400" />
                  <span>Run Empirical Experiments</span>
                </div>
                <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
              </button>
            </div>
          </div>

          {/* Planted Cluster Ground Truth Card */}
          {graph?.planted_cluster && (
            <div className="p-4 rounded-xl bg-navy-900 border border-red-900/40 shadow text-xs space-y-2">
              <div className="font-semibold text-red-300 flex items-center justify-between">
                <span>Planted Ground Truth</span>
                <span className="font-mono text-[11px] bg-red-950 px-2 py-0.5 rounded border border-red-800 text-red-300">
                  k = {graph.planted_cluster.size}
                </span>
              </div>
              <div className="text-slate-400">
                Internal Density:{' '}
                <span className="font-mono text-slate-200 font-semibold">
                  {Number(graph.planted_cluster.internal_density).toFixed(4)}
                </span>
              </div>
              <div className="flex flex-wrap gap-1 max-h-24 overflow-y-auto pt-1">
                {graph.planted_cluster.nodes.map((node) => (
                  <span
                    key={node}
                    className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-red-950/70 text-red-300 border border-red-800/60"
                  >
                    {node}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
