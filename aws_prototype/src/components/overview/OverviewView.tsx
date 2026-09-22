import React from 'react';
import {
  Station,
  NetworkSummary,
  AnomalyRecord,
  AlertRecord,
  ActivityEvent,
  TelemetryPoint,
} from '../../types';
import { MetricCard } from '../common/MetricCard';
import { AndhraPradeshMap } from '../maps/AndhraPradeshMap';
import { TelemetryChart } from '../charts/TelemetryChart';
import { NetworkHealthDonut } from '../charts/NetworkHealthDonut';
import { StatusBadge, CauseBadge, SeverityBadge } from '../common/Badges';
import { AnomalyDetailModal } from '../anomalies/AnomalyDetailModal';
import {
  Radio,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  FileCheck,
  BrainCircuit,
  CloudSun,
  Wrench,
  Clock,
  ArrowRight,
  ChevronRight,
} from 'lucide-react';

interface OverviewViewProps {
  stations: Station[];
  summary: NetworkSummary;
  alerts: AlertRecord[];
  anomalies: AnomalyRecord[];
  selectedAnomaly: AnomalyRecord | null;
  activityEvents: ActivityEvent[];
  timeSeries: TelemetryPoint[];
  selectedStationId: string;
  onSelectStation: (stationId: string) => void;
  onViewStationDetails: (stationId: string) => void;
  onSelectAnomaly: (anomaly: AnomalyRecord | null) => void;
  onNavigateToSection: (section: any) => void;
}

