import React, { useState } from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceDot,
} from 'recharts';
import { TelemetryPoint } from '../../types';
import { Thermometer, Droplets, Gauge, AlertCircle, Radio } from 'lucide-react';

interface TelemetryChartProps {
  data: TelemetryPoint[];
  stationName: string;
  stationId: string;
  timeRange?: '1h' | '6h' | '24h' | '7d';
  onTimeRangeChange?: (range: '1h' | '6h' | '24h' | '7d') => void;
  height?: number;
}

export const TelemetryChart: React.FC<TelemetryChartProps> = ({
  data,
  stationName,
  stationId,
  timeRange = '24h',
  onTimeRangeChange,
  height = 270,
}) => {
  const [activeParameter, setActiveParameter] = useState<'temp' | 'hum' | 'press'>('temp');
  const [selectedRange, setSelectedRange] = useState<'1h' | '6h' | '24h' | '7d'>(timeRange);

  const handleRange = (r: '1h' | '6h' | '24h' | '7d') => {
    setSelectedRange(r);
    if (onTimeRangeChange) onTimeRangeChange(r);
  };

  const paramConfig = {
    temp: {
      dataKey: 'temperatureC',
      label: 'Temperature',
      unit: '°C',
      color: '#0071e3', // Apple blue
      gradientStart: 'rgba(0, 113, 227, 0.16)',
      gradientEnd: 'rgba(0, 113, 227, 0.0)',
      domain: ['dataMin - 2', 'dataMax + 2'] as [string, string],
      icon: Thermometer,
    },
    hum: {
      dataKey: 'humidityPct',
      label: 'Relative Humidity',
      unit: '%',
      color: '#0284c7',
      gradientStart: 'rgba(2, 132, 199, 0.16)',
      gradientEnd: 'rgba(2, 132, 199, 0.0)',
      domain: [0, 100] as [number, number],
      icon: Droplets,
    },
    press: {
      dataKey: 'pressureHpa',
      label: 'Barometric Pressure',
      unit: 'hPa',
      color: '#6366f1',
      gradientStart: 'rgba(99, 102, 241, 0.16)',
      gradientEnd: 'rgba(99, 102, 241, 0.0)',
      domain: ['dataMin - 4', 'dataMax + 4'] as [string, string],
      icon: Gauge,
    },
  };

  const currentConfig = paramConfig[activeParameter];
  const Icon = currentConfig.icon;
  const anomalyPoints = data.filter((d) => d.isAnomaly);

  return (
    <div className="apple-glass-card rounded-2xl p-5 shadow-[0_8px_30px_rgba(15,23,42,0.04)]">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-200/50">
        <div>
          <div className="flex items-center gap-2">
            <Icon className="w-4 h-4 text-blue-600" />
            <h3 className="text-sm font-semibold text-slate-900">
              {currentConfig.label} Trend — {stationName} ({stationId})
            </h3>
          </div>
          <p className="text-[11px] text-slate-500 mt-0.5">
            15-minute telemetry resolution · High-frequency Stage 1 anomaly detection
          </p>
        </div>

        {/* Apple Segmented Controls */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Parameter switch */}
          <div className="inline-flex rounded-full bg-slate-100/80 p-0.5 text-xs border border-slate-200/50">
            <button
              type="button"
              onClick={() => setActiveParameter('temp')}
              className={`px-2.5 py-1 rounded-full font-medium cursor-pointer transition-all ${
                activeParameter === 'temp'
                  ? 'bg-white text-slate-900 shadow-2xs font-semibold'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Temp (°C)
            </button>
            <button
              type="button"
              onClick={() => setActiveParameter('hum')}
              className={`px-2.5 py-1 rounded-full font-medium cursor-pointer transition-all ${
                activeParameter === 'hum'
                  ? 'bg-white text-slate-900 shadow-2xs font-semibold'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Humidity (%)
            </button>
            <button
              type="button"
              onClick={() => setActiveParameter('press')}
              className={`px-2.5 py-1 rounded-full font-medium cursor-pointer transition-all ${
                activeParameter === 'press'
                  ? 'bg-white text-slate-900 shadow-2xs font-semibold'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Pressure (hPa)
            </button>
          </div>

          {/* Time range selector */}
          <div className="inline-flex rounded-full bg-slate-100/80 p-0.5 text-xs border border-slate-200/50">
            {(['1h', '6h', '24h', '7d'] as const).map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => handleRange(r)}
                className={`px-2.5 py-1 rounded-full font-medium cursor-pointer transition-all ${
                  selectedRange === r
                    ? 'bg-blue-600 text-white shadow-2xs font-semibold'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {r}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Chart Canvas */}
      <div className="mt-4" style={{ height }}>
        {data.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-6 bg-slate-50/50 rounded-xl border border-dashed border-slate-200 text-slate-400">
            <Radio className="w-6 h-6 text-slate-300 mb-2 animate-pulse" />
            <p className="text-xs font-semibold text-slate-700">No Historical Telemetry Ingested</p>
            <p className="text-[11px] text-slate-400 mt-1 max-w-sm">
              Awaiting time-series observation packets from the FastAPI backend (<span className="font-mono text-[10px] text-slate-600">GET /station/{stationId}/history</span>).
            </p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 10, right: 12, left: -14, bottom: 0 }}>
            <defs>
              <linearGradient id="appleChartGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={currentConfig.color} stopOpacity={0.18} />
                <stop offset="95%" stopColor={currentConfig.color} stopOpacity={0.0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="2 4" stroke="#f1f5f9" vertical={false} />
            <XAxis
              dataKey="timestamp"
              stroke="#94a3b8"
              fontSize={10}
              tickLine={false}
              axisLine={{ stroke: '#f1f5f9' }}
            />
            <YAxis
              stroke="#94a3b8"
              fontSize={10}
              tickLine={false}
              axisLine={{ stroke: '#f1f5f9' }}
              domain={currentConfig.domain}
              unit={` ${currentConfig.unit}`}
            />
            <Tooltip
              content={({ active, payload, label }) => {
                if (!active || !payload || !payload.length) return null;
                const point = payload[0].payload as TelemetryPoint;

                return (
                  <div className="apple-glass-floating p-3 rounded-xl border border-white/90 shadow-[0_12px_28px_rgba(15,23,42,0.1)] text-xs">
                    <div className="font-semibold text-slate-900">{label} IST</div>
                    <div className="mt-1 flex items-center gap-2">
                      <span className="text-slate-500">{currentConfig.label}:</span>
                      <span className="font-semibold text-slate-900 font-mono">
                        {payload[0].value} {currentConfig.unit}
                      </span>
                    </div>
                    {point.isAnomaly && (
                      <div className="mt-2 pt-1.5 border-t border-slate-200/50 flex items-center gap-1.5 text-rose-600 font-medium">
                        <AlertCircle className="w-3.5 h-3.5" />
                        <span>
                          {point.anomalyCause} ({point.anomalyType})
                        </span>
                      </div>
                    )}
                  </div>
                );
              }}
            />
            <Area
              type="monotone"
              dataKey={currentConfig.dataKey}
              stroke={currentConfig.color}
              strokeWidth={2.2}
              fillOpacity={1}
              fill="url(#appleChartGradient)"
              isAnimationActive={false}
            />

            {/* Anomaly Dots */}
            {anomalyPoints.map((pt, idx) => (
              <ReferenceDot
                key={idx}
                x={pt.timestamp}
                y={(pt as any)[currentConfig.dataKey]}
                r={4.5}
                fill="#f43f5e"
                stroke="#ffffff"
                strokeWidth={2}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
        )}
      </div>

      {anomalyPoints.length > 0 && (
        <div className="mt-3 pt-2.5 border-t border-slate-200/40 flex items-center justify-between text-[11px] text-slate-500">
          <span className="flex items-center gap-1.5 text-rose-600 font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-500 ring-2 ring-rose-400/25" />
            {anomalyPoints.length} anomalous observation intervals detected
          </span>
          <span className="text-slate-400">
            Red markers indicate Stage 1 statistical z-score flags
          </span>
        </div>
      )}
    </div>
  );
};
