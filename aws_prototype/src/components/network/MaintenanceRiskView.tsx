import React from 'react';
import { ArrowRight, BrainCircuit, Clock3, ShieldAlert, TrendingDown, TrendingUp, Minus } from 'lucide-react';
import { MaintenanceRiskResult } from '../../types';

interface Props {
  results: MaintenanceRiskResult[];
  onViewStation: (id: string) => void;
}

const priorityClass: Record<string, string> = {
  Priority: 'bg-rose-50 text-rose-700 border-rose-200',
  Elevated: 'bg-orange-50 text-orange-700 border-orange-200',
  Attention: 'bg-amber-50 text-amber-700 border-amber-200',
  Monitor: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  'Insufficient Data': 'bg-slate-50 text-slate-600 border-slate-200',
};

const riskClass = (risk: number | null) => {
  if (risk === null) return 'text-slate-400';
  if (risk >= 75) return 'text-rose-600';
  if (risk >= 50) return 'text-orange-600';
  if (risk >= 25) return 'text-amber-600';
  return 'text-emerald-600';
};

const DirectionIcon: React.FC<{ direction: string }> = ({ direction }) => {
  if (direction === 'worsening') return <TrendingUp className="w-3.5 h-3.5 text-rose-600" />;
  if (direction === 'improving') return <TrendingDown className="w-3.5 h-3.5 text-emerald-600" />;
  return <Minus className="w-3.5 h-3.5 text-slate-400" />;
};

export const MaintenanceRiskView: React.FC<Props> = ({ results, onViewStation }) => {
  const ranked = results.filter((r) => r.maintenance_risk !== null && r.confidence !== 'none');
  const elevated = ranked.filter((r) => (r.maintenance_risk ?? 0) >= 50).length;

  return (
    <section className="apple-glass-card rounded-2xl overflow-hidden">
      <div className="p-4 border-b border-slate-200/60 bg-white/70 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
            <BrainCircuit className="w-4 h-4 text-blue-600" />
            Predictive Maintenance Risk
          </h2>
          <p className="text-[11px] text-slate-500 mt-1">
            Deterministic maintenance-priority index from telemetry, anomaly burden, sensor faults and data quality.
          </p>
        </div>
        <div className="flex items-center gap-3 text-[11px] font-mono text-slate-500">
          <span>{ranked.length} ranked</span>
          <span>{elevated} elevated+</span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-slate-200/60 text-[10px] uppercase tracking-wider text-slate-400">
              <th className="py-2.5 px-4">Rank</th>
              <th className="py-2.5 px-3">Station</th>
              <th className="py-2.5 px-3 text-center">Risk</th>
              <th className="py-2.5 px-3">Priority</th>
              <th className="py-2.5 px-3">Confidence</th>
              <th className="py-2.5 px-3">Trajectory</th>
              <th className="py-2.5 px-3">Action</th>
              <th className="py-2.5 px-4 text-right"> </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {results.map((item) => {
              const id = item.station_id.replace('_', '-');
              const direction = item.trajectory?.direction || 'unknown';
              return (
                <tr key={item.station_id} className="hover:bg-blue-50/40 transition-colors">
                  <td className="py-3 px-4 font-mono font-semibold text-slate-500">{item.priority_rank ?? '—'}</td>
                  <td className="py-3 px-3 font-semibold text-slate-900">{id}</td>
                  <td className={`py-3 px-3 text-center font-mono text-base font-bold ${riskClass(item.maintenance_risk)}`}>
                    {item.maintenance_risk ?? '—'}
                  </td>
                  <td className="py-3 px-3">
                    <span className={`inline-flex px-2 py-0.5 rounded-full border text-[11px] font-medium ${priorityClass[item.priority] || priorityClass.Monitor}`}>
                      {item.priority}
                    </span>
                  </td>
                  <td className="py-3 px-3 capitalize text-slate-600">{item.confidence}</td>
                  <td className="py-3 px-3">
                    <span className="inline-flex items-center gap-1.5 capitalize text-slate-700">
                      <DirectionIcon direction={direction} />{direction}
                    </span>
                  </td>
                  <td className="py-3 px-3 text-slate-600">{item.recommended_action}</td>
                  <td className="py-3 px-4 text-right">
                    {item.attention_horizon !== null && (
                      <span className="inline-flex items-center gap-1 mr-3 text-[10px] text-orange-700 font-mono">
                        <Clock3 className="w-3 h-3" /> {item.attention_horizon.toFixed(1)}h
                      </span>
                    )}
                    <button type="button" onClick={() => onViewStation(item.station_id)} className="text-blue-600 hover:text-blue-800 font-semibold inline-flex items-center gap-1">
                      Inspect <ArrowRight className="w-3 h-3" />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="px-4 py-3 border-t border-slate-200/50 bg-slate-50/60 flex items-start gap-2 text-[10px] text-slate-500">
        <ShieldAlert className="w-3.5 h-3.5 shrink-0 mt-0.5 text-slate-400" />
        <span>Maintenance risk is a prioritization index, not a failure probability, survival estimate, or remaining-useful-life forecast.</span>
      </div>
    </section>
  );
};