export const OverviewView: React.FC<OverviewViewProps> = ({
  stations,
  summary,
  alerts,
  anomalies,
  selectedAnomaly,
  activityEvents,
  timeSeries,
  selectedStationId,
  onSelectStation,
  onViewStationDetails,
  onSelectAnomaly,
  onNavigateToSection,
}) => {
  const selectedStation = stations.find((s) => s.id === selectedStationId) || stations[0];

  if (!selectedStation) {
    return <div className="p-8 text-center text-slate-500 text-sm">No station telemetry is available from the SkyGuardAI backend.</div>;
  }

  return (
    <div className="space-y-6">
      {/* 7.1 KPI Deck with Apple Surface Styling */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
        <MetricCard
          label="Total Stations"
          value={summary.totalStations}
          subtitle="20 AP Districts"
          icon={<Radio className="w-4 h-4 text-blue-600" />}
          indicatorColor="blue"
          onClick={() => onNavigateToSection('network')}
        />
        <MetricCard
          label="Healthy"
          value={summary.healthyCount !== null ? summary.healthyCount : 'N/A'}
          subtitle={summary.healthyCount !== null ? 'Nominal status' : 'Awaiting telemetry'}
          icon={<CheckCircle2 className={`w-4 h-4 ${summary.healthyCount !== null ? 'text-emerald-600' : 'text-slate-400'}`} />}
          indicatorColor={summary.healthyCount !== null ? 'emerald' : 'slate'}
          onClick={() => onNavigateToSection('network')}
        />
        <MetricCard
          label="Watch"
          value={summary.watchCount !== null ? summary.watchCount : 'N/A'}
          subtitle={summary.watchCount !== null ? 'Mild divergence' : 'Awaiting telemetry'}
          icon={<AlertTriangle className={`w-4 h-4 ${summary.watchCount !== null ? 'text-amber-600' : 'text-slate-400'}`} />}
          indicatorColor={summary.watchCount !== null ? 'amber' : 'slate'}
          onClick={() => onNavigateToSection('network')}
        />
        <MetricCard
          label="Critical"
          value={summary.criticalCount !== null ? summary.criticalCount : 'N/A'}
          subtitle={summary.criticalCount !== null ? 'Urgent action' : 'Awaiting telemetry'}
          icon={<XCircle className={`w-4 h-4 ${summary.criticalCount !== null ? 'text-rose-600' : 'text-slate-400'}`} />}
          indicatorColor={summary.criticalCount !== null ? 'rose' : 'slate'}
          onClick={() => onNavigateToSection('network')}
        />
        <MetricCard
          label="Data Quality"
          value={summary.dataQualityPct !== null ? `${summary.dataQualityPct}%` : 'N/A'}
          subtitle={summary.dataQualityPct !== null ? 'Packet integrity' : 'Awaiting data'}
          icon={<FileCheck className={`w-4 h-4 ${summary.dataQualityPct !== null ? 'text-emerald-600' : 'text-slate-400'}`} />}
          indicatorColor={summary.dataQualityPct !== null ? 'emerald' : 'slate'}
          onClick={() => onNavigateToSection('monitoring')}
        />
        <MetricCard
          label="Recent Live Anomalies"
          value={summary.activeAnomalies}
          subtitle={summary.activeAnomalies > 0 ? 'Recent ML events' : '0 in backend'}
          icon={<BrainCircuit className={`w-4 h-4 ${summary.activeAnomalies > 0 ? 'text-rose-600' : 'text-blue-600'}`} />}
          indicatorColor={summary.activeAnomalies > 0 ? 'rose' : 'slate'}
          onClick={() => onNavigateToSection('anomalies')}
        />
        <MetricCard
          label="Weather Events"
          value={summary.weatherEventsCount !== null ? summary.weatherEventsCount : 'N/A'}
          subtitle={summary.weatherEventsCount !== null ? 'Regional sync' : 'Awaiting telemetry'}
          icon={<CloudSun className={`w-4 h-4 ${summary.weatherEventsCount !== null ? 'text-sky-600' : 'text-slate-400'}`} />}
          indicatorColor={summary.weatherEventsCount !== null ? 'blue' : 'slate'}
          onClick={() => onNavigateToSection('anomalies')}
        />
        <MetricCard
          label="Sensor Faults"
          value={summary.sensorFaultsCount !== null ? summary.sensorFaultsCount : 'N/A'}
          subtitle={summary.sensorFaultsCount !== null ? 'Isolated drift' : 'Awaiting telemetry'}
          icon={<Wrench className={`w-4 h-4 ${summary.sensorFaultsCount !== null ? 'text-amber-700' : 'text-slate-400'}`} />}
          indicatorColor={summary.sensorFaultsCount !== null ? 'amber' : 'slate'}
          onClick={() => onNavigateToSection('anomalies')}
        />
      </div>

      {/* Hero Andhra Pradesh Map & Live Anomaly Alerts */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Andhra Pradesh Hero Interactive Map (7 cols) */}
        <div className="lg:col-span-7 space-y-2">
          <div className="flex items-center justify-between px-1">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
              <Radio className="w-3.5 h-3.5 text-blue-600" />
              <span>Andhra Pradesh AWS Fleet Matrix</span>
            </h2>
            <span className="text-[11px] text-slate-400">
              Interactive Leaflet · Click station pin to inspect
            </span>
          </div>

          <AndhraPradeshMap
            stations={stations}
            selectedStationId={selectedStationId}
            onSelectStation={onSelectStation}
            onViewStationDetails={onViewStationDetails}
            height="480px"
          />
        </div>

        {/* Live Anomaly Alerts & Health Ring (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          {/* Live Alerts Panel */}
          <div className="apple-glass-card rounded-2xl p-5 shadow-[0_8px_30px_rgba(15,23,42,0.04)]">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200/50">
              <div className="flex items-center gap-2">
                <span className="flex h-2 w-2 relative">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-rose-500"></span>
                </span>
                <h3 className="text-sm font-semibold text-slate-900">Live Anomaly Alerts</h3>
              </div>
              <button
                type="button"
                onClick={() => onNavigateToSection('anomalies')}
                className="text-xs font-medium text-blue-600 hover:text-blue-800 flex items-center gap-0.5 cursor-pointer transition-colors"
              >
                <span>All Anomalies ({anomalies.length})</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="mt-3 space-y-2.5 max-h-72 overflow-y-auto pr-1">
              {alerts.length === 0 ? (
                <div className="p-8 text-center bg-slate-50/50 rounded-xl border border-dashed border-slate-200">
                  <div className="w-8 h-8 rounded-full bg-slate-100 text-slate-500 flex items-center justify-center mx-auto mb-2">
                    <CheckCircle2 className="w-4 h-4 text-slate-500" />
                  </div>
                  <div className="text-xs font-semibold text-slate-800">No Active Anomaly Alerts</div>
                  <div className="text-[11px] text-slate-500 mt-1 max-w-xs mx-auto leading-relaxed">
                    No active anomaly alerts logged in the backend. Station telemetry streams are currently awaiting live observation packets.
                  </div>
                </div>
              ) : (
                alerts.map((alert) => {
                  const alertObservationId = alert.id.replace(/^ALT-/, '');
                  const fullAnomaly = anomalies.find(
                    (a) => a.id === `ANO-${alertObservationId}`,
                  );

                  return (
                    <div
                      key={alert.id}
                      onClick={() => fullAnomaly && onSelectAnomaly(fullAnomaly)}
                      className="p-3.5 rounded-xl border border-slate-200/60 bg-white/70 hover:bg-blue-50/50 hover:border-blue-300/80 cursor-pointer transition-all duration-150 text-xs shadow-2xs"
                    >
                    <div className="flex items-center justify-between gap-2">
                      <div className="font-semibold text-slate-900">
                        {alert.stationId} • {alert.stationName}
                      </div>
                      <SeverityBadge severity={alert.severity} />
                    </div>

                    <div className="mt-1.5 flex items-center gap-2">
                      <CauseBadge cause={alert.cause} />
                      <span className="font-semibold text-slate-800">{alert.anomalyType}</span>
                      <span className="text-slate-400 font-mono text-[11px] ml-auto">
                        {alert.confidence}% conf
                      </span>
                    </div>

                    <p className="mt-1.5 text-slate-500 text-[11px] leading-relaxed">
                      {alert.shortExplanation}
                    </p>

                    <div className="mt-2 pt-1.5 border-t border-slate-100 flex items-center justify-between text-[10px] text-slate-400">
                      <span>{alert.timestamp} IST</span>
                        <button
                          type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                                if (fullAnomaly) {
                                  onSelectAnomaly(fullAnomaly);
                                }
                              }}
                              disabled={!fullAnomaly}
                              className="text-blue-600 font-medium hover:underline flex items-center gap-0.5 cursor-pointer disabled:cursor-default disabled:no-underline"
                      >
                          View evidence →
                    </button>
                    </div>
                  </div>
                );
              })
            )}
          </div>
          </div>

          {/* Network Fleet Status Activity Ring */}
          <NetworkHealthDonut summary={summary} />
        </div>
      </div>

      {/* Historical Telemetry Trend & Chronological Activity Feed */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-8">
          <TelemetryChart
            data={timeSeries}
            stationName={selectedStation.name}
            stationId={selectedStation.id}
            height={270}
          />
        </div>

        {/* Operational Activity Feed */}
        <div className="lg:col-span-4 apple-glass-card rounded-2xl p-5 shadow-[0_8px_30px_rgba(15,23,42,0.04)] flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-slate-200/50">
              <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-slate-400" />
                <span>Operational Activity Feed</span>
              </h3>
              <span className="text-[10px] font-mono text-slate-400 px-2 py-0.5 rounded-full bg-slate-100">
                Live Ingestion
              </span>
            </div>

            <div className="mt-3 space-y-3 max-h-64 overflow-y-auto pr-1 text-xs">
              {activityEvents.map((evt) => (
                <div key={evt.id} className="flex items-start gap-2.5">
                  <span className="font-mono text-[11px] text-slate-400 shrink-0 pt-0.5">
                    {evt.time}
                  </span>
                  <div className="flex-1">
                    <p className="text-slate-700 leading-snug font-normal text-[11px]">
                      {evt.message}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-4 pt-2.5 border-t border-slate-200/40 text-center">
            <span className="text-[10px] text-slate-400">
              Autonomous telemetry ingestion & anomaly diagnostic events
            </span>
          </div>
        </div>
      </div>

      {/* Live Telemetry Snapshot (Breathable Apple Table) */}
      <div className="apple-glass-card rounded-2xl p-5 shadow-[0_8px_30px_rgba(15,23,42,0.04)]">
        <div className="flex items-center justify-between pb-3 border-b border-slate-200/50 mb-3">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">
              Live Telemetry Snapshot (Latest Observations)
            </h3>
            <p className="text-[11px] text-slate-500 mt-0.5">
              {stations.some((s) => s.hasTelemetry)
                ? 'Active telemetry across all 20 Andhra Pradesh Automatic Weather Stations'
                : 'Station metadata registry (20 configured) • Live telemetry observations awaiting stream ingestion'}
            </p>
          </div>
          <button
            type="button"
            onClick={() => onNavigateToSection('network')}
            className="text-xs font-medium text-blue-600 hover:text-blue-800 flex items-center gap-1 cursor-pointer"
          >
            <span>Full Station Grid</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-slate-200/60 text-slate-400 uppercase font-medium text-[10px] tracking-wider">
                <th className="py-2.5 px-3">Station</th>
                <th className="py-2.5 px-3">Region</th>
                <th className="py-2.5 px-3 text-right">Temperature</th>
                <th className="py-2.5 px-3 text-right">Humidity</th>
                <th className="py-2.5 px-3 text-right">Pressure</th>
                <th className="py-2.5 px-3">Status</th>
                <th className="py-2.5 px-3 text-right">Health Score</th>
                <th className="py-2.5 px-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {stations.slice(0, 8).map((st) => (
                <tr
                  key={st.id}
                  onClick={() => onSelectStation(st.id)}
                  className={`hover:bg-blue-50/30 cursor-pointer transition-colors ${
                    st.id === selectedStationId ? 'bg-blue-50/50' : ''
                  }`}
                >
                  <td className="py-3 px-3">
                    <span className="font-semibold text-slate-900">{st.name}</span>
                    <span className="text-[11px] font-mono text-slate-400 ml-1.5">({st.id})</span>
                  </td>
                  <td className="py-3 px-3 text-slate-600">{st.region}</td>
                  <td className="py-3 px-3 text-right font-mono font-medium text-slate-900">
                    {st.telemetry.temperatureC !== null ? `${st.telemetry.temperatureC}°C` : '—'}
                  </td>
                  <td className="py-3 px-3 text-right font-mono text-slate-700">
                    {st.telemetry.humidityPct !== null ? `${st.telemetry.humidityPct}%` : '—'}
                  </td>
                  <td className="py-3 px-3 text-right font-mono text-slate-700">
                    {st.telemetry.pressureHpa !== null ? `${st.telemetry.pressureHpa} hPa` : '—'}
                  </td>
                  <td className="py-3 px-3">
                    <StatusBadge status={st.status} size="sm" />
                  </td>
                  <td className="py-3 px-3 text-right font-mono font-semibold text-slate-800">
                    {st.healthScore !== null ? `${st.healthScore}%` : '—'}
                  </td>
                  <td className="py-3 px-3 text-right">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onViewStationDetails(st.id);
                      }}
                      className="text-xs font-semibold text-blue-600 hover:text-blue-800 cursor-pointer"
                    >
                      Inspect →
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <AnomalyDetailModal
        anomaly={selectedAnomaly}
        onClose={() => onSelectAnomaly(null)}
        onViewStation={onViewStationDetails}
      />
    </div>
  );
};
