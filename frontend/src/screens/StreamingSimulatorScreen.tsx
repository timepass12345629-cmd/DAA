import React, { useState } from 'react'
import {
  Play,
  Square,
  FastForward,
  Radio,
  Clock,
  Zap,
  Sparkles,
} from 'lucide-react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import {
  StreamSessionResponse,
  StreamStepSnapshot,
  StreamStartRequest,
  StreamStepRequest,
  StreamInjectRingRequest,
} from '../api/types'

interface StreamingSimulatorScreenProps {
  stream: StreamSessionResponse | null
  snapshots: StreamStepSnapshot[]
  onStartStream: (req: StreamStartRequest) => Promise<void>
  onStepStream: (req: StreamStepRequest) => Promise<void>
  onInjectRing: (req: StreamInjectRingRequest) => Promise<void>
  onStopStream: () => Promise<void>
  loading: boolean
  onSelectCluster: (nodes: string[]) => void
}

export const StreamingSimulatorScreen: React.FC<StreamingSimulatorScreenProps> = ({
  stream,
  snapshots,
  onStartStream,
  onStepStream,
  onInjectRing,
  onStopStream,
  loading,
  onSelectCluster,
}) => {
  // Start parameters
  const [mode, setMode] = useState<
    'full_recomputation' | 'warm_started_recomputation' | 'incremental_heuristic'
  >('incremental_heuristic')
  const [algo, setAlgo] = useState<'greedy_peeling' | 'goldberg' | 'greedy_plus_plus'>('greedy_peeling')
  const [batchSize, setBatchSize] = useState<number>(5)
  const [recomputeInterval, setRecomputeInterval] = useState<number>(5)
  const [extEdgeThreshold, setExtEdgeThreshold] = useState<number>(10)

  // Inject Ring parameters
  const [ringSize, setRingSize] = useState<number>(6)
  const [isClique, setIsClique] = useState<boolean>(false)
  const [ringAmount, setRingAmount] = useState<number>(200.0)

  const isStreamActive = stream?.status === 'ACTIVE'

  const handleStart = async () => {
    await onStartStream({
      mode,
      algorithm: algo,
      batch_size: batchSize,
      config: {
        recompute_interval: recomputeInterval,
        external_edge_threshold: extEdgeThreshold,
      },
    })
  }

  const handleStep = async (numBatches = 1) => {
    if (!stream) return
    await onStepStream({
      stream_id: stream.stream_id,
      num_synthetic_batches: numBatches,
    })
  }

  const handleInject = async () => {
    if (!stream) return
    await onInjectRing({
      stream_id: stream.stream_id,
      ring_size: ringSize,
      complete_clique: isClique,
      amount: ringAmount,
    })
  }

  // Chart data
  const chartData = snapshots.map((s) => ({
    batch: `B${s.batch_index}`,
    latency_ms: Number(s.batch_latency_ms.toFixed(3)),
    density: Number(s.candidate_density.toFixed(4)),
    recomputations: s.recomputation_count,
    recomputed: s.recomputed_this_step,
  }))

  return (
    <div className="space-y-6">
      {/* Top Banner: Mode Selection & Controls */}
      <div className="p-4 rounded-xl bg-navy-900 border border-navy-700/80 shadow space-y-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-navy-700 pb-3">
          <div>
            <h2 className="text-base font-semibold text-slate-100 flex items-center gap-2">
              <Radio className={`w-5 h-5 ${isStreamActive ? 'text-accent-emerald animate-pulse' : 'text-slate-400'}`} />
              <span>Streaming Candidate Maintenance Simulator</span>
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Simulate dynamic transaction insertions and benchmark full recomputation against warm-started and heuristic maintenance.
            </p>
          </div>

          {/* Session Status Pill */}
          <div className="flex items-center gap-2">
            <span
              className={`px-3 py-1 rounded-full text-xs font-mono font-semibold border ${
                isStreamActive
                  ? 'bg-emerald-950/80 text-emerald-400 border-emerald-700'
                  : 'bg-navy-800 text-slate-400 border-navy-700'
              }`}
            >
              {isStreamActive ? `ACTIVE • ${stream?.mode}` : 'SESSION INACTIVE'}
            </span>
          </div>
        </div>

        {/* Configuration Bar */}
        {!isStreamActive ? (
          <div className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 text-xs items-end">
              <div>
                <label className="text-slate-400 block mb-1">Maintenance Mode</label>
                <select
                  value={mode}
                  onChange={(e) => setMode(e.target.value as any)}
                  className="w-full bg-navy-800 text-slate-200 border border-navy-600 rounded p-1.5 outline-none focus:border-accent-blue"
                >
                  <option value="full_recomputation">Mode A: Full Recomputation</option>
                  <option value="warm_started_recomputation">Mode B: Warm-Started Recomputation</option>
                  <option value="incremental_heuristic">Mode C: Incremental Heuristic</option>
                </select>
              </div>

              <div>
                <label className="text-slate-400 block mb-1">Solver Algorithm</label>
                <select
                  value={algo}
                  onChange={(e) => setAlgo(e.target.value as any)}
                  className="w-full bg-navy-800 text-slate-200 border border-navy-600 rounded p-1.5 outline-none focus:border-accent-blue"
                >
                  <option value="greedy_peeling">Charikar Greedy Peeling</option>
                  <option value="goldberg">Goldberg Flow (Exact)</option>
                  <option value="greedy_plus_plus">Greedy++ (T=10)</option>
                </select>
              </div>

              <div>
                <label className="text-slate-400 block mb-1">Batch Size (Tx / Step)</label>
                <input
                  type="number"
                  min={1}
                  max={50}
                  value={batchSize}
                  onChange={(e) => setBatchSize(Number(e.target.value))}
                  className="w-full bg-navy-800 text-slate-200 border border-navy-600 rounded p-1.5 outline-none font-mono"
                />
              </div>

              <div>
                <button
                  onClick={handleStart}
                  disabled={loading}
                  className="w-full flex items-center justify-center gap-2 p-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold transition disabled:opacity-50"
                >
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>Initialize Stream</span>
                </button>
              </div>
            </div>

            {mode === 'incremental_heuristic' && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs bg-navy-950/60 p-2.5 rounded-lg border border-navy-800">
                <div>
                  <label className="text-slate-400 block mb-0.5">Recompute Interval (Batches)</label>
                  <input
                    type="number"
                    min={1}
                    max={100}
                    value={recomputeInterval}
                    onChange={(e) => setRecomputeInterval(Number(e.target.value))}
                    className="w-full bg-navy-800 text-slate-200 border border-navy-600 rounded px-2 py-1 font-mono"
                  />
                </div>
                <div>
                  <label className="text-slate-400 block mb-0.5">Ext Edge Threshold</label>
                  <input
                    type="number"
                    min={1}
                    max={100}
                    value={extEdgeThreshold}
                    onChange={(e) => setExtEdgeThreshold(Number(e.target.value))}
                    className="w-full bg-navy-800 text-slate-200 border border-navy-600 rounded px-2 py-1 font-mono"
                  />
                </div>
              </div>
            )}
          </div>
        ) : (
          /* Active Streaming Control Bar */
          <div className="flex flex-wrap items-center justify-between gap-3 text-xs pt-1">
            <div className="flex items-center gap-2">
              <button
                onClick={() => handleStep(1)}
                disabled={loading}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent-blue hover:bg-sky-400 text-navy-950 font-bold transition disabled:opacity-50"
              >
                <FastForward className="w-3.5 h-3.5" />
                <span>Step 1 Batch</span>
              </button>

              <button
                onClick={() => handleStep(5)}
                disabled={loading}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-navy-800 hover:bg-navy-700 border border-navy-600 text-slate-200 font-medium transition disabled:opacity-50"
              >
                <FastForward className="w-3.5 h-3.5" />
                <span>Step 5 Batches</span>
              </button>
            </div>

            {/* Inject Ring Form */}
            <div className="flex items-center gap-2 bg-navy-950/80 px-3 py-1.5 rounded-lg border border-red-900/50">
              <span className="text-red-400 font-semibold flex items-center gap-1">
                <Sparkles className="w-3.5 h-3.5" />
                Inject Ring:
              </span>
              <input
                type="number"
                min={3}
                max={20}
                value={ringSize}
                onChange={(e) => setRingSize(Number(e.target.value))}
                className="w-12 bg-navy-800 text-slate-200 border border-navy-600 rounded px-1.5 py-0.5 font-mono text-[11px]"
                title="Ring Size k"
              />
              <label className="flex items-center gap-1 text-slate-400 cursor-pointer">
                <input
                  type="checkbox"
                  checked={isClique}
                  onChange={(e) => setIsClique(e.target.checked)}
                  className="rounded"
                />
                <span>Clique</span>
              </label>
              <input
                type="number"
                min={1}
                value={ringAmount}
                onChange={(e) => setRingAmount(Number(e.target.value))}
                className="w-16 bg-navy-800 text-slate-200 border border-navy-600 rounded px-1.5 py-0.5 font-mono text-[11px]"
                title="Transaction Amount ($)"
              />
              <button
                onClick={handleInject}
                disabled={loading}
                className="px-2.5 py-1 rounded bg-cluster-node hover:bg-red-500 text-white font-bold text-[11px] transition"
              >
                Inject
              </button>
            </div>

            <div>
              <button
                onClick={onStopStream}
                disabled={loading}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-950 hover:bg-red-900 text-red-300 border border-red-800 transition font-medium"
              >
                <Square className="w-3.5 h-3.5 fill-current" />
                <span>Stop Stream</span>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Real-time Streaming Metrics Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="p-3.5 rounded-xl bg-navy-900 border border-navy-700/80 shadow">
          <div className="text-xs text-slate-400">Total Inserted Transactions</div>
          <div className="text-xl font-bold font-mono text-slate-100 mt-1">
            {stream?.total_transactions ?? 0}
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-navy-900 border border-navy-700/80 shadow">
          <div className="text-xs text-slate-400">Unique Active Edges</div>
          <div className="text-xl font-bold font-mono text-slate-100 mt-1">
            {stream?.total_unique_edges ?? 0}
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-navy-900 border border-navy-700/80 shadow">
          <div className="text-xs text-slate-400">Current Candidate Density</div>
          <div className="text-xl font-bold font-mono text-red-400 mt-1">
            {Number(stream?.current_density ?? 0).toFixed(4)}
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-navy-900 border border-navy-700/80 shadow">
          <div className="text-xs text-slate-400">Recomputations Triggered</div>
          <div className="text-xl font-bold font-mono text-amber-400 mt-1">
            {stream?.recomputations_count ?? 0}
          </div>
        </div>
      </div>

      {/* Latency & Density Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Latency Progression Chart */}
        <div className="p-4 rounded-xl bg-navy-900 border border-navy-700/80 shadow space-y-2">
          <div className="flex items-center justify-between border-b border-navy-700 pb-2">
            <h3 className="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-accent-blue" />
              <span>Batch Processing Latency (ms)</span>
            </h3>
            <span className="text-[11px] text-slate-400 font-mono">Real Measured Latencies</span>
          </div>

          <div className="h-56 w-full pt-2">
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 10 }}>
                  <XAxis dataKey="batch" stroke="#64748B" fontSize={10} />
                  <YAxis stroke="#64748B" fontSize={10} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0F172A',
                      borderColor: '#334155',
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="latency_ms"
                    stroke="#38BDF8"
                    strokeWidth={2}
                    dot={{ r: 3, fill: '#38BDF8' }}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-56 flex items-center justify-center text-xs text-slate-500">
                Step through the simulator to record streaming latency.
              </div>
            )}
          </div>
        </div>

        {/* Density Progression Chart */}
        <div className="p-4 rounded-xl bg-navy-900 border border-navy-700/80 shadow space-y-2">
          <div className="flex items-center justify-between border-b border-navy-700 pb-2">
            <h3 className="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
              <Zap className="w-3.5 h-3.5 text-cluster-node" />
              <span>Candidate Cluster Density Evolution (λ)</span>
            </h3>
            <span className="text-[11px] text-slate-400 font-mono">Stream Trajectory</span>
          </div>

          <div className="h-56 w-full pt-2">
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 10 }}>
                  <XAxis dataKey="batch" stroke="#64748B" fontSize={10} />
                  <YAxis stroke="#64748B" fontSize={10} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0F172A',
                      borderColor: '#334155',
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="density"
                    stroke="#EF4444"
                    strokeWidth={2}
                    dot={{ r: 3, fill: '#EF4444' }}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-56 flex items-center justify-center text-xs text-slate-500">
                Density trajectory will render as batches arrive.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Snapshot Chronological Feed Table */}
      <div className="p-4 rounded-xl bg-navy-900 border border-navy-700/80 shadow space-y-3">
        <div className="flex items-center justify-between border-b border-navy-700 pb-2">
          <h3 className="text-xs font-semibold text-slate-200">
            Batch Snapshots Chronological Feed
          </h3>
          <span className="text-[11px] font-mono text-slate-400">{snapshots.length} snapshots recorded</span>
        </div>

        <div className="overflow-x-auto max-h-60 overflow-y-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-navy-800 text-slate-400 uppercase text-[10px] sticky top-0">
              <tr>
                <th className="p-2">Batch #</th>
                <th className="p-2">Graph Ver</th>
                <th className="p-2">New Tx</th>
                <th className="p-2">New Unique Edges</th>
                <th className="p-2">Total Edges</th>
                <th className="p-2">Density (λ)</th>
                <th className="p-2">Batch Latency</th>
                <th className="p-2">Recomputed?</th>
                <th className="p-2 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-navy-800 text-slate-300">
              {snapshots.map((snap) => (
                <tr key={snap.batch_index} className="hover:bg-navy-850 transition">
                  <td className="p-2 font-bold text-accent-blue">B{snap.batch_index}</td>
                  <td className="p-2">v{snap.version}</td>
                  <td className="p-2">{snap.num_inserted_tx}</td>
                  <td className="p-2">{snap.num_new_unique_edges}</td>
                  <td className="p-2">{snap.total_unique_edges}</td>
                  <td className="p-2 text-red-400 font-bold">{Number(snap.candidate_density).toFixed(4)}</td>
                  <td className="p-2 text-emerald-400">{Number(snap.batch_latency_ms).toFixed(3)} ms</td>
                  <td className="p-2">
                    <span
                      className={`px-1.5 py-0.5 rounded text-[10px] ${
                        snap.recomputed_this_step
                          ? 'bg-amber-950 text-amber-300 border border-amber-800'
                          : 'bg-navy-800 text-slate-500'
                      }`}
                    >
                      {snap.recomputed_this_step ? 'YES' : 'SKIPPED'}
                    </span>
                  </td>
                  <td className="p-2 text-right">
                    <button
                      onClick={() => onSelectCluster(snap.candidate_nodes)}
                      className="text-[11px] text-accent-blue hover:underline"
                    >
                      Highlight ({snap.candidate_nodes.length})
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
