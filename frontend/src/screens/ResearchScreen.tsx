import React, { useState } from 'react'
import { FlaskConical, BookOpen } from 'lucide-react'
import { ExperimentsScreen } from './ExperimentsScreen'
import { DocumentationScreen } from './DocumentationScreen'
import { ExperimentJobResponse, ExperimentRunRequest } from '../api/types'

interface ResearchScreenProps {
  onRunExperiment: (req: ExperimentRunRequest) => Promise<ExperimentJobResponse>
  loading: boolean
}

export const ResearchScreen: React.FC<ResearchScreenProps> = ({
  onRunExperiment,
  loading,
}) => {
  const [activeSubTab, setActiveSubTab] = useState<'benchmarks' | 'docs'>('benchmarks')

  return (
    <div className="space-y-6">
      {/* Secondary Sub-navigation */}
      <div className="flex items-center justify-between border-b border-border pb-3">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveSubTab('benchmarks')}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition ${
              activeSubTab === 'benchmarks'
                ? 'bg-forest text-white shadow-xs'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            <FlaskConical className="w-3.5 h-3.5" />
            <span>Benchmark Experiments</span>
          </button>

          <button
            onClick={() => setActiveSubTab('docs')}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition ${
              activeSubTab === 'docs'
                ? 'bg-forest text-white shadow-xs'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            <BookOpen className="w-3.5 h-3.5" />
            <span>Theory & Invariants</span>
          </button>
        </div>

        <div className="text-[11px] font-mono text-slate-500 hidden sm:block">
          Academic Research Suite • Discrete Algorithmic Analysis
        </div>
      </div>

      {/* Subtab Content */}
      {activeSubTab === 'benchmarks' ? (
        <ExperimentsScreen onRunExperiment={onRunExperiment} loading={loading} />
      ) : (
        <DocumentationScreen />
      )}
    </div>
  )
}
export default ResearchScreen
