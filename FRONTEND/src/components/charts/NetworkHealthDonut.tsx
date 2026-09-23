import React from 'react';
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from 'recharts';
import { NetworkSummary } from '../../types';

interface NetworkHealthDonutProps {
  summary: NetworkSummary;
}

export const NetworkHealthDonut: React.FC<NetworkHealthDonutProps> = ({ summary }) => {
  const reportedStationCount =
    (summary.healthyCount ?? 0) +
    (summary.watchCount ?? 0) +
    (summary.criticalCount ?? 0) +
    (summary.offlineCount ?? 0);

  const hasTelemetry =
    summary.healthyCount !== null &&
    reportedStationCount > 0;

  const data = hasTelemetry
    ? [
        { name: 'Healthy', value: summary.healthyCount ?? 0, color: '#10b981' },
        { name: 'Watch', value: summary.watchCount ?? 0, color: '#f59e0b' },
        { name: 'Critical', value: summary.criticalCount ?? 0, color: '#f43f5e' },
        { name: 'Offline', value: summary.offlineCount, color: '#94a3b8' },
      ]
    : [
        { name: 'Awaiting Telemetry', value: summary.totalStations, color: '#cbd5e1' },
      ];

  const centerValue = hasTelemetry
    ? `${Math.round(((summary.healthyCount ?? 0) / (summary.totalStations || 1)) * 100)}%`
    : '—';
  const centerLabel = hasTelemetry ? 'Healthy' : 'Awaiting Data';

  return (
    <div className="apple-glass-card rounded-2xl p-5 shadow-[0_8px_30px_rgba(15,23,42,0.04)] flex flex-col justify-between">
      <div className="flex items-center justify-between pb-2.5 border-b border-slate-200/50">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">Network Fleet Status</h3>
          <p className="text-[11px] text-slate-400 mt-0.5">Andhra Pradesh AWS Distribution</p>
        </div>
        <span className="text-[11px] font-mono font-medium px-2 py-0.5 rounded-full bg-slate-100 text-slate-600">
          {summary.totalStations} AWS Configured
        </span>
      </div>

      <div className="relative h-44 my-2">
        {hasTelemetry ? (
          <>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={data}
                  innerRadius={50}
                  outerRadius={68}
                  paddingAngle={4}
                  dataKey="value"
                  stroke="transparent"
                  isAnimationActive={false}
                >
                  {data.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  content={({ active, payload }) => {
                    if (!active || !payload || !payload.length) return null;
                    const item = payload[0];
                    return (
                      <div className="apple-glass-floating p-2.5 rounded-xl border border-white/80 shadow-md text-xs">
                        <span className="font-semibold text-slate-900">{item.name}: </span>
                        <span className="font-medium text-slate-700">
                          {item.value} station(s) (
                          {Math.round(((item.value as number) / (summary.totalStations || 1)) * 100)}%)
                        </span>
                      </div>
                    );
                  }}
                />
              </PieChart>
            </ResponsiveContainer>

            {/* Center label */}
            <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
              <span className="text-3xl font-light text-slate-900 leading-none tracking-tight">
                {centerValue}
              </span>
              <span className="text-[10px] uppercase tracking-widest text-slate-400 mt-1 font-medium">
                {centerLabel}
              </span>
            </div>
          </>
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-center">
            <div className="w-8 h-8 border-2 border-slate-200 border-t-blue-500 rounded-full animate-spin mb-3" />
            <span className="text-sm font-medium text-slate-700">
              Calculating fleet status...
            </span>
            <span className="text-[11px] text-slate-400 mt-1">
              Analyzing station telemetry. Please wait a moment.
            </span>
          </div>
        )}
      </div>

      {/* Breakdown Legend */}
      <div className="grid grid-cols-2 gap-2 text-xs pt-3 border-t border-slate-200/40">
        {hasTelemetry ? (
          data.map((item) => (
            <div key={item.name} className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <span
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: item.color }}
                />
                <span className="text-slate-600 text-[11px]">{item.name}</span>
              </div>
              <span className="font-mono text-xs font-semibold text-slate-800">{item.value}</span>
            </div>
          ))
        ) : (
          <>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-slate-300" />
                <span className="text-slate-600 text-[11px]">Configured AWS</span>
              </div>
              <span className="font-mono text-xs font-semibold text-slate-800">{summary.totalStations}</span>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-amber-400" />
                <span className="text-slate-600 text-[11px]">Live Telemetry</span>
              </div>
              <span className="font-mono text-xs font-medium text-amber-700">Awaiting stream</span>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
