import React, { useState, useEffect, useCallback } from 'react'
import {
  Layers,
  Radio,
  FlaskConical,
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

import { InvestigatorScreen } from './screens/InvestigatorScreen'
import { StreamingSimulatorScreen, ComparisonEntry } from './screens/StreamingSimulatorScreen'
import { ResearchScreen } from './screens/ResearchScreen'

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'investigator' | 'streaming' | 'research'>('investigator')

  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [graph, setGraph] = useState<GraphResponse | null>(null)
  const [analysis, setAnalysis] = useState<AnalysisJobResponse | null>(null)
  const [stream, setStream] = useState<StreamSessionResponse | null>(null)
  const [streamSnapshots, setStreamSnapshots] = useState<StreamStepSnapshot[]>([])
  const [streamComparisons, setStreamComparisons] = useState<ComparisonEntry[]>([])
  const [candidateNodes, setCandidateNodes] = useState<string[]>([])
  const [datasetName, setDatasetName] = useState<string | null>(null)

  const [loading, setLoading] = useState<boolean>(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  // Fetch initial system status
  const initSystem = useCallback(async () => {
    setLoading(true)
    setErrorMsg(null)
    try {
      const h = await api.getHealth()
      setHealth(h)
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to initialize RingScope system')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    initSystem()
    try {
      const params = new URLSearchParams(window.location.search)
      const tab = params.get('tab')
      if (tab === 'streaming' || tab === 'research') {
        setActiveTab(tab)
      }
    } catch {
      // Ignore URL parsing errors
    }
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
  const handleGenerateGraph = async (req: GraphGenerateRequest, label?: string): Promise<GraphResponse | null> => {
    setLoading(true)
    setErrorMsg(null)
    try {
      const g = await api.generateGraph(req)
      const detailed = await api.getGraph(g.graph_id, true)
      setGraph(detailed)
      setAnalysis(null)
      setCandidateNodes([]) // Only populated when user clicks Detect Groups
      setDatasetName(
        label ||
          (req.generator_type === 'planted_cluster'
            ? 'Planted Dense Group (30 accounts)'
            : req.generator_type === 'ring'
            ? 'Circular Ring Network (25 accounts)'
            : 'Sparse Baseline Network (30 accounts)')
      )
      return detailed
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to generate graph')
      return null
    } finally {
      setLoading(false)
    }
  }

  const handleImportGraph = async (req: GraphImportRequest, label?: string) => {
    setLoading(true)
    setErrorMsg(null)
    try {
      const g = await api.importGraph(req)
      const detailed = await api.getGraph(g.graph_id, true)
      setGraph(detailed)
      setAnalysis(null)
      setCandidateNodes([])
      setDatasetName(label || 'Imported Transaction Network')
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to import graph')
    } finally {
      setLoading(false)
    }
  }

  const handleClearGraph = () => {
    setGraph(null)
    setAnalysis(null)
    setCandidateNodes([])
    setDatasetName(null)
  }

  // Algorithm operations
  const handleRunAnalysis = async (req: AnalysisRunRequest) => {
    setLoading(true)
    setErrorMsg(null)
    try {
      const job = await api.runAnalysis(req)
      setAnalysis(job)

      // Extract candidate cluster or detected rings
      const ds = job.results?.densest_subgraph
      const cand = ds?.goldberg?.nodes || ds?.greedy_peeling?.nodes || ds?.greedy_plus_plus?.nodes
      if (cand && cand.length > 0) {
        setCandidateNodes(cand)
      } else if (job.results?.cycle_detection?.rings?.length) {
        // If cycle detection was run, aggregate ring accounts as candidates
        const ringNodes = new Set<string>()
        for (const r of job.results.cycle_detection.rings) {
          for (const n of r.nodes) ringNodes.add(n)
        }
        setCandidateNodes(Array.from(ringNodes))
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Analysis run failed')
    } finally {
      setLoading(false)
    }
  }

  // Streaming operations
  const handleStartStream = async (req: StreamStartRequest, overrideGraphId?: string) => {
    setLoading(true)
    setErrorMsg(null)
    try {
      const sess = await api.startStream({
        ...req,
        initial_graph_id: overrideGraphId ?? graph?.graph_id,
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

  const handleStepStream = async (req: StreamStepRequest): Promise<StreamStepResponse> => {
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
      return stepRes
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to advance stream')
      throw err
    } finally {
      setLoading(false)
    }
  }

  const handleInjectRing = async (req: StreamInjectRingRequest): Promise<StreamStepResponse> => {
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
      return stepRes
    } catch (err: any) {
      setErrorMsg(err.message || 'Ring injection failed')
      throw err
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
    <div className="min-h-screen bg-page text-slate-800 flex flex-col font-sans">
      {/* Top Navbar */}
      <header className="sticky top-0 z-50 bg-white/95 backdrop-blur-md border-b border-border px-4 py-2.5 flex items-center justify-between shadow-xs">
        <div className="flex items-center gap-6">
          {/* Brand Logo */}
          <div className="flex items-center gap-2.5 cursor-pointer" onClick={() => setActiveTab('investigator')}>
            <div className="w-8 h-8 rounded-lg bg-forest text-white flex items-center justify-center shadow-xs">
              <span className="font-mono font-black text-sm">RS</span>
            </div>
            <div>
              <h1 className="text-sm font-bold text-slate-900 tracking-wide flex items-center gap-1.5">
                <span>RingScope</span>
                <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full bg-forest-50 text-forest border border-forest-200">
                  Enterprise Analytics
                </span>
              </h1>
              <p className="text-[10px] text-slate-500 font-mono -mt-0.5">Transaction Network Investigator</p>
            </div>
          </div>

          {/* Primary Navigation: Only Investigator and Streaming Lab */}
          <nav className="hidden md:flex items-center gap-1.5 text-xs">
            <button
              onClick={() => setActiveTab('investigator')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-semibold transition ${
                activeTab === 'investigator'
                  ? 'bg-forest text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`}
            >
              <Layers className={`w-3.5 h-3.5 ${activeTab === 'investigator' ? 'text-white' : 'text-slate-500'}`} />
              <span>Investigator</span>
            </button>

            <button
              onClick={() => setActiveTab('streaming')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-semibold transition ${
                activeTab === 'streaming'
                  ? 'bg-forest text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`}
            >
              <Radio className={`w-3.5 h-3.5 ${activeTab === 'streaming' ? 'text-white' : 'text-slate-500'}`} />
              <span>Streaming Lab</span>
            </button>

            {/* Subtle dev badge if loaded with ?tab=research */}
            {activeTab === 'research' && (
              <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs bg-slate-100 text-slate-700 border border-border">
                <FlaskConical className="w-3 h-3 text-interactive" />
                <span>Research Mode</span>
              </span>
            )}
          </nav>
        </div>

        {/* Right Status & Controls */}
        <div className="flex items-center gap-3 text-xs">
          {/* Active Backend Indicator */}
          <div className="flex items-center gap-1.5 bg-slate-50 px-2.5 py-1 rounded-lg border border-border font-mono text-[11px]">
            <Server className="w-3 h-3 text-forest" />
            <span className="text-slate-700">127.0.0.1:8000</span>
            {health?.version && (
              <span className="text-slate-400 text-[10px]">v{health.version}</span>
            )}
            <span className="w-1.5 h-1.5 rounded-full bg-forest animate-pulse" />
          </div>

          <button
            onClick={initSystem}
            disabled={loading}
            title="Refresh System State"
            className="p-1.5 rounded-lg bg-slate-50 text-slate-600 hover:text-slate-900 hover:bg-slate-100 border border-border transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </header>

      {/* Dismissible Error Banner */}
      {errorMsg && (
        <div className="bg-critical-50 border-b border-critical-200 px-4 py-2 text-xs text-critical-900 flex items-center justify-between shadow-xs">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-critical" />
            <span className="font-semibold">Error:</span>
            <span>{errorMsg}</span>
          </div>
          <button onClick={() => setErrorMsg(null)} className="text-critical-600 hover:text-critical-900">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Main Content Area */}
      <main className="flex-1 w-full mx-auto p-4 sm:p-5">
        {activeTab === 'investigator' && (
          <InvestigatorScreen
            graph={graph}
            datasetName={datasetName}
            candidateNodes={candidateNodes}
            analysis={analysis}
            loading={loading}
            onGenerate={handleGenerateGraph}
            onImport={handleImportGraph}
            onClearGraph={handleClearGraph}
            onRunAnalysis={handleRunAnalysis}
          />
        )}

        {activeTab === 'streaming' && (
          <StreamingSimulatorScreen
            graph={graph}
            datasetName={datasetName}
            stream={stream}
            snapshots={streamSnapshots}
            comparisons={streamComparisons}
            onAddComparison={(entry) => setStreamComparisons((prev) => [...prev, entry])}
            onClearComparisons={() => setStreamComparisons([])}
            onStartStream={handleStartStream}
            onStepStream={handleStepStream}
            onInjectRing={handleInjectRing}
            onStopStream={handleStopStream}
            loading={loading}
            onSelectCluster={(nodes) => {
              setCandidateNodes(nodes)
              setActiveTab('investigator')
            }}
            onGenerate={handleGenerateGraph}
            onNavigateToInvestigator={() => setActiveTab('investigator')}
          />
        )}

        {activeTab === 'research' && (
          <ResearchScreen
            onRunExperiment={handleRunExperiment}
            loading={loading}
          />
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-border bg-white px-4 py-2.5 text-center text-slate-500 text-xs font-mono">
        RingScope Network Investigator • Enterprise Financial Analytics • White / Forest Green / Orange / Blue
      </footer>
    </div>
  )
}

export default App
