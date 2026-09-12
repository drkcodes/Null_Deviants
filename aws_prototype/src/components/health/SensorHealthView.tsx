import React, { useState } from 'react';
import { StationSensorHealth } from '../../types';
import { ChannelBadge } from '../common/Badges';
import { MetricCard } from '../common/MetricCard';
import {
  Activity,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Search,
  ShieldCheck,
  ArrowRight,
  Cpu,
} from 'lucide-react';

interface SensorHealthViewProps {
  healthList: StationSensorHealth[];
  onSelectStation: (stationId: string) => void;
}

export const SensorHealthView: React.FC<SensorHealthViewProps> = ({
  healthList,
  onSelectStation,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [channelFilter, setChannelFilter] = useState<'All' | 'Faulty' | 'Degraded'>('All');

  // Network-wide summary metrics
  const reportingList = healthList.filter((h) => h.overallHealth !== null);
  const hasReporting = reportingList.length > 0;
  const avgHealth = hasReporting
    ? Math.round(
        reportingList.reduce((acc, h) => acc + (h.overallHealth ?? 0), 0) / reportingList.length,
      )
    : null;
  const healthyCount = hasReporting
    ? reportingList.filter(
        (h) =>
          h.temperatureChannel === 'Normal' &&
          h.humidityChannel === 'Normal' &&
          h.pressureChannel === 'Normal',
      ).length
    : null;
  const degradedCount = hasReporting
    ? reportingList.filter(
        (h) =>
          (h.temperatureChannel === 'Degraded' ||
            h.humidityChannel === 'Degraded' ||
            h.pressureChannel === 'Degraded') &&
          h.temperatureChannel !== 'Suspected fault' &&
          h.humidityChannel !== 'Suspected fault' &&
          h.pressureChannel !== 'Suspected fault',
      ).length
    : null;
  const criticalCount = hasReporting
    ? reportingList.filter(
        (h) =>
          h.temperatureChannel === 'Suspected fault' ||
          h.humidityChannel === 'Suspected fault' ||
          h.pressureChannel === 'Suspected fault',
      ).length
    : null;

  const filtered = healthList.filter((item) => {
    const matchesSearch =
      searchTerm === '' ||
      item.stationId.toLowerCase().includes(searchTerm.toLowerCase()) ||
      item.stationName.toLowerCase().includes(searchTerm.toLowerCase()) ||
      item.district.toLowerCase().includes(searchTerm.toLowerCase());

    const hasFault =
      item.temperatureChannel === 'Suspected fault' ||
      item.humidityChannel === 'Suspected fault' ||
      item.pressureChannel === 'Suspected fault';
    const hasDegraded =
      item.temperatureChannel === 'Degraded' ||
      item.humidityChannel === 'Degraded' ||
      item.pressureChannel === 'Degraded';

    if (channelFilter === 'Faulty') return matchesSearch && hasFault;
    if (channelFilter === 'Degraded') return matchesSearch && hasDegraded;
    return matchesSearch;
  });

  return (
    <div className="space-y-6">
      {/* Network Summary Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <MetricCard
          label="Fleet Health Index"
          value={avgHealth !== null ? `${avgHealth}%` : 'N/A'}
          subtitle={avgHealth !== null ? 'Mean sensor integrity score' : 'Awaiting observation telemetry'}
          icon={<Activity className="w-4 h-4 text-blue-600" />}
          indicatorColor="blue"
        />
        <MetricCard
          label="Healthy Stations"
          value={healthyCount !== null ? healthyCount : 'N/A'}
          subtitle={healthyCount !== null ? 'All 3 channels operating nominal' : 'Awaiting observation telemetry'}
          icon={<CheckCircle2 className={`w-4 h-4 ${healthyCount !== null ? 'text-emerald-600' : 'text-slate-400'}`} />}
          indicatorColor={healthyCount !== null ? 'emerald' : 'slate'}
        />
        <MetricCard
          label="Degraded Stations"
          value={degradedCount !== null ? degradedCount : 'N/A'}
          subtitle={degradedCount !== null ? 'Early calibration drift / noise' : 'Awaiting observation telemetry'}
          icon={<AlertTriangle className={`w-4 h-4 ${degradedCount !== null ? 'text-amber-600' : 'text-slate-400'}`} />}
          indicatorColor={degradedCount !== null ? 'amber' : 'slate'}
        />
        <MetricCard
          label="Faulty Sensors"
          value={criticalCount !== null ? criticalCount : 'N/A'}
          subtitle={criticalCount !== null ? 'Hardware failure or packet loss' : 'Awaiting observation telemetry'}
          icon={<XCircle className={`w-4 h-4 ${criticalCount !== null ? 'text-rose-600' : 'text-slate-400'}`} />}
          indicatorColor={criticalCount !== null ? 'rose' : 'slate'}
        />
      </div>

      {/* Conceptual Principle Callout */}
      <div className="apple-glass-card rounded-2xl p-4 border border-blue-200/50 flex items-start gap-3">
        <ShieldCheck className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
        <div className="text-xs text-slate-700 leading-relaxed">
          <span className="font-semibold text-slate-900">SkyGuardAI Core Architecture Principle: </span>
          <span>
            A genuine weather event (such as a synoptic heatwave or cold front) affects ambient telemetry across regions, but does <strong>NOT</strong> degrade hardware sensor health. Sensor health scores reflect true physical transducer reliability, zero-variance entropy, packet receipt regularity, and long-term neighbor baseline drift.
          </span>
        </div>
      </div>

      {/* Sensor Health Table */}
      <div className="apple-glass-card rounded-2xl shadow-[0_8px_30px_rgba(15,23,42,0.04)] overflow-hidden">
        <div className="p-4 bg-white/70 border-b border-slate-200/50 flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2">
            <span className="font-medium text-slate-600">Filter Channels:</span>
            <div className="inline-flex rounded-full bg-slate-100/80 p-0.5 border border-slate-200/50">
              {(['All', 'Degraded', 'Faulty'] as const).map((filter) => (
                <button
                  key={filter}
                  type="button"
                  onClick={() => setChannelFilter(filter)}
                  className={`px-3 py-1 rounded-full font-medium cursor-pointer transition-all ${
                    channelFilter === filter
                      ? 'bg-blue-600 text-white shadow-2xs font-semibold'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  {filter}
                </button>
              ))}
            </div>
          </div>

          <div className="relative w-full md:w-64">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="text"
              placeholder="Search station or district..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 bg-slate-100/70 border border-slate-200/60 rounded-full text-xs text-slate-800 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-slate-200/50 text-slate-400 uppercase font-medium tracking-wider text-[10px]">
                <th className="py-3 px-4">Station ID</th>
                <th className="py-3 px-3">District</th>
                <th className="py-3 px-3">Temp Channel</th>
                <th className="py-3 px-3">Humidity Channel</th>
                <th className="py-3 px-3">Pressure Channel</th>
                <th className="py-3 px-3 text-center">Health Index</th>
                <th className="py-3 px-3">Maintenance Priority</th>
                <th className="py-3 px-4 text-right">Audit</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.map((item) => {
                const isUrgent = item.overallHealth !== null && item.overallHealth < 70;

                return (
                  <tr
                    key={item.stationId}
                    onClick={() => onSelectStation(item.stationId)}
                    className="hover:bg-blue-50/40 cursor-pointer transition-colors"
                  >
                    <td className="py-3.5 px-4 font-mono font-semibold text-slate-900">
                      <div>{item.stationName}</div>
                      <span className="text-[10px] text-slate-400">{item.stationId}</span>
                    </td>
                    <td className="py-3.5 px-3 text-slate-600">{item.district}</td>
                    <td className="py-3.5 px-3">
                      <ChannelBadge status={item.temperatureChannel} />
                    </td>
                    <td className="py-3.5 px-3">
                      <ChannelBadge status={item.humidityChannel} />
                    </td>
                    <td className="py-3.5 px-3">
                      <ChannelBadge status={item.pressureChannel} />
                    </td>
                    <td className="py-3.5 px-3 text-center">
                      {item.overallHealth !== null ? (
                        <div className="flex items-center justify-center gap-2">
                          <div className="w-16 bg-slate-100 h-2 rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full ${
                                item.overallHealth >= 90
                                  ? 'bg-emerald-500'
                                  : item.overallHealth >= 70
                                  ? 'bg-amber-500'
                                  : 'bg-rose-500'
                              }`}
                              style={{ width: `${item.overallHealth}%` }}
                            />
                          </div>
                          <span className="font-mono font-semibold text-slate-800 text-xs">
                            {item.overallHealth}%
                          </span>
                        </div>
                      ) : (
                        <span className="font-mono text-slate-400 text-xs">—</span>
                      )}
                    </td>
                    <td className="py-3.5 px-3">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium border ${
                          item.overallHealth === null
                            ? 'bg-slate-100 text-slate-600 border-slate-200'
                            : isUrgent
                            ? 'bg-rose-500/10 text-rose-800 border-rose-400/25 font-semibold'
                            : item.overallHealth < 85
                            ? 'bg-amber-500/10 text-amber-800 border-amber-400/25'
                            : 'bg-emerald-500/10 text-emerald-800 border-emerald-400/20'
                        }`}
                      >
                        {item.overallHealth === null
                          ? 'Awaiting telemetry'
                          : isUrgent
                          ? 'Immediate Field Dispatch'
                          : item.overallHealth < 85
                          ? 'Routine Inspection'
                          : 'Operational'}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectStation(item.stationId);
                        }}
                        className="text-xs font-semibold text-blue-600 hover:text-blue-800 inline-flex items-center gap-0.5 cursor-pointer"
                      >
                        <span>Audit</span>
                        <ArrowRight className="w-3 h-3" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
