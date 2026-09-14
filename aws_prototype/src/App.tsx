import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivePage,
  Station,
  NetworkSummary,
  AlertRecord,
  AnomalyRecord,
  StationSensorHealth,
  ActivityEvent,
  DataQualityMetrics,
  ModelStatusInfo,
  SimulationScenario,
  TelemetryPoint,
  MaintenanceRiskResult,
} from './types';
import { stationService } from './lib/api/stationService';
import { Sidebar } from './components/layout/Sidebar';
import { TopBar } from './components/layout/TopBar';
import { PageHeader } from './components/common/PageHeader';
import { AlertCircle, RefreshCw } from 'lucide-react';

// Page Views
import { OverviewView } from './components/overview/OverviewView';
import { NetworkView } from './components/network/NetworkView';
import { StationDetailView } from './components/stations/StationDetailView';
import { AnomalyView } from './components/anomalies/AnomalyView';
import { SensorHealthView } from './components/health/SensorHealthView';
import { DataMonitoringView } from './components/monitoring/DataMonitoringView';
import { ReportsView } from './components/reports/ReportsView';
import { SettingsView } from './components/settings/SettingsView';
import { SimulationDemoCenter } from './components/simulator/SimulationDemoCenter';

const LIVE_REFRESH_MS = 2000;

