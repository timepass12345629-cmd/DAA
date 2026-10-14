import React, { useState } from 'react'
import {
  FlaskConical,
  Play,
  Download,
  FileText,
  AlertCircle,
  BarChart3,
} from 'lucide-react'
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import { ExperimentJobResponse, ExperimentRunRequest } from '../api/types'
import { api } from '../api/client'

interface ExperimentsScreenProps {
  onRunExperiment: (req: ExperimentRunRequest) => Promise<ExperimentJobResponse>
  loading: boolean
}

const EXPERIMENTS_CONFIG = [
  {
    id: 'exp1_runtime_vs_size',
    name: '1. Runtime vs Graph Size',
    description: 'Empirical scaling benchmarks comparing Goldberg Flow, Charikar Peeling, and Greedy++.',
    defaultParams: { sizes: [10, 20, 30] },
  },
  {
    id: 'exp2_cluster_size_recovery',
    name: '2. Cluster Size vs Recovery',
    description: 'Precision, Recall, F1, and Jaccard overlap metrics against planted clusters of varying size k.',
    defaultParams: { n: 25, cluster_sizes: [4, 6, 8] },
  },
  {
    id: 'exp3_cluster_sparsity',
    name: '3. Cluster Sparsity vs Recovery',
    description: 'Evaluating cluster boundary recovery as internal edge probability varies from sparse to clique.',
    defaultParams: { n: 25, p_in_values: [0.5, 0.7, 0.9] },
  },
  {
    id: 'exp4_background_connectivity',
    name: '4. Background Noise vs Overlap',
    description: 'False candidate overlap and noise tolerance as external background density p_out increases.',
    defaultParams: { n: 25, p_out_values: [0.03, 0.08, 0.15] },
  },
  {
    id: 'exp5_exact_vs_approx',
    name: '5. Exact vs Approximate Density',
    description: 'Goldberg flow and peeling approximations validated against small-instance Brute-Force Oracle.',
    defaultParams: { sizes: [8, 12] },
  },
  {
    id: 'exp6_streaming_modes',
    name: '6. Streaming Modes Comparison',
    description: 'Full Recomputation vs Warm-Started vs Incremental Heuristic across multi-batch stream.',
    defaultParams: { n: 20, num_batches: 8, batch_size: 4 },
  },
  {
    id: 'exp7_clusters_and_hubs',
    name: '7. Competing Clusters & Hubs',
    description: 'Performance in multi-community networks with deceptive star hubs and competing dense cores.',
    defaultParams: { n: 25 },
  },
]

