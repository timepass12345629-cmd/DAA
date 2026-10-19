import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import {
  Play,
  Pause,
  Square,
  FastForward,
  Radio,
  Clock,
  Zap,
  Sparkles,
  SkipForward,
  ChevronDown,
  ChevronUp,
  BarChart3,
  AlertTriangle,
  Activity,
  Eye,
  Settings,
  CheckCircle2,
  ArrowRight,
  Network,
} from 'lucide-react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import {
  GraphResponse,
  StreamSessionResponse,
  StreamStepSnapshot,
  StreamStartRequest,
  StreamStepRequest,
  StreamInjectRingRequest,
  GraphGenerateRequest,
} from '../api/types'
import { CytoscapeGraph } from '../components/CytoscapeGraph'

// ---------------------------------------------------------------------------
// The Three Streaming Maintenance Strategies
// ---------------------------------------------------------------------------
type StreamingMode = 'full_recomputation' | 'warm_started_recomputation' | 'incremental_heuristic'

interface StrategyDefinition {
  mode: StreamingMode
  title: string
  badge: string
  description: string
}

const STRATEGIES: StrategyDefinition[] = [
  {
    mode: 'full_recomputation',
    title: 'Mode A — Full Recomputation',
    badge: 'Exact Baseline',
    description: 'Recomputes the dense candidate group from scratch on every incoming batch.',
  },
  {
    mode: 'warm_started_recomputation',
    title: 'Mode B — Warm-Started',
    badge: 'Warm-Start Optimization',
    description: 'Re-evaluates candidate subgraph using the previous solution as a warm start for lower latency.',
  },
  {
    mode: 'incremental_heuristic',
    title: 'Mode C — Incremental Updates',
    badge: 'Adaptive Triggers',
    description: 'Maintains candidate group locally without full recomputation; recomputes when trigger thresholds are breached.',
  },
]

const MODE_LABELS: Record<string, string> = {
  full_recomputation: 'Mode A',
  warm_started_recomputation: 'Mode B',
  incremental_heuristic: 'Mode C',
}

const MODE_COLORS: Record<string, string> = {
  full_recomputation: '#38BDF8',
  warm_started_recomputation: '#A78BFA',
  incremental_heuristic: '#34D399',
}

const ALGO_LABELS: Record<string, string> = {
  greedy_peeling: 'Charikar Greedy Peeling',
  goldberg: 'Goldberg Flow (Exact)',
  greedy_plus_plus: 'Greedy++ (T=10)',
}

const SYNTHETIC_BASELINES: {
  name: string
  subtitle: string
  req: GraphGenerateRequest
  label: string
}[] = [
  {
    name: 'Planted Dense Cluster',
    subtitle: '30 accounts, 8-node dense group',
    req: { generator_type: 'planted_cluster', num_nodes: 30, cluster_size: 8, p_internal: 0.85, p_external: 0.05, seed: 42 },
    label: 'Planted Dense Group (30 accounts)',
  },
  {
    name: 'Circular Ring Network',
    subtitle: '25 accounts, fund-routing cycle',
    req: { generator_type: 'ring', num_nodes: 25 },
    label: 'Circular Ring Network (25 accounts)',
  },
  {
    name: 'Sparse Background',
    subtitle: '50 accounts, random graph',
    req: { generator_type: 'erdos_renyi', num_nodes: 50, p_external: 0.05, seed: 42 },
    label: 'Sparse Background Network (50 accounts)',
  },
]

export interface ComparisonEntry {
  mode: string
  algorithm: string
  batches: number
  avgLatencyMs: number
  peakDensity: number
  recomputations: number
  totalTx: number
}

export interface StreamingSimulatorScreenProps {
  graph?: GraphResponse | null
  datasetName?: string | null
  stream: StreamSessionResponse | null
  snapshots: StreamStepSnapshot[]
  comparisons: ComparisonEntry[]
  onAddComparison: (entry: ComparisonEntry) => void
  onClearComparisons: () => void
  onStartStream: (req: StreamStartRequest, overrideGraphId?: string) => Promise<void>
  onStepStream: (req: StreamStepRequest) => Promise<StreamStepResponse | void>
  onInjectRing: (req: StreamInjectRingRequest) => Promise<StreamStepResponse | void>
  onStopStream: () => Promise<void>
  loading: boolean
  onSelectCluster: (nodes: string[]) => void
  onGenerate?: (req: GraphGenerateRequest, label?: string) => Promise<GraphResponse | null>
  onNavigateToInvestigator?: () => void
}

