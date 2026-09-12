import React, { useState } from 'react';
import { AnomalyRecord, AnomalyCause, AnomalySeverity } from '../../types';
import { CauseBadge, SeverityBadge } from '../common/Badges';
import { Search, ArrowRight, CheckCircle2, Clock } from 'lucide-react';

interface AnomalyTableProps {
  anomalies: AnomalyRecord[];
  onSelectAnomaly: (anomaly: AnomalyRecord) => void;
}

export const AnomalyTable: React.FC<AnomalyTableProps> = ({
  anomalies,
  onSelectAnomaly,
}) => {
  const [causeFilter, setCauseFilter] = useState<AnomalyCause | 'All'>('All');
  const [severityFilter, setSeverityFilter] = useState<AnomalySeverity | 'All'>('All');
  const [searchTerm, setSearchTerm] = useState('');

  const filtered = anomalies.filter((item) => {
    const matchesCause = causeFilter === 'All' || item.cause === causeFilter;
    const matchesSeverity = severityFilter === 'All' || item.severity === severityFilter;
    const matchesSearch =
      searchTerm === '' ||
      item.stationId.toLowerCase().includes(searchTerm.toLowerCase()) ||
      item.stationName.toLowerCase().includes(searchTerm.toLowerCase()) ||
      item.faultType.toLowerCase().includes(searchTerm.toLowerCase()) ||
      item.id.toLowerCase().includes(searchTerm.toLowerCase());

    return matchesCause && matchesSeverity && matchesSearch;
  });

  return (
    <div className="apple-glass-card rounded-2xl shadow-[0_8px_30px_rgba(15,23,42,0.04)] overflow-hidden">
      {/* Table Filter Bar */}
      <div className="p-4 bg-white/70 border-b border-slate-200/50 flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs">
        <div className="flex flex-wrap items-center gap-2">
          {/* Cause Filter Segmented Pills */}
          <div className="inline-flex rounded-full bg-slate-100/80 p-0.5 border border-slate-200/50">
            {(['All', 'Weather', 'Sensor'] as const).map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => setCauseFilter(c)}
                className={`px-3 py-1 rounded-full font-medium cursor-pointer transition-all ${
                  causeFilter === c
                    ? 'bg-blue-600 text-white shadow-2xs font-semibold'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {c === 'All' ? 'All Causes' : c === 'Weather' ? 'Weather Events' : 'Sensor Faults'}
              </button>
            ))}
          </div>

          {/* Severity Filter Pills */}
          <div className="inline-flex rounded-full bg-slate-100/80 p-0.5 border border-slate-200/50">
            {(['All', 'Critical', 'High', 'Medium', 'Low'] as const).map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setSeverityFilter(s)}
                className={`px-2.5 py-1 rounded-full text-xs font-medium cursor-pointer transition-all ${
                  severityFilter === s
                    ? 'bg-slate-900 text-white shadow-2xs font-semibold'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        {/* Search */}
        <div className="relative w-full md:w-64">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            type="text"
            placeholder="Search anomaly or station..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 bg-slate-100/70 border border-slate-200/60 rounded-full text-xs text-slate-800 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
          />
        </div>
      </div>

      {/* Table Data */}
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="border-b border-slate-200/50 text-slate-400 uppercase font-medium tracking-wider text-[10px]">
              <th className="py-3 px-4">Station</th>
              <th className="py-3 px-3">Timestamp</th>
              <th className="py-3 px-3">Diagnosis Category</th>
              <th className="py-3 px-3">Detected Pattern</th>
              <th className="py-3 px-3">Severity</th>
              <th className="py-3 px-3 font-mono">Score</th>
              <th className="py-3 px-3 font-mono">Confidence</th>
              <th className="py-3 px-3">Status</th>
              <th className="py-3 px-4 text-right">Investigation</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={9} className="py-8 text-center text-slate-400 text-xs">
                  No anomaly records match the selected criteria.
                </td>
              </tr>
            ) : (
              filtered.map((item) => (
                <tr
                  key={item.id}
                  onClick={() => onSelectAnomaly(item)}
                  className="hover:bg-blue-50/40 cursor-pointer transition-colors"
                >
                  <td className="py-3.5 px-4 font-medium text-slate-900">
                    <div className="font-semibold text-slate-900">{item.stationName}</div>
                    <div className="text-[11px] font-mono text-slate-400">
                      {item.stationId} • {item.region}
                    </div>
                  </td>
                  <td className="py-3.5 px-3 font-mono text-[11px] text-slate-500">
                    {item.timestamp} IST
                  </td>
                  <td className="py-3.5 px-3">
                    <CauseBadge cause={item.cause} />
                  </td>
                  <td className="py-3.5 px-3">
                    <span className="font-semibold text-slate-800">{item.faultType}</span>
                    <span className="text-[10px] text-slate-400 block">
                      Param: {item.evidence.affectedParameter}
                    </span>
                  </td>
                  <td className="py-3.5 px-3">
                    <SeverityBadge severity={item.severity} />
                  </td>
                  <td className="py-3.5 px-3 font-mono font-semibold text-slate-800">
                    {item.anomalyScore.toFixed(2)}
                  </td>
                  <td className="py-3.5 px-3 font-mono text-slate-600">
                    {item.confidence}%
                  </td>
                  <td className="py-3.5 px-3">
                    {item.status === 'Resolved' ? (
                      <span className="inline-flex items-center gap-1 text-[11px] text-emerald-700 font-medium">
                        <CheckCircle2 className="w-3 h-3" />
                        Resolved
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-[11px] text-amber-800 font-medium">
                        <Clock className="w-3 h-3 text-amber-600" />
                        Active
                      </span>
                    )}
                  </td>
                  <td className="py-3.5 px-4 text-right">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectAnomaly(item);
                      }}
                      className="text-xs font-semibold text-blue-600 hover:text-blue-800 inline-flex items-center gap-0.5 cursor-pointer"
                    >
                      <span>Explain</span>
                      <ArrowRight className="w-3 h-3" />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
