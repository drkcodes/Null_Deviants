import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Station, StationSensorHealth, AnomalyRecord, TelemetryPoint, MaintenanceRiskResult } from '../../types';
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
  BrainCircuit,
  Clock3,
  TrendingUp,
  TrendingDown,
} from 'lucide-react';

interface StationDetailViewProps {
  stationId: string;
  onBack: () => void;
  onSelectStation: (id: string) => void;
  onSelectAnomaly: (anomaly: AnomalyRecord) => void;
}

const HISTORY_REFRESH_MS = 60_000;

function timeRangeToHours(timeRange: '1h' | '6h' | '24h' | '7d'): number {
  if (timeRange === '1h') return 1;
  if (timeRange === '6h') return 6;
  if (timeRange === '7d') return 168;
  return 24;
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
  const [maintenanceRisk, setMaintenanceRisk] = useState<MaintenanceRiskResult | null>(null);
  const [timeRange, setTimeRange] = useState<'1h' | '6h' | '24h' | '7d'>('24h');
  const [loading, setLoading] = useState(true);
  const timeSeriesRefreshInProgress = useRef(false);

  const fetchTimeSeries = useCallback(() => {
    return stationService.getTimeSeries(
      stationId,
      timeRangeToHours(timeRange),
    );
  }, [stationId, timeRange]);

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        const [s, h, all, anos, risk] = await Promise.all([
          stationService.getStationById(stationId).catch(() => undefined),
          stationService.getStationSensorHealth(stationId).catch(() => undefined),
          stationService.getStations().catch(() => []),
          stationService.getAnomalies({ search: stationId }).catch(() => []),
          stationService.getStationMaintenanceRisk(stationId).catch(() => null),
        ]);

        if (!s) {
          throw new Error(`Station ${stationId} was not returned by the SkyGuardAI backend.`);
        }
        setStation(s);

        if (h) setHealth(h);
        setAllStations(all || []);
        setAnomalies(anos || []);
        setMaintenanceRisk(risk);
      } catch (err) {
        console.error('Error loading station detail:', err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [stationId]);

  useEffect(() => {
    let isActive = true;

    async function refreshTimeSeries() {
      if (!isActive) {
        return;
      }

      if (timeSeriesRefreshInProgress.current) {
        return;
      }

      timeSeriesRefreshInProgress.current = true;

      try {
        const ts = await fetchTimeSeries();
        if (isActive) {
          setTimeSeries(ts || []);
        }
      } catch (err) {
        if (isActive) {
          console.warn('Station detail history refresh failed:', err);
        }
      } finally {
        timeSeriesRefreshInProgress.current = false;
      }
    }

    refreshTimeSeries();

    const intervalId = window.setInterval(
      refreshTimeSeries,
      HISTORY_REFRESH_MS,
    );

    return () => {
      isActive = false;
      window.clearInterval(intervalId);
    };
  }, [fetchTimeSeries]);

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
                 {health.explanation[0] || 'Evaluated from current telemetry and station history.'}
              </p>
            </div>
            <div className="text-xs text-slate-400 font-mono">
              {health.dataSufficiency.status === 'insufficient'
                ? 'Insufficient telemetry history'
                : `Last audit: ${health.lastEvaluationTime}`}
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
              <span className="font-mono text-slate-900">
                {health.missingDataPct !== null ? `${health.missingDataPct.toFixed(1)}%` : '—'}
              </span>
            </div>
            <div>
              <span className="font-medium text-slate-700">Drift Status: </span>
              <span className="font-mono text-slate-900">
                {health.drift.score !== null ? `${Math.round(health.drift.score * 100)}%` : '—'}
              </span>
            </div>
            <div>
              <span className="font-medium text-slate-700">Neighbour Agreement: </span>
              <span className="font-mono text-slate-900">
                {health.neighbourAgreementPct !== null ? `${health.neighbourAgreementPct.toFixed(1)}%` : '—'}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* 3. Predictive Maintenance Risk */}
      {maintenanceRisk && (
        <div className="apple-glass-card rounded-2xl p-6 shadow-[0_8px_30px_rgba(15,23,42,0.04)]">
          <div className="flex items-start justify-between gap-4 pb-3 border-b border-slate-200/50">
            <div>
              <h2 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                <BrainCircuit className="w-4 h-4 text-blue-600" /> Predictive Maintenance Risk
              </h2>
              <p className="text-xs text-slate-500 mt-1">Deterministic prioritization from the Phase 8 maintenance-risk engine.</p>
            </div>
            <span className="text-[10px] font-mono text-slate-400">{maintenanceRisk.engine_version}</span>
          </div>
          {maintenanceRisk.maintenance_risk === null ? (
            <div className="py-5 text-xs text-slate-500">Insufficient telemetry history for maintenance prioritization.</div>
          ) : (
            <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="rounded-xl border border-slate-200/60 bg-white/70 p-4">
                <div className="text-[10px] uppercase tracking-wider text-slate-400">Risk</div>
                <div className="mt-1 text-2xl font-bold font-mono text-slate-900">{maintenanceRisk.maintenance_risk}/100</div>
                <div className="text-[11px] text-slate-500 mt-1">{maintenanceRisk.priority}</div>
              </div>
              <div className="rounded-xl border border-slate-200/60 bg-white/70 p-4">
                <div className="text-[10px] uppercase tracking-wider text-slate-400">Confidence</div>
                <div className="mt-1 text-lg font-semibold capitalize text-slate-900">{maintenanceRisk.confidence}</div>
                <div className="text-[11px] text-slate-500 mt-1">{maintenanceRisk.data_sufficiency.samples_used} samples</div>
              </div>
              <div className="rounded-xl border border-slate-200/60 bg-white/70 p-4">
                <div className="text-[10px] uppercase tracking-wider text-slate-400">Trajectory</div>
                <div className="mt-1 flex items-center gap-2 text-lg font-semibold capitalize text-slate-900">
                  {maintenanceRisk.trajectory?.direction === 'worsening' ? <TrendingUp className="w-4 h-4 text-rose-600" /> : <TrendingDown className="w-4 h-4 text-emerald-600" />}
                  {maintenanceRisk.trajectory?.direction || 'unknown'}
                </div>
                <div className="text-[11px] text-slate-500 mt-1">Δ {maintenanceRisk.trajectory?.delta_risk ?? '—'}</div>
              </div>
              <div className="rounded-xl border border-slate-200/60 bg-white/70 p-4">
                <div className="text-[10px] uppercase tracking-wider text-slate-400">Recommended Action</div>
                <div className="mt-1 text-sm font-semibold text-slate-900">{maintenanceRisk.recommended_action}</div>
                <div className="text-[11px] text-slate-500 mt-1 flex items-center gap-1"><Clock3 className="w-3 h-3" /> {maintenanceRisk.attention_horizon !== null ? `${maintenanceRisk.attention_horizon.toFixed(1)}h horizon` : 'No attention horizon'}</div>
              </div>
            </div>
          )}
          {maintenanceRisk.drivers.length > 0 && (
            <div className="mt-4 rounded-xl border border-slate-200/60 bg-slate-50/60 p-4">
              <div className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 mb-2">Why this station is ranked here</div>
              <ul className="space-y-1.5 text-[11px] text-slate-600 list-disc pl-4">
                {maintenanceRisk.drivers.slice(0, 5).map((driver) => <li key={driver}>{driver}</li>)}
              </ul>
            </div>
          )}
          {maintenanceRisk.attention_horizon !== null && (
            <p className="mt-3 text-[10px] text-slate-400">Trend estimate only; not a failure forecast or remaining useful life.</p>
          )}
        </div>
      )}

      {/* 4. Historical Telemetry Chart */}
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
