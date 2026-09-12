export type Region = 'Coastal' | 'Rayalaseema';

export type StationStatus = 'Healthy' | 'Watch' | 'Critical' | 'Offline' | 'Awaiting Data';

export type AnomalyCause = 'Weather' | 'Sensor';

export type AnomalySeverity = 'Low' | 'Medium' | 'High' | 'Critical';

export type AnomalyFaultType =
  | 'Spike'
  | 'Drop'
  | 'Freeze/Stuck'
  | 'Drift'
  | 'Pressure Jump'
  | 'Multivariate Inconsistency'
  | 'Missing Data'
  | 'Communication Failure'
  | 'Duplicate Observation'
  | 'Out-of-order Timestamp'
  | 'Invalid Value'
  | 'Heatwave'
  | 'Cold Spell';

export type ChannelStatus = 'Normal' | 'Degraded' | 'Suspected fault' | 'Awaiting data';

export interface Station {
  id: string; // display ID e.g. 'AWS-AP-01'
  backendId?: string; // backend authoritative ID e.g. 'AWS_AP01'
  name: string; // e.g. 'Visakhapatnam'
  district: string;
  region: Region;
  latitude: number;
  longitude: number;
  elevationM: number;
  neighbours: string[]; // IDs of nearest stations
  nearestStationId?: string;
  nearestStationDistanceKm?: number;
  status: StationStatus;
  healthScore: number | null; // 0 - 100 or null if awaiting observation
  lastObservationTime: string;
  telemetry: {
    temperatureC: number | null;
    humidityPct: number | null;
    pressureHpa: number | null;
  };
  hasTelemetry?: boolean;
  activeAnomaliesCount: number;
  latestAnomaly?: {
    type: AnomalyFaultType;
    cause: AnomalyCause;
    confidence: number;
    timestamp: string;
  };
}

export interface TelemetryPoint {
  timestamp: string;
  stationId: string;
  temperatureC: number;
  humidityPct: number;
  pressureHpa: number;
  isAnomaly?: boolean;
  anomalyType?: AnomalyFaultType;
  anomalyCause?: AnomalyCause;
}

export interface AnomalyEvidence {
  temporalScore: number; // 0.0 - 1.0
  spatialScore: number; // 0.0 - 1.0
  multivariateScore: number; // 0.0 - 1.0
  explanation: string;
  neighbourAgreementText: string;
  affectedParameter: 'Temperature' | 'Humidity' | 'Pressure' | 'Multiple' | 'Communication';
  physicalConsistencyNote: string;
}

export interface AnomalyRecord {
  id: string;
  stationId: string;
  stationName: string;
  region: Region;
  timestamp: string;
  anomalyScore: number; // e.g. 0.88
  cause: AnomalyCause; // 'Weather' | 'Sensor'
  faultType: AnomalyFaultType;
  severity: AnomalySeverity;
  confidence: number; // 0 - 100%
  status: 'Active' | 'Investigating' | 'Resolved';
  evidence: AnomalyEvidence;
}

export interface AlertRecord {
  id: string;
  stationId: string;
  stationName: string;
  timestamp: string;
  severity: AnomalySeverity;
  cause: AnomalyCause;
  anomalyType: AnomalyFaultType;
  anomalyScore: number;
  confidence: number;
  shortExplanation: string;
  isRead: boolean;
}

export interface StationSensorHealth {
  stationId: string;
  stationName: string;
  district: string;
  region: Region;
  overallHealth: number | null; // 0 - 100 or null if awaiting data
  temperatureChannel: ChannelStatus;
  temperatureScore: number;
  humidityChannel: ChannelStatus;
  humidityScore: number;
  pressureChannel: ChannelStatus;
  pressureScore: number;
  missingDataPct: number;
  driftDetected: boolean;
  neighbourAgreementPct: number;
  lastEvaluationTime: string;
}

export interface NetworkSummary {
  totalStations: number;
  healthyCount: number | null; // null if awaiting observation telemetry
  watchCount: number | null;   // null if awaiting observation telemetry
  criticalCount: number | null; // null if awaiting observation telemetry
  offlineCount: number;
  awaitingCount: number;
  dataQualityPct: number | null; // null if awaiting observation telemetry
  activeAnomalies: number;
  weatherEventsCount: number | null;
  sensorFaultsCount: number | null;
  reportingStationsCount: number;
  lastUpdated: string;
}

export interface ActivityEvent {
  id: string;
  time: string;
  stationId?: string;
  message: string;
  type: 'anomaly' | 'telemetry' | 'model' | 'network';
  severity?: AnomalySeverity;
}

export interface SimulationScenario {
  id: string;
  name: string;
  category: AnomalyCause;
  faultType: AnomalyFaultType;
  description: string;
  defaultSeverity: AnomalySeverity;
  affectedParameter: string;
}

export interface PipelineStep {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  summary?: string;
  details?: string[];
}

export interface SimulationResult {
  scenario: SimulationScenario;
  stationId: string;
  timestamp: string;
  observation: {
    temperatureC: number;
    humidityPct: number;
    pressureHpa: number;
  };
  featuresComputedCount: number;
  stage1AnomalyDetected: boolean;
  stage1Score: number;
  stage2Cause: AnomalyCause;
  stage2Confidence: number;
  rootCauseDetails: {
    faultComponent: string;
    evidenceType: string;
    summary: string;
  };
  sensorHealthImpact: {
    channel: string;
    previousScore: number;
    newScore: number;
    status: ChannelStatus;
  };
  seasonalEvidence: {
    baselineTemp: number;
    baselineHumidity: number;
    baselinePressure: number;
    tempDeviation: number;
    humidityDeviation: number;
    pressureDeviation: number;
    status: string;
  };
}

export interface DataQualityMetrics {
  totalObservationsExpected: number;
  missingObservationsCount: number;
  missingTempCount: number;
  missingHumidityCount: number;
  missingPressureCount: number;
  duplicateObservationsCount: number;
  outOfOrderTimestampsCount: number;
  invalidValuesCount: number;
  timestampGapsCount: number;
  overallQualityPct: number | null;
}

export interface ModelStatusInfo {
  stage1: {
    name: string;
    algorithm: string;
    status: string;
    version: string;
    featuresCount: number;
    trainingPeriod: string;
    evaluationPeriod: string;
    lastTrained: string;
    accuracy: string; // "Not available" if not from backend
    f1Score: string; // "Not available" if not from backend
  };
  stage2: {
    name: string;
    algorithm: string;
    status: string;
    version: string;
    featuresCount: number;
    trainingPeriod: string;
    evaluationPeriod: string;
    lastTrained: string;
    accuracy: string;
    f1Score: string;
  };
}

export type ActivePage =
  | 'overview'
  | 'network'
  | 'anomalies'
  | 'health'
  | 'monitoring'
  | 'reports'
  | 'settings'
  | 'simulator'
  | 'station-detail';
