import React, { useEffect, useRef, useState, useMemo } from 'react'
import cytoscape, { Core, EventObject } from 'cytoscape'
import {
  ZoomIn,
  ZoomOut,
  Maximize2,
  RotateCcw,
  Layers,
  Sliders,
  AlertTriangle,
} from 'lucide-react'

interface CytoscapeGraphProps {
  nodes?: string[] | null
  edges?: [string, string][] | null
  candidateNodes?: string[] | null
  plantedNodes?: string[] | null
  onSelectNode?: (nodeId: string | null) => void
  maxRenderNodes?: number
}

export const CytoscapeGraph: React.FC<CytoscapeGraphProps> = ({
  nodes = [],
  edges = [],
  candidateNodes = [],
  plantedNodes = [],
  onSelectNode,
  maxRenderNodes = 200,
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<Core | null>(null)
  const [layoutName, setLayoutName] = useState<'cose' | 'concentric' | 'circle' | 'breadthfirst'>('cose')
  const [enableSampling, setEnableSampling] = useState<boolean>(true)
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const candidateSet = useMemo(() => new Set(candidateNodes || []), [candidateNodes])
  const plantedSet = useMemo(() => new Set(plantedNodes || []), [plantedNodes])

  const totalNodes = nodes ? nodes.length : 0
  const isLargeGraph = totalNodes > maxRenderNodes

  // Prepare filtered/sampled nodes and edges
  const { displayNodes, displayEdges, isSampled } = useMemo(() => {
    const rawNodes = nodes || []
    const rawEdges = edges || []

    if (!enableSampling || rawNodes.length <= maxRenderNodes) {
      return {
        displayNodes: rawNodes,
        displayEdges: rawEdges,
        isSampled: false,
      }
    }

    // Smart sampling: always prioritize candidate cluster and planted nodes
    const priorityNodes = new Set<string>()
    for (const n of candidateSet) priorityNodes.add(n)
    for (const n of plantedSet) priorityNodes.add(n)

    const remainingBudget = Math.max(0, maxRenderNodes - priorityNodes.size)
    const otherNodes = rawNodes.filter((n) => !priorityNodes.has(n))
    const sampledOthers = otherNodes.slice(0, remainingBudget)

    const activeNodeSet = new Set([...priorityNodes, ...sampledOthers])
    const sampledEdges = rawEdges.filter(
      ([u, v]) => activeNodeSet.has(u) && activeNodeSet.has(v)
    )

    return {
      displayNodes: Array.from(activeNodeSet),
      displayEdges: sampledEdges,
      isSampled: true,
    }
  }, [nodes, edges, enableSampling, maxRenderNodes, candidateSet, plantedSet])

  useEffect(() => {
    if (!containerRef.current) return

    // Convert to Cytoscape elements
    const elements: cytoscape.ElementDefinition[] = [
      ...displayNodes.map((nodeId) => {
        const isCandidate = candidateSet.has(nodeId)
        const isPlanted = plantedSet.has(nodeId)

        let nodeClass = 'background'
        if (isCandidate) {
          nodeClass = 'candidate'
        } else if (isPlanted) {
          nodeClass = 'planted'
        }

        return {
          data: {
            id: nodeId,
            label: nodeId,
            isCandidate,
            isPlanted,
          },
          classes: nodeClass,
        }
      }),
      ...displayEdges.map(([u, v], idx) => {
        const isInternalCandidate = candidateSet.has(u) && candidateSet.has(v)
        const isInternalPlanted = plantedSet.has(u) && plantedSet.has(v)

        let edgeClass = 'normal'
        if (isInternalCandidate) {
          edgeClass = 'candidate-edge'
        } else if (isInternalPlanted) {
          edgeClass = 'planted-edge'
        }

        return {
          data: {
            id: `e_${u}_${v}_${idx}`,
            source: u,
            target: v,
          },
          classes: edgeClass,
        }
      }),
    ]

    // Initialize Cytoscape core
    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: 'node',
          style: {
            'label': 'data(label)',
            'color': '#94A3B8',
            'font-size': '10px',
            'font-family': 'ui-monospace, monospace',
            'text-valign': 'center',
            'text-halign': 'center',
            'background-color': '#1E293B',
            'border-width': 1.5,
            'border-color': '#475569',
            'width': 26,
            'height': 26,
            'transition-property': 'background-color, border-color, width, height',
            'transition-duration': 0.2,
          },
        },
        {
          selector: 'node.candidate',
          style: {
            'background-color': '#EF4444',
            'border-color': '#DC2626',
            'border-width': 2.5,
            'color': '#FFFFFF',
            'font-weight': 'bold',
            'width': 34,
            'height': 34,
            'underlay-color': '#EF4444',
            'underlay-padding': 4,
            'underlay-opacity': 0.35,
            'z-index': 100,
          },
        },
        {
          selector: 'node.planted',
          style: {
            'background-color': '#B91C1C',
            'border-color': '#F87171',
            'border-width': 2,
            'color': '#FECACA',
            'width': 30,
            'height': 30,
          },
        },
        {
          selector: 'node:selected',
          style: {
            'border-color': '#38BDF8',
            'border-width': 3,
            'underlay-color': '#38BDF8',
            'underlay-padding': 4,
            'underlay-opacity': 0.45,
          },
        },
        {
          selector: 'edge',
          style: {
            'width': 1.2,
            'line-color': '#334155',
            'curve-style': 'bezier',
            'opacity': 0.65,
          },
        },
        {
          selector: 'edge.candidate-edge',
          style: {
            'width': 2.8,
            'line-color': '#EF4444',
            'opacity': 0.95,
            'z-index': 50,
          },
        },
        {
          selector: 'edge.planted-edge',
          style: {
            'width': 2.0,
            'line-color': '#F87171',
            'line-style': 'dashed',
            'opacity': 0.8,
          },
        },
      ],
      layout: {
        name: layoutName,
        animate: false,
        padding: 30,
      },
      minZoom: 0.2,
      maxZoom: 3.5,
      wheelSensitivity: 0.25,
    })

    cy.on('tap', 'node', (evt: EventObject) => {
      const nodeId = evt.target.id()
      setSelectedId(nodeId)
      if (onSelectNode) onSelectNode(nodeId)
    })

    cy.on('tap', (evt: EventObject) => {
      if (evt.target === cy) {
        setSelectedId(null)
        if (onSelectNode) onSelectNode(null)
      }
    })

    cyRef.current = cy

    return () => {
      cy.destroy()
      cyRef.current = null
    }
  }, [displayNodes, displayEdges, layoutName, candidateSet, plantedSet, onSelectNode])

  const handleZoomIn = () => {
    if (cyRef.current) cyRef.current.zoom(cyRef.current.zoom() * 1.25)
  }

  const handleZoomOut = () => {
    if (cyRef.current) cyRef.current.zoom(cyRef.current.zoom() * 0.8)
  }

  const handleFit = () => {
    if (cyRef.current) cyRef.current.fit(undefined, 30)
  }

  const handleResetLayout = () => {
    if (cyRef.current) {
      cyRef.current.layout({ name: layoutName, animate: true, animationDuration: 400 }).run()
    }
  }

  return (
    <div className="relative w-full h-full min-h-[460px] bg-navy-950 rounded-xl border border-navy-700/60 overflow-hidden flex flex-col">
      {/* Top Toolbar */}
      <div className="absolute top-3 left-3 z-10 flex flex-wrap items-center gap-2 bg-navy-900/90 backdrop-blur-md px-3 py-1.5 rounded-lg border border-navy-700/80 shadow-lg text-xs">
        <div className="flex items-center gap-1.5 font-medium text-slate-300 pr-2 border-r border-navy-700">
          <Layers className="w-3.5 h-3.5 text-accent-blue" />
          <span>Layout:</span>
          <select
            value={layoutName}
            onChange={(e) => setLayoutName(e.target.value as any)}
            className="bg-navy-800 text-slate-200 border border-navy-600 rounded px-2 py-0.5 outline-none focus:border-accent-blue"
          >
            <option value="cose">Force-Directed (CoSE)</option>
            <option value="concentric">Concentric Rings</option>
            <option value="circle">Circular</option>
            <option value="breadthfirst">Breadth-First Tree</option>
          </select>
        </div>

        {/* View Controls */}
        <div className="flex items-center gap-1">
          <button
            onClick={handleZoomIn}
            title="Zoom In"
            className="p-1 text-slate-300 hover:text-white hover:bg-navy-800 rounded transition"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
          <button
            onClick={handleZoomOut}
            title="Zoom Out"
            className="p-1 text-slate-300 hover:text-white hover:bg-navy-800 rounded transition"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <button
            onClick={handleFit}
            title="Fit to Viewport"
            className="p-1 text-slate-300 hover:text-white hover:bg-navy-800 rounded transition"
          >
            <Maximize2 className="w-4 h-4" />
          </button>
          <button
            onClick={handleResetLayout}
            title="Relayout"
            className="p-1 text-slate-300 hover:text-white hover:bg-navy-800 rounded transition"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
        </div>

        {/* Safeguard / Sampling toggle */}
        {isLargeGraph && (
          <div className="flex items-center gap-1.5 pl-2 border-l border-navy-700">
            <button
              onClick={() => setEnableSampling(!enableSampling)}
              className={`flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium transition ${
                enableSampling
                  ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                  : 'bg-navy-800 text-slate-400 hover:text-slate-200'
              }`}
            >
              <Sliders className="w-3 h-3" />
              <span>{enableSampling ? `Sampled (${displayNodes.length}/${totalNodes})` : 'Full Graph'}</span>
            </button>
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="absolute bottom-3 left-3 z-10 flex items-center gap-3 bg-navy-900/90 backdrop-blur-md px-3 py-1.5 rounded-lg border border-navy-700/80 shadow-md text-xs text-slate-300">
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-cluster-node shadow-[0_0_8px_rgba(239,68,68,0.7)]" />
          <span className="text-[11px]">Candidate Cluster ({candidateSet.size})</span>
        </div>
        {plantedSet.size > 0 && (
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-red-800 border border-red-400" />
            <span className="text-[11px]">Planted Ground Truth ({plantedSet.size})</span>
          </div>
        )}
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-navy-800 border border-slate-600" />
          <span className="text-[11px]">Peripheral Accounts</span>
        </div>
      </div>

      {/* Warning badge if sampled */}
      {isSampled && (
        <div className="absolute top-3 right-3 z-10 flex items-center gap-1.5 bg-amber-950/80 border border-amber-600/40 text-amber-300 px-2.5 py-1 rounded text-xs backdrop-blur-md">
          <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
          <span>Performance Safeguard Active: Rendered {displayNodes.length} priority vertices</span>
        </div>
      )}

      {/* Selected Node Details Box */}
      {selectedId && (
        <div className="absolute top-14 right-3 z-10 w-60 bg-navy-900/95 border border-navy-700/90 rounded-lg p-3 text-xs shadow-xl backdrop-blur-md">
          <div className="font-semibold text-slate-200 border-b border-navy-700 pb-1 mb-2 flex items-center justify-between">
            <span>Account Details</span>
            <span className="mono text-[10px] text-accent-blue">{selectedId}</span>
          </div>
          <div className="space-y-1.5 text-slate-300">
            <div className="flex justify-between">
              <span className="text-slate-400">Cluster Status:</span>
              <span
                className={`font-semibold ${
                  candidateSet.has(selectedId)
                    ? 'text-red-400'
                    : plantedSet.has(selectedId)
                    ? 'text-amber-400'
                    : 'text-slate-400'
                }`}
              >
                {candidateSet.has(selectedId)
                  ? 'Candidate (Densest)'
                  : plantedSet.has(selectedId)
                  ? 'Planted Cluster'
                  : 'Background'}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Canvas container */}
      <div ref={containerRef} className="w-full flex-1 min-h-[460px] cursor-grab active:cursor-grabbing" />
    </div>
  )
}
