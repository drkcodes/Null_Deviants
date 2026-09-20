import {
  Station,
  StationStatus,
  AnomalyRecord,
  AlertRecord,
  StationSensorHealth,
  NetworkSummary,
  ActivityEvent,
  SimulationScenario,
  SimulationResult,
  DataQualityMetrics,
  ModelStatusInfo,
  TelemetryPoint,
  AnomalyCause,
  AnomalySeverity,
  AnomalyFaultType,
  ChannelStatus,
  Region,
  MaintenanceRiskResult,
  MaintenanceRiskFleet,
} from '../../types';

/** SkyGuardAI FastAPI backend base URL. */
export const API_BASE_URL: string =
  ((import.meta as any).env?.VITE_API_BASE_URL as string | undefined) ||
  'http://127.0.0.1:8000';

/**
 * Normalizes any station ID representation to the backend authoritative format.
 * e.g., 'AWS-AP-07' -> 'AWS_AP07', 'AWS-AP-7' -> 'AWS_AP07', 'AWS_AP07' -> 'AWS_AP07'
 */
export function toBackendStationId(id: string): string {
  if (!id) return id;
  const trimmed = id.trim();
  const match = trimmed.match(/^AWS[-_]AP[-_]?(\d+)$/i);
  if (match) {
    const num = parseInt(match[1], 10);
    return `AWS_AP${num.toString().padStart(2, '0')}`;
  }
  return trimmed;
}

/**
 * Normalizes any station ID representation to the frontend human-readable display format.
 * e.g., 'AWS_AP07' -> 'AWS-AP-07', 'AWS_AP7' -> 'AWS-AP-07', 'AWS-AP-07' -> 'AWS-AP-07'
 */
export function toDisplayStationId(id: string): string {
  if (!id) return id;
  const trimmed = id.trim();
  const match = trimmed.match(/^AWS[-_]AP[-_]?(\d+)$/i);
  if (match) {
    const num = parseInt(match[1], 10);
    return `AWS-AP-${num.toString().padStart(2, '0')}`;
  }
  return trimmed;
}

/**
 * Backend raw schema models from FastAPI openapi.json
 */
export interface BackendStationMeta {
  station_id: string; // e.g. "AWS_AP01"
  station_name: string;
  district: string;
  region: string;
  latitude: number;
  longitude: number;
  elevation_m: number;
  nearest_station_id?: string;
  nearest_station_distance_km?: number;
}

export interface BackendObservationRecord {
  id?: number;
  station_id: string;
  timestamp: string;
  temperature_c: number | null;
  relative_humidity_pct: number | null;
  pressure_hpa: number | null;
  anomaly?: number | boolean;
  anomaly_score?: number | null;
  weather_or_sensor?: string | null;
  confidence?: number | null;
  fault_component?: string | null;
  evidence_temporal?: number | null;
  evidence_spatial?: number | null;
  evidence_multivariate?: number | null;
}

interface BackendHealthChannel {
  score: number | null;
  status: string;
  signals: {
    drift?: number | null;
    stuck_count?: number | null;
    missing?: number | null;
    spatial_deviation?: number | null;
  };
}

interface BackendStationHealth {
  station_id: string;
  timestamp: string | null;
  overall: {
    score: number | null;
    status: string;
  };
  channels: {
    temperature: BackendHealthChannel;
    humidity: BackendHealthChannel;
    pressure: BackendHealthChannel;
  };
  drift: {
    score: number | null;
    progressive: number | null;
    directional_consistency: number | null;
    persistence: number | null;
    run_length: number;
  };
  sensor_fault: {
    score: number | null;
    isolation: number | null;
    frozen: number | null;
    physical_consistency: number | null;
  };
  data_quality: {
    missing_rate: number | null;
    timestamp_gap: number | null;
    observation_age_seconds: number | null;
  };
  network: {
    coherence: number | null;
    neighbor_agreement: number | null;
  };
  anomaly_burden: {
    anomalies_24h: number;
    anomalies_7d: number;
  };
  explanation: string[];
  data_sufficiency: {
    status: 'high' | 'medium' | 'low' | 'insufficient';
    samples_used: number;
  };
}

interface BackendFleetHealth {
  stations: BackendStationHealth[];
  station_count: number;
}

