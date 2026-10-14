import React, { useState, useEffect, useCallback } from 'react'
import {
  Activity,
  Layers,
  Cpu,
  Radio,
  FlaskConical,
  BookOpen,
  AlertCircle,
  X,
  Server,
  RefreshCw,
} from 'lucide-react'
import { api } from './api/client'
import {
  GraphResponse,
  HealthResponse,
  AnalysisJobResponse,
  StreamSessionResponse,
  StreamStepSnapshot,
  GraphGenerateRequest,
  GraphImportRequest,
  AnalysisRunRequest,
  StreamStartRequest,
  StreamStepRequest,
  StreamInjectRingRequest,
  ExperimentRunRequest,
  ExperimentJobResponse,
} from './api/types'

import { OverviewScreen } from './screens/OverviewScreen'
import { GraphExplorerScreen } from './screens/GraphExplorerScreen'
import { AlgorithmLabScreen } from './screens/AlgorithmLabScreen'
import { StreamingSimulatorScreen } from './screens/StreamingSimulatorScreen'
import { ExperimentsScreen } from './screens/ExperimentsScreen'
import { DocumentationScreen } from './screens/DocumentationScreen'

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<
    'overview' | 'explorer' | 'algorithms' | 'streaming' | 'experiments' | 'docs'
  >('overview')

  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [graph, setGraph] = useState<GraphResponse | null>(null)
  const [analysis, setAnalysis] = useState<AnalysisJobResponse | null>(null)
  const [stream, setStream] = useState<StreamSessionResponse | null>(null)
  const [streamSnapshots, setStreamSnapshots] = useState<StreamStepSnapshot[]>([])
  const [candidateNodes, setCandidateNodes] = useState<string[]>([])

  const [loading, setLoading] = useState<boolean>(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  // Fetch initial system status and generate benchmark graph
  const initSystem = useCallback(async () => {
    setLoading(true)
    setErrorMsg(null)
    try {
      // 1. Health probe
      const h = await api.getHealth()
      setHealth(h)

      // 2. Initial synthetic benchmark graph
      const g = await api.generateGraph({
        generator_type: 'planted_cluster',
        num_nodes: 30,
        cluster_size: 8,
        p_internal: 0.85,
        p_external: 0.05,
        seed: 42,
      })

      // Fetch elements for graph visualization
      const detailed = await api.getGraph(g.graph_id, true)
      setGraph(detailed)

      if (detailed.planted_cluster?.nodes) {
        setCandidateNodes(detailed.planted_cluster.nodes)
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to initialize RingScope system')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    initSystem()
  }, [initSystem])

  // Periodic health ping
  useEffect(() => {
    const timer = setInterval(async () => {
      try {
        const h = await api.getHealth()
        setHealth(h)
      } catch {
        // silent fail on poll
      }
    }, 15000)
    return () => clearInterval(timer)
  }, [])

  // Graph operations
  const handleGenerateGraph = async (req: GraphGenerateRequest) => {
    setLoading(true)
    setErrorMsg(null)
    try {
      const g = await api.generateGraph(req)
      const detailed = await api.getGraph(g.graph_id, true)
      setGraph(detailed)
      setAnalysis(null)
      if (detailed.planted_cluster?.nodes) {
        setCandidateNodes(detailed.planted_cluster.nodes)
      } else {
        setCandidateNodes([])
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to generate graph')
    } finally {
      setLoading(false)
    }
  }

  const handleImportGraph = async (req: GraphImportRequest) => {
    setLoading(true)
    setErrorMsg(null)
    try {
      const g = await api.importGraph(req)
      const detailed = await api.getGraph(g.graph_id, true)
      setGraph(detailed)
      setAnalysis(null)
      setCandidateNodes([])
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to import graph')
    } finally {
      setLoading(false)
    }
  }

  // Algorithm operations
  const handleRunAnalysis = async (req: AnalysisRunRequest) => {
    setLoading(true)
    setErrorMsg(null)
    try {
      const job = await api.runAnalysis(req)
      setAnalysis(job)

      // Extract candidate cluster
      const ds = job.results?.densest_subgraph
      const cand = ds?.goldberg?.nodes || ds?.greedy_peeling?.nodes || ds?.greedy_plus_plus?.nodes || []
      setCandidateNodes(cand)
    } catch (err: any) {
      setErrorMsg(err.message || 'Analysis run failed')
    } finally {
      setLoading(false)
    }
  }

  // Streaming operations
  const handleStartStream = async (req: StreamStartRequest) => {
    setLoading(true)
    setErrorMsg(null)
    try {
      const sess = await api.startStream({
        ...req,
        initial_graph_id: graph?.graph_id,
      })
      setStream(sess)
      setStreamSnapshots([])
      setCandidateNodes(sess.current_candidate_nodes || [])
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to start streaming session')
    } finally {
      setLoading(false)
    }
  }

  const handleStepStream = async (req: StreamStepRequest) => {
    setLoading(true)
    setErrorMsg(null)
    try {
      const stepRes = await api.stepStream(req)
      setStreamSnapshots((prev) => [...prev, ...stepRes.snapshots])
      setCandidateNodes(stepRes.current_candidate_nodes || [])

      // Update active stream stats
      if (stream) {
        setStream({
          ...stream,
          current_density: stepRes.current_density,
          total_transactions: stepRes.total_transactions,
          total_unique_edges: stepRes.total_unique_edges,
          recomputations_count: stepRes.recomputations_count,
        })
      }

      // Refresh graph topology
      if (graph) {
        const refreshed = await api.getGraph(graph.graph_id, true)
        setGraph(refreshed)
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to advance stream')
    } finally {
      setLoading(false)
    }
  }

  const handleInjectRing = async (req: StreamInjectRingRequest) => {
    setLoading(true)
    setErrorMsg(null)
    try {
      const stepRes = await api.injectRing(req)
      setStreamSnapshots((prev) => [...prev, ...stepRes.snapshots])
      setCandidateNodes(stepRes.current_candidate_nodes || [])

      if (stream) {
        setStream({
          ...stream,
          current_density: stepRes.current_density,
          total_transactions: stepRes.total_transactions,
          total_unique_edges: stepRes.total_unique_edges,
          recomputations_count: stepRes.recomputations_count,
        })
      }

      // Refresh graph topology
      if (graph) {
        const refreshed = await api.getGraph(graph.graph_id, true)
        setGraph(refreshed)
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Ring injection failed')
    } finally {
      setLoading(false)
    }
  }

  const handleStopStream = async () => {
    if (!stream) return
    setLoading(true)
    try {
      await api.stopStream(stream.stream_id)
      setStream({
        ...stream,
        status: 'STOPPED',
      })
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to stop stream')
    } finally {
      setLoading(false)
    }
  }

  // Experiments
  const handleRunExperiment = async (req: ExperimentRunRequest): Promise<ExperimentJobResponse> => {
    return await api.runExperiment(req)
  }

  return (
    <div className="min-h-screen bg-navy-950 text-slate-200 flex flex-col font-sans">
      {/* Top Navbar */}
      <header className="sticky top-0 z-50 bg-navy-900/95 backdrop-blur-md border-b border-navy-700/80 px-4 py-2.5 flex items-center justify-between shadow-lg">
        <div className="flex items-center gap-6">
          {/* Brand Logo */}
          <div className="flex items-center gap-2.5 cursor-pointer" onClick={() => setActiveTab('overview')}>
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cluster-node to-navy-950 border border-red-500/50 flex items-center justify-center shadow-[0_0_12px_rgba(239,68,68,0.35)]">
              <span className="font-mono font-black text-sm text-white">RS</span>
            </div>
            <div>
              <h1 className="text-sm font-bold text-slate-100 tracking-wide flex items-center gap-1.5">
                <span>RingScope</span>
                <span className="text-[10px] font-mono font-semibold px-1.5 py-0.2 rounded bg-navy-800 text-accent-blue border border-navy-600">
                  Research
                </span>
              </h1>
              <p className="text-[10px] text-slate-400 font-mono -mt-0.5">Transaction Graph Analyzer</p>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="hidden md:flex items-center gap-1 text-xs">
            <button
              onClick={() => setActiveTab('overview')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition ${
                activeTab === 'overview'
                  ? 'bg-navy-800 text-white border border-navy-600'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-navy-850'
              }`}
            >
              <Activity className="w-3.5 h-3.5 text-accent-blue" />
              <span>Overview</span>
            </button>

            <button
              onClick={() => setActiveTab('explorer')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition ${
                activeTab === 'explorer'
                  ? 'bg-navy-800 text-white border border-navy-600'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-navy-850'
              }`}
            >
              <Layers className="w-3.5 h-3.5 text-accent-emerald" />
              <span>Graph Explorer</span>
            </button>

            <button
              onClick={() => setActiveTab('algorithms')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition ${
                activeTab === 'algorithms'
                  ? 'bg-navy-800 text-white border border-navy-600'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-navy-850'
              }`}
            >
              <Cpu className="w-3.5 h-3.5 text-cluster-node" />
              <span>Algorithm Lab</span>
            </button>

            <button
              onClick={() => setActiveTab('streaming')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition ${
                activeTab === 'streaming'
                  ? 'bg-navy-800 text-white border border-navy-600'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-navy-850'
              }`}
            >
              <Radio className="w-3.5 h-3.5 text-accent-amber" />
              <span>Streaming</span>
            </button>

            <button
              onClick={() => setActiveTab('experiments')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition ${
                activeTab === 'experiments'
                  ? 'bg-navy-800 text-white border border-navy-600'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-navy-850'
              }`}
            >
              <FlaskConical className="w-3.5 h-3.5 text-purple-400" />
              <span>Experiments</span>
            </button>

            <button
              onClick={() => setActiveTab('docs')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition ${
                activeTab === 'docs'
                  ? 'bg-navy-800 text-white border border-navy-600'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-navy-850'
              }`}
            >
              <BookOpen className="w-3.5 h-3.5 text-slate-400" />
              <span>Docs</span>
            </button>
          </nav>
        </div>

        {/* Right Status & Controls */}
        <div className="flex items-center gap-3 text-xs">
          {/* Active Backend Indicator */}
          <div className="flex items-center gap-1.5 bg-navy-800/80 px-2.5 py-1 rounded-lg border border-navy-700 font-mono text-[11px]">
            <Server className="w-3 h-3 text-emerald-400" />
            <span className="text-slate-300">127.0.0.1:8000</span>
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          </div>

          <button
            onClick={initSystem}
            disabled={loading}
            title="Refresh System State"
            className="p-1.5 rounded-lg bg-navy-800 text-slate-400 hover:text-white border border-navy-700 transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </header>

      {/* Dismissible Error Banner */}
      {errorMsg && (
        <div className="bg-red-950/90 border-b border-red-800 px-4 py-2.5 text-xs text-red-200 flex items-center justify-between shadow-md">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-red-400" />
            <span className="font-semibold">Error:</span>
            <span>{errorMsg}</span>
          </div>
          <button onClick={() => setErrorMsg(null)} className="text-red-400 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6">
        {activeTab === 'overview' && (
          <OverviewScreen
            graph={graph}
            health={health}
            analysis={analysis}
            stream={stream}
            onNavigate={(screen) => setActiveTab(screen as any)}
            onQuickGenerate={() =>
              handleGenerateGraph({
                generator_type: 'planted_cluster',
                num_nodes: 30,
                cluster_size: 8,
                p_internal: 0.85,
                p_external: 0.05,
                seed: 42,
              })
            }
            onQuickAnalyze={() =>
              graph &&
              handleRunAnalysis({
                graph_id: graph.graph_id,
                analysis_type: 'densest_subgraph',
                algorithm: 'goldberg',
              })
            }
            candidateNodes={candidateNodes}
          />
        )}

        {activeTab === 'explorer' && (
          <GraphExplorerScreen
            graph={graph}
            candidateNodes={candidateNodes}
            onGenerate={handleGenerateGraph}
            onImport={handleImportGraph}
            loading={loading}
          />
        )}

        {activeTab === 'algorithms' && (
          <AlgorithmLabScreen
            graph={graph}
            analysis={analysis}
            onRunAnalysis={handleRunAnalysis}
            loading={loading}
            onSelectCandidateCluster={(nodes) => {
              setCandidateNodes(nodes)
              setActiveTab('explorer')
            }}
          />
        )}

        {activeTab === 'streaming' && (
          <StreamingSimulatorScreen
            stream={stream}
            snapshots={streamSnapshots}
            onStartStream={handleStartStream}
            onStepStream={handleStepStream}
            onInjectRing={handleInjectRing}
            onStopStream={handleStopStream}
            loading={loading}
            onSelectCluster={(nodes) => {
              setCandidateNodes(nodes)
              setActiveTab('explorer')
            }}
          />
        )}

        {activeTab === 'experiments' && (
          <ExperimentsScreen
            onRunExperiment={handleRunExperiment}
            loading={loading}
          />
        )}

        {activeTab === 'docs' && <DocumentationScreen />}
      </main>

      {/* Footer */}
      <footer className="border-t border-navy-800/80 px-4 py-3 text-center text-slate-500 text-xs font-mono">
        RingScope Graph Analytics • Discrete Algorithmic Analysis (DAA) Research Platform • 2026
      </footer>
    </div>
  )
}

export default App
