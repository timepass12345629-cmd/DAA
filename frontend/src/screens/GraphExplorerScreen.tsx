import React, { useState } from 'react'
import {
  Upload,
  RefreshCw,
  Search,
  Hash,
} from 'lucide-react'
import { GraphResponse, GraphGenerateRequest, GraphImportRequest } from '../api/types'
import { CytoscapeGraph } from '../components/CytoscapeGraph'

interface GraphExplorerScreenProps {
  graph: GraphResponse | null
  candidateNodes: string[]
  onGenerate: (req: GraphGenerateRequest) => Promise<void>
  onImport: (req: GraphImportRequest) => Promise<void>
  loading: boolean
}

export const GraphExplorerScreen: React.FC<GraphExplorerScreenProps> = ({
  graph,
  candidateNodes,
  onGenerate,
  onImport,
  loading,
}) => {
  const [selectedNode, setSelectedNode] = useState<string | null>(null)
  const [searchFilter, setSearchFilter] = useState('')
  const [tab, setTab] = useState<'generate' | 'import'>('generate')

  // Generate form state
  const [genType, setGenType] = useState<'planted_cluster' | 'random' | 'ring'>('planted_cluster')
  const [numNodes, setNumNodes] = useState<number>(30)
  const [clusterSize, setClusterSize] = useState<number>(8)
  const [pInternal, setPInternal] = useState<number>(0.8)
  const [pExternal, setPExternal] = useState<number>(0.05)
  const [seed, setSeed] = useState<number>(42)

  // Import form state
  const [importFormat, setImportFormat] = useState<'csv' | 'snap'>('csv')
  const [importContent, setImportContent] = useState<string>(
    'source,target,amount\nACC_A,ACC_B,100\nACC_B,ACC_C,120\nACC_C,ACC_A,150\nACC_C,ACC_D,50'
  )

  const handleGenerateSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    await onGenerate({
      generator_type: genType,
      num_nodes: numNodes,
      cluster_size: clusterSize,
      p_internal: pInternal,
      p_external: pExternal,
      seed,
    })
  }

  const handleImportSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    await onImport({
      content: importContent,
      format: importFormat,
    })
  }

  const handleLoadSampleSnap = () => {
    setImportFormat('snap')
    setImportContent(
      `# Stanford Network Analysis Project (SNAP) Format\n# Nodes: 6 Edges: 8\n1 2\n2 3\n3 1\n3 4\n4 5\n5 6\n6 4\n2 4`
    )
  }

  const candidateSet = new Set(candidateNodes)
  const filteredNodes = (graph?.nodes || []).filter((n) =>
    n.toLowerCase().includes(searchFilter.toLowerCase())
  )

  return (
    <div className="space-y-6">
      {/* Top Controls & Generator Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Form: Generate or Import */}
        <div className="p-4 rounded-xl bg-navy-900 border border-navy-700/80 shadow space-y-4">
          <div className="flex items-center justify-between border-b border-navy-700 pb-2">
            <div className="flex gap-2">
              <button
                onClick={() => setTab('generate')}
                className={`text-xs font-semibold px-3 py-1 rounded transition ${
                  tab === 'generate'
                    ? 'bg-accent-blue/15 text-accent-blue border border-accent-blue/40'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Synthesize Graph
              </button>
              <button
                onClick={() => setTab('import')}
                className={`text-xs font-semibold px-3 py-1 rounded transition ${
                  tab === 'import'
                    ? 'bg-purple-500/15 text-purple-300 border border-purple-500/40'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Import Edge List
              </button>
            </div>
          </div>

          {tab === 'generate' ? (
            <form onSubmit={handleGenerateSubmit} className="space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-slate-400 block mb-1">Generator Strategy</label>
                  <select
                    value={genType}
                    onChange={(e) => setGenType(e.target.value as any)}
                    className="w-full bg-navy-800 text-slate-200 border border-navy-600 rounded p-1.5 outline-none focus:border-accent-blue"
                  >
                    <option value="planted_cluster">Planted Cluster</option>
                    <option value="random">Random OTC Graph</option>
                    <option value="ring">Synthetic Rings</option>
                  </select>
                </div>

                <div>
                  <label className="text-slate-400 block mb-1">Accounts (N)</label>
                  <input
                    type="number"
                    min={4}
                    max={500}
                    value={numNodes}
                    onChange={(e) => setNumNodes(Number(e.target.value))}
                    className="w-full bg-navy-800 text-slate-200 border border-navy-600 rounded p-1.5 outline-none focus:border-accent-blue font-mono"
                  />
                </div>
              </div>

              {genType === 'planted_cluster' && (
                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="text-slate-400 block mb-1">Cluster (k)</label>
                    <input
                      type="number"
                      min={2}
                      max={numNodes}
                      value={clusterSize}
                      onChange={(e) => setClusterSize(Number(e.target.value))}
                      className="w-full bg-navy-800 text-slate-200 border border-navy-600 rounded p-1.5 outline-none focus:border-accent-blue font-mono"
                    />
                  </div>
                  <div>
                    <label className="text-slate-400 block mb-1">p (internal)</label>
                    <input
                      type="number"
                      step={0.05}
                      min={0}
                      max={1}
                      value={pInternal}
                      onChange={(e) => setPInternal(Number(e.target.value))}
                      className="w-full bg-navy-800 text-slate-200 border border-navy-600 rounded p-1.5 outline-none focus:border-accent-blue font-mono"
                    />
                  </div>
                  <div>
                    <label className="text-slate-400 block mb-1">p (external)</label>
                    <input
                      type="number"
                      step={0.01}
                      min={0}
                      max={1}
                      value={pExternal}
                      onChange={(e) => setPExternal(Number(e.target.value))}
                      className="w-full bg-navy-800 text-slate-200 border border-navy-600 rounded p-1.5 outline-none focus:border-accent-blue font-mono"
                    />
                  </div>
                </div>
              )}

              <div className="flex items-center justify-between pt-1">
                <div className="flex items-center gap-1.5">
                  <span className="text-slate-400">Seed:</span>
                  <input
                    type="number"
                    value={seed}
                    onChange={(e) => setSeed(Number(e.target.value))}
                    className="w-16 bg-navy-800 text-slate-200 border border-navy-600 rounded px-1.5 py-1 outline-none font-mono text-[11px]"
                  />
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent-blue hover:bg-sky-400 text-navy-950 font-bold transition disabled:opacity-50"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                  <span>Generate Graph</span>
                </button>
              </div>
            </form>
          ) : (
            <form onSubmit={handleImportSubmit} className="space-y-3 text-xs">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <label className="text-slate-400">Format:</label>
                  <select
                    value={importFormat}
                    onChange={(e) => setImportFormat(e.target.value as any)}
                    className="bg-navy-800 text-slate-200 border border-navy-600 rounded px-2 py-0.5 outline-none"
                  >
                    <option value="csv">CSV (source, target)</option>
                    <option value="snap">SNAP (# Header edge list)</option>
                  </select>
                </div>
                <button
                  type="button"
                  onClick={handleLoadSampleSnap}
                  className="text-[11px] text-accent-blue hover:underline"
                >
                  Load SNAP Sample
                </button>
              </div>

              <div>
                <textarea
                  rows={4}
                  value={importContent}
                  onChange={(e) => setImportContent(e.target.value)}
                  placeholder="Paste CSV or SNAP edge list..."
                  className="w-full bg-navy-800 text-slate-200 border border-navy-600 rounded p-2 font-mono text-[11px] outline-none focus:border-purple-400 resize-none"
                />
              </div>

              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={loading}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white font-medium transition disabled:opacity-50"
                >
                  <Upload className="w-3.5 h-3.5" />
                  <span>Import Data</span>
                </button>
              </div>
            </form>
          )}
        </div>

        {/* Center/Right: Current Graph Topology Stats */}
        <div className="lg:col-span-2 p-4 rounded-xl bg-navy-900 border border-navy-700/80 shadow flex flex-col justify-between">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-navy-700 pb-2">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-sm text-slate-200">Active Topology Metadata</span>
              <span className="text-[11px] font-mono text-slate-400">ID: {graph?.graph_id || 'none'}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-[11px] px-2 py-0.5 rounded font-mono bg-navy-800 text-slate-300 border border-navy-600">
                Type: {graph?.generator_type || 'unloaded'}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 my-3">
            <div className="p-2.5 rounded-lg bg-navy-800/80 border border-navy-700/70">
              <div className="text-[11px] text-slate-400">Vertices (|V|)</div>
              <div className="text-lg font-bold font-mono text-slate-100">{graph?.num_nodes ?? 0}</div>
            </div>
            <div className="p-2.5 rounded-lg bg-navy-800/80 border border-navy-700/70">
              <div className="text-[11px] text-slate-400">Unique Edges (|E|)</div>
              <div className="text-lg font-bold font-mono text-slate-100">{graph?.num_edges ?? 0}</div>
            </div>
            <div className="p-2.5 rounded-lg bg-navy-800/80 border border-navy-700/70">
              <div className="text-[11px] text-slate-400">Graph Density (|E|/|V|)</div>
              <div className="text-lg font-bold font-mono text-accent-blue">
                {Number(graph?.density ?? 0).toFixed(4)}
              </div>
            </div>
            <div className="p-2.5 rounded-lg bg-navy-800/80 border border-navy-700/70">
              <div className="text-[11px] text-slate-400">Degrees (min / avg / max)</div>
              <div className="text-sm font-bold font-mono text-slate-100 mt-1">
                {graph?.degree_stats.min ?? 0} / {graph?.degree_stats.avg ?? 0} / {graph?.degree_stats.max ?? 0}
              </div>
            </div>
          </div>

          <div className="text-xs text-slate-400 flex items-center justify-between">
            <span>
              Candidate Cluster Identified: <strong className="text-red-400">{candidateNodes.length}</strong> accounts
            </span>
            <span>
              Connected Components: <strong className="text-slate-200">{graph?.connected_components_count ?? 0}</strong>
            </span>
          </div>
        </div>
      </div>

      {/* Main Cytoscape Graph Canvas & Sidebar */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="lg:col-span-3 h-[520px]">
          <CytoscapeGraph
            nodes={graph?.nodes}
            edges={graph?.edges}
            candidateNodes={candidateNodes}
            plantedNodes={graph?.planted_cluster?.nodes}
            onSelectNode={(nodeId) => setSelectedNode(nodeId)}
          />
        </div>

        {/* Sidebar: Node Filter & Inspection */}
        <div className="p-4 rounded-xl bg-navy-900 border border-navy-700/80 shadow flex flex-col h-[520px]">
          <div className="font-semibold text-xs text-slate-200 border-b border-navy-700 pb-2 mb-3 flex items-center justify-between">
            <span>Account Roster</span>
            <span className="text-[11px] font-mono text-slate-400">{filteredNodes.length} total</span>
          </div>

          {/* Search box */}
          <div className="relative mb-3">
            <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-2.5" />
            <input
              type="text"
              placeholder="Search account ID..."
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              className="w-full bg-navy-800 text-slate-200 text-xs border border-navy-600 rounded pl-8 pr-2 py-1.5 outline-none focus:border-accent-blue"
            />
          </div>

          {/* Node List */}
          <div className="flex-1 overflow-y-auto space-y-1.5 pr-1 text-xs">
            {filteredNodes.map((nodeId) => {
              const isCand = candidateSet.has(nodeId)
              const isSelected = selectedNode === nodeId

              return (
                <div
                  key={nodeId}
                  onClick={() => setSelectedNode(nodeId)}
                  className={`flex items-center justify-between p-2 rounded cursor-pointer transition ${
                    isSelected
                      ? 'bg-accent-blue/20 border border-accent-blue text-white'
                      : isCand
                      ? 'bg-red-950/50 border border-red-800/60 text-red-300 hover:bg-red-900/40'
                      : 'bg-navy-800/60 border border-navy-700/60 text-slate-300 hover:bg-navy-800'
                  }`}
                >
                  <div className="flex items-center gap-1.5 font-mono text-[11px]">
                    <Hash className="w-3 h-3 text-slate-500" />
                    <span>{nodeId}</span>
                  </div>

                  {isCand && (
                    <span className="text-[10px] font-semibold px-1.5 py-0.2 rounded bg-cluster-node text-white">
                      Candidate
                    </span>
                  )}
                </div>
              )
            })}
          </div>

          {/* Selected Account Detail */}
          {selectedNode && (
            <div className="mt-3 pt-3 border-t border-navy-700 text-xs space-y-1 bg-navy-950/60 p-2.5 rounded-lg border border-navy-700/80">
              <div className="font-semibold text-slate-200 flex items-center justify-between">
                <span>Inspecting:</span>
                <span className="font-mono text-accent-blue">{selectedNode}</span>
              </div>
              <div className="text-[11px] text-slate-400">
                In Densest Cluster:{' '}
                <strong className={candidateSet.has(selectedNode) ? 'text-red-400' : 'text-slate-400'}>
                  {candidateSet.has(selectedNode) ? 'YES (High Risk)' : 'NO'}
                </strong>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