export const StreamingSimulatorScreen: React.FC<StreamingSimulatorScreenProps> = ({
  graph,
  datasetName,
  stream,
  snapshots,
  comparisons,
  onAddComparison,
  onClearComparisons,
  onStartStream,
  onStepStream,
  onInjectRing,
  onStopStream,
  loading,
  onSelectCluster,
  onGenerate,
  onNavigateToInvestigator,
}) => {
  // Strategy & Advanced Settings State
  const [selectedMode, setSelectedMode] = useState<StreamingMode>('incremental_heuristic')
  const [algorithm, setAlgorithm] = useState<StreamStartRequest['algorithm']>('greedy_peeling')
  const [batchSize, setBatchSize] = useState<number>(5)
  const [recomputeInterval, setRecomputeInterval] = useState<number>(5)
  const [extEdgeThreshold, setExtEdgeThreshold] = useState<number>(10)
  const [showAdvancedSettings, setShowAdvancedSettings] = useState<boolean>(false)

  // Dynamic nodes & edges tracked during stream execution
  const [streamExtraNodes, setStreamExtraNodes] = useState<string[]>([])
  const [streamExtraEdges, setStreamExtraEdges] = useState<[string, string][]>([])

  // Inject Ring State
  const [ringSize, setRingSize] = useState<number>(6)
  const [isClique, setIsClique] = useState<boolean>(false)
  const [ringAmount, setRingAmount] = useState<number>(200.0)

  // Auto-advance
  const [autoRunning, setAutoRunning] = useState<boolean>(false)
  const [autoInterval, setAutoInterval] = useState<number>(800)
  const isSteppingRef = useRef<boolean>(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Progressive Disclosure Toggles
  const [showCharts, setShowCharts] = useState<boolean>(false)
  const [showFeed, setShowFeed] = useState<boolean>(false)
  const [showComparisons, setShowComparisons] = useState<boolean>(false)

  const isStreamActive = stream?.status === 'ACTIVE'

  // Reset extra stream elements on graph or stream session change
  useEffect(() => {
    setStreamExtraNodes([])
    setStreamExtraEdges([])
  }, [graph?.graph_id, stream?.stream_id])

  // Helper to add incoming streaming edges and accounts without duplicates
  const addStreamEdges = useCallback((incomingEdges?: Array<{ source: string; target: string; amount?: number }>) => {
    if (!incomingEdges || incomingEdges.length === 0) return

    setStreamExtraNodes((prev) => {
      const existing = new Set([...(graph?.nodes || []), ...prev])
      const toAdd: string[] = []
      for (const e of incomingEdges) {
        if (!existing.has(e.source)) {
          existing.add(e.source)
          toAdd.push(e.source)
        }
        if (!existing.has(e.target)) {
          existing.add(e.target)
          toAdd.push(e.target)
        }
      }
      return toAdd.length > 0 ? [...prev, ...toAdd] : prev
    })

    setStreamExtraEdges((prev) => {
      const existingKeys = new Set(
        [...(graph?.edges || []), ...prev].map(([u, v]) => (u < v ? `${u}--${v}` : `${v}--${u}`))
      )
      const toAdd: [string, string][] = []
      for (const e of incomingEdges) {
        const u = e.source
        const v = e.target
        if (u === v) continue
        const k = u < v ? `${u}--${v}` : `${v}--${u}`
        if (!existingKeys.has(k)) {
          existingKeys.add(k)
          toAdd.push([u, v])
        }
      }
      return toAdd.length > 0 ? [...prev, ...toAdd] : prev
    })
  }, [graph?.nodes, graph?.edges])

  // Process snapshot responses: extract actual affected vertices and new edges into streamExtra state
  useEffect(() => {
    if (snapshots.length === 0) return

    const allSnapshotEdges: Array<{ source: string; target: string }> = []
    const allSnapshotNodes = new Set<string>()

    snapshots.forEach((snap) => {
      if (snap.affected_vertices) {
        snap.affected_vertices.forEach((v) => allSnapshotNodes.add(v))
      }
      if (snap.new_edges) {
        snap.new_edges.forEach((e) => allSnapshotEdges.push(e))
      }
    })

    if (allSnapshotNodes.size > 0) {
      setStreamExtraNodes((prev) => {
        const existing = new Set([...(graph?.nodes || []), ...prev])
        const toAdd = Array.from(allSnapshotNodes).filter((v) => !existing.has(v))
        return toAdd.length > 0 ? [...prev, ...toAdd] : prev
      })
    }

    if (allSnapshotEdges.length > 0) {
      setStreamExtraEdges((prev) => {
        const existingKeys = new Set(
          [...(graph?.edges || []), ...prev].map(([u, v]) => (u < v ? `${u}--${v}` : `${v}--${u}`))
        )
        const toAdd: [string, string][] = []
        for (const e of allSnapshotEdges) {
          if (e.source === e.target) continue
          const k = e.source < e.target ? `${e.source}--${e.target}` : `${e.target}--${e.source}`
          if (!existingKeys.has(k)) {
            existingKeys.add(k)
            toAdd.push([e.source, e.target])
          }
        }
        return toAdd.length > 0 ? [...prev, ...toAdd] : prev
      })
    }
  }, [snapshots, graph?.nodes, graph?.edges])

  // Sequential, non-overlapping auto-advance loop
  useEffect(() => {
    let cancelled = false

    const runAutoStep = async () => {
      if (cancelled || !autoRunning || !isStreamActive) return

      if (!isSteppingRef.current && stream) {
        isSteppingRef.current = true
        try {
          const res = await onStepStream({
            stream_id: stream.stream_id,
            num_synthetic_batches: 1,
            include_edges: true,
          })
          if (res && 'new_edges' in res && res.new_edges) {
            addStreamEdges(res.new_edges)
          }
        } catch {
          if (!cancelled) setAutoRunning(false)
          return
        } finally {
          isSteppingRef.current = false
        }
      }

      if (!cancelled && autoRunning && isStreamActive) {
        timerRef.current = setTimeout(runAutoStep, autoInterval)
      }
    }

    if (autoRunning && isStreamActive) {
      timerRef.current = setTimeout(runAutoStep, autoInterval)
    } else {
      if (timerRef.current) clearTimeout(timerRef.current)
    }

    return () => {
      cancelled = true
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [autoRunning, isStreamActive, autoInterval, stream, onStepStream, addStreamEdges])

  // ---- Handlers ----
  const buildStartRequest = (): StreamStartRequest => {
    return {
      mode: selectedMode,
      algorithm,
      batch_size: batchSize,
      config: selectedMode === 'incremental_heuristic'
        ? { recompute_interval: recomputeInterval, external_edge_threshold: extEdgeThreshold }
        : {},
    }
  }

  const handleStart = async () => {
    let overrideId: string | undefined = graph?.graph_id
    if (!overrideId && onGenerate) {
      const defaultB = SYNTHETIC_BASELINES[0]
      const gen = await onGenerate(defaultB.req, defaultB.label)
      if (gen?.graph_id) overrideId = gen.graph_id
    }
    await onStartStream(buildStartRequest(), overrideId)
  }

  const handleStep = async (n = 1) => {
    if (!stream || isSteppingRef.current || loading) return
    isSteppingRef.current = true
    try {
      const res = await onStepStream({
        stream_id: stream.stream_id,
        num_synthetic_batches: n,
        include_edges: true,
      })
      if (res && 'new_edges' in res && res.new_edges) {
        addStreamEdges(res.new_edges)
      }
    } catch {
      // Handled by parent error toast
    } finally {
      isSteppingRef.current = false
    }
  }

  const handleInject = async () => {
    if (!stream || isSteppingRef.current || loading) return
    isSteppingRef.current = true
    try {
      const res = await onInjectRing({
        stream_id: stream.stream_id,
        ring_size: ringSize,
        complete_clique: isClique,
        amount: ringAmount,
        include_edges: true,
      })
      if (res && 'new_edges' in res && res.new_edges && res.new_edges.length > 0) {
        addStreamEdges(res.new_edges)
      } else {
        // Fallback to deterministic ring edges matching what the backend added
        const ringNodes = Array.from({ length: ringSize }, (_, i) => `RING_${stream.stream_id.slice(-4)}_${i}`)
        const newEdges: [string, string][] = []
        if (isClique) {
          for (let i = 0; i < ringNodes.length; i++) {
            for (let j = i + 1; j < ringNodes.length; j++) {
              newEdges.push([ringNodes[i], ringNodes[j]])
            }
          }
        } else {
          for (let i = 0; i < ringNodes.length; i++) {
            newEdges.push([ringNodes[i], ringNodes[(i + 1) % ringNodes.length]])
          }
        }
        setStreamExtraEdges((prev) => [...prev, ...newEdges])
      }
    } catch {
      // Handled by parent error toast
    } finally {
      isSteppingRef.current = false
    }
  }

  const handleStop = async () => {
    setAutoRunning(false)
    if (timerRef.current) clearTimeout(timerRef.current)
    if (stream && snapshots.length > 0) {
      const avgLatency = snapshots.reduce((s, x) => s + x.batch_latency_ms, 0) / snapshots.length
      const peakDensity = Math.max(...snapshots.map((x) => x.candidate_density))
      onAddComparison({
        mode: stream.mode,
        algorithm: stream.algorithm,
        batches: snapshots.length,
        avgLatencyMs: avgLatency,
        peakDensity,
        recomputations: stream.recomputations_count,
        totalTx: stream.total_transactions,
      })
      setShowComparisons(true)
    }
    await onStopStream()
  }

  const handleQuickLoadBaseline = async (b: typeof SYNTHETIC_BASELINES[0]) => {
    if (onGenerate) {
      await onGenerate(b.req, b.label)
    }
  }

  // Active candidate nodes from current stream or latest snapshot
  const activeCandidateNodes = stream?.current_candidate_nodes && stream.current_candidate_nodes.length > 0
    ? stream.current_candidate_nodes
    : (snapshots.length > 0 ? snapshots[snapshots.length - 1].candidate_nodes : [])

  // Derived display nodes and edges incorporating genuine stream additions
  const displayNodes = useMemo(() => {
    const base = graph?.nodes || []
    if (streamExtraNodes.length === 0) return base
    const set = new Set([...base, ...streamExtraNodes])
    return Array.from(set)
  }, [graph?.nodes, streamExtraNodes])

  const displayEdges = useMemo(() => {
    const base = graph?.edges || []
    if (streamExtraEdges.length === 0) return base
    return [...base, ...streamExtraEdges]
  }, [graph?.edges, streamExtraEdges])

  // Chart data
  const chartData = snapshots.map((s) => ({
    batch: s.batch_index,
    latency_ms: Number(s.batch_latency_ms.toFixed(3)),
    density: Number(s.candidate_density.toFixed(4)),
  }))
  const recomputedBatches = snapshots.filter((s) => s.recomputed_this_step)
  const avgLatency = snapshots.length > 0
    ? snapshots.reduce((a, s) => a + s.batch_latency_ms, 0) / snapshots.length
    : 0
  const streamColor = MODE_COLORS[stream?.mode ?? 'full_recomputation']

  return (
    <div className="space-y-4">
      {/* ================================================================
          TOP WORKSTATION BAR: Scenario Selector & Lifecycle Controls
      ================================================================ */}
      <div className="p-3.5 sm:p-4 rounded-xl bg-white border border-border shadow-xs space-y-3">
        {/* Header title & active badge */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-border pb-3">
          <div className="flex items-center gap-2.5">
            <Radio className={`w-4 h-4 ${isStreamActive ? 'text-forest animate-pulse' : 'text-slate-400'}`} />
            <div>
              <h2 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                <span>Streaming Lab</span>
                <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${
                  isStreamActive
                    ? 'bg-forest-50 text-forest border-forest-200 font-semibold'
                    : 'bg-slate-100 text-slate-600 border-border'
                }`}>
                  {isStreamActive
                    ? `${MODE_LABELS[stream!.mode] ?? stream!.mode} • ${ALGO_LABELS[stream!.algorithm] ?? stream!.algorithm}`
                    : 'SESSION INACTIVE'}
                </span>
              </h2>
            </div>
          </div>

          {/* Quick Metrics Strip */}
          {isStreamActive && (
            <div className="flex items-center gap-4 text-xs font-mono">
              <div className="text-right">
                <span className="text-[10px] text-slate-500 block font-sans">Ingested Tx</span>
                <span className="font-bold text-slate-900">{(stream?.total_transactions ?? 0).toLocaleString()}</span>
              </div>
              <div className="h-6 w-px bg-border" />
              <div className="text-right">
                <span className="text-[10px] text-slate-500 block font-sans">Density λ</span>
                <span className="font-bold text-critical">{Number(stream?.current_density ?? 0).toFixed(4)}</span>
              </div>
              <div className="h-6 w-px bg-border" />
              <div className="text-right">
                <span className="text-[10px] text-slate-500 block font-sans">Recomputations</span>
                <span className="font-bold text-attention">{stream?.recomputations_count ?? 0}</span>
              </div>
              <div className="h-6 w-px bg-border" />
              <div className="text-right">
                <span className="text-[10px] text-slate-500 block font-sans">Batches</span>
                <span className="font-bold text-interactive">{snapshots.length}</span>
              </div>
            </div>
          )}
        </div>

        {/* Baseline Network Status & Controls */}
        {graph ? (
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2.5 p-2.5 rounded-lg bg-forest-50/50 border border-forest-200 text-xs">
            <div className="flex items-center gap-2.5">
              <span className="w-2.5 h-2.5 rounded-full bg-forest shrink-0" />
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-slate-900">{datasetName || `Baseline Graph ${graph.graph_id}`}</span>
                  <span className="text-[10px] px-2 py-0.5 rounded bg-forest-50 text-forest border border-forest-200 font-mono font-medium">
                    Baseline Loaded
                  </span>
                </div>
                <span className="text-[11px] text-slate-500 font-mono">
                  {graph.num_nodes} accounts • {graph.num_edges} connections
                </span>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {!isStreamActive && (
                <div className="flex items-center gap-1.5">
                  <span className="text-[11px] text-slate-600">Switch Baseline:</span>
                  <select
                    onChange={(e) => {
                      const idx = Number(e.target.value)
                      if (!isNaN(idx) && SYNTHETIC_BASELINES[idx]) {
                        handleQuickLoadBaseline(SYNTHETIC_BASELINES[idx])
                      }
                    }}
                    defaultValue=""
                    className="bg-white text-slate-800 border border-border rounded px-2 py-1 text-[11px] outline-none shadow-xs"
                  >
                    <option value="" disabled>Select baseline...</option>
                    {SYNTHETIC_BASELINES.map((b, i) => (
                      <option key={b.name} value={i}>{b.name}</option>
                    ))}
                  </select>
                </div>
              )}
              {onNavigateToInvestigator && (
                <button
                  onClick={onNavigateToInvestigator}
                  className="text-[11px] text-interactive hover:underline px-1.5 py-0.5 font-medium"
                >
                  Investigator →
                </button>
              )}
            </div>
          </div>
        ) : (
          <div className="p-3 rounded-lg bg-attention-50 border border-attention-200 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2.5 text-xs">
            <div className="flex items-center gap-2 text-attention-800">
              <AlertTriangle className="w-4 h-4 shrink-0 text-attention" />
              <span>No baseline network loaded. Initialize a synthetic baseline below to enable live visualization:</span>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button
                onClick={() => handleQuickLoadBaseline(SYNTHETIC_BASELINES[0])}
                disabled={loading}
                className="px-2.5 py-1 rounded bg-white hover:bg-attention-50 text-attention-800 border border-attention-300 text-[11px] font-semibold transition shadow-xs"
              >
                Quick-Load Planted Dense (30 accounts)
              </button>
              {onNavigateToInvestigator && (
                <button
                  onClick={onNavigateToInvestigator}
                  className="text-[11px] text-interactive hover:underline font-medium"
                >
                  Go to Investigator →
                </button>
              )}
            </div>
          </div>
        )}

        {/* INACTIVE: Strategy Selector (Mode A, Mode B, Mode C) */}
        {!isStreamActive ? (
          <div className="space-y-3 pt-1">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-800">Select Streaming Strategy:</span>
              <button
                onClick={() => setShowAdvancedSettings((v) => !v)}
                className={`text-xs px-2.5 py-1 rounded-lg border transition flex items-center gap-1.5 ${
                  showAdvancedSettings
                    ? 'bg-interactive-50 border-interactive-200 text-interactive shadow-xs'
                    : 'bg-white border-border text-slate-700 hover:text-slate-900 shadow-xs'
                }`}
              >
                <Settings className="w-3.5 h-3.5" />
                <span>{showAdvancedSettings ? 'Hide Advanced Settings' : 'Advanced Settings'}</span>
              </button>
            </div>

            {/* Three Clearly Separated Strategy Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {STRATEGIES.map((s) => {
                const isSelected = selectedMode === s.mode
                return (
                  <button
                    key={s.mode}
                    onClick={() => setSelectedMode(s.mode)}
                    className={`text-left p-3.5 rounded-xl border transition flex flex-col justify-between space-y-2 relative shadow-xs ${
                      isSelected
                        ? 'bg-interactive-50/30 border-interactive text-slate-900 ring-1 ring-interactive'
                        : 'bg-white border-border text-slate-600 hover:border-slate-300 hover:text-slate-900'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="font-semibold text-slate-900 text-xs">{s.title}</div>
                      {isSelected ? (
                        <CheckCircle2 className="w-4 h-4 text-interactive shrink-0" />
                      ) : (
                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 border border-border">
                          {s.badge}
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] text-slate-500 leading-relaxed">{s.description}</p>
                  </button>
                )
              })}
            </div>

            {/* Advanced Settings (Collapsible) */}
            {showAdvancedSettings && (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs bg-slate-50 p-3.5 rounded-xl border border-border mt-2 animate-fadeIn">
                <div>
                  <label className="text-slate-700 block mb-1 font-medium">Solver Algorithm</label>
                  <select
                    value={algorithm}
                    onChange={(e) => setAlgorithm(e.target.value as any)}
                    className="w-full bg-white text-slate-800 border border-border rounded-lg p-1.5 outline-none focus:border-interactive font-sans shadow-xs"
                  >
                    <option value="greedy_peeling">Charikar Greedy Peeling (Linear 2-approx)</option>
                    <option value="goldberg">Goldberg Flow (Exact Max-Flow)</option>
                    <option value="greedy_plus_plus">Greedy++ (T=10 Iterative Weights)</option>
                  </select>
                </div>

                <div>
                  <label className="text-slate-700 block mb-1 font-medium">Batch Size (Transactions / Step)</label>
                  <input
                    type="number"
                    min={1}
                    max={50}
                    value={batchSize}
                    onChange={(e) => setBatchSize(Number(e.target.value))}
                    className="w-full bg-white text-slate-800 border border-border rounded-lg p-1.5 font-mono outline-none focus:border-interactive shadow-xs"
                  />
                </div>

                {selectedMode === 'incremental_heuristic' ? (
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="text-slate-700 block mb-1 text-[11px] font-medium">Recompute Interval</label>
                      <input
                        type="number"
                        min={1}
                        value={recomputeInterval}
                        onChange={(e) => setRecomputeInterval(Number(e.target.value))}
                        className="w-full bg-white text-slate-800 border border-border rounded-lg px-2 py-1 font-mono outline-none focus:border-interactive shadow-xs"
                      />
                    </div>
                    <div>
                      <label className="text-slate-700 block mb-1 text-[11px] font-medium">Ext Edge Threshold</label>
                      <input
                        type="number"
                        min={1}
                        value={extEdgeThreshold}
                        onChange={(e) => setExtEdgeThreshold(Number(e.target.value))}
                        className="w-full bg-white text-slate-800 border border-border rounded-lg px-2 py-1 font-mono outline-none focus:border-interactive shadow-xs"
                      />
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center text-[11px] text-slate-500 italic pt-5">
                    Trigger thresholds apply to Mode C incremental maintenance.
                  </div>
                )}
              </div>
            )}

            {/* Initialize Action */}
            <div className="pt-1 flex items-center gap-3">
              <button
                onClick={handleStart}
                disabled={loading}
                className="flex items-center justify-center gap-2 px-5 py-2 rounded-xl bg-forest hover:bg-forest-700 text-white font-semibold text-xs shadow-xs transition disabled:opacity-50"
              >
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>Initialize Stream — {MODE_LABELS[selectedMode]}</span>
              </button>
              {graph ? (
                <span className="text-[11px] text-slate-500">
                  Using baseline network with {graph.num_nodes} accounts
                </span>
              ) : (
                <span className="text-[11px] text-attention-700">
                  (Auto-initializes 30-account baseline network if none selected)
                </span>
              )}
            </div>
          </div>
        ) : (
          /* ACTIVE: Streaming Control Bar */
          <div className="flex flex-wrap items-center gap-2.5 text-xs pt-1">
            {/* Auto-Advance / Pause */}
            {autoRunning ? (
              <button
                onClick={() => setAutoRunning(false)}
                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-attention hover:bg-attention-600 text-white font-semibold transition shadow-xs"
              >
                <Pause className="w-3.5 h-3.5" />
                <span>Pause</span>
              </button>
            ) : (
              <button
                onClick={() => setAutoRunning(true)}
                disabled={loading}
                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-forest hover:bg-forest-700 text-white font-bold transition disabled:opacity-50 shadow-xs"
              >
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>Resume / Auto-Run</span>
              </button>
            )}

            <div className="flex items-center gap-1.5 bg-slate-50 border border-border rounded-lg px-2.5 py-1">
              <Clock className="w-3 h-3 text-slate-500" />
              <span className="text-slate-500 text-[11px]">Rate:</span>
              <select
                value={autoInterval}
                onChange={(e) => setAutoInterval(Number(e.target.value))}
                className="bg-transparent text-slate-800 outline-none text-[11px] font-mono cursor-pointer"
              >
                <option value={400}>0.4s</option>
                <option value={800}>0.8s</option>
                <option value={1500}>1.5s</option>
                <option value={3000}>3.0s</option>
              </select>
            </div>

            <div className="h-4 w-px bg-border" />

            {/* Manual Step Controls */}
            <button
              onClick={() => handleStep(1)}
              disabled={loading || autoRunning}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-white hover:bg-slate-50 border border-border text-slate-700 font-medium transition disabled:opacity-40 shadow-xs"
            >
              <SkipForward className="w-3 h-3" />
              <span>Step 1</span>
            </button>
            <button
              onClick={() => handleStep(5)}
              disabled={loading || autoRunning}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-white hover:bg-slate-50 border border-border text-slate-700 font-medium transition disabled:opacity-40 shadow-xs"
            >
              <FastForward className="w-3 h-3" />
              <span>Step 5</span>
            </button>

            <div className="h-4 w-px bg-border" />

            {/* Inject Ring / Spike */}
            <div className="flex items-center gap-2 bg-slate-50 px-2.5 py-1 rounded-lg border border-border">
              <span className="text-critical font-medium flex items-center gap-1 text-[11px]">
                <Sparkles className="w-3 h-3" />
                <span>Inject Ring:</span>
              </span>
              <input
                type="number"
                min={3}
                max={20}
                value={ringSize}
                onChange={(e) => setRingSize(Number(e.target.value))}
                className="w-10 bg-white text-slate-800 border border-border rounded px-1 py-0.5 font-mono text-[11px] outline-none shadow-xs"
                title="Ring node count k"
              />
              <label className="flex items-center gap-1 text-slate-600 cursor-pointer text-[11px]">
                <input
                  type="checkbox"
                  checked={isClique}
                  onChange={(e) => setIsClique(e.target.checked)}
                  className="rounded border-border text-forest focus:ring-forest"
                />
                <span>Clique</span>
              </label>
              <input
                type="number"
                min={1}
                value={ringAmount}
                onChange={(e) => setRingAmount(Number(e.target.value))}
                className="w-14 bg-white text-slate-800 border border-border rounded px-1.5 py-0.5 font-mono text-[11px] outline-none shadow-xs"
                title="Amount ($)"
              />
              <button
                onClick={handleInject}
                disabled={loading}
                className="px-2.5 py-0.5 rounded bg-critical hover:bg-red-700 text-white font-semibold text-[11px] transition shadow-xs"
              >
                Inject
              </button>
            </div>

            {/* Stop and Record */}
            <button
              onClick={handleStop}
              disabled={loading}
              className="ml-auto flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white hover:bg-critical-50 text-critical border border-critical-200 transition font-medium shadow-xs"
            >
              <Square className="w-3 h-3 fill-current" />
              <span>Stop &amp; Log</span>
            </button>
          </div>
        )}
      </div>

      {/* ================================================================
          MAIN WORKSPACE: NETWORK GRAPH & CANDIDATE HIGHLIGHT
      ================================================================ */}
      <div className="relative rounded-xl border border-border bg-white overflow-hidden shadow-xs min-h-[460px]">
        {graph || displayNodes.length > 0 ? (
          <>
            <CytoscapeGraph
              nodes={displayNodes}
              edges={displayEdges}
              candidateNodes={activeCandidateNodes}
              showSelectedBox={false}
              datasetLabel={datasetName || (graph ? `Baseline Graph ${graph.graph_id}` : 'Streaming Topology')}
              onSelectNode={(id) => {
                if (id) onSelectCluster([id])
              }}
            />

            {/* Compact Floating Stream State Overlay — positioned below Cytoscape top toolbar */}
            <div className="absolute top-14 left-3 z-10 flex items-center gap-2 bg-white/95 backdrop-blur-md px-3 py-1.5 rounded-lg border border-border shadow-sm text-xs">
              <span className={`w-2 h-2 rounded-full ${isStreamActive ? 'bg-forest animate-ping' : 'bg-slate-400'}`} />
              <span className="text-slate-800 font-medium">
                {isStreamActive ? `${MODE_LABELS[stream!.mode]} Active` : 'Baseline Topology'}
              </span>
              <span className="text-slate-400">•</span>
              <span className="text-slate-600 font-mono text-[11px]">
                {displayNodes.length} nodes, {displayEdges.length} edges
              </span>
              {activeCandidateNodes.length > 0 && (
                <>
                  <span className="text-slate-400">•</span>
                  <span className="text-critical font-mono font-semibold">
                    {activeCandidateNodes.length} candidate accounts highlighted
                  </span>
                </>
              )}
            </div>

            {/* Floating Quick Action */}
            {activeCandidateNodes.length > 0 && (
              <div className="absolute top-3 right-3 z-10">
                <button
                  onClick={() => onSelectCluster(activeCandidateNodes)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white hover:bg-slate-50 text-slate-800 border border-border text-xs shadow-sm transition font-medium"
                >
                  <Eye className="w-3.5 h-3.5 text-interactive" />
                  <span>Inspect in Investigator</span>
                </button>
              </div>
            )}
          </>
        ) : (
          <div className="h-[460px] flex flex-col items-center justify-center text-center p-6 space-y-4">
            <div className="w-14 h-14 rounded-2xl bg-forest-50 border border-forest-200 flex items-center justify-center text-forest shadow-xs">
              <Network className="w-7 h-7" />
            </div>
            <div className="space-y-1 max-w-md">
              <h3 className="text-sm font-bold text-slate-900">Initialize Streaming Baseline Network</h3>
              <p className="text-xs text-slate-500 leading-relaxed">
                Streaming simulation requires a baseline network topology to observe dynamic node and edge evolution. Select a preset below:
              </p>
            </div>

            {/* 3 Quick-Load Synthetic Baselines */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 w-full max-w-xl">
              {SYNTHETIC_BASELINES.map((b) => (
                <button
                  key={b.name}
                  onClick={() => handleQuickLoadBaseline(b)}
                  disabled={loading}
                  className="p-3.5 rounded-xl bg-white hover:bg-slate-50 border border-border hover:border-forest text-left transition flex flex-col justify-between space-y-1.5 group cursor-pointer shadow-xs"
                >
                  <div className="font-semibold text-slate-900 text-xs group-hover:text-forest transition">{b.name}</div>
                  <div className="text-[11px] text-slate-500 leading-tight">{b.subtitle}</div>
                  <div className="text-[10px] text-interactive font-medium pt-1 group-hover:underline">Load Baseline →</div>
                </button>
              ))}
            </div>

            {onNavigateToInvestigator && (
              <div className="pt-2">
                <button
                  onClick={onNavigateToInvestigator}
                  className="text-xs text-slate-500 hover:text-interactive transition flex items-center gap-1.5 font-medium"
                >
                  <span>Or load custom transaction CSV in Investigator</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ================================================================
          PROGRESSIVE DISCLOSURE DRAWER / COLLAPSIBLE ACCORDIONS
      ================================================================ */}
      <div className="space-y-3">
        {/* Accordion 1: Performance Charts */}
        <div className="rounded-xl bg-white border border-border overflow-hidden shadow-xs">
          <button
            onClick={() => setShowCharts((v) => !v)}
            className="w-full flex items-center justify-between p-3.5 text-xs font-semibold text-slate-800 hover:bg-slate-50 transition"
          >
            <span className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-interactive" />
              <span>Performance Analytics: Latency &amp; Density Trajectory</span>
              {snapshots.length > 0 && (
                <span className="text-[11px] text-slate-500 font-mono font-normal">
                  ({snapshots.length} batches, avg {avgLatency.toFixed(2)} ms)
                </span>
              )}
            </span>
            {showCharts ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
          </button>

          {showCharts && (
            <div className="p-4 pt-1 border-t border-border space-y-4">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Latency chart */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-xs text-slate-600">
                    <span>Batch Latency (ms)</span>
                    <span className="font-mono text-slate-800">{avgLatency.toFixed(2)} ms avg</span>
                  </div>
                  <div className="h-44 w-full">
                    {chartData.length > 0 ? (
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={chartData} margin={{ top: 8, right: 10, left: -20, bottom: 4 }}>
                          <XAxis dataKey="batch" stroke="#94A3B8" fontSize={10} />
                          <YAxis stroke="#94A3B8" fontSize={10} />
                          <Tooltip
                            contentStyle={{ backgroundColor: '#FFFFFF', borderColor: '#E2E8E4', color: '#1F2937', borderRadius: 8, fontSize: 11, boxShadow: '0 2px 4px rgba(0,0,0,0.06)' }}
                            formatter={(v: any) => [`${Number(v).toFixed(3)} ms`, 'Latency']}
                          />
                          {recomputedBatches.map((s) => (
                            <ReferenceLine key={s.batch_index} x={s.batch_index} stroke="#E58A2B" strokeDasharray="3 3" strokeWidth={1} />
                          ))}
                          <Line type="monotone" dataKey="latency_ms" stroke={streamColor || '#356AC3'} strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
                        </LineChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="h-44 flex items-center justify-center text-xs text-slate-400 bg-slate-50 rounded-lg border border-border">
                        Step through the simulator to record streaming latency.
                      </div>
                    )}
                  </div>
                </div>

                {/* Density chart */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-xs text-slate-600">
                    <span>Candidate Density Evolution (λ = |E|/|V|)</span>
                    <span className="font-mono text-critical font-semibold">
                      peak {snapshots.length > 0 ? Math.max(...snapshots.map((s) => s.candidate_density)).toFixed(4) : '0.0000'}
                    </span>
                  </div>
                  <div className="h-44 w-full">
                    {chartData.length > 0 ? (
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={chartData} margin={{ top: 8, right: 10, left: -20, bottom: 4 }}>
                          <XAxis dataKey="batch" stroke="#94A3B8" fontSize={10} />
                          <YAxis stroke="#94A3B8" fontSize={10} />
                          <Tooltip
                            contentStyle={{ backgroundColor: '#FFFFFF', borderColor: '#E2E8E4', color: '#1F2937', borderRadius: 8, fontSize: 11, boxShadow: '0 2px 4px rgba(0,0,0,0.06)' }}
                            formatter={(v: any) => [Number(v).toFixed(4), 'λ']}
                          />
                          {recomputedBatches.map((s) => (
                            <ReferenceLine key={s.batch_index} x={s.batch_index} stroke="#E58A2B" strokeDasharray="3 3" strokeWidth={1} />
                          ))}
                          <Line type="monotone" dataKey="density" stroke="#DC2626" strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
                        </LineChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="h-44 flex items-center justify-center text-xs text-slate-400 bg-slate-50 rounded-lg border border-border">
                        Density trajectory will render as batches arrive.
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Accordion 2: Mode Comparison Log */}
        {comparisons.length > 0 && (
          <div className="rounded-xl bg-white border border-border overflow-hidden shadow-xs">
            <button
              onClick={() => setShowComparisons((v) => !v)}
              className="w-full flex items-center justify-between p-3.5 text-xs font-semibold text-slate-800 hover:bg-slate-50 transition"
            >
              <span className="flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-interactive" />
                <span>Strategy Comparison Log</span>
                <span className="text-[11px] text-slate-500 font-mono font-normal">
                  ({comparisons.length} recorded runs)
                </span>
              </span>
              {showComparisons ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
            </button>

            {showComparisons && (
              <div className="p-4 pt-1 border-t border-border space-y-2">
                <div className="flex justify-end">
                  <button onClick={onClearComparisons} className="text-xs text-slate-500 hover:text-critical transition">
                    Clear Log
                  </button>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs font-mono">
                    <thead className="text-[10px] uppercase text-slate-500 border-b border-border bg-slate-50">
                      <tr>
                        <th className="py-2 px-3">Mode</th>
                        <th className="py-2 px-3">Algorithm</th>
                        <th className="py-2 px-3 text-right">Batches</th>
                        <th className="py-2 px-3 text-right">Avg Latency</th>
                        <th className="py-2 px-3 text-right">Peak λ</th>
                        <th className="py-2 px-3 text-right">Recomputes</th>
                        <th className="py-2 px-3 text-right">Total Tx</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border text-slate-700">
                      {comparisons.map((c, i) => (
                        <tr key={i} className="hover:bg-slate-50 transition">
                          <td className="py-2 px-3 font-bold text-slate-900">
                            {MODE_LABELS[c.mode] ?? c.mode}
                          </td>
                          <td className="py-2 px-3 text-slate-600">{ALGO_LABELS[c.algorithm] ?? c.algorithm}</td>
                          <td className="py-2 px-3 text-right">{c.batches}</td>
                          <td className="py-2 px-3 text-right text-forest font-semibold">{c.avgLatencyMs.toFixed(3)} ms</td>
                          <td className="py-2 px-3 text-right text-critical font-semibold">{c.peakDensity.toFixed(4)}</td>
                          <td className="py-2 px-3 text-right text-attention font-semibold">{c.recomputations}</td>
                          <td className="py-2 px-3 text-right text-slate-600">{c.totalTx.toLocaleString()}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Accordion 3: Ingested Batch Ledger */}
        <div className="rounded-xl bg-white border border-border overflow-hidden shadow-xs">
          <button
            onClick={() => setShowFeed((v) => !v)}
            className="w-full flex items-center justify-between p-3.5 text-xs font-semibold text-slate-800 hover:bg-slate-50 transition"
          >
            <span className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-attention" />
              <span>Batch Ingestion Ledger</span>
              {snapshots.length > 0 && (
                <span className="text-[11px] text-slate-500 font-mono font-normal">
                  ({snapshots.length} snapshots recorded)
                </span>
              )}
            </span>
            {showFeed ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
          </button>

          {showFeed && (
            <div className="p-4 pt-1 border-t border-border">
              {snapshots.length === 0 ? (
                <div className="text-xs text-slate-400 py-4 text-center">No streaming batches processed yet.</div>
              ) : (
                <div className="overflow-x-auto max-h-64">
                  <table className="w-full text-left text-xs font-mono">
                    <thead className="text-[10px] uppercase text-slate-500 border-b border-border sticky top-0 bg-slate-50">
                      <tr>
                        <th className="p-2">Batch</th>
                        <th className="p-2">Version</th>
                        <th className="p-2">Tx In</th>
                        <th className="p-2">New Edges</th>
                        <th className="p-2">Total Edges</th>
                        <th className="p-2">Density λ</th>
                        <th className="p-2">Latency</th>
                        <th className="p-2">Recomputed</th>
                        <th className="p-2 text-right">Cluster</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border text-slate-700">
                      {[...snapshots].reverse().map((snap) => (
                        <tr key={snap.batch_index} className={`hover:bg-slate-50 transition ${snap.recomputed_this_step ? 'bg-attention-50/30' : ''}`}>
                          <td className="p-2 font-bold text-interactive">B{snap.batch_index}</td>
                          <td className="p-2 text-slate-600">v{snap.version}</td>
                          <td className="p-2">{snap.num_inserted_tx}</td>
                          <td className="p-2">{snap.num_new_unique_edges}</td>
                          <td className="p-2">{snap.total_unique_edges}</td>
                          <td className="p-2 text-critical font-bold">{Number(snap.candidate_density).toFixed(4)}</td>
                          <td className="p-2 text-forest font-semibold">{Number(snap.batch_latency_ms).toFixed(3)} ms</td>
                          <td className="p-2">
                            {snap.recomputed_this_step ? (
                              <span className="px-1.5 py-0.5 rounded text-[10px] bg-attention-50 text-attention-800 border border-attention-200 font-semibold">
                                YES
                              </span>
                            ) : (
                              <span className="text-slate-400 text-[10px]">skipped</span>
                            )}
                          </td>
                          <td className="p-2 text-right">
                            <button
                              onClick={() => onSelectCluster(snap.candidate_nodes)}
                              className="text-[11px] text-interactive hover:underline font-medium"
                            >
                              Inspect ({snap.candidate_nodes.length})
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Methodology Note */}
      <div className="flex items-start gap-2 text-[11px] text-slate-500 px-1 pt-1">
        <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5 text-slate-600" />
        <span>
          Real wall-clock backend latencies. Density λ = |E(S)| / |V(S)| (Goldberg 1984).
          Recomputation events are logged when graph changes breach update thresholds.
        </span>
      </div>
    </div>
  )
}
