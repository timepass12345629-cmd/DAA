import React, { useState } from 'react'
import {
  Play,
  Zap,
  Layers,
  Cpu,
  Clock,
  CheckCircle2,
  Copy,
  Info,
} from 'lucide-react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import { GraphResponse, AnalysisJobResponse, AnalysisRunRequest } from '../api/types'

interface AlgorithmLabScreenProps {
  graph: GraphResponse | null
  analysis: AnalysisJobResponse | null
  onRunAnalysis: (req: AnalysisRunRequest) => Promise<void>
  loading: boolean
  onSelectCandidateCluster: (nodes: string[]) => void
}

export const AlgorithmLabScreen: React.FC<AlgorithmLabScreenProps> = ({
  graph,
  analysis,
  onRunAnalysis,
  loading,
  onSelectCandidateCluster,
}) => {
  const [selectedAlgo, setSelectedAlgo] = useState<'all' | 'goldberg' | 'greedy_peeling' | 'greedy_plus_plus'>('all')
  const [tolerance, setTolerance] = useState<number>(0.0001)
  const [gppIterations, setGppIterations] = useState<number>(10)
  const [copied, setCopied] = useState(false)

  const handleExecute = async () => {
    if (!graph) return
    await onRunAnalysis({
      graph_id: graph.graph_id,
      analysis_type: 'densest_subgraph',
      algorithm: selectedAlgo,
      params: {
        tolerance,
        iterations: gppIterations,
      },
    })
  }

  const dsResults = analysis?.results?.densest_subgraph
  const goldberg = dsResults?.goldberg
  const peeling = dsResults?.greedy_peeling
  const gpp = dsResults?.greedy_plus_plus

  // Prepare comparison chart data
  const chartData = [
    ...(goldberg
      ? [
          {
            name: 'Goldberg Flow (Exact)',
            density: Number(goldberg.density.toFixed(4)),
            runtime_ms: goldberg.time_ms ?? 0,
            nodes: goldberg.nodes.length,
            fill: '#EF4444',
          },
        ]
      : []),
    ...(peeling
      ? [
          {
            name: 'Charikar Peeling',
            density: Number(peeling.density.toFixed(4)),
            runtime_ms: peeling.time_ms ?? 0,
            nodes: peeling.nodes.length,
            fill: '#38BDF8',
          },
        ]
      : []),
    ...(gpp
      ? [
          {
            name: 'Greedy++ (T=10)',
            density: Number(gpp.density.toFixed(4)),
            runtime_ms: gpp.time_ms ?? 0,
            nodes: gpp.nodes.length,
            fill: '#10B981',
          },
        ]
      : []),
  ]

  // Get currently inspected candidate nodes
  const activeClusterNodes = goldberg?.nodes || peeling?.nodes || gpp?.nodes || []

  const handleCopyCluster = () => {
    navigator.clipboard.writeText(JSON.stringify(activeClusterNodes, null, 2))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="space-y-6">
      {/* Top Header & Execution Bar */}
      <div className="p-4 rounded-xl bg-navy-900 border border-navy-700/80 shadow flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-slate-100 flex items-center gap-2">
            <Cpu className="w-5 h-5 text-accent-blue" />
            <span>Algorithm Research Lab: Densest Subgraph Solvers</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Compare exact flow-network decision cuts with linear peeling approximations and iterative load-weighting.
          </p>
        </div>

        {/* Algorithm selection & parameters */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 text-xs">
            <label className="text-slate-400">Algorithm:</label>
            <select
              value={selectedAlgo}
              onChange={(e) => setSelectedAlgo(e.target.value as any)}
              className="bg-navy-800 text-slate-200 border border-navy-600 rounded px-2.5 py-1.5 outline-none focus:border-accent-blue"
            >
              <option value="all">Compare All Solvers Side-by-Side</option>
              <option value="goldberg">Goldberg's Exact Max-Flow</option>
              <option value="greedy_peeling">Charikar Greedy Peeling (2-approx)</option>
              <option value="greedy_plus_plus">Greedy++ Multiplicative Weights</option>
            </select>
          </div>

          {selectedAlgo === 'goldberg' && (
            <div className="flex items-center gap-1.5 text-xs">
              <span className="text-slate-400">ε:</span>
              <input
                type="number"
                step={0.0001}
                value={tolerance}
                onChange={(e) => setTolerance(Number(e.target.value))}
                className="w-20 bg-navy-800 text-slate-200 border border-navy-600 rounded px-2 py-1 font-mono text-[11px]"
              />
            </div>
          )}

          {selectedAlgo === 'greedy_plus_plus' && (
            <div className="flex items-center gap-1.5 text-xs">
              <span className="text-slate-400">Passes (T):</span>
              <input
                type="number"
                min={1}
                max={50}
                value={gppIterations}
                onChange={(e) => setGppIterations(Number(e.target.value))}
                className="w-16 bg-navy-800 text-slate-200 border border-navy-600 rounded px-2 py-1 font-mono text-[11px]"
              />
            </div>
          )}

          <button
            onClick={handleExecute}
            disabled={loading || !graph}
            className="flex items-center gap-2 px-4 py-1.5 rounded-lg bg-cluster-node hover:bg-red-500 text-white font-bold text-xs transition disabled:opacity-50 shadow-[0_0_12px_rgba(239,68,68,0.4)]"
          >
            <Play className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>{loading ? 'Solving...' : 'Run Analysis'}</span>
          </button>
        </div>
      </div>

      {/* Main Analysis Display: Side-by-Side Comparison Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Card 1: Goldberg Flow */}
        <div className="p-4 rounded-xl bg-navy-900 border border-navy-700/80 shadow flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-red-400 flex items-center gap-1.5">
                <Zap className="w-3.5 h-3.5" />
                Goldberg Flow Solver
              </span>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-red-950 text-red-300 border border-red-800">
                Exact Decision Cut
              </span>
            </div>

            <div className="text-2xl font-bold font-mono text-slate-100">
              {goldberg ? Number(goldberg.density).toFixed(4) : '—'}
            </div>
            <div className="text-xs text-slate-400 mt-1">
              Nodes in Optimum S: <strong className="text-slate-200 font-mono">{goldberg?.nodes.length ?? '—'}</strong>
            </div>
            <div className="text-xs text-slate-400">
              Internal Edges: <strong className="text-slate-200 font-mono">{goldberg?.edge_count ?? '—'}</strong>
            </div>
            <div className="text-xs text-slate-400">
              Flow Computations: <strong className="text-slate-200 font-mono">{goldberg?.flow_computations ?? '—'}</strong>
            </div>
          </div>

          <div className="mt-3 pt-2 border-t border-navy-700 flex items-center justify-between text-xs">
            <span className="text-slate-500">Latency:</span>
            <span className="font-mono text-emerald-400 font-semibold">
              {goldberg?.time_ms ? `${goldberg.time_ms.toFixed(3)} ms` : (goldberg ? `${(goldberg.runtime_sec * 1000).toFixed(3)} ms` : '—')}
            </span>
          </div>
        </div>

        {/* Card 2: Charikar Greedy Peeling */}
        <div className="p-4 rounded-xl bg-navy-900 border border-navy-700/80 shadow flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-accent-blue flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5" />
                Charikar Greedy Peeling
              </span>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-sky-950 text-sky-300 border border-sky-800">
                2-Approximation
              </span>
            </div>

            <div className="text-2xl font-bold font-mono text-slate-100">
              {peeling ? Number(peeling.density).toFixed(4) : '—'}
            </div>
            <div className="text-xs text-slate-400 mt-1">
              Nodes in Candidate S: <strong className="text-slate-200 font-mono">{peeling?.nodes.length ?? '—'}</strong>
            </div>
            <div className="text-xs text-slate-400">
              Internal Edges: <strong className="text-slate-200 font-mono">{peeling?.edge_count ?? '—'}</strong>
            </div>
            <div className="text-xs text-slate-400">
              Theoretical Bound: <strong className="text-slate-200 font-mono">≥ OPT / 2</strong>
            </div>
          </div>

          <div className="mt-3 pt-2 border-t border-navy-700 flex items-center justify-between text-xs">
            <span className="text-slate-500">Latency:</span>
            <span className="font-mono text-emerald-400 font-semibold">
              {peeling?.time_ms ? `${peeling.time_ms.toFixed(3)} ms` : (peeling ? `${(peeling.runtime_sec * 1000).toFixed(3)} ms` : '—')}
            </span>
          </div>
        </div>

        {/* Card 3: Greedy++ */}
        <div className="p-4 rounded-xl bg-navy-900 border border-navy-700/80 shadow flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-accent-emerald flex items-center gap-1.5">
                <Cpu className="w-3.5 h-3.5" />
                Greedy++ Iterative Peeling
              </span>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800">
                (1-ε)-Approximation
              </span>
            </div>

            <div className="text-2xl font-bold font-mono text-slate-100">
              {gpp ? Number(gpp.density).toFixed(4) : '—'}
            </div>
            <div className="text-xs text-slate-400 mt-1">
              Nodes in Candidate S: <strong className="text-slate-200 font-mono">{gpp?.nodes.length ?? '—'}</strong>
            </div>
            <div className="text-xs text-slate-400">
              Best Iteration: <strong className="text-slate-200 font-mono">Pass {gpp?.best_iteration ?? 1} of {gpp?.total_iterations ?? gppIterations}</strong>
            </div>
            <div className="text-xs text-slate-400">
              Multiplicative Weights: <strong className="text-slate-200 font-mono">Accumulated Load</strong>
            </div>
          </div>

          <div className="mt-3 pt-2 border-t border-navy-700 flex items-center justify-between text-xs">
            <span className="text-slate-500">Latency:</span>
            <span className="font-mono text-emerald-400 font-semibold">
              {gpp?.time_ms ? `${gpp.time_ms.toFixed(3)} ms` : (gpp ? `${(gpp.runtime_sec * 1000).toFixed(3)} ms` : '—')}
            </span>
          </div>
        </div>
      </div>

      {/* Comparison Chart & Cluster Inspector */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Bar Chart: Density & Latency Tradeoff */}
        <div className="p-4 rounded-xl bg-navy-900 border border-navy-700/80 shadow space-y-3">
          <div className="flex items-center justify-between border-b border-navy-700 pb-2">
            <h3 className="text-xs font-semibold text-slate-200 flex items-center gap-2">
              <Clock className="w-4 h-4 text-accent-blue" />
              <span>Density vs Solver Output Comparison</span>
            </h3>
            <span className="text-[11px] text-slate-400 font-mono">Actual Benchmark Results</span>
          </div>

          {chartData.length > 0 ? (
            <div className="h-56 w-full pt-2">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                  <XAxis dataKey="name" stroke="#64748B" fontSize={11} interval={0} />
                  <YAxis stroke="#64748B" fontSize={11} domain={[0, 'auto']} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0F172A',
                      borderColor: '#334155',
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                  />
                  <Bar dataKey="density" radius={[4, 4, 0, 0]}>
                    {chartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="h-56 flex items-center justify-center text-xs text-slate-500">
              Run an analysis above to populate comparative density benchmarks.
            </div>
          )}
        </div>

        {/* Candidate Cluster Node Inspector */}
        <div className="p-4 rounded-xl bg-navy-900 border border-navy-700/80 shadow flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between border-b border-navy-700 pb-2 mb-3">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-cluster-node" />
                <h3 className="text-xs font-semibold text-slate-200">
                  Extracted Dense Component Accounts
                </h3>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleCopyCluster}
                  className="flex items-center gap-1 text-[11px] text-slate-400 hover:text-white transition"
                >
                  {copied ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copied ? 'Copied' : 'Copy JSON'}</span>
                </button>
                <button
                  onClick={() => onSelectCandidateCluster(activeClusterNodes)}
                  className="px-2 py-0.5 rounded bg-red-950 text-red-300 border border-red-800 text-[11px] font-semibold hover:bg-red-900"
                >
                  Highlight in Graph
                </button>
              </div>
            </div>

            <div className="flex flex-wrap gap-1.5 max-h-56 overflow-y-auto p-1">
              {activeClusterNodes.length > 0 ? (
                activeClusterNodes.map((node) => (
                  <span
                    key={node}
                    className="font-mono text-xs px-2 py-1 rounded bg-navy-800 text-red-300 border border-red-900/60 font-semibold"
                  >
                    {node}
                  </span>
                ))
              ) : (
                <span className="text-xs text-slate-500 p-2">
                  No candidate cluster extracted yet. Click "Run Analysis" to execute.
                </span>
              )}
            </div>
          </div>

          <div className="pt-3 border-t border-navy-700/80 mt-3 text-[11px] text-slate-400 flex items-center gap-1.5">
            <Info className="w-3.5 h-3.5 text-accent-blue" />
            <span>
              Goldberg guarantees the exact maximum density cut via Dinic's blocking flow. Peeling runs in linear time.
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