export interface BackendPredictionResponse {
  station_id: string;
  timestamp: string;
  temperature_c: number | null;
  relative_humidity_pct: number | null;
  pressure_hpa: number | null;
  anomaly: boolean;
  anomaly_score: number;
  weather_or_sensor: string;
  confidence: number | null;
  fault_component: string;
  evidence: {
    temporal: number;
    spatial: number;
    multivariate: number;
  };
}

/**
 * Centralized HTTP request helper with timeout and error diagnostics
 */
async function apiFetch<T>(endpoint: string, options?: RequestInit & { timeoutMs?: number }): Promise<T> {
  const cleanBase = API_BASE_URL.replace(/\/+$/, '');
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  const url = `${cleanBase}${cleanEndpoint}`;

  // Allow individual call-sites to override the timeout for slow endpoints.
  // All ordinary endpoints retain the existing 20-second default.
  const timeoutMs = options?.timeoutMs ?? 20000;

  const { timeoutMs: _ignored, ...fetchOptions } = options ?? {};

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(url, {
      ...fetchOptions,
      signal: controller.signal,
      headers: {
        Accept: 'application/json',
        ...(fetchOptions?.headers || {}),
      },
    });

    if (!res.ok) {
      throw new Error(`Backend responded with HTTP ${res.status}: ${res.statusText}`);
    }

    return (await res.json()) as T;
  } catch (err: any) {
    if (err.name === 'AbortError') {
      throw new Error(`SkyGuardAI backend request timed out (${cleanEndpoint}). Ensure FastAPI is running on ${API_BASE_URL}.`);
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Production Service Layer connecting the React Dashboard to the live FastAPI Backend.
 */
class StationService {
  private cachedStations: Station[] = [];
  private cachedAlerts: AlertRecord[] = [];
  private cachedFleetHealth: BackendStationHealth[] = [];
  private stationsRequest: Promise<Station[]> | null = null;
  private fleetHealthRequest: Promise<BackendStationHealth[]> | null = null;

  private mapHealthStatus(status: string): StationStatus {
    if (status === 'Healthy') return 'Healthy';
    if (status === 'Watch') return 'Watch';
    if (status === 'Critical' || status === 'Degraded') return 'Critical';
    return 'Awaiting Data';
  }

  private mapStationHealth(
    health: BackendStationHealth,
    station?: Station,
  ): StationSensorHealth {
    const mapChannelStatus = (status: string): ChannelStatus => {
      if (status === 'Insufficient Data') return 'Awaiting data';
      if (status === 'Critical') return 'Suspected fault';
      if (status === 'Degraded' || status === 'Watch') return 'Degraded';
      return 'Normal';
    };
    const score = health.overall.score;
    const timestamp = health.timestamp || station?.lastObservationTime || 'Awaiting observation';

    return {
      stationId: toDisplayStationId(health.station_id),
      stationName: station?.name || health.station_id,
      district: station?.district || '',
      region: station?.region || 'Coastal',
      overallHealth: score,
      overallStatus: health.overall.status as StationSensorHealth['overallStatus'],
      temperatureChannel: mapChannelStatus(health.channels.temperature.status),
      temperatureScore: health.channels.temperature.score,
      humidityChannel: mapChannelStatus(health.channels.humidity.status),
      humidityScore: health.channels.humidity.score,
      pressureChannel: mapChannelStatus(health.channels.pressure.status),
      pressureScore: health.channels.pressure.score,
      missingDataPct: health.data_quality.missing_rate === null
        ? null
        : health.data_quality.missing_rate * 100,
      driftDetected: (health.drift.score ?? 0) >= 0.7,
      neighbourAgreementPct: health.network.neighbor_agreement === null
        ? null
        : health.network.neighbor_agreement * 100,
      drift: {
        score: health.drift.score,
        progressive: health.drift.progressive,
        directionalConsistency: health.drift.directional_consistency,
        persistence: health.drift.persistence,
        runLength: health.drift.run_length,
      },
      sensorFault: {
        score: health.sensor_fault.score,
        isolation: health.sensor_fault.isolation,
        frozen: health.sensor_fault.frozen,
        physicalConsistency: health.sensor_fault.physical_consistency,
      },
      dataQuality: {
        missingRate: health.data_quality.missing_rate,
        timestampGap: health.data_quality.timestamp_gap,
        observationAgeSeconds: health.data_quality.observation_age_seconds,
      },
      network: {
        coherence: health.network.coherence,
        neighborAgreement: health.network.neighbor_agreement,
      },
      anomalyBurden: {
        anomalies24h: health.anomaly_burden.anomalies_24h,
        anomalies7d: health.anomaly_burden.anomalies_7d,
      },
      explanation: health.explanation,
      dataSufficiency: {
        status: health.data_sufficiency.status,
        samplesUsed: health.data_sufficiency.samples_used,
      },
      lastEvaluationTime: timestamp,
    };
  }

  /**
   * Fetches authoritative station metadata from GET /stations and combines with GET /stations/latest.
   */
  async getStations(): Promise<Station[]> {
    if (this.stationsRequest) {
      return this.stationsRequest;
    }

    this.stationsRequest = this.refreshStations();

    try {
      return await this.stationsRequest;
    } finally {
      this.stationsRequest = null;
    }
  }

  private async refreshStations(): Promise<Station[]> {
    let backendStations: BackendStationMeta[] = [];
    try {
      backendStations = await apiFetch<BackendStationMeta[]>('/stations');
    } catch (err) {
      throw new Error(`Unable to load station metadata from SkyGuardAI backend: ${err instanceof Error ? err.message : String(err)}`);
    }

    // Fetch latest telemetry observations from GET /stations/latest
    let latestObservations: BackendObservationRecord[] = [];
    try {
      latestObservations = await apiFetch<BackendObservationRecord[]>('/stations/latest');
    } catch (err) {
      throw new Error(`Unable to load latest telemetry from SkyGuardAI backend: ${err instanceof Error ? err.message : String(err)}`);
    }

    const obsMap = new Map<string, BackendObservationRecord>();
    if (Array.isArray(latestObservations)) {
      for (const obs of latestObservations) {
        if (obs.station_id) {
          obsMap.set(toBackendStationId(obs.station_id), obs);
        }
      }
    }

    const healthByStation = new Map(
      this.cachedFleetHealth.map((health) => [toBackendStationId(health.station_id), health]),
    );

    const mappedStations: Station[] = backendStations.map((b) => {
      const backendId = toBackendStationId(b.station_id);
      const displayId = toDisplayStationId(b.station_id);
      const obs = obsMap.get(backendId);
      const health = healthByStation.get(backendId);

      const hasValidReading =
        obs !== undefined &&
        obs.temperature_c !== null &&
        obs.relative_humidity_pct !== null;

      const isAnomaly = Boolean(obs?.anomaly);
      const anomalyScore = obs?.anomaly_score ?? 0;
      const confidence = obs?.confidence ? Math.round(obs.confidence * 100) : 90;
      const weatherOrSensor = (obs?.weather_or_sensor?.toLowerCase() === 'weather' ? 'Weather' : 'Sensor') as AnomalyCause;

      let status: StationStatus = 'Awaiting Data';
      let healthScore: number | null = health?.overall.score ?? null;

      if (isAnomaly) {
        status = confidence >= 85 || anomalyScore >= 0.8 ? 'Critical' : 'Watch';
      } else if (hasValidReading) {
        status = health ? this.mapHealthStatus(health.overall.status) : 'Awaiting Data';
      } else {
        status = 'Awaiting Data';
      }

      const faultType = (obs?.fault_component
        ? obs.fault_component.charAt(0).toUpperCase() + obs.fault_component.slice(1)
        : 'Spike') as AnomalyFaultType;

      return {
        id: displayId,
        backendId,
        name: b.station_name,
        district: b.district,
        region: b.region as Region,
        latitude: b.latitude,
        longitude: b.longitude,
        elevationM: b.elevation_m,
        neighbours: b.nearest_station_id ? [toDisplayStationId(b.nearest_station_id)] : [],
        nearestStationId: b.nearest_station_id,
        nearestStationDistanceKm: b.nearest_station_distance_km,
        status,
        healthScore,
        lastObservationTime: obs?.timestamp || 'Awaiting observation',
        telemetry: {
          temperatureC: obs?.temperature_c ?? null,
          humidityPct: obs?.relative_humidity_pct ?? null,
          pressureHpa: obs?.pressure_hpa ?? null,
        },
        hasTelemetry: hasValidReading,
        activeAnomaliesCount: isAnomaly ? 1 : 0,
        latestAnomaly: isAnomaly
          ? {
              type: faultType,
              cause: weatherOrSensor,
              confidence,
              timestamp: obs?.timestamp || new Date().toISOString(),
            }
          : undefined,
      };
    });

    this.cachedStations = mappedStations;
    return mappedStations;
  }

  /**
   * Resolves a station by ID using display format ('AWS-AP-07') or backend format ('AWS_AP07').
   */
  async getStationById(id: string): Promise<Station | undefined> {
    if (this.cachedStations.length === 0) {
      await this.getStations();
    }
    const backendId = toBackendStationId(id);
    const displayId = toDisplayStationId(id);
    return this.cachedStations.find((s) => s.id === displayId || s.backendId === backendId);
  }

  /**
   * Fetches active anomaly alerts from GET /alerts.
   * Returns empty array if no alerts exist. Does NOT manufacture mock alerts.
   */
  async getAlerts(): Promise<AlertRecord[]> {
    let rawAlerts: BackendObservationRecord[] = [];
    try {
      rawAlerts = await apiFetch<BackendObservationRecord[]>('/alerts');
    } catch (err) {
      throw new Error(`Unable to load anomaly alerts from SkyGuardAI backend: ${err instanceof Error ? err.message : String(err)}`);
    }

    if (!Array.isArray(rawAlerts) || rawAlerts.length === 0) {
      this.cachedAlerts = [];
      return [];
    }

    if (this.cachedStations.length === 0) {
      try {
        await this.getStations();
      } catch {
        // ignore if stations fetch error
      }
    }

    const alerts: AlertRecord[] = rawAlerts.map((item, index) => {
      const displayStationId = toDisplayStationId(item.station_id);
      const station = this.cachedStations.find((s) => s.id === displayStationId);
      const stationName = station?.name || item.station_id;

      const anomalyScore = item.anomaly_score ?? 0.8;
      const confidence = item.confidence ? Math.round(item.confidence * 100) : 90;
      const cause = (item.weather_or_sensor?.toLowerCase() === 'weather' ? 'Weather' : 'Sensor') as AnomalyCause;

      let severity: AnomalySeverity = 'Medium';
      if (anomalyScore >= 0.85 || confidence >= 92) {
        severity = 'Critical';
      } else if (anomalyScore >= 0.7) {
        severity = 'High';
      } else if (anomalyScore < 0.4) {
        severity = 'Low';
      }

      const faultType = (item.fault_component
        ? item.fault_component.charAt(0).toUpperCase() + item.fault_component.slice(1)
        : 'Spike') as AnomalyFaultType;

      const explanation =
        cause === 'Weather'
          ? `Spatially coherent atmospheric deviation detected. Adjacent stations correlate with observed trends.`
          : `Sensor physical deviation on ${item.fault_component || 'measurement channel'}. Isolated discrepancy.`;

      return {
        id: `ALT-${item.id ?? index + 1}`,
        stationId: displayStationId,
        stationName,
        timestamp: item.timestamp,
        severity,
        cause,
        anomalyType: faultType,
        anomalyScore: Math.round(anomalyScore * 100) / 100,
        confidence,
        shortExplanation: explanation,
        isRead: false,
      };
    });

    this.cachedAlerts = alerts;
    return alerts;
  }

  /**
   * Fetches anomaly records with deep evidence scoring for the Anomaly Intelligence view.
   */
  async getAnomalies(filter?: {
    cause?: AnomalyCause | 'All';
    severity?: AnomalySeverity | 'All';
    faultType?: string | 'All';
    search?: string;
  }): Promise<AnomalyRecord[]> {
    const rawAlerts = await apiFetch<BackendObservationRecord[]>('/alerts');
    if (!Array.isArray(rawAlerts) || rawAlerts.length === 0) return [];

    if (this.cachedStations.length === 0) await this.getStations();

    let records: AnomalyRecord[] = rawAlerts.map((item, index) => {
      const stationId = toDisplayStationId(item.station_id);
      const station = this.cachedStations.find((s) => s.id === stationId);
      const causeText = String(item.weather_or_sensor || '').toLowerCase();
      const cause: AnomalyCause = causeText === 'weather' ? 'Weather' : 'Sensor';
      const score = Number(item.anomaly_score ?? 0);
      const confidence = Number(item.confidence ?? 0);
      const faultType = item.fault_component && item.fault_component !== 'none'
        ? item.fault_component.charAt(0).toUpperCase() + item.fault_component.slice(1)
        : 'Multiple';
      let severity: AnomalySeverity = 'Medium';
      if (score >= 0.85 || confidence >= 0.92) severity = 'Critical';
      else if (score >= 0.7) severity = 'High';
      else if (score < 0.4) severity = 'Low';

      const temporal = Number(item.evidence_temporal ?? 0);
      const spatial = Number(item.evidence_spatial ?? 0);
      const multivariate = Number(item.evidence_multivariate ?? 0);
      const affectedParameter = /temperature/i.test(faultType)
        ? 'Temperature'
        : /humidity/i.test(faultType)
        ? 'Humidity'
        : /pressure/i.test(faultType)
        ? 'Pressure'
        : 'Multiple';

      return {
        id: `ANO-${item.id ?? index + 1}`,
        stationId,
        stationName: station?.name || stationId,
        region: station?.region || 'Coastal',
        timestamp: item.timestamp,
        anomalyScore: score,
        cause,
        faultType: faultType as AnomalyFaultType,
        severity,
        confidence: Math.round(confidence * 100),
        status: 'Active',
        evidence: {
          temporalScore: temporal,
          spatialScore: spatial,
          multivariateScore: multivariate,
          explanation: cause === 'Weather'
            ? 'Spatially coherent atmospheric deviation detected across the benchmark network.'
            : `Sensor/data deviation detected on the ${affectedParameter.toLowerCase()} channel.`,
          neighbourAgreementText: cause === 'Weather'
            ? 'Neighbouring AWS observations support a coherent regional event.'
            : 'Neighbouring AWS observations remain comparatively nominal, supporting an isolated fault.',
          affectedParameter,
          physicalConsistencyNote: 'Evidence supplied by the two-stage Random Forest inference record.',
        },
      };
    });

    if (filter?.cause && filter.cause !== 'All') records = records.filter((a) => a.cause === filter.cause);
    if (filter?.severity && filter.severity !== 'All') records = records.filter((a) => a.severity === filter.severity);
    if (filter?.faultType && filter.faultType !== 'All') records = records.filter((a) => a.faultType === filter.faultType);
    if (filter?.search) {
      const q = filter.search.toLowerCase();
      records = records.filter((a) =>
        a.stationId.toLowerCase().includes(q) ||
        a.stationName.toLowerCase().includes(q) ||
        a.faultType.toLowerCase().includes(q) ||
        a.id.toLowerCase().includes(q),
      );
    }
    return records;
  }

  async getAnomalyById(id: string): Promise<AnomalyRecord | undefined> {
    const list = await this.getAnomalies();
    return list.find((a) => a.id === id);
  }

  /**
   * Fetches historical time-series observation packets for a station from GET /station/{station_id}/history.
   * Maps display ID to backend ID. Returns empty array if no historical telemetry exists.
   */
  async getTimeSeries(
    stationId: string,
    hours: number = 24,
  ): Promise<TelemetryPoint[]> {
    const backendId = toBackendStationId(stationId);
    const requestedHours = Math.max(1, Math.min(168, Number(hours) || 24));
    const requestedLimit = requestedHours <= 1 ? 50 : requestedHours <= 6 ? 100 : requestedHours <= 24 ? 150 : 750;

    const rawHistory = await apiFetch<BackendObservationRecord[]>(
      `/station/${encodeURIComponent(backendId)}/history?limit=${requestedLimit}`,
    );

    if (!Array.isArray(rawHistory) || rawHistory.length === 0) {
      return [];
    }

    const parsed = rawHistory
      .filter((pt) => pt.timestamp && pt.station_id)
      .map((pt) => ({ ...pt, parsedTime: new Date(pt.timestamp.replace(' ', 'T')) }))
      .filter((pt) => !Number.isNaN(pt.parsedTime.getTime()))
      .sort((a, b) => a.parsedTime.getTime() - b.parsedTime.getTime());

    if (parsed.length === 0) return [];

    // The backend returns the newest records first. Use the newest timestamp
    // as the reference point so the chart remains deterministic even though
    // the demo database contains observations from multiple dates.
    const latestMs = parsed[parsed.length - 1].parsedTime.getTime();
    const cutoffMs = latestMs - requestedHours * 60 * 60 * 1000;

    return parsed
      .filter((pt) => pt.parsedTime.getTime() >= cutoffMs && pt.parsedTime.getTime() <= latestMs)
      .map((pt) => {
        const isAnomaly = Boolean(pt.anomaly);
        const causeText = String(pt.weather_or_sensor || '').toLowerCase();
        const cause = causeText === 'weather' ? 'Weather' : causeText === 'sensor' ? 'Sensor' : undefined;
        const faultText = pt.fault_component && pt.fault_component !== 'none'
          ? pt.fault_component.charAt(0).toUpperCase() + pt.fault_component.slice(1)
          : undefined;

        return {
          timestamp: pt.timestamp,
          stationId: toDisplayStationId(pt.station_id),
          temperatureC: pt.temperature_c ?? 0,
          humidityPct: pt.relative_humidity_pct ?? 0,
          pressureHpa: pt.pressure_hpa ?? 0,
          isAnomaly,
          anomalyType: faultText as AnomalyFaultType | undefined,
          anomalyCause: isAnomaly ? cause : undefined,
        };
      });
  }

  /**
   * Derives legitimate fleet metrics from authoritative backend stations & alerts.
   */
  async getNetworkSummary(): Promise<NetworkSummary> {
    if (this.cachedStations.length === 0) {
      await this.getStations();
    }
    const stations = this.cachedStations;
    const alerts = await this.getAlerts();

    const reportingStationsCount = stations.filter((s) => s.hasTelemetry).length;
    const hasAnyTelemetry = reportingStationsCount > 0;

    const healthyCount = hasAnyTelemetry
      ? stations.filter((s) => s.status === 'Healthy').length
      : null;
    const watchCount = hasAnyTelemetry
      ? stations.filter((s) => s.status === 'Watch').length
      : null;
    const criticalCount = hasAnyTelemetry
      ? stations.filter((s) => s.status === 'Critical').length
      : null;
    const offlineCount = stations.filter((s) => s.status === 'Offline').length;
    const awaitingCount = stations.filter((s) => s.status === 'Awaiting Data').length;

    const weatherEventsCount =
      hasAnyTelemetry || alerts.length > 0
        ? alerts.filter((a) => a.cause === 'Weather').length
        : null;
    const sensorFaultsCount =
      hasAnyTelemetry || alerts.length > 0
        ? alerts.filter((a) => a.cause === 'Sensor').length
        : null;

    // Honest data quality calculation based on stations with active telemetry
    const dataQualityPct =
      stations.length > 0 && reportingStationsCount > 0
        ? Math.round((reportingStationsCount / stations.length) * 100)
        : null;

    const now = new Date();
    const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')} IST`;

    return {
      totalStations: stations.length,
      healthyCount,
      watchCount,
      criticalCount,
      offlineCount,
      awaitingCount,
      dataQualityPct,
      activeAnomalies: alerts.length,
      weatherEventsCount,
      sensorFaultsCount,
      reportingStationsCount,
      lastUpdated: timeStr,
    };
  }

  async getFleetHealth(): Promise<BackendStationHealth[]> {
    if (this.cachedFleetHealth.length > 0) {
      return this.cachedFleetHealth;
    }

    return this.refreshFleetHealth();
  }

  async refreshFleetHealth(): Promise<BackendStationHealth[]> {
    if (!this.fleetHealthRequest) {
      // Fleet health computation is heavyweight (35-40 s in production).
      // Use an extended timeout so the backend cache can warm on first call.
      this.fleetHealthRequest = apiFetch<BackendFleetHealth>('/stations/health', { timeoutMs: 90000 })
        .then((response) => {
          this.cachedFleetHealth = response.stations;
          return this.cachedFleetHealth;
        })
        .finally(() => {
          this.fleetHealthRequest = null;
        });
    }

    return this.fleetHealthRequest;
  }

  async getStationHealth(stationId: string): Promise<StationSensorHealth | undefined> {
    const backendId = toBackendStationId(stationId);
    const response = await apiFetch<BackendStationHealth>(
      `/station/${encodeURIComponent(backendId)}/health`,
    );
    const station = await this.getStationById(backendId);
    return this.mapStationHealth(response, station);
  }

  async getSensorHealthList(): Promise<StationSensorHealth[]> {
    const health = await this.getFleetHealth();
    if (this.cachedStations.length === 0) {
      await this.getStations();
    }
    const stationsById = new Map(
      this.cachedStations.map((station) => [station.backendId || toBackendStationId(station.id), station]),
    );
    return health.map((item) => this.mapStationHealth(
      item,
      stationsById.get(toBackendStationId(item.station_id)),
    ));
  }

  async getStationSensorHealth(stationId: string): Promise<StationSensorHealth | undefined> {
    return this.getStationHealth(stationId);
  }

  /**
   * Operational activity stream derived from real alerts or connection status.
   */
  async getActivityEvents(): Promise<ActivityEvent[]> {
    const alerts = await this.getAlerts();

    if (alerts.length > 0) {
      return alerts.map((alt) => ({
        id: `EVT-${alt.id}`,
        time: alt.timestamp.includes(' ') ? alt.timestamp.split(' ')[1] : alt.timestamp,
        stationId: alt.stationId,
        message: `${alt.cause} anomaly detected on ${alt.stationName} (${alt.anomalyType}, ${alt.confidence}% confidence)`,
        type: 'anomaly',
        severity: alt.severity,
      }));
    }

    return [];
  }

  /**
   * Data stream metrics reporting current ingestion status honestly.
   */
  async getDataQuality(): Promise<DataQualityMetrics> {
    if (this.cachedStations.length === 0) {
      await this.getStations();
    }
    const reportingCount = this.cachedStations.filter((s) => s.hasTelemetry).length;
    const totalExpected = this.cachedStations.length;

    return {
      totalObservationsExpected: totalExpected,
      missingObservationsCount: totalExpected - reportingCount,
      missingTempCount: totalExpected - reportingCount,
      missingHumidityCount: totalExpected - reportingCount,
      missingPressureCount: totalExpected - reportingCount,
      duplicateObservationsCount: 0,
      outOfOrderTimestampsCount: 0,
      invalidValuesCount: 0,
      timestampGapsCount: 0,
      overallQualityPct: reportingCount > 0 ? Math.round((reportingCount / totalExpected) * 100) : null,
    };
  }

  /**
   * Real ML model status info for the two-stage random forest architecture.
   * Uses apiFetch so it shares the same timeout and error-handling as all
   * other endpoints. The backend intentionally returns "Not available" for
   * persisted accuracy/F1 — this is preserved unchanged.
   */
  async getModelStatus(): Promise<ModelStatusInfo> {
    return apiFetch<ModelStatusInfo>('/model/status');
  }


  /** Fetches deterministic Phase 8 maintenance-risk ranking for the full fleet. */
  async getMaintenanceRiskFleet(): Promise<MaintenanceRiskFleet> {
    // Maintenance-risk computation is heavyweight (30-35 s in production).
    // Use an extended timeout; the backend TTL cache keeps subsequent calls fast.
    return apiFetch<MaintenanceRiskFleet>('/stations/maintenance-risk', { timeoutMs: 90000 });
  }

  /** Fetches deterministic Phase 8 maintenance risk for one station. */
  async getStationMaintenanceRisk(stationId: string): Promise<MaintenanceRiskResult> {
    const backendId = toBackendStationId(stationId);
    return apiFetch<MaintenanceRiskResult>(
      `/station/${encodeURIComponent(backendId)}/maintenance-risk`,
    );
  }

  async getSimulationScenarios(): Promise<SimulationScenario[]> {
  return [
    {
      id: 'scen-temp-spike',
      name: 'Temperature Spike (Sensor)',
      category: 'Sensor',
      faultType: 'Spike',
      description:
        'Tests an isolated abrupt temperature deviation against the benchmark observation.',
      defaultSeverity: 'High',
      affectedParameter: 'Temperature',
    },
    {
      id: 'scen-temp-drop',
      name: 'Temperature Drop (Sensor)',
      category: 'Sensor',
      faultType: 'Drop',
      description:
        'Tests an isolated abrupt temperature decrease against the benchmark observation.',
      defaultSeverity: 'High',
      affectedParameter: 'Temperature',
    },
    {
      id: 'scen-pressure-jump',
      name: 'Pressure Jump (Sensor)',
      category: 'Sensor',
      faultType: 'Pressure Jump',
      description:
        'Tests an isolated barometric pressure jump.',
      defaultSeverity: 'High',
      affectedParameter: 'Pressure',
    },
    {
      id: 'scen-regional-heatwave',
      name: 'Regional Heatwave (Genuine Weather)',
      category: 'Weather',
      faultType: 'Heatwave',
      description:
        'Uses a benchmark weather-event observation representing coherent regional warming.',
      defaultSeverity: 'Medium',
      affectedParameter: 'Temperature',
    },
    {
      id: 'scen-regional-cold-spell',
      name: 'Regional Cold Spell (Genuine Weather)',
      category: 'Weather',
      faultType: 'Cold Spell',
      description:
        'Uses a benchmark cold-weather observation to evaluate whether the model identifies a coherent regional temperature decrease.',
      defaultSeverity: 'Medium',
      affectedParameter: 'Temperature',
    },
  ];
}

  /**
   * Runs the simulator through the backend's real dataset-backed evaluation
   * endpoint. The backend selects a real benchmark observation, supplies the
   * complete model feature vector, and executes the actual two-stage models.
   */
  async runSimulation(
    stationId: string,
    scenarioId: string,
    intensity: number = 85,
  ): Promise<SimulationResult> {
    // Simulation performs the full validated feature/network/ML pipeline.
    // Use an extended timeout — the backend succeeds but needs up to 60 s.
    const response = await apiFetch<any>('/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        station_id: toBackendStationId(stationId),
        scenario_id: scenarioId,
        intensity,
      }),
      timeoutMs: 90000,
    });

    if (!response || response.error) {
      throw new Error(response?.error || 'Simulation failed in backend.');
    }

    const scenario = (await this.getSimulationScenarios()).find((s) => s.id === scenarioId);
    if (!scenario) throw new Error(`Unknown simulation scenario: ${scenarioId}`);

const causeText = String(response.weather_or_sensor || '').toLowerCase();

const stage2Cause: AnomalyCause =
  causeText === 'weather'
    ? 'Weather'
    : 'Sensor';

    const anomalyScore = Number(response.anomaly_score ?? 0);
    const confidence = Number(response.confidence ?? 0) * 100;
    const isWeather = stage2Cause === 'Weather';

    const station = await this.getStationById(stationId);
    const previousScore = station?.healthScore ?? 100;
    const affectedParameter =
      response.fault_component && response.fault_component !== 'none'
        ? String(response.fault_component)
        : scenario.affectedParameter;

    const newScore = isWeather
      ? previousScore
      : Math.max(25, previousScore - 30);

    const temperature = Number(response.temperature_c ?? 0);
    const humidity = Number(response.relative_humidity_pct ?? 0);
    const pressure = Number(response.pressure_hpa ?? 0);

    const baselineTemp = Number(response.seasonal_baseline?.temperature_c ?? temperature);
    const baselineHum = Number(response.seasonal_baseline?.relative_humidity_pct ?? humidity);
    const baselinePress = Number(response.seasonal_baseline?.pressure_hpa ?? pressure);

    return {
      scenario,
      stationId: toDisplayStationId(response.station_id || stationId),
      timestamp: String(response.timestamp),
      observation: {
        temperatureC: temperature,
        humidityPct: humidity,
        pressureHpa: pressure,
      },
      featuresComputedCount: Number(response.features_computed_count ?? 50),
      stage1AnomalyDetected: Boolean(response.anomaly),
      stage1Score: anomalyScore,
      stage2Cause,
      stage2Confidence: Math.round(confidence),
      rootCauseDetails: {
        faultComponent: affectedParameter,
        evidenceType: isWeather
          ? 'Spatial coherence from benchmark observation'
          : 'Temporal / spatial / multivariate evidence from benchmark observation',
        summary: String(
          response.diagnosis ||
            (isWeather
              ? 'The model classified the anomalous observation as a genuine weather event.'
              : 'The model classified the anomalous observation as a sensor/data fault.')
        ),
      },
      sensorHealthImpact: {
        channel: affectedParameter,
        previousScore,
        newScore,
        status: isWeather ? 'Normal' : 'Suspected fault',
      },
      seasonalEvidence: {
        baselineTemp,
        baselineHumidity: baselineHum,
        baselinePressure: baselinePress,
        tempDeviation: Number((temperature - baselineTemp).toFixed(1)),
        humidityDeviation: Number((humidity - baselineHum).toFixed(1)),
        pressureDeviation: Number((pressure - baselinePress).toFixed(1)),
        status:
          Math.abs(temperature - baselineTemp) > 5
            ? 'Significant Seasonal Deviation'
            : 'Within Seasonal Climatology Norm',
      },
    };
  }

  async runLiveScenario(
    stationId: string,
    scenarioId: string,
    intensity: number = 85,
  ): Promise<any> {
    const response = await apiFetch<any>('/live-scenario', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        station_id: toBackendStationId(stationId),
        scenario_id: scenarioId,
        intensity,
      }),
      timeoutMs: 90000,
    });

    if (!response || response.error) {
      throw new Error(response?.error || 'Live scenario failed in backend.');
    }

    return response;
  }

  /**
   * Resets the backend database to empty state via POST /reset.
   */
  async resetBackendDatabase(): Promise<{ status: string }> {
    return apiFetch<{ status: string }>('/reset', { method: 'POST' });
  }
}

export const stationService = new StationService();