export default function App() {
  const [activePage, setActivePage] = useState<ActivePage>('overview');

  const [selectedStationId, setSelectedStationId] =
    useState<string>('AWS-AP-07');

  const [selectedAnomaly, setSelectedAnomaly] =
    useState<AnomalyRecord | null>(null);

  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  // Core Data State
  const [stations, setStations] = useState<Station[]>([]);
  const [networkSummary, setNetworkSummary] =
    useState<NetworkSummary | null>(null);
  const [alerts, setAlerts] = useState<AlertRecord[]>([]);
  const [anomalies, setAnomalies] = useState<AnomalyRecord[]>([]);
  const [sensorHealthList, setSensorHealthList] =
    useState<StationSensorHealth[]>([]);
  const [activityEvents, setActivityEvents] =
    useState<ActivityEvent[]>([]);
  const [dataQuality, setDataQuality] =
    useState<DataQualityMetrics | null>(null);
  const [modelStatus, setModelStatus] =
    useState<ModelStatusInfo | null>(null);
  const [scenarios, setScenarios] =
    useState<SimulationScenario[]>([]);
  const [timeSeries, setTimeSeries] =
    useState<TelemetryPoint[]>([]);
  const [maintenanceRisk, setMaintenanceRisk] =
    useState<MaintenanceRiskResult[]>([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  /*
   * Prevent overlapping polling requests.
   *
   * The simulator sends observations every 2 seconds, so the frontend
   * also refreshes every 2 seconds. If one request takes longer than
   * expected, another polling cycle will not start on top of it.
   */
  const liveRefreshInProgress = useRef(false);

  /*
   * Initial application load.
   *
   * This loads everything required to render the application for the
   * first time. The loading screen is shown only during this operation.
   */
  const initData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const [
        stList,
        summ,
        altList,
        anomList,
        health,
        act,
        qual,
        model,
        scen,
        maintenanceFleet,
      ] = await Promise.all([
        stationService.getStations(),
        stationService.getNetworkSummary(),
        stationService.getAlerts(),
        stationService.getAnomalies(),
        stationService.getSensorHealthList(),
        stationService.getActivityEvents(),
        stationService.getDataQuality(),
        stationService.getModelStatus(),
        stationService.getSimulationScenarios(),
        stationService.getMaintenanceRiskFleet(),
      ]);

      setStations(stList);
      setNetworkSummary(summ);
      setAlerts(altList);
      setAnomalies(anomList);
      setSensorHealthList(health);
      setActivityEvents(act);
      setDataQuality(qual);
      setModelStatus(model);
      setScenarios(scen);
      setMaintenanceRisk(maintenanceFleet.stations || []);

      const targetId = stList.some(
        (station) => station.id === selectedStationId,
      )
        ? selectedStationId
        : stList[0]?.id || 'AWS-AP-01';

      if (targetId !== selectedStationId) {
        setSelectedStationId(targetId);
      }

      const ts = await stationService.getTimeSeries(targetId, 24);
      setTimeSeries(ts);
      setMaintenanceRisk(maintenanceFleet.stations || []);
    } catch (err: any) {
      console.error(
        'Failed to reach SkyGuardAI backend:',
        err,
      );

      setError(
        err?.message ||
          'Unable to reach SkyGuardAI backend',
      );
    } finally {
      setLoading(false);
    }
  }, [selectedStationId]);

  /*
   * Refresh only the data that changes while the simulator is running.
   *
   * IMPORTANT:
   * We deliberately do not call initData() here because that would
   * repeatedly activate the application's loading screen.
   */
  const refreshLiveData = useCallback(async () => {
    if (liveRefreshInProgress.current) {
      return;
    }

    liveRefreshInProgress.current = true;

    try {
      const [
        stList,
        summ,
        altList,
        anomList,
        health,
        act,
        qual,
        ts,
        maintenanceFleet,
      ] = await Promise.all([
        stationService.getStations(),
        stationService.getNetworkSummary(),
        stationService.getAlerts(),
        stationService.getAnomalies(),
        stationService.getSensorHealthList(),
        stationService.getActivityEvents(),
        stationService.getDataQuality(),
        selectedStationId
          ? stationService.getTimeSeries(
              selectedStationId,
              24,
            )
          : Promise.resolve([]),
        stationService.getMaintenanceRiskFleet(),
      ]);

      /*
       * Update the dashboard state atomically after the requests
       * complete. React will then re-render the affected views.
       */
      setStations(stList);
      setNetworkSummary(summ);
      setAlerts(altList);
      setAnomalies(anomList);
      setSensorHealthList(health);
      setActivityEvents(act);
      setDataQuality(qual);
      setTimeSeries(ts);

      /*
       * If the currently selected station disappears from the
       * backend station list, move to the first available station.
       */
      if (
        stList.length > 0 &&
        !stList.some(
          (station) => station.id === selectedStationId,
        )
      ) {
        setSelectedStationId(stList[0].id);
      }
    } catch (err) {
      /*
       * Do NOT destroy the dashboard if one background refresh fails.
       *
       * The previous successful data remains visible and the next
       * polling cycle will try again.
       */
      console.warn(
        'Live dashboard refresh failed:',
        err,
      );
    } finally {
      liveRefreshInProgress.current = false;
    }
  }, [selectedStationId]);

  /*
   * Initial load.
   */
  useEffect(() => {
    initData();
  }, [initData]);

  /*
   * LIVE DASHBOARD POLLING
   *
   * The backend simulator posts a new observation approximately every
   * 2 seconds. We therefore refresh the dashboard at the same interval.
   *
   * This updates:
   *   - station latest readings
   *   - network summary
   *   - anomaly alerts
   *   - anomaly intelligence
   *   - sensor health
   *   - activity feed
   *   - data quality
   *   - selected station graph
   */
  useEffect(() => {
    const intervalId = window.setInterval(() => {
      refreshLiveData();
    }, LIVE_REFRESH_MS);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [refreshLiveData]);

  /*
   * Update time series immediately when the selected station changes.
   *
   * This avoids waiting up to 2 seconds for the next polling cycle.
   */
  useEffect(() => {
    if (!selectedStationId) {
      return;
    }

    let cancelled = false;

    stationService
      .getTimeSeries(selectedStationId, 24)
      .then((ts) => {
        if (!cancelled) {
          setTimeSeries(ts);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          console.warn(
            'Failed to load station time series:',
            err,
          );
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedStationId]);

  const handleStationClick = useCallback((id: string) => {
    setSelectedStationId(id);
  }, []);

  const handleViewStationDetails = (id: string) => {
    setSelectedStationId(id);
    setActivePage('station-detail');
  };

  const handleSelectAlert = (alert: AlertRecord) => {
    const fullAnomaly = anomalies.find(
      (anomaly) => anomaly.stationId === alert.stationId,
    );

    if (fullAnomaly) {
      setSelectedAnomaly(fullAnomaly);
    } else {
      setSelectedStationId(alert.stationId);
      setActivePage('station-detail');
    }
  };

  const handleSearchJump = (term: string) => {
    if (!term) {
      return;
    }

    const lower = term.toLowerCase();

    const matchedStation = stations.find(
      (station) =>
        station.id.toLowerCase().includes(lower) ||
        station.name.toLowerCase().includes(lower) ||
        station.district.toLowerCase().includes(lower),
    );

    if (matchedStation) {
      setSelectedStationId(matchedStation.id);
      setActivePage('station-detail');
      return;
    }

    const matchedAnomaly = anomalies.find(
      (anomaly) =>
        anomaly.stationName
          .toLowerCase()
          .includes(lower) ||
        anomaly.faultType
          .toLowerCase()
          .includes(lower),
    );

    if (matchedAnomaly) {
      setSelectedAnomaly(matchedAnomaly);
      setActivePage('anomalies');
    }
  };

  /*
   * Initial backend connection failure.
   *
   * Background polling failures do NOT reach this screen.
   */
  if (error) {
    return (
      <div className="min-h-screen bg-slate-100 flex items-center justify-center p-4">
        <div className="apple-glass-card p-8 rounded-2xl shadow-xl border border-rose-200 text-center max-w-md bg-white">
          <div className="w-12 h-12 rounded-full bg-rose-50 text-rose-600 flex items-center justify-center mx-auto mb-4 border border-rose-100">
            <AlertCircle className="w-6 h-6" />
          </div>

          <h2 className="text-base font-semibold text-slate-900">
            Unable to reach SkyGuardAI backend
          </h2>

          <p className="text-xs text-slate-500 mt-2 leading-relaxed">
            {error}
          </p>

          <div className="mt-3 p-2.5 bg-slate-50 rounded-xl text-[11px] font-mono text-slate-600 break-all border border-slate-200 text-left">
            <div className="text-[10px] text-slate-400 font-sans uppercase tracking-wider mb-1 font-semibold">
              Backend Endpoint
            </div>

            http://127.0.0.1:8000
          </div>

          <button
            type="button"
            onClick={initData}
            className="mt-5 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-xl inline-flex items-center gap-2 cursor-pointer transition-colors shadow-sm"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Retry Connection</span>
          </button>
        </div>
      </div>
    );
  }

  /*
   * Initial loading screen only.
   */
  if (
    loading ||
    !networkSummary ||
    !dataQuality ||
    !modelStatus
  ) {
    return (
      <div className="min-h-screen bg-slate-100 flex items-center justify-center p-4">
        <div className="apple-glass-card p-8 rounded-2xl shadow-xl border border-slate-200 text-center max-w-sm bg-white">
          <div className="w-10 h-10 border-3 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />

          <h2 className="text-base font-semibold text-slate-900">
            Loading AWS network...
          </h2>

          <p className="text-xs text-slate-500 mt-1">
            Connecting to FastAPI backend and retrieving
            20 Andhra Pradesh stations...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-100 text-slate-800 flex flex-col antialiased">
      {/* Sidebar Navigation */}
      <Sidebar
        activePage={activePage}
        onNavigate={(page) => {
          setActivePage(page);
          window.scrollTo({
            top: 0,
            behavior: 'smooth',
          });
        }}
        isOpenMobile={isMobileMenuOpen}
        onCloseMobile={() =>
          setIsMobileMenuOpen(false)
        }
      />

      {/* Mobile Overlay */}
      {isMobileMenuOpen && (
        <div
          className="fixed inset-0 z-30 bg-slate-900/50 backdrop-blur-xs lg:hidden"
          onClick={() =>
            setIsMobileMenuOpen(false)
          }
        />
      )}

      {/* Main Content Layout */}
      <div className="lg:pl-64 flex-1 flex flex-col min-w-0">
        <TopBar
          networkSummary={networkSummary}
          alerts={alerts}
          onOpenMobileMenu={() =>
            setIsMobileMenuOpen(true)
          }
          onSearch={handleSearchJump}
          onSelectAlert={handleSelectAlert}
        />

        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto">
          {/* Overview */}
          {activePage === 'overview' && (
            <>
              <PageHeader
                title="AWS Network Operations Overview"
                subtitle="Real-time telemetry monitoring • AI-powered anomaly detection • Andhra Pradesh (SIH26073)"
              />

              <OverviewView
                stations={stations}
                summary={networkSummary}
                alerts={alerts}
                anomalies={anomalies}
                activityEvents={activityEvents}
                timeSeries={timeSeries}
                selectedStationId={selectedStationId}
                onSelectStation={handleStationClick}
                onViewStationDetails={
                  handleViewStationDetails
                }
                onSelectAnomaly={setSelectedAnomaly}
                onNavigateToSection={setActivePage}
              />
            </>
          )}

          {/* Network */}
          {activePage === 'network' && (
            <>
              <PageHeader
                title="AWS Network Operations"
                subtitle="Fleet observability across all 20 Automatic Weather Stations in Coastal and Rayalaseema AP"
                breadcrumbs={[
                  {
                    label: 'SkyGuardAI',
                    onClick: () =>
                      setActivePage('overview'),
                  },
                  {
                    label: 'AWS Network',
                  },
                ]}
              />

              <NetworkView
                stations={stations}
                summary={networkSummary}
                selectedStationId={selectedStationId}
                onSelectStation={handleStationClick}
                onViewStationDetails={
                  handleViewStationDetails
                }
                maintenanceRisk={maintenanceRisk}
              />
            </>
          )}

          {/* Station Detail */}
          {activePage === 'station-detail' && (
            <>
              <PageHeader
                title="Station Deep Diagnostics"
                subtitle="Channel-level sensor health, time-series telemetry, and spatial neighbour validation"
                breadcrumbs={[
                  {
                    label: 'Overview',
                    onClick: () =>
                      setActivePage('overview'),
                  },
                  {
                    label: 'AWS Network',
                    onClick: () =>
                      setActivePage('network'),
                  },
                  {
                    label: `Station ${selectedStationId}`,
                  },
                ]}
              />

              <StationDetailView
                stationId={selectedStationId}
                onBack={() =>
                  setActivePage('network')
                }
                onSelectStation={(id) =>
                  setSelectedStationId(id)
                }
                onSelectAnomaly={(ano) =>
                  setSelectedAnomaly(ano)
                }
              />
            </>
          )}

          {/* Anomalies */}
          {activePage === 'anomalies' && (
            <>
              <PageHeader
                title="Anomaly Intelligence & Diagnosis"
                subtitle="Two-stage ML detection: Disentangling genuine regional weather events from isolated sensor malfunctions"
                breadcrumbs={[
                  {
                    label: 'Overview',
                    onClick: () =>
                      setActivePage('overview'),
                  },
                  {
                    label: 'Anomaly Intelligence',
                  },
                ]}
              />

              <AnomalyView
                anomalies={anomalies}
                summary={networkSummary}
                selectedAnomaly={selectedAnomaly}
                onSelectAnomaly={setSelectedAnomaly}
                onViewStation={
                  handleViewStationDetails
                }
              />
            </>
          )}

          {/* Sensor Health */}
          {activePage === 'health' && (
            <>
              <PageHeader
                title="Sensor Hardware & Channel Health"
                subtitle="Station-by-station hardware audit: RTD temperature probes, humidity transducers, and barometers"
                breadcrumbs={[
                  {
                    label: 'Overview',
                    onClick: () =>
                      setActivePage('overview'),
                  },
                  {
                    label: 'Sensor Health',
                  },
                ]}
              />

              <SensorHealthView
                healthList={sensorHealthList}
                onSelectStation={
                  handleViewStationDetails
                }
              />
            </>
          )}

          {/* Monitoring */}
          {activePage === 'monitoring' && (
            <>
              <PageHeader
                title="Data & ML Pipeline Monitoring"
                subtitle="Dataset specifications, telemetry stream quality metrics, and feature group architecture"
                breadcrumbs={[
                  {
                    label: 'Overview',
                    onClick: () =>
                      setActivePage('overview'),
                  },
                  {
                    label: 'Data & ML Monitoring',
                  },
                ]}
              />

              <DataMonitoringView
                quality={dataQuality}
                modelStatus={modelStatus}
              />
            </>
          )}

          {/* Reports */}
          {activePage === 'reports' && (
            <>
              <PageHeader
                title="Operational Intelligence Reports"
                subtitle="Generate, preview, and export fleet reliability audits and weather anomaly reports"
                breadcrumbs={[
                  {
                    label: 'Overview',
                    onClick: () =>
                      setActivePage('overview'),
                  },
                  {
                    label: 'Reports',
                  },
                ]}
              />

              <ReportsView
                stations={stations}
              />
            </>
          )}

          {/* Settings */}
          {activePage === 'settings' && (
            <>
              <PageHeader
                title="System Configuration & Preferences"
                subtitle="Manage telemetry refresh intervals, alert confidence thresholds, and spatial overlays"
                breadcrumbs={[
                  {
                    label: 'Overview',
                    onClick: () =>
                      setActivePage('overview'),
                  },
                  {
                    label: 'Settings',
                  },
                ]}
              />

              <SettingsView />
            </>
          )}

          {/* Simulator */}
          {activePage === 'simulator' && (
            <>
              <PageHeader
                title="Simulation & Evaluator Demo Center"
                subtitle="Controlled testbed for Smart India Hackathon 2026: Inject fault scenarios and trace the complete two-stage ML pipeline"
                breadcrumbs={[
                  {
                    label: 'Overview',
                    onClick: () =>
                      setActivePage('overview'),
                  },
                  {
                    label: 'Simulator Demo Center',
                  },
                ]}
              />

              <SimulationDemoCenter
                stations={stations}
                scenarios={scenarios}
                onViewStationDetails={
                  handleViewStationDetails
                }
              />
            </>
          )}
        </main>
      </div>
    </div>
  );
}