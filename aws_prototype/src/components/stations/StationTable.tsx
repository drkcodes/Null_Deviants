import React, { useState } from 'react';
import { Station, StationStatus, Region } from '../../types';
import { StatusBadge, CauseBadge } from '../common/Badges';
import { Search, Eye, ArrowRight } from 'lucide-react';

interface StationTableProps {
  stations: Station[];
  onSelectStation: (stationId: string) => void;
  selectedStationId?: string;
}

export const StationTable: React.FC<StationTableProps> = ({
  stations,
  onSelectStation,
  selectedStationId,
}) => {
  const [statusFilter, setStatusFilter] = useState<StationStatus | 'All'>('All');
  const [regionFilter, setRegionFilter] = useState<Region | 'All'>('All');
  const [searchTerm, setSearchTerm] = useState('');

  const filtered = stations.filter((s) => {
    const matchesStatus = statusFilter === 'All' || s.status === statusFilter;
    const matchesRegion = regionFilter === 'All' || s.region === regionFilter;
    const matchesSearch =
      searchTerm === '' ||
      s.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      s.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      s.district.toLowerCase().includes(searchTerm.toLowerCase());

    return matchesStatus && matchesRegion && matchesSearch;
  });

  return (
    <div className="apple-glass-card rounded-2xl shadow-[0_8px_30px_rgba(15,23,42,0.04)] overflow-hidden">
      {/* Controls Bar */}
      <div className="p-4 bg-white/70 border-b border-slate-200/50 flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs">
        <div className="flex flex-wrap items-center gap-2">
          {/* Status Filter */}
          <div className="inline-flex rounded-full bg-slate-100/80 p-0.5 border border-slate-200/50">
            {(['All', 'Healthy', 'Watch', 'Critical', 'Awaiting Data', 'Offline'] as const).map((st) => (
              <button
                key={st}
                type="button"
                onClick={() => setStatusFilter(st)}
                className={`px-3 py-1 rounded-full font-medium cursor-pointer transition-all ${
                  statusFilter === st
                    ? 'bg-blue-600 text-white shadow-2xs font-semibold'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {st}
              </button>
            ))}
          </div>

          {/* Region Filter */}
          <div className="inline-flex rounded-full bg-slate-100/80 p-0.5 border border-slate-200/50">
            {(['All', 'Coastal', 'Rayalaseema'] as const).map((reg) => (
              <button
                key={reg}
                type="button"
                onClick={() => setRegionFilter(reg)}
                className={`px-3 py-1 rounded-full font-medium cursor-pointer transition-all ${
                  regionFilter === reg
                    ? 'bg-slate-900 text-white shadow-2xs font-semibold'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {reg}
              </button>
            ))}
          </div>
        </div>

        {/* Search */}
        <div className="relative w-full md:w-64">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            type="text"
            placeholder="Filter by station or district..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 bg-slate-100/70 border border-slate-200/60 rounded-full text-xs text-slate-800 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
          />
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="border-b border-slate-200/50 text-slate-400 uppercase font-medium tracking-wider text-[10px]">
              <th className="py-3 px-4">Station ID</th>
              <th className="py-3 px-3">Location & District</th>
              <th className="py-3 px-3">Region</th>
              <th className="py-3 px-3">Status</th>
              <th className="py-3 px-3 text-right">Temp (°C)</th>
              <th className="py-3 px-3 text-right">Humidity (%)</th>
              <th className="py-3 px-3 text-right">Pressure (hPa)</th>
              <th className="py-3 px-3 text-center">Health</th>
              <th className="py-3 px-3">Active Diagnosis</th>
              <th className="py-3 px-4 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filtered.map((station) => {
              const isSelected = station.id === selectedStationId;

              return (
                <tr
                  key={station.id}
                  onClick={() => onSelectStation(station.id)}
                  className={`hover:bg-blue-50/40 cursor-pointer transition-colors ${
                    isSelected ? 'bg-blue-50/60 font-medium' : ''
                  }`}
                >
                  <td className="py-3.5 px-4 font-mono font-semibold text-slate-900">
                    {station.id}
                  </td>
                  <td className="py-3.5 px-3">
                    <div className="font-semibold text-slate-900">{station.name}</div>
                    <div className="text-[11px] text-slate-400">{station.district} Dist</div>
                  </td>
                  <td className="py-3.5 px-3">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium border ${
                        station.region === 'Coastal'
                          ? 'bg-sky-500/10 text-sky-800 border-sky-400/20'
                          : 'bg-amber-500/10 text-amber-900 border-amber-400/20'
                      }`}
                    >
                      {station.region}
                    </span>
                  </td>
                  <td className="py-3.5 px-3">
                    <StatusBadge status={station.status} size="sm" />
                  </td>
                  <td className="py-3.5 px-3 text-right font-mono font-semibold text-slate-900">
                    {station.telemetry.temperatureC !== null ? `${station.telemetry.temperatureC}°C` : '—'}
                  </td>
                  <td className="py-3.5 px-3 text-right font-mono text-slate-700">
                    {station.telemetry.humidityPct !== null ? `${station.telemetry.humidityPct}%` : '—'}
                  </td>
                  <td className="py-3.5 px-3 text-right font-mono text-slate-700">
                    {station.telemetry.pressureHpa !== null ? station.telemetry.pressureHpa : '—'}
                  </td>
                  <td className="py-3.5 px-3 text-center">
                    <div className="inline-flex items-center gap-1 font-mono font-semibold text-slate-800 text-xs">
                      <span>{station.healthScore !== null ? `${station.healthScore}%` : '—'}</span>
                    </div>
                  </td>
                  <td className="py-3.5 px-3">
                    {station.latestAnomaly ? (
                      <div className="flex items-center gap-1.5">
                        <CauseBadge cause={station.latestAnomaly.cause} showIcon={false} />
                        <span className="text-slate-700 text-[11px] truncate max-w-[130px]">
                          {station.latestAnomaly.type}
                        </span>
                      </div>
                    ) : !station.hasTelemetry ? (
                      <span className="text-slate-500 text-[11px] font-medium flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
                        Awaiting Telemetry
                      </span>
                    ) : (
                      <span className="text-emerald-700 text-[11px] font-medium flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                        Nominal
                      </span>
                    )}
                  </td>
                  <td className="py-3.5 px-4 text-right">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectStation(station.id);
                      }}
                      className="text-xs font-semibold text-blue-600 hover:text-blue-800 inline-flex items-center gap-0.5 cursor-pointer"
                    >
                      <span>Inspect</span>
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
  );
};
