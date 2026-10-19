import React, { useState, useMemo, useCallback } from 'react'
import {
  Play,
  RotateCcw,
  Upload,
  Download,
  Search,
  ChevronDown,
  ChevronRight,
  ShieldAlert,
  Info,
  Hash,
  Activity,
  Copy,
  Check,
  Settings,
  X,
  FileSpreadsheet,
  Network,
  Sparkles,
  ArrowRight,
  ArrowLeft,
} from 'lucide-react'
import {
  GraphResponse,
  AnalysisJobResponse,
  GraphGenerateRequest,
  GraphImportRequest,
  AnalysisRunRequest,
} from '../api/types'
import { CytoscapeGraph } from '../components/CytoscapeGraph'

export interface InvestigatorScreenProps {
  graph: GraphResponse | null
  datasetName: string | null
  candidateNodes: string[]
  analysis: AnalysisJobResponse | null
  loading: boolean
  onGenerate: (req: GraphGenerateRequest, label?: string) => Promise<void>
  onImport: (req: GraphImportRequest, label?: string) => Promise<void>
  onClearGraph: () => void
  onRunAnalysis: (req: AnalysisRunRequest) => Promise<void>
}

type AlgorithmChoice = 'goldberg' | 'greedy_peeling' | 'greedy_plus_plus' | 'cycle_detection'

const SAMPLE_CSV = `source,target,amount,timestamp
ACC_001,ACC_002,1500.0,1700000000
ACC_002,ACC_003,1500.0,1700000060
ACC_003,ACC_001,1500.0,1700000120
ACC_003,ACC_004,250.0,1700000180
ACC_004,ACC_005,180.0,1700000240
ACC_005,ACC_001,300.0,1700000300
ACC_006,ACC_007,850.0,1700000360
ACC_007,ACC_008,920.0,1700000420
ACC_008,ACC_006,900.0,1700000480`