export const ExperimentsScreen: React.FC<ExperimentsScreenProps> = ({
  onRunExperiment,
  loading,
}) => {
  const [selectedExpId, setSelectedExpId] = useState<string>('exp1_runtime_vs_size')
  const [seed, setSeed] = useState<number>(42)
  const [activeJob, setActiveJob] = useState<ExperimentJobResponse | null>(null)
  const [resultsData, setResultsData] = useState<any[] | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const selectedExp = EXPERIMENTS_CONFIG.find((e) => e.id === selectedExpId) || EXPERIMENTS_CONFIG[0]

  const handleExecute = async () => {
    setErrorMsg(null)
    setResultsData(null)
    try {
      const job = await onRunExperiment({
        experiment_name: selectedExpId as any,
        seed,
        params: selectedExp.defaultParams,
      })
      setActiveJob(job)

      // Fetch computed results records
      const records = await api.getExperimentResults(job.experiment_id)
      setResultsData(records)
    } catch (err: any) {
      setErrorMsg(err.message || 'Experiment execution failed')
    }
  }

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="p-4 rounded-xl bg-navy-900 border border-navy-700/80 shadow flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-slate-100 flex items-center gap-2">
            <FlaskConical className="w-5 h-5 text-purple-400" />
            <span>Reproducible Empirical Evaluation Harness</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Automated benchmark suite executing real trials on identical graphs, with true measured metrics and CSV/JSON exports.
          </p>
        </div>

        {activeJob && (
          <div className="flex items-center gap-2">
            <span
              className={`px-3 py-1 rounded-full text-xs font-mono font-semibold border ${
                activeJob.status === 'COMPLETED'
                  ? 'bg-emerald-950 text-emerald-400 border-emerald-700'
                  : 'bg-amber-950 text-amber-300 border-amber-700'
              }`}
            >
              STATUS: {activeJob.status}
            </span>
          </div>
        )}
      </div>

      {/* Experiment Selector & Parameter Controls */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="p-4 rounded-xl bg-navy-900 border border-navy-700/80 shadow space-y-4">
          <div className="font-semibold text-xs text-slate-200 border-b border-navy-700 pb-2">
            Select Empirical Benchmark
          </div>

          <div className="space-y-1.5 text-xs">
            {EXPERIMENTS_CONFIG.map((exp) => (
              <button
                key={exp.id}
                onClick={() => setSelectedExpId(exp.id)}
                className={`w-full text-left p-2.5 rounded-lg border transition ${
                  selectedExpId === exp.id
                    ? 'bg-purple-950/60 border-purple-600/80 text-purple-200 font-semibold shadow-[0_0_12px_rgba(168,85,247,0.2)]'
                    : 'bg-navy-800/60 border-navy-700/60 text-slate-400 hover:text-slate-200 hover:bg-navy-800'
                }`}
              >
                <div className="text-xs">{exp.name}</div>
                <div className="text-[10px] text-slate-500 line-clamp-1 mt-0.5">{exp.description}</div>
              </button>
            ))}
          </div>

          <div className="pt-2 border-t border-navy-700 space-y-3 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Random Seed:</span>
              <input
                type="number"
                value={seed}
                onChange={(e) => setSeed(Number(e.target.value))}
                className="w-20 bg-navy-800 text-slate-200 border border-navy-600 rounded px-2 py-1 font-mono text-[11px]"
              />
            </div>

            <button
              onClick={handleExecute}
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 p-2 rounded-lg bg-purple-600 hover:bg-purple-500 text-white font-bold transition disabled:opacity-50 shadow-md"
            >
              <Play className={`w-3.5 h-3.5 fill-current ${loading ? 'animate-spin' : ''}`} />
              <span>{loading ? 'Running Benchmark...' : 'Execute Trial'}</span>
            </button>
          </div>
        </div>

        {/* Experiment Results Preview & Export Controls */}
        <div className="lg:col-span-2 p-4 rounded-xl bg-navy-900 border border-navy-700/80 shadow flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center justify-between border-b border-navy-700 pb-2">
              <div>
                <h3 className="text-xs font-semibold text-slate-200">{selectedExp.name}</h3>
                <p className="text-[11px] text-slate-400">{selectedExp.description}</p>
              </div>

              {activeJob?.status === 'COMPLETED' && (
                <div className="flex items-center gap-2">
                  <a
                    href={api.getExportUrl(activeJob.experiment_id, 'json')}
                    download
                    className="flex items-center gap-1 px-2.5 py-1 rounded bg-navy-800 hover:bg-navy-700 text-accent-blue border border-navy-600 text-xs font-medium transition"
                  >
                    <Download className="w-3.5 h-3.5" />
                    <span>JSON</span>
                  </a>
                  <a
                    href={api.getExportUrl(activeJob.experiment_id, 'csv')}
                    download
                    className="flex items-center gap-1 px-2.5 py-1 rounded bg-navy-800 hover:bg-navy-700 text-emerald-400 border border-navy-600 text-xs font-medium transition"
                  >
                    <FileText className="w-3.5 h-3.5" />
                    <span>CSV</span>
                  </a>
                </div>
              )}
            </div>

            {errorMsg && (
              <div className="p-3 rounded-lg bg-red-950/70 border border-red-800 text-red-300 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4" />
                <span>{errorMsg}</span>
              </div>
            )}

            {/* Benchmark Visualization Chart */}
            {resultsData && resultsData.length > 0 ? (
              <div className="h-64 w-full pt-2">
                <ResponsiveContainer width="100%" height="100%">
                  {selectedExpId === 'exp1_runtime_vs_size' ? (
                    <LineChart data={resultsData} margin={{ top: 10, right: 20, left: -10, bottom: 10 }}>
                      <XAxis dataKey="num_nodes" stroke="#64748B" fontSize={11} label={{ value: 'Nodes (N)', position: 'insideBottom', offset: -5 }} />
                      <YAxis stroke="#64748B" fontSize={11} label={{ value: 'Runtime (ms)', angle: -90, position: 'insideLeft' }} />
                      <Tooltip contentStyle={{ backgroundColor: '#0F172A', borderColor: '#334155', borderRadius: 8, fontSize: 12 }} />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      <Line type="monotone" dataKey="goldberg_ms" name="Goldberg (Flow)" stroke="#EF4444" strokeWidth={2} />
                      <Line type="monotone" dataKey="greedy_peeling_ms" name="Charikar Peeling" stroke="#38BDF8" strokeWidth={2} />
                      <Line type="monotone" dataKey="greedy_plus_plus_ms" name="Greedy++" stroke="#10B981" strokeWidth={2} />
                    </LineChart>
                  ) : (
                    <BarChart data={resultsData} margin={{ top: 10, right: 20, left: -10, bottom: 10 }}>
                      <XAxis dataKey={resultsData[0]?.mode ? 'mode' : 'num_nodes'} stroke="#64748B" fontSize={11} />
                      <YAxis stroke="#64748B" fontSize={11} />
                      <Tooltip contentStyle={{ backgroundColor: '#0F172A', borderColor: '#334155', borderRadius: 8, fontSize: 12 }} />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      {resultsData[0]?.final_density && <Bar dataKey="final_density" fill="#EF4444" name="Final Density" />}
                      {resultsData[0]?.precision && <Bar dataKey="precision" fill="#38BDF8" name="Precision" />}
                      {resultsData[0]?.recall && <Bar dataKey="recall" fill="#10B981" name="Recall" />}
                      {resultsData[0]?.f1 && <Bar dataKey="f1" fill="#F59E0B" name="F1 Score" />}
                      {resultsData[0]?.optimal_density && <Bar dataKey="optimal_density" fill="#EF4444" name="True OPT" />}
                    </BarChart>
                  )}
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="h-64 flex flex-col items-center justify-center text-xs text-slate-500 space-y-2">
                <BarChart3 className="w-8 h-8 text-slate-600" />
                <span>Select an experiment on the left and click "Execute Trial" to view real benchmark metrics.</span>
              </div>
            )}
          </div>

          {activeJob && (
            <div className="pt-3 border-t border-navy-700 flex items-center justify-between text-xs text-slate-400">
              <span className="font-mono">ID: {activeJob.experiment_id}</span>
              <span className="font-mono text-emerald-400">Runtime: {activeJob.runtime_ms?.toFixed(2)} ms</span>
            </div>
          )}
        </div>
      </div>

      {/* Raw Data Records Table */}
      {resultsData && resultsData.length > 0 && (
        <div className="p-4 rounded-xl bg-navy-900 border border-navy-700/80 shadow space-y-3">
          <div className="flex items-center justify-between border-b border-navy-700 pb-2">
            <h3 className="text-xs font-semibold text-slate-200">Exported Benchmark Trial Records</h3>
            <span className="text-[11px] font-mono text-slate-400">{resultsData.length} records</span>
          </div>

          <div className="overflow-x-auto max-h-64 overflow-y-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-navy-800 text-slate-400 uppercase text-[10px] sticky top-0">
                <tr>
                  {Object.keys(resultsData[0]).map((key) => (
                    <th key={key} className="p-2 whitespace-nowrap">
                      {key.replace(/_/g, ' ')}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-navy-800 text-slate-300">
                {resultsData.map((row, idx) => (
                  <tr key={idx} className="hover:bg-navy-850 transition">
                    {Object.values(row).map((val: any, cIdx) => (
                      <td key={cIdx} className="p-2 whitespace-nowrap">
                        {typeof val === 'number'
                          ? Number(val).toFixed(typeof val === 'number' && val < 10 ? 4 : 2)
                          : String(val)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
