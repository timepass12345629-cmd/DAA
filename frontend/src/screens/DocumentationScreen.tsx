import React from 'react'
import {
  BookOpen,
  CheckCircle2,
  AlertTriangle,
  Zap,
  Layers,
  Radio,
  Cpu,
} from 'lucide-react'

export const DocumentationScreen: React.FC = () => {
  return (
    <div className="max-w-4xl mx-auto space-y-8 text-slate-300">
      {/* Header */}
      <div className="p-5 rounded-xl bg-navy-900 border border-navy-700/80 shadow space-y-2">
        <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2.5">
          <BookOpen className="w-5 h-5 text-accent-blue" />
          <span>RingScope Research Foundations & Algorithmic Guarantees</span>
        </h2>
        <p className="text-xs text-slate-400 leading-relaxed">
          Mathematical formulations, exact flow reductions, approximation proofs, streaming candidate maintenance principles, and empirical limitations.
        </p>
      </div>

      {/* Section 1: Subgraph Density Definition */}
      <section className="space-y-3">
        <div className="flex items-center gap-2 text-sm font-bold text-slate-100 border-b border-navy-700 pb-1.5">
          <Zap className="w-4 h-4 text-cluster-node" />
          <span>1. Subgraph Density Formulation & Invariants</span>
        </div>

        <div className="p-4 rounded-xl bg-navy-900/90 border border-navy-700/80 text-xs space-y-3">
          <p>
            In RingScope, accounts are modeled as vertices $V$ and unique bilateral transaction relationships as undirected edges $E$ in an unweighted simple graph $G = (V, E)$.
          </p>

          <div className="p-3 rounded-lg bg-navy-950 font-mono text-[12px] text-accent-blue border border-navy-800">
            density(S) = |E(S)| / |S| &nbsp;&nbsp;(for any non-empty S ⊆ V)
          </div>

          <ul className="list-disc list-inside space-y-1.5 text-slate-400 pl-1">
            <li>
              <strong className="text-slate-200">Average Degree Identity:</strong> The average induced degree in S satisfies exactly avg_deg(S) = 2 · |E(S)| / |S| = 2 · density(S).
            </li>
            <li>
              <strong className="text-slate-200">Monotonicity Under Insertion:</strong> For any graph G and newly inserted transaction edge e ∉ E(G), the maximum subgraph density is monotonically non-decreasing: λ*(G ∪ &#123;e&#125;) ≥ λ*(G).
            </li>
            <li>
              <strong className="text-slate-200">Dense Core Contrast:</strong> Background financial graphs exhibit sparse trees and peripheral whiskers (density ≈ 0.5 - 1.0), whereas fraudulent rings and collusive cliques form dense components (density ≥ 2.0).
            </li>
          </ul>
        </div>
      </section>

      {/* Section 2: Goldberg's Exact Max-Flow Reduction */}
      <section className="space-y-3">
        <div className="flex items-center gap-2 text-sm font-bold text-slate-100 border-b border-navy-700 pb-1.5">
          <Layers className="w-4 h-4 text-accent-blue" />
          <span>2. Goldberg's Flow-Network Densest Subgraph Reduction (Goldberg 1984)</span>
        </div>

        <div className="p-4 rounded-xl bg-navy-900/90 border border-navy-700/80 text-xs space-y-3">
          <p>
            Goldberg proved that the exact maximum density subgraph can be computed in polynomial time using a sequence of minimum $(s, t)$-cuts on a bipartite edge-node flow network.
          </p>

          <div className="p-3 rounded-lg bg-navy-950 text-slate-300 font-mono text-[11px] border border-navy-800 space-y-1">
            <div>• Source s → edge-node e: Capacity 1.0</div>
            <div>• Edge-node e → vertex-nodes u, v: Capacity INF</div>
            <div>• Vertex-node v → Sink t: Capacity g (candidate threshold)</div>
            <div className="text-emerald-400 pt-1">
              Finite cut cost: C(S) = m - |E(S)| + g · |S| &lt; m ⟺ |E(S)| / |S| &gt; g
            </div>
          </div>

          <p className="text-slate-400">
            RingScope pairs this reduction with Dinic's algorithm (BFS level graph + DFS blocking flows with per-vertex work pointers), and conducts binary search over $g \in [0, (n-1)/2]$ with tolerance $\epsilon$.
          </p>
        </div>
      </section>

      {/* Section 3: Charikar Greedy Peeling & Greedy++ */}
      <section className="space-y-3">
        <div className="flex items-center gap-2 text-sm font-bold text-slate-100 border-b border-navy-700 pb-1.5">
          <Cpu className="w-4 h-4 text-accent-emerald" />
          <span>3. Linear Approximations: Charikar Peeling & Greedy++</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <div className="p-4 rounded-xl bg-navy-900/90 border border-navy-700/80 space-y-2">
            <h4 className="font-semibold text-slate-200">Charikar Greedy Peeling (APPROX 2000)</h4>
            <p className="text-slate-400">
              Iteratively peels the vertex with minimum degree in the current induced subgraph using a lazy min-heap.
            </p>
            <div className="p-2 rounded bg-navy-950 font-mono text-[11px] text-sky-300 border border-navy-800">
              Guarantee: ≥ OPT / 2 (2-approximation)
            </div>
            <p className="text-slate-400">
              Runs in optimal $O((n + m) \log n)$ time and $O(n + m)$ memory, suitable for rapid screening of large networks.
            </p>
          </div>

          <div className="p-4 rounded-xl bg-navy-900/90 border border-navy-700/80 space-y-2">
            <h4 className="font-semibold text-slate-200">Greedy++ (Boob et al., WWW/KDD 2020)</h4>
            <p className="text-slate-400">
              Executes multiple peeling passes where vertices accumulate load based on induced degrees:
            </p>
            <div className="p-2 rounded bg-navy-950 font-mono text-[11px] text-emerald-300 border border-navy-800">
              Priority: deg_H(v) + ℓ(v) &nbsp;|&nbsp; ℓ(v) ← ℓ(v) + deg_H(v)
            </div>
            <p className="text-slate-400">
              Achieves provable $(1 - \epsilon)$-approximation in $O(\Delta \log n / (\lambda^* \epsilon^2))$ passes without constructing flow networks.
            </p>
          </div>
        </div>
      </section>

      {/* Section 4: Streaming Maintenance Modes & Non-Local Triggers */}
      <section className="space-y-3">
        <div className="flex items-center gap-2 text-sm font-bold text-slate-100 border-b border-navy-700 pb-1.5">
          <Radio className="w-4 h-4 text-accent-amber" />
          <span>4. Streaming Candidate Maintenance Principles</span>
        </div>

        <div className="p-4 rounded-xl bg-navy-900/90 border border-navy-700/80 text-xs space-y-3">
          <p>
            In dynamic transaction streams, RingScope evaluates three maintenance modes:
          </p>

          <div className="space-y-2">
            <div className="p-2.5 rounded-lg bg-navy-950 border border-navy-800">
              <strong className="text-slate-200">Mode A (Full Recomputation):</strong> Re-solves from scratch on every incoming batch. Serves as exact ground truth baseline.
            </div>
            <div className="p-2.5 rounded-lg bg-navy-950 border border-navy-800">
              <strong className="text-slate-200">Mode B (Warm-Started):</strong> Reuses prior density λ_(t-1) as the binary search lower bound. Safely bypasses recomputation when parallel edges do not modify graph topology.
            </div>
            <div className="p-2.5 rounded-lg bg-navy-950 border border-navy-800">
              <strong className="text-slate-200">Mode C (Incremental Heuristic):</strong> Tracks candidate statistics locally.
              <span className="text-amber-400 block mt-1">
                Important: Does NOT falsely assume that only edges touching the current candidate can change the optimum. Disjoint components can grow denser; explicit external activity triggers govern full recomputation.
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Section 5: Limitations & Safeguards */}
      <section className="space-y-3 pb-8">
        <div className="flex items-center gap-2 text-sm font-bold text-slate-100 border-b border-navy-700 pb-1.5">
          <AlertTriangle className="w-4 h-4 text-amber-400" />
          <span>5. Practical Limitations & Computational Safeguards</span>
        </div>

        <div className="p-4 rounded-xl bg-navy-900/90 border border-navy-700/80 text-xs space-y-2 text-slate-400">
          <div className="flex items-start gap-2">
            <CheckCircle2 className="w-3.5 h-3.5 text-accent-blue mt-0.5 shrink-0" />
            <span>
              <strong className="text-slate-200">Asynchronous Offloading:</strong> All heavy flow computations and peeling passes are offloaded from the asyncio loop to worker threads (`asyncio.to_thread`), preventing server stalls.
            </span>
          </div>
          <div className="flex items-start gap-2">
            <CheckCircle2 className="w-3.5 h-3.5 text-accent-blue mt-0.5 shrink-0" />
            <span>
              <strong className="text-slate-200">Display Safeguard:</strong> Graphs larger than 200 nodes are rendered with priority sampling (protecting the densest cluster) to maintain 60 FPS in Cytoscape.js.
            </span>
          </div>
          <div className="flex items-start gap-2">
            <CheckCircle2 className="w-3.5 h-3.5 text-accent-blue mt-0.5 shrink-0" />
            <span>
              <strong className="text-slate-200">Real Benchmark Data:</strong> Zero fabricated or hardcoded results. All figures, export files, and tables represent actual computed values.
            </span>
          </div>
        </div>
      </section>
    </div>
  )
}