export const InvestigatorScreen: React.FC<InvestigatorScreenProps> = ({
  graph,
  datasetName,
  candidateNodes,
  analysis,
  loading,
  onGenerate,
  onImport,
  onClearGraph,
  onRunAnalysis,
}) => {
  // Navigation & Modals
  const [showLoadModal, setShowLoadModal] = useState<boolean>(false)
  const [loadModalTab, setLoadModalTab] = useState<'upload' | 'scenarios'>('upload')
  const [showAdvancedSettings, setShowAdvancedSettings] = useState<boolean>(false)
  const [showExportModal, setShowExportModal] = useState<boolean>(false)

  // Contextual Drawer (Progressive Disclosure)
  const [drawerOpen, setDrawerOpen] = useState<boolean>(false)
  const [drawerMode, setDrawerMode] = useState<'group' | 'account'>('group')
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [memberSearchQuery, setMemberSearchQuery] = useState<string>('')
  const [showTechnicalMetrics, setShowTechnicalMetrics] = useState<boolean>(false)
  const [copiedNotification, setCopiedNotification] = useState<string | null>(null)
  const [exportFeedback, setExportFeedback] = useState<string | null>(null)

  // Algorithm & Parameters
  const [activeAlgo, setActiveAlgo] = useState<AlgorithmChoice>('goldberg')
  const [gppIterations, setGppIterations] = useState<number>(10)
  const [minRingLen, setMinRingLen] = useState<number>(3)
  const [maxRingLen, setMaxRingLen] = useState<number>(10)

  // Upload state
  const [importContent, setImportContent] = useState<string>(SAMPLE_CSV)
  const [importFormat, setImportFormat] = useState<'csv' | 'snap'>('csv')

  // Custom Generator state
  const [showCustomGen, setShowCustomGen] = useState<boolean>(false)
  const [genNumNodes, setGenNumNodes] = useState<number>(30)
  const [genClusterSize, setGenClusterSize] = useState<number>(8)
  const [genPInternal, setGenPInternal] = useState<number>(0.85)
  const [genPExternal, setGenPExternal] = useState<number>(0.05)
  const [genSeed, setGenSeed] = useState<number>(42)

  // Sets for fast lookups
  const candidateSet = useMemo(() => new Set(candidateNodes || []), [candidateNodes])
  const plantedSet = useMemo(
    () => new Set(graph?.planted_cluster?.nodes || []),
    [graph?.planted_cluster?.nodes]
  )

  // Subgraph Metrics (Goldberg 1984 / Charikar 2000 definition: lambda = |E(S)| / |S|)
  const { internalEdgesCount, candidateDensity, densityContrastRatio } = useMemo(() => {
    if (!graph || candidateNodes.length === 0 || !graph.edges) {
      return { internalEdgesCount: 0, candidateDensity: 0, densityContrastRatio: 0 }
    }
    let internal = 0
    for (const [u, v] of graph.edges) {
      if (candidateSet.has(u) && candidateSet.has(v)) {
        internal++
      }
    }
    const candDens = internal / candidateNodes.length
    const contrast = graph.density > 0 ? candDens / graph.density : 0
    return {
      internalEdgesCount: internal,
      candidateDensity: candDens,
      densityContrastRatio: contrast,
    }
  }, [graph, candidateNodes, candidateSet])

  // Incident edges & neighbors for selected account
  const selectedNodeIncidentEdges = useMemo(() => {
    if (!selectedNodeId || !graph?.edges) return []
    return graph.edges.filter(([u, v]) => u === selectedNodeId || v === selectedNodeId)
  }, [selectedNodeId, graph?.edges])

  const selectedNodeNeighbors = useMemo(() => {
    const set = new Set<string>()
    for (const [u, v] of selectedNodeIncidentEdges) {
      if (u === selectedNodeId) set.add(v)
      else set.add(u)
    }
    return Array.from(set)
  }, [selectedNodeId, selectedNodeIncidentEdges])

  // Filtered members in candidate group
  const filteredCandidateMembers = useMemo(() => {
    if (!memberSearchQuery.trim()) return candidateNodes
    const q = memberSearchQuery.toLowerCase()
    return candidateNodes.filter((n) => n.toLowerCase().includes(q))
  }, [candidateNodes, memberSearchQuery])

  // Cycles if cycle detection was run
  const cycleResults = analysis?.results?.cycle_detection?.rings || []

  // ---- Handlers ----
  const handleLoadScenario = async (
    type: 'planted_cluster' | 'ring' | 'random',
    label: string
  ) => {
    setSelectedNodeId(null)
    setDrawerOpen(false)
    setShowLoadModal(false)
    if (type === 'planted_cluster') {
      await onGenerate(
        {
          generator_type: 'planted_cluster',
          num_nodes: 30,
          cluster_size: 8,
          p_internal: 0.85,
          p_external: 0.05,
          seed: 42,
        },
        label
      )
    } else if (type === 'ring') {
      await onGenerate(
        {
          generator_type: 'ring',
          num_nodes: 25,
          cluster_size: 6,
          seed: 42,
        },
        label
      )
    } else {
      await onGenerate(
        {
          generator_type: 'random',
          num_nodes: 30,
          cluster_size: 4,
          seed: 42,
        },
        label
      )
    }
  }

  const handleCustomGenerate = async (e: React.FormEvent) => {
    e.preventDefault()
    setSelectedNodeId(null)
    setDrawerOpen(false)
    setShowLoadModal(false)
    await onGenerate(
      {
        generator_type: 'planted_cluster',
        num_nodes: genNumNodes,
        cluster_size: genClusterSize,
        p_internal: genPInternal,
        p_external: genPExternal,
        seed: genSeed,
      },
      `Custom Network (${genNumNodes} accounts)`
    )
  }

  const handleImportSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSelectedNodeId(null)
    setDrawerOpen(false)
    setShowLoadModal(false)
    await onImport(
      { content: importContent, format: importFormat },
      'Imported Transaction File'
    )
  }

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (event) => {
      const text = event.target?.result as string
      setImportContent(text)
    }
    reader.readAsText(file)
  }

  const handleRunDetection = async () => {
    if (!graph) return
    if (activeAlgo === 'cycle_detection') {
      await onRunAnalysis({
        graph_id: graph.graph_id,
        analysis_type: 'cycle_detection',
        algorithm: 'goldberg',
        params: {
          min_ring_length: minRingLen,
          max_ring_length: maxRingLen,
        },
      })
    } else {
      await onRunAnalysis({
        graph_id: graph.graph_id,
        analysis_type: 'densest_subgraph',
        algorithm: activeAlgo,
        params: {
          tolerance: 0.0001,
          iterations: gppIterations,
        },
      })
    }
  }

  const handleSelectNode = useCallback((nodeId: string | null) => {
    if (nodeId) {
      setSelectedNodeId(nodeId)
      setDrawerMode('account')
      setDrawerOpen(true)
    } else {
      setSelectedNodeId(null)
    }
  }, [])

  const handleOpenGroupDetails = () => {
    setDrawerMode('group')
    setDrawerOpen(true)
  }

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text)
    setCopiedNotification(label)
    setTimeout(() => setCopiedNotification(null), 2000)
  }

  // Export builders
  const buildFindingsJSON = () => {
    if (!graph) return {}
    return {
      export_version: '2.0',
      exported_at: new Date().toISOString(),
      dataset: {
        name: datasetName || graph.graph_id,
        graph_id: graph.graph_id,
        generator_type: graph.generator_type,
      },
      graph_metrics: {
        num_accounts: graph.num_nodes,
        num_connections: graph.num_edges,
        whole_graph_density: graph.density,
        whole_graph_density_formula: '|E| / |V| (Goldberg average-degree / 2)',
        standard_combinatorial_density:
          graph.num_nodes > 1
            ? Number(((2 * graph.num_edges) / (graph.num_nodes * (graph.num_nodes - 1))).toFixed(5))
            : 0,
        standard_combinatorial_formula: '2*|E| / (|V|*(|V|-1))',
      },
      detection_findings: {
        algorithm_applied: activeAlgo,
        runtime_ms: analysis?.runtime_ms ?? null,
        candidate_count: candidateNodes.length,
        candidate_accounts: candidateNodes,
        candidate_density: Number(candidateDensity.toFixed(4)),
        candidate_density_formula: '|E(S)| / |S|',
        density_contrast_ratio: Number(densityContrastRatio.toFixed(3)),
        density_contrast_formula: 'ρ(S) / ρ(G)',
      },
      detected_cycles: cycleResults.map((r) => ({
        length: r.length,
        nodes: r.nodes,
        total_amount: r.total_amount,
      })),
      audit_disclaimer:
        'NOTICE: RingScope identifies structural edge density concentrations and cyclic topologies. Candidate groupings represent technical structural anomalies requiring investigative verification and do not constitute an autonomous determination of fraud.',
    }
  }

  const downloadBlob = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.style.display = 'none'
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    setTimeout(() => {
      if (document.body.contains(a)) {
        document.body.removeChild(a)
      }
      URL.revokeObjectURL(url)
    }, 1500)
  }

  const handleExportJSON = () => {
    const findings = buildFindingsJSON()
    const content = JSON.stringify(findings, null, 2)
    const blob = new Blob([content], { type: 'application/json' })
    const filename = `ringscope_investigation_${graph?.graph_id || 'findings'}.json`
    downloadBlob(blob, filename)
    setExportFeedback(`Downloaded: ${filename}`)
    setTimeout(() => setExportFeedback(null), 4000)
  }

  const handleExportCSV = () => {
    if (!graph) return
    const lines = ['account_id,is_candidate_group_member,in_planted_ground_truth']
    for (const n of graph.nodes || []) {
      lines.push(`${n},${candidateSet.has(n) ? 'true' : 'false'},${plantedSet.has(n) ? 'true' : 'false'}`)
    }
    const blob = new Blob([lines.join('\n')], { type: 'text/csv' })
    const filename = `ringscope_accounts_${graph.graph_id}.csv`
    downloadBlob(blob, filename)
    setExportFeedback(`Downloaded: ${filename}`)
    setTimeout(() => setExportFeedback(null), 4000)
  }

  const handleCopyJSON = () => {
    const findings = buildFindingsJSON()
    copyToClipboard(JSON.stringify(findings, null, 2), 'JSON Copied!')
    setExportFeedback('Findings JSON copied to clipboard!')
    setTimeout(() => setExportFeedback(null), 4000)
  }

  const handleCopyCSV = () => {
    if (!graph) return
    const lines = ['account_id,is_candidate_group_member,in_planted_ground_truth']
    for (const n of graph.nodes || []) {
      lines.push(`${n},${candidateSet.has(n) ? 'true' : 'false'},${plantedSet.has(n) ? 'true' : 'false'}`)
    }
    copyToClipboard(lines.join('\n'), 'CSV Copied!')
    setExportFeedback('Account Roster CSV copied to clipboard!')
    setTimeout(() => setExportFeedback(null), 4000)
  }

  // =========================================================================
  // VIEW A: BEFORE DATASET IS LOADED (Clean Empty State)
  // =========================================================================
  if (!graph) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[75vh] px-4 py-8">
        <div className="max-w-xl w-full text-center space-y-6">
          {/* Main Visual Emblem */}
          <div className="w-16 h-16 mx-auto rounded-2xl bg-forest-50 border border-forest-200 flex items-center justify-center shadow-xs">
            <Network className="w-8 h-8 text-forest" />
          </div>

          <div className="space-y-2">
            <h2 className="text-2xl font-bold tracking-tight text-slate-900">
              Investigate a Transaction Network
            </h2>
            <p className="text-sm text-slate-500 max-w-md mx-auto leading-relaxed">
              Detect dense candidate groups, circular fund routing, and structural network anomalies.
            </p>
          </div>

          {/* Primary Action Buttons */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
            <button
              onClick={() => {
                setLoadModalTab('upload')
                setShowLoadModal(true)
              }}
              className="w-full sm:w-auto px-6 py-2.5 rounded-xl bg-forest hover:bg-forest-700 text-white font-bold transition flex items-center justify-center gap-2 shadow-xs text-sm"
            >
              <Upload className="w-4 h-4" />
              <span>Load Transaction Data</span>
            </button>

            <button
              onClick={() => {
                setLoadModalTab('scenarios')
                setShowLoadModal(true)
              }}
              className="w-full sm:w-auto px-5 py-2.5 rounded-xl bg-white hover:bg-slate-50 text-slate-700 border border-border transition flex items-center justify-center gap-2 text-sm font-semibold shadow-xs"
            >
              <Sparkles className="w-4 h-4 text-interactive" />
              <span>Try a Synthetic Scenario</span>
            </button>
          </div>
        </div>

        {/* Load Data Modal */}
        {showLoadModal && renderLoadDataModal()}
      </div>
    )
  }

  // =========================================================================
  // VIEW B: LOADED DATASET WORKSPACE (Clean, Graph-Dominant, Progressive Disclosure)
  // =========================================================================
  return (
    <div className="flex flex-col gap-3 font-sans h-[calc(100vh-115px)] min-h-[600px]">
      {/* 1. TOP INVESTIGATION BAR */}
      <header className="px-4 py-2.5 rounded-xl bg-white border border-border shadow-xs flex flex-wrap items-center justify-between gap-3 shrink-0">
        {/* Left: Dataset Name & Change action */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-forest" />
            <span className="text-xs font-bold text-slate-900 max-w-[200px] sm:max-w-xs truncate" title={datasetName || graph.graph_id}>
              {datasetName || `Network ${graph.graph_id}`}
            </span>
          </div>

          <div className="flex items-center gap-1.5">
            <button
              onClick={() => {
                setLoadModalTab('upload')
                setShowLoadModal(true)
              }}
              disabled={loading}
              className="text-[11px] text-interactive hover:underline px-2 py-0.5 rounded hover:bg-slate-100 transition font-medium"
            >
              Change Dataset
            </button>
            <button
              onClick={onClearGraph}
              disabled={loading}
              className="text-[11px] text-slate-400 hover:text-critical px-1 py-0.5 rounded hover:bg-slate-100 transition"
              title="Unload current dataset to reset to blank slate"
            >
              Unload
            </button>
          </div>
        </div>

        {/* Center: Three Compact Factual Stats */}
        <div className="flex items-center gap-4 text-xs font-mono">
          <div className="flex items-center gap-1.5">
            <span className="text-slate-500">Accounts:</span>
            <span className="font-bold text-slate-800">{graph.num_nodes}</span>
          </div>

          <div className="w-px h-3.5 bg-border" />

          <div className="flex items-center gap-1.5">
            <span className="text-slate-500">Connections:</span>
            <span className="font-bold text-slate-800">{graph.num_edges}</span>
          </div>

          <div className="w-px h-3.5 bg-border" />

          <div className="flex items-center gap-1.5">
            <span className="text-slate-500">Candidate Groups:</span>
            {candidateNodes.length > 0 ? (
              <span className="font-bold text-critical bg-critical-50 border border-critical-200 px-1.5 py-0.5 rounded text-[11px]">
                1 Group ({candidateNodes.length})
              </span>
            ) : (
              <span className="text-slate-400">Not run</span>
            )}
          </div>
        </div>

        {/* Right: Actions (Settings, Export, Detect Groups) */}
        <div className="flex items-center gap-2">
          {/* Advanced Settings Toggle */}
          <button
            onClick={() => setShowAdvancedSettings(!showAdvancedSettings)}
            className={`px-2.5 py-1.5 rounded-lg border text-xs font-medium transition flex items-center gap-1.5 ${
              showAdvancedSettings
                ? 'bg-interactive-50 text-interactive border-interactive-200 shadow-xs'
                : 'bg-white text-slate-700 hover:text-slate-900 hover:bg-slate-50 border-border shadow-xs'
            }`}
            title="Algorithm & Detection Settings"
          >
            <Settings className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Settings</span>
          </button>

          {/* Export findings */}
          <button
            onClick={() => setShowExportModal(true)}
            className="px-2.5 py-1.5 rounded-lg bg-white hover:bg-slate-50 text-slate-700 hover:text-slate-900 border border-border transition flex items-center gap-1.5 text-xs font-medium shadow-xs"
            title="Export Findings as JSON or CSV"
          >
            <Download className="w-3.5 h-3.5 text-forest" />
            <span className="hidden sm:inline">Export</span>
          </button>

          {/* Primary Call to Action: Detect Groups */}
          <button
            onClick={handleRunDetection}
            disabled={loading}
            className="px-4 py-1.5 rounded-lg bg-forest hover:bg-forest-700 text-white text-xs font-bold transition flex items-center gap-1.5 shadow-xs disabled:opacity-50"
          >
            <Play className={`w-3.5 h-3.5 fill-current ${loading ? 'animate-spin' : ''}`} />
            <span>{loading ? 'Detecting...' : 'Detect Groups'}</span>
          </button>
        </div>
      </header>

      {/* Advanced Settings Panel (Collapsible, Progressive Disclosure) */}
      {showAdvancedSettings && (
        <div className="p-3.5 rounded-xl bg-white border border-border shadow-xs text-xs space-y-3 shrink-0 animate-fadeIn">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-3">
              <span className="font-semibold text-slate-800">Solver Method:</span>
              <select
                value={activeAlgo}
                onChange={(e) => setActiveAlgo(e.target.value as AlgorithmChoice)}
                className="bg-slate-50 text-slate-800 border border-border rounded-lg px-2.5 py-1 outline-none focus:border-interactive transition-colors"
              >
                <option value="goldberg">Goldberg Exact Max-Flow (Optimal λ*)</option>
                <option value="greedy_peeling">Charikar Greedy Peeling (Linear 2-approx)</option>
                <option value="greedy_plus_plus">Greedy++ Multiplicative Weights</option>
                <option value="cycle_detection">Directed Cycle Detection</option>
              </select>

              {activeAlgo === 'greedy_plus_plus' && (
                <div className="flex items-center gap-1.5 text-slate-600">
                  <span>Passes (T):</span>
                  <input
                    type="number"
                    min={1}
                    max={50}
                    value={gppIterations}
                    onChange={(e) => setGppIterations(Number(e.target.value))}
                    className="w-12 bg-slate-50 text-slate-800 border border-border rounded px-1.5 py-0.5 font-mono focus:border-interactive"
                  />
                </div>
              )}

              {activeAlgo === 'cycle_detection' && (
                <div className="flex items-center gap-1.5 text-slate-600">
                  <span>Length Range:</span>
                  <input
                    type="number"
                    min={3}
                    max={10}
                    value={minRingLen}
                    onChange={(e) => setMinRingLen(Number(e.target.value))}
                    className="w-10 bg-slate-50 text-slate-800 border border-border rounded px-1 py-0.5 font-mono focus:border-interactive"
                  />
                  <span>-</span>
                  <input
                    type="number"
                    min={minRingLen}
                    max={25}
                    value={maxRingLen}
                    onChange={(e) => setMaxRingLen(Number(e.target.value))}
                    className="w-10 bg-slate-50 text-slate-800 border border-border rounded px-1 py-0.5 font-mono focus:border-interactive"
                  />
                </div>
              )}
            </div>

            <button
              onClick={() => setShowAdvancedSettings(false)}
              className="text-slate-500 hover:text-slate-800 text-xs transition"
            >
              Close Settings
            </button>
          </div>
          <p className="text-[11px] text-slate-500">
            Goldberg computes the globally optimal densest subgraph via binary search on flow networks (Goldberg 1984). Charikar peeling runs in O(|V| + |E|) time and achieves a 2-approximation (Charikar 2000).
          </p>
        </div>
      )}

      {/* 2. MAIN WORKSPACE: GRAPH DOMINANT + CONTEXTUAL RIGHT DRAWER */}
      <div className="relative flex-1 flex gap-3 overflow-hidden min-h-0">
        {/* Cytoscape Canvas (>75% width or 100% width when drawer is closed) */}
        <main className="flex-1 flex flex-col gap-2 overflow-hidden min-h-0">
          <div className="flex-1 relative rounded-xl overflow-hidden border border-border shadow-xs bg-white">
            <CytoscapeGraph
              nodes={graph.nodes}
              edges={graph.edges}
              candidateNodes={candidateNodes}
              plantedNodes={graph.planted_cluster?.nodes}
              selectedNodeId={selectedNodeId}
              onSelectNode={handleSelectNode}
              showSelectedBox={false}
              datasetLabel={datasetName}
            />
          </div>

          {/* Compact Candidate Group Findings Area (Immediately Below Graph Canvas) */}
          {candidateNodes.length > 0 && (
            <div className="px-4 py-2.5 rounded-xl bg-white border border-border shadow-xs flex items-center justify-between text-xs shrink-0 animate-fadeIn">
              <div className="flex items-center gap-3">
                <div className="w-7 h-7 rounded-lg bg-critical-50 border border-critical-200 flex items-center justify-center shrink-0">
                  <ShieldAlert className="w-3.5 h-3.5 text-critical" />
                </div>
                <div className="flex items-center gap-2 sm:gap-3 flex-wrap">
                  <span className="font-bold text-slate-900">Candidate Group 1</span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-attention-50 text-attention-800 border border-attention-200">
                    Needs Review
                  </span>
                  <span className="text-slate-400 hidden sm:inline">•</span>
                  <span className="text-slate-600 font-mono text-[11px]">
                    {candidateNodes.length} accounts
                  </span>
                  <span className="text-slate-400 hidden sm:inline">•</span>
                  <span className="text-slate-600 font-mono text-[11px]">
                    Density λ={candidateDensity.toFixed(2)}
                  </span>
                </div>
              </div>

              <button
                onClick={handleOpenGroupDetails}
                className="px-3 py-1.5 rounded-lg bg-white hover:bg-critical-50 text-critical border border-critical-200 font-semibold transition text-xs flex items-center gap-1.5 shadow-xs ml-2 shrink-0"
              >
                <span>View Details</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </main>

        {/* Contextual Right-Side Drawer (Progressive Disclosure Inspector) */}
        {drawerOpen && (
          <aside className="w-80 lg:w-96 rounded-xl bg-white border border-border shadow-lg flex flex-col overflow-hidden shrink-0 animate-fadeIn text-xs">
            {drawerMode === 'group' ? renderGroupInspector() : renderAccountInspector()}
          </aside>
        )}
      </div>

      {/* Load Data Modal */}
      {showLoadModal && renderLoadDataModal()}

      {/* Export Modal */}
      {showExportModal && renderExportModal()}
    </div>
  )

  // =========================================================================
  // DRAWER SUB-COMPONENT: GROUP INSPECTOR
  // =========================================================================
  function renderGroupInspector() {
    return (
      <div className="flex flex-col h-full overflow-hidden bg-white">
        {/* Drawer Header */}
        <div className="p-3.5 border-b border-border bg-slate-50/50 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-critical" />
            <div>
              <h3 className="font-bold text-slate-900">Candidate Group 1</h3>
              <span className="inline-block mt-0.5 text-[10px] px-2 py-0.5 rounded bg-attention-50 text-attention-800 border border-attention-200 font-semibold">
                Needs Review
              </span>
            </div>
          </div>
          <button
            onClick={() => setDrawerOpen(false)}
            className="p-1.5 rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-100 bg-white border border-border transition shadow-xs"
            title="Close Drawer"
            aria-label="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto p-3.5 space-y-4">
          {/* Summary Metric Cards */}
          <div className="grid grid-cols-2 gap-2">
            <div className="p-2.5 rounded-lg bg-slate-50 border border-border">
              <span className="text-[10px] text-slate-500 block font-medium">Member Accounts</span>
              <span className="text-lg font-bold font-mono text-slate-900">
                {candidateNodes.length}
              </span>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-50 border border-border">
              <span className="text-[10px] text-slate-500 block font-medium">Internal Connections</span>
              <span className="text-lg font-bold font-mono text-critical">
                {internalEdgesCount}
              </span>
            </div>
          </div>

          {/* Members List */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-slate-800">Member Accounts</span>
              <span className="text-[11px] font-mono text-slate-500">
                {filteredCandidateMembers.length} accounts
              </span>
            </div>

            <div className="relative">
              <Search className="w-3 h-3 text-slate-400 absolute left-2.5 top-2.5" />
              <input
                type="text"
                placeholder="Filter members..."
                value={memberSearchQuery}
                onChange={(e) => setMemberSearchQuery(e.target.value)}
                className="w-full bg-slate-50 text-slate-800 border border-border rounded-lg pl-8 pr-2 py-1.5 outline-none focus:border-interactive font-mono text-[11px] transition-colors"
              />
            </div>

            <div className="max-h-48 overflow-y-auto space-y-1 pr-1">
              {filteredCandidateMembers.map((memberId) => (
                <div
                  key={memberId}
                  onClick={() => {
                    setSelectedNodeId(memberId)
                    setDrawerMode('account')
                  }}
                  className="flex items-center justify-between p-2 rounded-lg bg-white hover:bg-slate-50 border border-border transition cursor-pointer group shadow-xs"
                >
                  <div className="flex items-center gap-1.5 font-mono text-slate-700 group-hover:text-slate-900">
                    <Hash className="w-3 h-3 text-slate-400" />
                    <span>{memberId}</span>
                  </div>
                  <span className="text-[10px] text-interactive font-semibold flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition">
                    <span>Inspect</span>
                    <ChevronRight className="w-3 h-3" />
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Technical Details (Collapsible Section) */}
          <div className="pt-2 border-t border-border">
            <button
              onClick={() => setShowTechnicalMetrics(!showTechnicalMetrics)}
              className="w-full flex items-center justify-between text-slate-600 hover:text-slate-900 py-1"
            >
              <span className="font-semibold text-[11px]">Technical Density Metrics</span>
              {showTechnicalMetrics ? (
                <ChevronDown className="w-3.5 h-3.5" />
              ) : (
                <ChevronRight className="w-3.5 h-3.5" />
              )}
            </button>

            {showTechnicalMetrics && (
              <div className="mt-2 p-3 rounded-lg bg-slate-50 border border-border space-y-2 text-[11px] font-mono text-slate-700 animate-fadeIn">
                <div className="flex justify-between">
                  <span className="text-slate-500">Candidate Density:</span>
                  <span className="font-bold text-critical">
                    ρ(S) = {candidateDensity.toFixed(4)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Whole Graph Density:</span>
                  <span className="text-slate-800">
                    ρ(G) = {Number(graph?.density ?? 0).toFixed(4)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Density Contrast Ratio:</span>
                  <span className="font-bold text-attention">
                    {densityContrastRatio.toFixed(2)}x
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Algorithm Applied:</span>
                  <span className="text-slate-800 uppercase">{activeAlgo}</span>
                </div>
                {analysis?.runtime_ms && (
                  <div className="flex justify-between">
                    <span className="text-slate-500">Execution Runtime:</span>
                    <span className="text-forest font-semibold">{analysis.runtime_ms.toFixed(2)} ms</span>
                  </div>
                )}
                <p className="text-[10px] text-slate-500 pt-1 border-t border-border font-sans leading-tight">
                  Density is calculated as edges per vertex |E(S)| / |S| (Goldberg 1984), distinct from combinatorial edge-completeness 2|E|/(|V|(|V|-1)).
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Drawer Footer Actions */}
        <div className="p-3.5 border-t border-border bg-slate-50/50 flex items-center justify-between gap-2">
          <button
            onClick={() => copyToClipboard(JSON.stringify(candidateNodes, null, 2), 'Copied!')}
            className="px-3 py-1.5 rounded-lg bg-white hover:bg-slate-50 text-slate-700 border border-border transition flex items-center gap-1.5 text-xs font-medium shadow-xs"
          >
            {copiedNotification ? <Check className="w-3.5 h-3.5 text-forest" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copiedNotification || 'Copy IDs'}</span>
          </button>

          <button
            onClick={() => setShowExportModal(true)}
            className="px-3 py-1.5 rounded-lg bg-interactive hover:bg-interactive-700 text-white transition flex items-center gap-1.5 text-xs font-semibold shadow-xs"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export Findings</span>
          </button>
        </div>
      </div>
    )
  }

  // =========================================================================
  // DRAWER SUB-COMPONENT: ACCOUNT INSPECTOR
  // =========================================================================
  function renderAccountInspector() {
    const isCandidateMember = selectedNodeId ? candidateSet.has(selectedNodeId) : false
    const isPlanted = selectedNodeId ? plantedSet.has(selectedNodeId) : false

    return (
      <div className="flex flex-col h-full overflow-hidden bg-white">
        {/* Drawer Header with Back Button */}
        <div className="p-3.5 border-b border-border bg-slate-50/50 flex items-center justify-between">
          <div className="flex items-center gap-2">
            {candidateNodes.length > 0 && (
              <button
                onClick={() => setDrawerMode('group')}
                className="p-1 rounded text-slate-500 hover:text-slate-900 hover:bg-slate-100 transition"
                title="Back to Candidate Group"
              >
                <ArrowLeft className="w-4 h-4" />
              </button>
            )}
            <div>
              <span className="text-[10px] text-slate-500 block uppercase font-mono">Account Inspector</span>
              <h3 className="font-bold text-slate-900 font-mono text-sm">{selectedNodeId}</h3>
            </div>
          </div>
          <button
            onClick={() => {
              setSelectedNodeId(null)
              setDrawerOpen(false)
            }}
            className="p-1.5 rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-100 bg-white border border-border transition shadow-xs"
            title="Close Inspector"
            aria-label="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Account Details */}
        <div className="flex-1 overflow-y-auto p-3.5 space-y-4">
          {/* Status Badge & Connections */}
          <div className="p-3 rounded-lg bg-slate-50 border border-border space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Membership:</span>
              <span
                className={`font-semibold text-[11px] px-2 py-0.5 rounded border ${
                  isCandidateMember
                    ? 'bg-critical-50 text-critical border-critical-200'
                    : isPlanted
                    ? 'bg-attention-50 text-attention-800 border-attention-200'
                    : 'bg-white text-slate-600 border-border'
                }`}
              >
                {isCandidateMember ? 'Candidate Group 1' : isPlanted ? 'Planted Group' : 'Background Activity'}
              </span>
            </div>

            <div className="flex items-center justify-between font-mono">
              <span className="text-slate-500">Degree / Connections:</span>
              <span className="font-bold text-slate-900">{selectedNodeIncidentEdges.length}</span>
            </div>
          </div>

          {/* Connected Neighbor Accounts */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-slate-800">Connected Neighbors</span>
              <span className="text-[11px] font-mono text-slate-500">
                {selectedNodeNeighbors.length} accounts
              </span>
            </div>

            <div className="max-h-56 overflow-y-auto space-y-1 pr-1">
              {selectedNodeNeighbors.map((neighborId) => {
                const neighborInCandidate = candidateSet.has(neighborId)
                return (
                  <div
                    key={neighborId}
                    onClick={() => setSelectedNodeId(neighborId)}
                    className="flex items-center justify-between p-2 rounded-lg bg-white hover:bg-slate-50 border border-border transition cursor-pointer group shadow-xs"
                  >
                    <div className="flex items-center gap-1.5 font-mono text-slate-700 group-hover:text-slate-900">
                      <Hash className="w-3 h-3 text-slate-400" />
                      <span>{neighborId}</span>
                    </div>

                    <span
                      className={`text-[9px] font-semibold px-1.5 py-0.5 rounded border ${
                        neighborInCandidate
                          ? 'bg-critical-50 text-critical border-critical-200'
                          : 'bg-slate-100 text-slate-600 border-border'
                      }`}
                    >
                      {neighborInCandidate ? 'Candidate' : 'Background'}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Factual Evidence Note */}
          <div className="p-2.5 rounded-lg bg-slate-50 border border-border text-[11px] text-slate-600 space-y-1">
            <div className="flex items-center gap-1.5 text-slate-800 font-semibold">
              <Info className="w-3.5 h-3.5 text-interactive" />
              <span>Network Structure Evidence</span>
            </div>
            <p className="leading-relaxed">
              Displaying factual incident edges from current graph topology. Full temporal transaction logs and timestamps can be monitored in the Streaming Lab.
            </p>
          </div>
        </div>

        {/* Account Actions Footer */}
        <div className="p-3.5 border-t border-border bg-slate-50/50 flex items-center justify-between gap-2">
          <button
            onClick={() => copyToClipboard(selectedNodeId || '', 'Copied ID!')}
            className="px-3 py-1.5 rounded-lg bg-white hover:bg-slate-50 text-slate-700 border border-border transition flex items-center gap-1.5 text-xs font-medium shadow-xs"
          >
            {copiedNotification ? <Check className="w-3.5 h-3.5 text-forest" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copiedNotification || 'Copy Account ID'}</span>
          </button>

          <button
            onClick={() => setSelectedNodeId(null)}
            className="text-xs text-interactive hover:underline"
          >
            Deselect
          </button>
        </div>
      </div>
    )
  }

  // =========================================================================
  // MODAL 1: LOAD TRANSACTION DATA (CSV or Benchmark Scenario)
  // =========================================================================
  function renderLoadDataModal() {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs animate-fadeIn">
        <div className="max-w-xl w-full rounded-2xl bg-white border border-border shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
          {/* Modal Header */}
          <div className="p-4 border-b border-border bg-slate-50/50 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Network className="w-5 h-5 text-forest" />
              <h3 className="font-bold text-slate-900 text-sm">Load Network Data</h3>
            </div>
            <button
              onClick={() => setShowLoadModal(false)}
              className="p-1.5 rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-100 bg-white border border-border transition shadow-xs"
              title="Close Modal"
              aria-label="Close"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Modal Tabs */}
          <div className="flex border-b border-border px-4 pt-2 gap-4 text-xs font-semibold bg-white">
            <button
              onClick={() => setLoadModalTab('upload')}
              className={`pb-2.5 transition border-b-2 flex items-center gap-1.5 ${
                loadModalTab === 'upload'
                  ? 'border-forest text-forest font-bold'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              <Upload className="w-3.5 h-3.5" />
              <span>Import Transaction Data (CSV)</span>
            </button>

            <button
              onClick={() => setLoadModalTab('scenarios')}
              className={`pb-2.5 transition border-b-2 flex items-center gap-1.5 ${
                loadModalTab === 'scenarios'
                  ? 'border-forest text-forest font-bold'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Benchmark Scenarios</span>
            </button>
          </div>

          {/* Modal Body */}
          <div className="p-4 overflow-y-auto flex-1 space-y-4 text-xs">
            {loadModalTab === 'upload' ? (
              <form onSubmit={handleImportSubmit} className="space-y-4">
                <div className="flex items-center justify-between">
                  <label className="text-slate-800 font-semibold">Upload File or Paste Data</label>
                  <button
                    type="button"
                    onClick={() => setImportContent(SAMPLE_CSV)}
                    className="text-[11px] text-interactive hover:underline font-medium"
                  >
                    Load Sample Template
                  </button>
                </div>

                {/* File picker */}
                <div className="border-2 border-dashed border-border hover:border-slate-400 rounded-xl p-4 text-center cursor-pointer transition bg-slate-50/50">
                  <input
                    type="file"
                    accept=".csv,.txt,.snap"
                    onChange={handleFileUpload}
                    className="hidden"
                    id="csv-file-input"
                  />
                  <label htmlFor="csv-file-input" className="cursor-pointer block space-y-1">
                    <Upload className="w-6 h-6 mx-auto text-slate-400" />
                    <span className="text-slate-700 block font-medium">Choose a CSV file or drag here</span>
                    <span className="text-[10px] text-slate-500 block">Supports standard transaction headers: source, target, amount, timestamp</span>
                  </label>
                </div>

                {/* Direct text editor */}
                <div>
                  <label className="text-slate-600 block mb-1">CSV Data Preview</label>
                  <textarea
                    rows={6}
                    value={importContent}
                    onChange={(e) => setImportContent(e.target.value)}
                    className="w-full bg-slate-50 text-slate-800 border border-border rounded-lg p-2 font-mono text-[11px] outline-none focus:border-interactive transition-colors"
                  />
                </div>

                <div className="flex items-center justify-between pt-2">
                  <div className="flex items-center gap-2">
                    <span className="text-slate-500">Format:</span>
                    <select
                      value={importFormat}
                      onChange={(e) => setImportFormat(e.target.value as any)}
                      className="bg-slate-50 text-slate-800 border border-border rounded px-2 py-1 outline-none"
                    >
                      <option value="csv">Standard CSV</option>
                      <option value="snap">SNAP Edge List</option>
                    </select>
                  </div>

                  <button
                    type="submit"
                    disabled={loading || !importContent.trim()}
                    className="px-5 py-2 rounded-xl bg-forest hover:bg-forest-700 text-white font-bold transition disabled:opacity-50 text-xs shadow-xs"
                  >
                    {loading ? 'Importing...' : 'Import & Investigate'}
                  </button>
                </div>
              </form>
            ) : (
              <div className="space-y-4">
                <p className="text-slate-600 text-xs">
                  Select a reproducible synthetic transaction network to investigate:
                </p>

                <div className="grid grid-cols-1 gap-2.5">
                  <div
                    onClick={() => handleLoadScenario('planted_cluster', 'Planted Dense Group (30 accounts)')}
                    className="p-3 rounded-xl bg-white hover:bg-slate-50 border border-border hover:border-forest transition cursor-pointer space-y-1 group shadow-xs"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-slate-900 flex items-center gap-1.5">
                        <ShieldAlert className="w-4 h-4 text-critical" />
                        <span>Planted Dense Collusive Group</span>
                      </span>
                      <span className="text-[10px] text-forest group-hover:translate-x-0.5 transition font-semibold">
                        Load →
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-500">
                      30 accounts total with an 8-account dense cluster (p=0.85 internal density). Simulates hidden collusive fraud rings.
                    </p>
                  </div>

                  <div
                    onClick={() => handleLoadScenario('ring', 'Circular Ring Network (25 accounts)')}
                    className="p-3 rounded-xl bg-white hover:bg-slate-50 border border-border hover:border-attention transition cursor-pointer space-y-1 group shadow-xs"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-slate-900 flex items-center gap-1.5">
                        <RotateCcw className="w-4 h-4 text-attention" />
                        <span>Circular Ring Network</span>
                      </span>
                      <span className="text-[10px] text-attention group-hover:translate-x-0.5 transition font-semibold">
                        Load →
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-500">
                      25 accounts with an embedded 6-node circular flow ring. Simulates round-tripping and wash trading loops.
                    </p>
                  </div>

                  <div
                    onClick={() => handleLoadScenario('random', 'Sparse Baseline Network (30 accounts)')}
                    className="p-3 rounded-xl bg-white hover:bg-slate-50 border border-border hover:border-interactive transition cursor-pointer space-y-1 group shadow-xs"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-slate-900 flex items-center gap-1.5">
                        <Activity className="w-4 h-4 text-interactive" />
                        <span>Sparse Baseline Network</span>
                      </span>
                      <span className="text-[10px] text-interactive group-hover:translate-x-0.5 transition font-semibold">
                        Load →
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-500">
                      30 accounts with uniform random Erdős–Rényi background traffic. No planted collusive structure.
                    </p>
                  </div>
                </div>

                {/* Collapsible custom generator */}
                <div className="pt-2 border-t border-border">
                  <button
                    onClick={() => setShowCustomGen(!showCustomGen)}
                    className="text-slate-600 hover:text-slate-900 text-xs flex items-center gap-1 font-semibold"
                  >
                    <span>Custom Generator Parameters</span>
                    {showCustomGen ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                  </button>

                  {showCustomGen && (
                    <form onSubmit={handleCustomGenerate} className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 pt-3 animate-fadeIn">
                      <div>
                        <label className="text-[10px] text-slate-500 block mb-0.5">Accounts (|V|)</label>
                        <input
                          type="number"
                          min={4}
                          max={500}
                          value={genNumNodes}
                          onChange={(e) => setGenNumNodes(Number(e.target.value))}
                          className="w-full bg-slate-50 text-slate-800 border border-border rounded px-2 py-1 font-mono focus:border-interactive"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] text-slate-500 block mb-0.5">Cluster Size (k)</label>
                        <input
                          type="number"
                          min={2}
                          max={genNumNodes}
                          value={genClusterSize}
                          onChange={(e) => setGenClusterSize(Number(e.target.value))}
                          className="w-full bg-slate-50 text-slate-800 border border-border rounded px-2 py-1 font-mono focus:border-interactive"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] text-slate-500 block mb-0.5">Internal p</label>
                        <input
                          type="number"
                          step={0.05}
                          min={0}
                          max={1}
                          value={genPInternal}
                          onChange={(e) => setGenPInternal(Number(e.target.value))}
                          className="w-full bg-slate-50 text-slate-800 border border-border rounded px-2 py-1 font-mono focus:border-interactive"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] text-slate-500 block mb-0.5">External p</label>
                        <input
                          type="number"
                          step={0.01}
                          min={0}
                          max={1}
                          value={genPExternal}
                          onChange={(e) => setGenPExternal(Number(e.target.value))}
                          className="w-full bg-slate-50 text-slate-800 border border-border rounded px-2 py-1 font-mono focus:border-interactive"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] text-slate-500 block mb-0.5">Seed</label>
                        <input
                          type="number"
                          value={genSeed}
                          onChange={(e) => setGenSeed(Number(e.target.value))}
                          className="w-full bg-slate-50 text-slate-800 border border-border rounded px-2 py-1 font-mono focus:border-interactive"
                        />
                      </div>
                      <div className="col-span-full pt-1">
                        <button
                          type="submit"
                          disabled={loading}
                          className="w-full py-1.5 rounded-lg bg-forest hover:bg-forest-700 text-white font-semibold shadow-xs transition"
                        >
                          Generate Custom Network
                        </button>
                      </div>
                    </form>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    )
  }

  // =========================================================================
  // MODAL 2: EXPORT FINDINGS DIALOG
  // =========================================================================
  function renderExportModal() {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs animate-fadeIn">
        <div className="max-w-md w-full rounded-2xl bg-white border border-border shadow-2xl p-5 space-y-4 text-xs">
          <div className="flex items-center justify-between border-b border-border pb-3">
            <div className="flex items-center gap-2">
              <Download className="w-5 h-5 text-forest" />
              <h3 className="font-bold text-slate-900 text-sm">Export Investigation Findings</h3>
            </div>
            <button
              onClick={() => {
                setShowExportModal(false)
                setExportFeedback(null)
              }}
              className="p-1.5 rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-100 bg-white border border-border transition shadow-xs"
              title="Close Modal"
              aria-label="Close"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {exportFeedback && (
            <div className="p-2.5 rounded-lg bg-forest-50 border border-forest-200 text-forest text-xs flex items-center gap-2 font-semibold animate-fadeIn">
              <Check className="w-4 h-4 text-forest shrink-0" />
              <span>{exportFeedback}</span>
            </div>
          )}

          <p className="text-slate-600 text-xs">
            Export reproducible investigation records including verified candidate nodes, density contrast formulas, and network parameters:
          </p>

          <div className="space-y-3">
            {/* Complete Findings (JSON) */}
            <div className="p-3.5 rounded-xl bg-slate-50 border border-border space-y-2.5">
              <div className="flex items-start gap-2.5">
                <FileSpreadsheet className="w-5 h-5 text-interactive shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                  <div className="font-bold text-slate-900">Complete Findings (JSON)</div>
                  <div className="text-[11px] text-slate-500 leading-snug">
                    Includes Goldberg formulas, density metrics, detected rings, and audit metadata.
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2 pt-1">
                <button
                  onClick={handleExportJSON}
                  className="flex-1 py-1.5 px-3 rounded-lg bg-interactive hover:bg-interactive-700 text-white font-semibold transition flex items-center justify-center gap-1.5 shadow-xs"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Download .json</span>
                </button>
                <button
                  onClick={handleCopyJSON}
                  className="py-1.5 px-3 rounded-lg bg-white hover:bg-slate-100 text-slate-700 border border-border font-medium transition flex items-center gap-1.5 shadow-xs"
                  title="Copy JSON to Clipboard"
                >
                  <Copy className="w-3.5 h-3.5" />
                  <span>Copy</span>
                </button>
              </div>
            </div>

            {/* Account Roster (CSV) */}
            <div className="p-3.5 rounded-xl bg-slate-50 border border-border space-y-2.5">
              <div className="flex items-start gap-2.5">
                <FileSpreadsheet className="w-5 h-5 text-forest shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                  <div className="font-bold text-slate-900">Account Roster (CSV)</div>
                  <div className="text-[11px] text-slate-500 leading-snug">
                    Full account IDs table with candidate group membership and ground truth flags.
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2 pt-1">
                <button
                  onClick={handleExportCSV}
                  className="flex-1 py-1.5 px-3 rounded-lg bg-forest hover:bg-forest-700 text-white font-semibold transition flex items-center justify-center gap-1.5 shadow-xs"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Download .csv</span>
                </button>
                <button
                  onClick={handleCopyCSV}
                  className="py-1.5 px-3 rounded-lg bg-white hover:bg-slate-100 text-slate-700 border border-border font-medium transition flex items-center gap-1.5 shadow-xs"
                  title="Copy CSV to Clipboard"
                >
                  <Copy className="w-3.5 h-3.5" />
                  <span>Copy</span>
                </button>
              </div>
            </div>
          </div>

          <div className="flex justify-end pt-2">
            <button
              onClick={() => {
                setShowExportModal(false)
                setExportFeedback(null)
              }}
              className="px-4 py-1.5 rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200 font-medium transition"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    )
  }
}

export default InvestigatorScreen
