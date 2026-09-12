import React, { useState, useEffect } from 'react';
import { Station, StationSensorHealth, AnomalyRecord, TelemetryPoint } from '../../types';
import { stationService } from '../../lib/api/stationService';
import { StatusBadge, CauseBadge, SeverityBadge, ChannelBadge } from '../common/Badges';
import { TelemetryChart } from '../charts/TelemetryChart';
import {
  ArrowLeft,
  Thermometer,
  Droplets,
  Gauge,
  Activity,
  MapPin,
  Clock,
  Compass,
  Radio,
  ArrowRight,
} from 'lucide-react';

interface StationDetailViewProps {
  stationId: string;
  onBack: () => void;
  onSelectStation: (id: string) => void;
  onSelectAnomaly: (anomaly: AnomalyRecord) => void;
}

export const StationDetailView: React.FC<StationDetailViewProps> = ({
  stationId,
  onBack,
  onSelectStation,
  onSelectAnomaly,
}) => {
  const [station, setStation] = useState<Station | null>(null);
  const [health, setHealth] = useState<StationSensorHealth | null>(null);
  const [allStations, setAllStations] = useState<Station[]>([]);
  const [anomalies, setAnomalies] = useState<AnomalyRecord[]>([]);
  const [timeSeries, setTimeSeries] = useState<TelemetryPoint[]>([]);
  const [timeRange, setTimeRange] = useState<'1h' | '6h' | '24h' | '7d'>('24h');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        const s = await stationService.getStationById(stationId).catch(() => undefined);
        const h = await stationService.getStationSensorHealth(stationId).catch(() => undefined);
        const all = await stationService.getStations().catch(() => []);
        const anos = await stationService.getAnomalies({ search: stationId }).catch(() => []);
        const ts = await stationService.getTimeSeries(
          stationId,
          timeRange === '1h' ? 1 : timeRange === '6h' ? 6 : timeRange === '7d' ? 168 : 24,
        ).catch(() => []);

        if (!s) {
          throw new Error(`Station ${stationId} was not returned by the SkyGuardAI backend.`);
        }
        setStation(s);

        if (h) setHealth(h);
        setAllStations(all || []);
        setAnomalies(anos || []);
        setTimeSeries(ts || []);
      } catch (err) {
        console.error('Error loading station detail:', err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [stationId, timeRange]);

  if (loading || !station) {
    return (
      <div className="p-16 text-center text-slate-400">
        <div className="inline-block animate-spin rounded-full h-8 w-8 border-2 border-blue-600 border-t-transparent mb-3"></div>
        <p className="text-xs">Loading AWS station telemetry & diagnostics...</p>
      </div>
    );
  }

  const neighbourStations = allStations.filter((s) => (station.neighbours || []).includes(s.id));

  return (
    <div className="space-y-6">
      {/* Back button and Station Inspector Header */}
      <div>
        <button
          type="button"
          onClick={onBack}
          className="mb-3 inline-flex items-center gap-1.5 text-xs font-semibold text-blue-600 hover:text-blue-800 cursor-pointer transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to All Stations</span>
        </button>

        <div className="apple-glass-card rounded-2xl p-6 shadow-[0_8px_30px_rgba(15,23,42,0.04)]">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-3 flex-wrap">
                <span className="font-mono text-sm font-semibold text-slate-700 bg-slate-100 px-2.5 py-0.5 rounded-full border border-slate-200">
                  {station.id}
                </span>
                <h1 className="text-2xl font-semibold text-slate-900 tracking-tight">{station.name}</h1>
                <StatusBadge status={station.status} />
                <span className="text-xs px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-600 font-medium">
                  {station.region} Region
                </span>
              </div>
              <p className="mt-1.5 text-xs text-slate-500">
                {station.district} District, Andhra Pradesh • Coordinates: {station.latitude != null ? station.latitude.toFixed(4) : '—'}°N,{' '}
                {station.longitude != null ? station.longitude.toFixed(4) : '—'}°E • Elevation: {station.elevationM ?? '—'}m ASL
              </p>
            </div>

            <div className="flex items-center gap-5 bg-white/70 p-3.5 rounded-2xl border border-slate-200/60 shrink-0">
              <div>
                <div className="text-[10px] uppercase font-medium text-slate-400">Health Index</div>
                <div
                  className={`text-2xl font-light tracking-tight mt-0.5 ${
                    station.healthScore === null
                      ? 'text-slate-400'
                      : station.healthScore >= 90
                      ? 'text-emerald-600'
                      : station.healthScore >= 70
                      ? 'text-amber-600'
                      : 'text-rose-600'
                  }`}
                >
                  {station.healthScore !== null ? `${station.healthScore}%` : '—'}
                </div>
              </div>
              <div className="border-l border-slate-200/60 pl-4">
                <div className="text-[10px] uppercase font-medium text-slate-400">Last Observation</div>
                <div className="text-xs font-mono font-medium text-slate-700 flex items-center gap-1 mt-1">
                  <Clock className="w-3 h-3 text-slate-400" />
                  <span>{station.hasTelemetry ? station.lastObservationTime : 'Telemetry unavailable'}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 1. Current Telemetry Cards */}
      <div>
        <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3 flex items-center gap-1.5 px-1">
          <Radio className="w-3.5 h-3.5 text-blue-600" />
          <span>Current Instantaneous Telemetry</span>
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="apple-glass-card rounded-2xl p-5 shadow-[0_8px_30px_rgba(15,23,42,0.04)]">
            <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
              <span>Ambient Air Temperature</span>
              <Thermometer className="w-4 h-4 text-rose-500" />
            </div>
            <div className="mt-3 flex items-baseline gap-1.5">
              <span className="text-3xl font-light tracking-tight text-slate-900">
                {station.telemetry.temperatureC !== null ? station.telemetry.temperatureC : '—'}
              </span>
              {station.telemetry.temperatureC !== null && (
                <span className="text-sm text-slate-400 font-normal">°C</span>
              )}
            </div>
            <div className="mt-3 text-[11px] text-slate-400 flex items-center justify-between border-t border-slate-100 pt-2.5">
              <span>PT100 RTD Sensor</span>
              <span>15m Sampling</span>
            </div>
          </div>

          <div className="apple-glass-card rounded-2xl p-5 shadow-[0_8px_30px_rgba(15,23,42,0.04)]">
            <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
              <span>Relative Humidity</span>
              <Droplets className="w-4 h-4 text-sky-500" />
            </div>
            <div className="mt-3 flex items-baseline gap-1.5">
              <span className="text-3xl font-light tracking-tight text-slate-900">
                {station.telemetry.humidityPct !== null ? station.telemetry.humidityPct : '—'}
              </span>
              {station.telemetry.humidityPct !== null && (
                <span className="text-sm text-slate-400 font-normal">%</span>
              )}
            </div>
            <div className="mt-3 text-[11px] text-slate-400 flex items-center justify-between border-t border-slate-100 pt-2.5">
              <span>Capacitive Polymer Probe</span>
              <span>15m Sampling</span>
            </div>
          </div>

          <div className="apple-glass-card rounded-2xl p-5 shadow-[0_8px_30px_rgba(15,23,42,0.04)]">
            <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
              <span>Barometric Station Pressure</span>
              <Gauge className="w-4 h-4 text-purple-500" />
            </div>
            <div className="mt-3 flex items-baseline gap-1.5">
              <span className="text-3xl font-light tracking-tight text-slate-900">
                {station.telemetry.pressureHpa !== null ? station.telemetry.pressureHpa : '—'}
              </span>
              {station.telemetry.pressureHpa !== null && (
                <span className="text-sm text-slate-400 font-normal">hPa</span>
              )}
            </div>
            <div className="mt-3 text-[11px] text-slate-400 flex items-center justify-between border-t border-slate-100 pt-2.5">
              <span>Piezoresistive Transducer</span>
              <span>15m Sampling</span>
            </div>
          </div>
        </div>
      </div>

      {/* 2. Sensor Health Breakdown */}
      {health && (
        <div className="apple-glass-card rounded-2xl p-6 shadow-[0_8px_30px_rgba(15,23,42,0.04)]">
          <div className="flex items-center justify-between pb-3 border-b border-slate-200/50 mb-4">
            <div>
              <h2 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                <Activity className="w-4 h-4 text-blue-600" />
                <span>Station Hardware & Channel Diagnostics</span>
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Evaluated from zero-variance entropy, drift coefficients, and neighbour divergence
              </p>
            </div>
            <div className="text-xs text-slate-400 font-mono">
              Last audit: {health.lastEvaluationTime}
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="p-4 rounded-xl border border-slate-200/60 bg-white/70">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-slate-800">Temperature Channel</span>
                <ChannelBadge status={health.temperatureChannel} />
              </div>
              <div className="flex items-baseline justify-between text-xs mt-1">
                <span className="text-slate-500">Channel Integrity:</span>
                <span className="font-mono font-semibold text-slate-900">
                  {health.temperatureScore !== null ? `${health.temperatureScore}%` : '—'}
                </span>
              </div>
            </div>

            <div className="p-4 rounded-xl border border-slate-200/60 bg-white/70">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-slate-800">Humidity Channel</span>
                <ChannelBadge status={health.humidityChannel} />
              </div>
              <div className="flex items-baseline justify-between text-xs mt-1">
                <span className="text-slate-500">Channel Integrity:</span>
                <span className="font-mono font-semibold text-slate-900">
                  {health.humidityScore !== null ? `${health.humidityScore}%` : '—'}
                </span>
              </div>
            </div>

            <div className="p-4 rounded-xl border border-slate-200/60 bg-white/70">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-slate-800">Pressure Channel</span>
                <ChannelBadge status={health.pressureChannel} />
              </div>
              <div className="flex items-baseline justify-between text-xs mt-1">
                <span className="text-slate-500">Channel Integrity:</span>
                <span className="font-mono font-semibold text-slate-900">
                  {health.pressureScore !== null ? `${health.pressureScore}%` : '—'}
                </span>
              </div>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-200/40 grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs text-slate-500">
            <div>
              <span className="font-medium text-slate-700">Missing Observation Rate: </span>
              <span className="font-mono text-slate-900">{health.missingDataPct ?? 0}%</span>
            </div>
            <div>
              <span className="font-medium text-slate-700">Drift Status: </span>
              <span className="font-mono text-slate-900">{health.driftDetected ? 'Detected' : 'Nominal'}</span>
            </div>
            <div>
              <span className="font-medium text-slate-700">Neighbour Agreement: </span>
              <span className="font-mono text-slate-900">{health.neighbourAgreementPct ?? 0}%</span>
            </div>
          </div>
        </div>
      )}

      {/* 3. Historical Telemetry Chart */}
      <TelemetryChart
        data={timeSeries}
        stationName={station.name}
        stationId={station.id}
        timeRange={timeRange}
        onTimeRangeChange={(r) => setTimeRange(r)}
        height={280}
      />

      {/* 4. Spatial Neighbour Stations Comparison */}
      <div className="apple-glass-card rounded-2xl p-6 shadow-[0_8px_30px_rgba(15,23,42,0.04)]">
        <div className="flex items-center justify-between pb-3 border-b border-slate-200/50 mb-4">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">
              Connected Spatial Neighbours ({neighbourStations.length} Adjacent AWS)
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Continuously monitored for spatial disagreement and cross-station coherence
            </p>
          </div>
          <span className="text-[11px] font-mono text-slate-400">
            k-Nearest Graph (AP Grid)
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-slate-200/50 text-slate-400 uppercase font-medium tracking-wider text-[10px]">
                <th className="py-2.5 px-3">Neighbour AWS</th>
                <th className="py-2.5 px-3">District</th>
                <th className="py-2.5 px-3">Status</th>
                <th className="py-2.5 px-3 text-right">Temp</th>
                <th className="py-2.5 px-3 text-right">Humidity</th>
                <th className="py-2.5 px-3 text-right">Pressure</th>
                <th className="py-2.5 px-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {neighbourStations.map((nbr) => (
                <tr key={nbr.id} className="hover:bg-blue-50/40 transition-colors">
                  <td className="py-3 px-3">
                    <span className="font-semibold text-slate-900">{nbr.name}</span>
                    <span className="font-mono text-[11px] text-slate-400 ml-1.5">({nbr.id})</span>
                  </td>
                  <td className="py-3 px-3 text-slate-600">{nbr.district}</td>
                  <td className="py-3 px-3">
                    <StatusBadge status={nbr.status} size="sm" />
                  </td>
                  <td className="py-3 px-3 text-right font-mono font-medium text-slate-900">
                    {nbr.telemetry.temperatureC !== null ? `${nbr.telemetry.temperatureC}°C` : '—'}
                  </td>
                  <td className="py-3 px-3 text-right font-mono text-slate-700">
                    {nbr.telemetry.humidityPct !== null ? `${nbr.telemetry.humidityPct}%` : '—'}
                  </td>
                  <td className="py-3 px-3 text-right font-mono text-slate-700">
                    {nbr.telemetry.pressureHpa !== null ? `${nbr.telemetry.pressureHpa} hPa` : '—'}
                  </td>
                  <td className="py-3 px-3 text-right">
                    <button
                      type="button"
                      onClick={() => onSelectStation(nbr.id)}
                      className="text-xs font-semibold text-blue-600 hover:text-blue-800 inline-flex items-center gap-0.5 cursor-pointer"
                    >
                      <span>Inspect</span>
                      <ArrowRight className="w-3 h-3" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 5. Anomaly History For Station */}
      <div className="apple-glass-card rounded-2xl p-6 shadow-[0_8px_30px_rgba(15,23,42,0.04)]">
        <div className="flex items-center justify-between pb-3 border-b border-slate-200/50 mb-3">
          <h3 className="text-sm font-semibold text-slate-900">
            Anomaly History for {station.name} ({station.id})
          </h3>
          <span className="text-xs font-mono text-slate-400">
            {anomalies.length} Flagged Events
          </span>
        </div>

        {anomalies.length === 0 ? (
          <div className="py-8 text-center text-slate-400 text-xs">
            No active or historical anomalies recorded for this station.
          </div>
        ) : (
          <div className="space-y-2.5">
            {anomalies.map((ano) => (
              <div
                key={ano.id}
                onClick={() => onSelectAnomaly(ano)}
                className="p-3.5 rounded-xl border border-slate-200/60 bg-white/70 hover:bg-blue-50/50 hover:border-blue-300/80 cursor-pointer transition-colors text-xs"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-slate-900">{ano.faultType}</span>
                    <CauseBadge cause={ano.cause} />
                    <SeverityBadge severity={ano.severity} />
                  </div>
                  <span className="font-mono text-slate-500 text-[11px]">{ano.timestamp} IST</span>
                </div>
                <p className="mt-1.5 text-[11px] text-slate-500 leading-relaxed">
                  {ano.evidence?.explanation || 'No explanation available'}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
