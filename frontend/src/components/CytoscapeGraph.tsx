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
  selectedNodeId?: string | null
  onSelectNode?: (nodeId: string | null) => void
  maxRenderNodes?: number
  showSelectedBox?: boolean
  datasetLabel?: string | null
}

export const CytoscapeGraph: React.FC<CytoscapeGraphProps> = ({
  nodes = [],
  edges = [],
  candidateNodes = [],
  plantedNodes = [],
  selectedNodeId,
  onSelectNode,
  maxRenderNodes = 200,
  showSelectedBox = false,
  datasetLabel = null,
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<Core | null>(null)
  const onSelectNodeRef = useRef(onSelectNode)
  onSelectNodeRef.current = onSelectNode

  const [layoutName, setLayoutName] = useState<'cose' | 'concentric' | 'circle' | 'breadthfirst'>('cose')
  const [enableSampling, setEnableSampling] = useState<boolean>(true)
  const [internalSelectedId, setInternalSelectedId] = useState<string | null>(null)

  const activeSelectedId = selectedNodeId !== undefined ? selectedNodeId : internalSelectedId

  const rawNodes = useMemo(() => nodes || [], [nodes])
  const rawEdges = useMemo(() => edges || [], [edges])
  const totalNodes = rawNodes.length
  const isLargeGraph = totalNodes > maxRenderNodes

  // Prepare filtered/sampled nodes and edges
  const { displayNodes, displayEdges, isSampled } = useMemo(() => {
    if (!enableSampling || rawNodes.length <= maxRenderNodes) {
      return {
        displayNodes: rawNodes,
        displayEdges: rawEdges,
        isSampled: false,
      }
    }

    // Smart sampling: prioritize candidate and planted clusters if present
    const priorityNodes = new Set<string>()
    for (const n of candidateNodes || []) priorityNodes.add(n)
    for (const n of plantedNodes || []) priorityNodes.add(n)

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
  }, [rawNodes, rawEdges, enableSampling, maxRenderNodes, candidateNodes, plantedNodes])

  // Topology fingerprint: triggers layout ONLY when graph topology genuinely changes
  const topologyFingerprint = useMemo(() => {
    if (displayNodes.length === 0) return ''
    const nodeSample = displayNodes.slice(0, 5).join(',')
    const edgeCount = displayEdges.length
    return `${datasetLabel || ''}|${displayNodes.length}|${edgeCount}|${nodeSample}`
  }, [displayNodes, displayEdges, datasetLabel])

  // 1. Initialize Cytoscape core ONCE on mount
  useEffect(() => {
    if (!containerRef.current) return

    const cy = cytoscape({
      container: containerRef.current,
      elements: [],
      style: [
        {
          selector: 'node',
          style: {
            'label': 'data(label)',
            'color': '#1F2937',
            'font-size': '8px',
            'font-family': 'ui-monospace, monospace',
            'font-weight': 500,
            'text-valign': 'center',
            'text-halign': 'center',
            'text-outline-color': '#FFFFFF',
            'text-outline-width': 1.5,
            'text-outline-opacity': 0.9,
            'background-color': '#E0F2E8',
            'border-width': 1.5,
            'border-color': '#176B45',
            'width': 26,
            'height': 26,
            'transition-property': 'background-color, border-color, width, height',
            'transition-duration': 0.15,
          },
        },
        {
          selector: 'node.candidate',
          style: {
            'background-color': '#DC2626',
            'border-color': '#991B1B',
            'border-width': 2.5,
            'color': '#FFFFFF',
            'font-size': '8.5px',
            'font-weight': 700,
            'text-outline-color': '#7F1D1D',
            'text-outline-width': 1,
            'text-outline-opacity': 0.9,
            'width': 32,
            'height': 32,
            'underlay-color': '#DC2626',
            'underlay-padding': 3,
            'underlay-opacity': 0.25,
            'z-index': 100,
          },
        },
        {
          selector: 'node.planted',
          style: {
            'background-color': '#E58A2B',
            'border-color': '#B45309',
            'border-width': 2,
            'color': '#FFFFFF',
            'font-size': '8px',
            'font-weight': 600,
            'text-outline-color': '#78350F',
            'text-outline-width': 1,
            'width': 28,
            'height': 28,
          },
        },
        {
          selector: 'node:selected, node.selected-node',
          style: {
            'border-color': '#356AC3',
            'border-width': 3,
            'underlay-color': '#356AC3',
            'underlay-padding': 4,
            'underlay-opacity': 0.25,
            'z-index': 110,
          },
        },
        {
          selector: 'node.neighbor-highlight',
          style: {
            'border-color': '#356AC3',
            'border-width': 2.5,
            'underlay-color': '#356AC3',
            'underlay-padding': 2,
            'underlay-opacity': 0.15,
            'z-index': 105,
          },
        },
        {
          selector: 'edge',
          style: {
            'width': 1.2,
            'line-color': '#94A3B8',
            'curve-style': 'bezier',
            'opacity': 0.7,
          },
        },
        {
          selector: 'edge.candidate-edge',
          style: {
            'width': 2.8,
            'line-color': '#DC2626',
            'opacity': 0.95,
            'z-index': 50,
          },
        },
        {
          selector: 'edge.planted-edge',
          style: {
            'width': 2.0,
            'line-color': '#E58A2B',
            'line-style': 'dashed',
            'opacity': 0.85,
          },
        },
        {
          selector: 'edge.incident-highlight',
          style: {
            'width': 2.5,
            'line-color': '#356AC3',
            'opacity': 1.0,
            'z-index': 45,
          },
        },
      ],
      minZoom: 0.2,
      maxZoom: 3.5,
      wheelSensitivity: 0.25,
    })

    cy.on('tap', 'node', (evt: EventObject) => {
      const nodeId = evt.target.id()
      setInternalSelectedId(nodeId)
      onSelectNodeRef.current?.(nodeId)
    })

    cy.on('tap', (evt: EventObject) => {
      if (evt.target === cy) {
        setInternalSelectedId(null)
        onSelectNodeRef.current?.(null)
      }
    })

    cyRef.current = cy

    // Auto-resize viewport smoothly when surrounding UI changes without resetting layout
    let resizeObserver: ResizeObserver | null = null
    if (typeof ResizeObserver !== 'undefined' && containerRef.current) {
      resizeObserver = new ResizeObserver(() => {
        cy.resize()
      })
      resizeObserver.observe(containerRef.current)
    }

    return () => {
      resizeObserver?.disconnect()
      cy.destroy()
      cyRef.current = null
    }
  }, [])

  // 2. Topology & Layout Effect: Updates elements & runs layout ONLY when topology or layoutName changes
  useEffect(() => {
    const cy = cyRef.current
    if (!cy || !topologyFingerprint) return

    const elements: cytoscape.ElementDefinition[] = [
      ...displayNodes.map((nodeId) => ({
        data: { id: nodeId, label: nodeId },
        classes: 'background',
      })),
      ...displayEdges.map(([u, v], idx) => ({
        data: {
          id: `e_${u}_${v}_${idx}`,
          source: u,
          target: v,
        },
        classes: 'normal',
      })),
    ]

    cy.batch(() => {
      cy.elements().remove()
      cy.add(elements)
    })

    const layout = cy.layout({
      name: layoutName,
      animate: false,
      padding: 30,
    })
    layout.run()
    cy.fit(undefined, 30)
  }, [topologyFingerprint, layoutName])

  // 3. Candidate & Planted Highlight Effect: Updates classes without touching node coordinates
  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return

    const cSet = new Set(candidateNodes || [])
    const pSet = new Set(plantedNodes || [])

    cy.batch(() => {
      cy.nodes().forEach((node) => {
        const id = node.id()
        if (cSet.has(id)) {
          node.addClass('candidate').removeClass('planted background')
        } else if (pSet.has(id)) {
          node.addClass('planted').removeClass('candidate background')
        } else {
          node.addClass('background').removeClass('candidate planted')
        }
      })

      cy.edges().forEach((edge) => {
        const src = edge.source().id()
        const tgt = edge.target().id()
        const isCandidate = cSet.has(src) && cSet.has(tgt)
        const isPlanted = pSet.has(src) && pSet.has(tgt)

        if (isCandidate) {
          edge.addClass('candidate-edge').removeClass('planted-edge normal')
        } else if (isPlanted) {
          edge.addClass('planted-edge').removeClass('candidate-edge normal')
        } else {
          edge.addClass('normal').removeClass('candidate-edge planted-edge')
        }
      })
    })
  }, [candidateNodes, plantedNodes, topologyFingerprint])

  // 4. Selection & Neighborhood Highlighting Effect: Updates focus classes without touching positions
  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return

    cy.batch(() => {
      cy.elements().removeClass('selected-node neighbor-highlight incident-highlight')

      if (activeSelectedId) {
        const node = cy.$id(activeSelectedId)
        if (node.length > 0) {
          node.addClass('selected-node')
          const neighborhood = node.neighborhood()
          neighborhood.nodes().addClass('neighbor-highlight')
          neighborhood.edges().addClass('incident-highlight')
        }
      }
    })
  }, [activeSelectedId])

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
    <div className="relative w-full h-full min-h-[460px] bg-white rounded-xl border border-border overflow-hidden flex flex-col shadow-sm">
      {/* Top Toolbar */}
      <div className="absolute top-3 left-3 z-10 flex flex-wrap items-center gap-2 bg-white/95 backdrop-blur-md px-3 py-1.5 rounded-lg border border-border shadow-sm text-xs">
        <div className="flex items-center gap-1.5 font-medium text-slate-700 pr-2 border-r border-border">
          <Layers className="w-3.5 h-3.5 text-interactive" />
          <span>Layout:</span>
          <select
            value={layoutName}
            onChange={(e) => setLayoutName(e.target.value as any)}
            className="bg-slate-50 text-slate-800 border border-border rounded px-2 py-0.5 outline-none focus:border-interactive transition-colors"
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
            className="p-1 text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded transition"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
          <button
            onClick={handleZoomOut}
            title="Zoom Out"
            className="p-1 text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded transition"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <button
            onClick={handleFit}
            title="Fit to Viewport"
            className="p-1 text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded transition"
          >
            <Maximize2 className="w-4 h-4" />
          </button>
          <button
            onClick={handleResetLayout}
            title="Relayout"
            className="p-1 text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded transition"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
        </div>

        {/* Safeguard / Sampling toggle */}
        {isLargeGraph && (
          <div className="flex items-center gap-1.5 pl-2 border-l border-border">
            <button
              onClick={() => setEnableSampling(!enableSampling)}
              className={`flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium transition ${
                enableSampling
                  ? 'bg-attention-50 text-attention-800 border border-attention-300'
                  : 'bg-slate-100 text-slate-600 hover:text-slate-900'
              }`}
            >
              <Sliders className="w-3 h-3" />
              <span>{enableSampling ? `Sampled (${displayNodes.length}/${totalNodes})` : 'Full Graph'}</span>
            </button>
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="absolute bottom-3 left-3 z-10 flex items-center gap-3 bg-white/95 backdrop-blur-md px-3 py-1.5 rounded-lg border border-border shadow-sm text-xs text-slate-700">
        <div className="flex items-center gap-1.5">
          <span
            className="w-3 h-3 rounded-full bg-critical shadow-[0_0_6px_rgba(220,38,38,0.4)]"
            style={{ backgroundColor: '#DC2626' }}
          />
          <span className="text-[11px] font-medium">Candidate Cluster ({candidateNodes ? candidateNodes.length : 0})</span>
        </div>
        {plantedNodes && plantedNodes.length > 0 && (
          <div className="flex items-center gap-1.5">
            <span
              className="w-3 h-3 rounded-full bg-attention border border-attention-700"
              style={{ backgroundColor: '#E58A2B', borderColor: '#B45309' }}
            />
            <span className="text-[11px] font-medium">Planted Ground Truth ({plantedNodes.length})</span>
          </div>
        )}
        <div className="flex items-center gap-1.5">
          <span
            className="w-3 h-3 rounded-full bg-forest-50 border border-forest"
            style={{ backgroundColor: '#E0F2E8', borderColor: '#176B45' }}
          />
          <span className="text-[11px] font-medium">Normal Accounts</span>
        </div>
      </div>

      {/* Top right status badges */}
      <div className="absolute top-3 right-3 z-10 flex items-center gap-2">
        {isSampled && (
          <div className="flex items-center gap-1.5 bg-attention-50 border border-attention-300 text-attention-800 px-2 py-0.5 rounded text-[11px] backdrop-blur-md shadow-sm">
            <AlertTriangle className="w-3 h-3 text-attention" />
            <span>Sampled ({displayNodes.length}/${totalNodes})</span>
          </div>
        )}
        {datasetLabel ? (
          <div className="bg-white/95 backdrop-blur-md px-2.5 py-0.5 rounded border border-border text-[11px] text-slate-700 font-mono shadow-sm">
            {datasetLabel}
          </div>
        ) : null}
      </div>

      {/* Selected Node Details Box (Optional floating fallback) */}
      {showSelectedBox && activeSelectedId && (
        <div className="absolute top-14 right-3 z-10 w-64 bg-white/98 border border-border rounded-lg p-3 text-xs shadow-md backdrop-blur-md">
          <div className="font-semibold text-slate-800 border-b border-border pb-1 mb-2 flex items-center justify-between">
            <span>Account Details</span>
            <span className="font-mono text-[11px] text-interactive font-medium">{activeSelectedId}</span>
          </div>
          <div className="space-y-1.5 text-slate-600">
            <div className="flex justify-between">
              <span className="text-slate-500">Cluster Status:</span>
              <span
                className={`font-semibold ${
                  (candidateNodes || []).includes(activeSelectedId)
                    ? 'text-critical'
                    : (plantedNodes || []).includes(activeSelectedId)
                    ? 'text-attention'
                    : 'text-slate-700'
                }`}
              >
                {(candidateNodes || []).includes(activeSelectedId)
                  ? 'Candidate (Suspicious)'
                  : (plantedNodes || []).includes(activeSelectedId)
                  ? 'Planted Cluster'
                  : 'Normal'}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Canvas container */}
      <div ref={containerRef} className="w-full flex-1 min-h-[460px] cursor-grab active:cursor-grabbing bg-white" />
    </div>
  )
}
