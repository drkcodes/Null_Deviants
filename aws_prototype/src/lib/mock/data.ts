import {
  Station,
  AnomalyRecord,
  AlertRecord,
  StationSensorHealth,
  NetworkSummary,
  ActivityEvent,
  SimulationScenario,
  DataQualityMetrics,
  ModelStatusInfo,
  TelemetryPoint,
} from '../../types';

export const MOCK_STATIONS: Station[] = [
  // Coastal (12 Stations)
  {
    id: 'AWS-AP-01',
    name: 'Visakhapatnam',
    district: 'Visakhapatnam',
    region: 'Coastal',
    latitude: 17.6868,
    longitude: 83.2185,
    elevationM: 45,
    neighbours: ['AWS-AP-09', 'AWS-AP-08', 'AWS-AP-04'],
    status: 'Healthy',
    healthScore: 97,
    lastObservationTime: '2025-06-14 14:45',
    telemetry: { temperatureC: 32.4, humidityPct: 76, pressureHpa: 1008.2 },
    activeAnomaliesCount: 0,
  },
  {
    id: 'AWS-AP-02',
    name: 'Vijayawada',
    district: 'NTR Krishna',
    region: 'Coastal',
    latitude: 16.5062,
    longitude: 80.648,
    elevationM: 23,
    neighbours: ['AWS-AP-03', 'AWS-AP-12', 'AWS-AP-11', 'AWS-AP-06'],
    status: 'Watch',
    healthScore: 84,
    lastObservationTime: '2025-06-14 14:45',
    telemetry: { temperatureC: 41.2, humidityPct: 48, pressureHpa: 1004.5 },
    activeAnomaliesCount: 1,
    latestAnomaly: {
      type: 'Heatwave',
      cause: 'Weather',
      confidence: 89,
      timestamp: '2025-06-14 14:30',
    },
  },
  {
    id: 'AWS-AP-03',
    name: 'Guntur',
    district: 'Guntur',
    region: 'Coastal',
    latitude: 16.3067,
    longitude: 80.4365,
    elevationM: 31,
    neighbours: ['AWS-AP-02', 'AWS-AP-11', 'AWS-AP-10'],
    status: 'Watch',
    healthScore: 82,
    lastObservationTime: '2025-06-14 14:45',
    telemetry: { temperatureC: 41.6, humidityPct: 46, pressureHpa: 1004.2 },
    activeAnomaliesCount: 1,
    latestAnomaly: {
      type: 'Heatwave',
      cause: 'Weather',
      confidence: 91,
      timestamp: '2025-06-14 14:30',
    },
  },
  {
    id: 'AWS-AP-04',
    name: 'Kakinada',
    district: 'Kakinada',
    region: 'Coastal',
    latitude: 16.9891,
    longitude: 82.2475,
    elevationM: 10,
    neighbours: ['AWS-AP-05', 'AWS-AP-01', 'AWS-AP-12'],
    status: 'Healthy',
    healthScore: 94,
    lastObservationTime: '2025-06-14 14:45',
    telemetry: { temperatureC: 33.8, humidityPct: 72, pressureHpa: 1007.4 },
    activeAnomaliesCount: 0,
  },
  {
    id: 'AWS-AP-05',
    name: 'Rajahmundry',
    district: 'East Godavari',
    region: 'Coastal',
    latitude: 17.0005,
    longitude: 81.804,
    elevationM: 14,
    neighbours: ['AWS-AP-04', 'AWS-AP-12', 'AWS-AP-02'],
    status: 'Healthy',
    healthScore: 96,
    lastObservationTime: '2025-06-14 14:45',
    telemetry: { temperatureC: 36.5, humidityPct: 62, pressureHpa: 1006.1 },
    activeAnomaliesCount: 0,
  },
  {
    id: 'AWS-AP-06',
    name: 'Machilipatnam',
    district: 'Krishna',
    region: 'Coastal',
    latitude: 16.1875,
    longitude: 81.1389,
    elevationM: 8,
    neighbours: ['AWS-AP-02', 'AWS-AP-11', 'AWS-AP-07'],
    status: 'Healthy',
    healthScore: 92,
    lastObservationTime: '2025-06-14 14:45',
    telemetry: { temperatureC: 32.1, humidityPct: 81, pressureHpa: 1008.9 },
    activeAnomaliesCount: 0,
  },
  {
    id: 'AWS-AP-07',
    name: 'Nellore',
    district: 'SPSR Nellore',
    region: 'Coastal',
    latitude: 14.4426,
    longitude: 79.9865,
    elevationM: 19,
    neighbours: ['AWS-AP-10', 'AWS-AP-13', 'AWS-AP-06'],
    status: 'Critical',
    healthScore: 48,
    lastObservationTime: '2025-06-14 14:45',
    telemetry: { temperatureC: 49.8, humidityPct: 68, pressureHpa: 1007.0 },
    activeAnomaliesCount: 2,
    latestAnomaly: {
      type: 'Spike',
      cause: 'Sensor',
      confidence: 94,
      timestamp: '2025-06-14 14:35',
    },
  },
  {
    id: 'AWS-AP-08',
    name: 'Srikakulam',
    district: 'Srikakulam',
    region: 'Coastal',
    latitude: 18.2969,
    longitude: 83.8967,
    elevationM: 10,
    neighbours: ['AWS-AP-09', 'AWS-AP-01'],
    status: 'Healthy',
    healthScore: 98,
    lastObservationTime: '2025-06-14 14:45',
    telemetry: { temperatureC: 31.9, humidityPct: 78, pressureHpa: 1008.5 },
    activeAnomaliesCount: 0,
  },
  {
    id: 'AWS-AP-09',
    name: 'Vizianagaram',
    district: 'Vizianagaram',
    region: 'Coastal',
    latitude: 18.1067,
    longitude: 83.3956,
    elevationM: 66,
    neighbours: ['AWS-AP-08', 'AWS-AP-01'],
    status: 'Healthy',
    healthScore: 95,
    lastObservationTime: '2025-06-14 14:45',
    telemetry: { temperatureC: 33.1, humidityPct: 74, pressureHpa: 1007.8 },
    activeAnomaliesCount: 0,
  },
  {
    id: 'AWS-AP-10',
    name: 'Ongole',
    district: 'Prakasam',
    region: 'Coastal',
    latitude: 15.5057,
    longitude: 80.0499,
    elevationM: 24,
    neighbours: ['AWS-AP-11', 'AWS-AP-07', 'AWS-AP-03'],
    status: 'Healthy',
    healthScore: 91,
    lastObservationTime: '2025-06-14 14:45',
    telemetry: { temperatureC: 35.7, humidityPct: 66, pressureHpa: 1006.8 },
    activeAnomaliesCount: 0,
  },
  {
    id: 'AWS-AP-11',
    name: 'Bapatla',
    district: 'Bapatla',
    region: 'Coastal',
    latitude: 15.9042,
    longitude: 80.4674,
    elevationM: 6,
    neighbours: ['AWS-AP-03', 'AWS-AP-02', 'AWS-AP-10', 'AWS-AP-06'],
    status: 'Healthy',
    healthScore: 93,
    lastObservationTime: '2025-06-14 14:45',
    telemetry: { temperatureC: 34.0, humidityPct: 75, pressureHpa: 1008.0 },
    activeAnomaliesCount: 0,
  },
  {
    id: 'AWS-AP-12',
    name: 'Eluru',
    district: 'Eluru',
    region: 'Coastal',
    latitude: 16.7107,
    longitude: 81.0952,
    elevationM: 22,
    neighbours: ['AWS-AP-02', 'AWS-AP-05', 'AWS-AP-04'],
    status: 'Watch',
    healthScore: 78,
    lastObservationTime: '2025-06-14 14:45',
    telemetry: { temperatureC: 36.2, humidityPct: 15.0, pressureHpa: 1006.0 },
    activeAnomaliesCount: 1,
    latestAnomaly: {
      type: 'Drop',
      cause: 'Sensor',
      confidence: 88,
      timestamp: '2025-06-14 14:15',
    },
  },

  // Rayalaseema (8 Stations)
  {
    id: 'AWS-AP-13',
    name: 'Tirupati',
    district: 'Tirupati',
    region: 'Rayalaseema',
    latitude: 13.6288,
    longitude: 79.4192,
    elevationM: 161,
    neighbours: ['AWS-AP-18', 'AWS-AP-07', 'AWS-AP-16'],
    status: 'Healthy',
    healthScore: 95,
    lastObservationTime: '2025-06-14 14:45',
    telemetry: { temperatureC: 36.8, humidityPct: 52, pressureHpa: 991.4 },
    activeAnomaliesCount: 0,
  },
  {
    id: 'AWS-AP-14',
    name: 'Kurnool',
    district: 'Kurnool',
    region: 'Rayalaseema',
    latitude: 15.8281,
    longitude: 78.0373,
    elevationM: 273,
    neighbours: ['AWS-AP-17', 'AWS-AP-15'],
    status: 'Watch',
    healthScore: 81,
    lastObservationTime: '2025-06-14 14:45',
    telemetry: { temperatureC: 42.1, humidityPct: 34, pressureHpa: 978.6 },
    activeAnomaliesCount: 1,
    latestAnomaly: {
      type: 'Heatwave',
      cause: 'Weather',
      confidence: 93,
      timestamp: '2025-06-14 14:00',
    },
  },
  {
    id: 'AWS-AP-15',
    name: 'Anantapur',
    district: 'Ananthapuramu',
    region: 'Rayalaseema',
    latitude: 14.6819,
    longitude: 77.6006,
    elevationM: 335,
    neighbours: ['AWS-AP-14', 'AWS-AP-16', 'AWS-AP-20'],
    status: 'Critical',
    healthScore: 52,
    lastObservationTime: '2025-06-14 14:45',
    telemetry: { temperatureC: 38.0, humidityPct: 42, pressureHpa: 940.2 },
    activeAnomaliesCount: 1,
    latestAnomaly: {
      type: 'Pressure Jump',
      cause: 'Sensor',
      confidence: 96,
      timestamp: '2025-06-14 13:45',
    },
  },
  {
    id: 'AWS-AP-16',
    name: 'Kadapa',
    district: 'YSR Kadapa',
    region: 'Rayalaseema',
    latitude: 14.4673,
    longitude: 78.8242,
    elevationM: 138,
    neighbours: ['AWS-AP-17', 'AWS-AP-15', 'AWS-AP-19', 'AWS-AP-13'],
    status: 'Healthy',
    healthScore: 92,
    lastObservationTime: '2025-06-14 14:45',
    telemetry: { temperatureC: 40.5, humidityPct: 39, pressureHpa: 994.5 },
    activeAnomaliesCount: 0,
  },
  {
    id: 'AWS-AP-17',
    name: 'Nandyal',
    district: 'Nandyal',
    region: 'Rayalaseema',
    latitude: 15.4883,
    longitude: 78.4832,
    elevationM: 203,
    neighbours: ['AWS-AP-14', 'AWS-AP-16'],
    status: 'Watch',
    healthScore: 83,
    lastObservationTime: '2025-06-14 14:45',
    telemetry: { temperatureC: 41.8, humidityPct: 35, pressureHpa: 986.2 },
    activeAnomaliesCount: 1,
    latestAnomaly: {
      type: 'Heatwave',
      cause: 'Weather',
      confidence: 90,
      timestamp: '2025-06-14 14:00',
    },
  },
  {
    id: 'AWS-AP-18',
    name: 'Chittoor',
    district: 'Chittoor',
    region: 'Rayalaseema',
    latitude: 13.2172,
    longitude: 79.1003,
    elevationM: 315,
    neighbours: ['AWS-AP-13', 'AWS-AP-19'],
    status: 'Healthy',
    healthScore: 94,
    lastObservationTime: '2025-06-14 14:45',
    telemetry: { temperatureC: 35.6, humidityPct: 54, pressureHpa: 974.1 },
    activeAnomaliesCount: 0,
  },
  {
    id: 'AWS-AP-19',
    name: 'Madanapalle',
    district: 'Annamayya',
    region: 'Rayalaseema',
    latitude: 13.556,
    longitude: 78.501,
    elevationM: 695,
    neighbours: ['AWS-AP-18', 'AWS-AP-20', 'AWS-AP-16'],
    status: 'Watch',
    healthScore: 76,
    lastObservationTime: '2025-06-14 14:45',
    telemetry: { temperatureC: 32.0, humidityPct: 60, pressureHpa: 932.0 },
    activeAnomaliesCount: 1,
    latestAnomaly: {
      type: 'Freeze/Stuck',
      cause: 'Sensor',
      confidence: 91,
      timestamp: '2025-06-14 12:30',
    },
  },
  {
    id: 'AWS-AP-20',
    name: 'Hindupur',
    district: 'Sri Sathya Sai',
    region: 'Rayalaseema',
    latitude: 13.829,
    longitude: 77.4919,
    elevationM: 621,
    neighbours: ['AWS-AP-15', 'AWS-AP-19'],
    status: 'Offline',
    healthScore: 35,
    lastObservationTime: '2025-06-14 11:30',
    telemetry: { temperatureC: 33.4, humidityPct: 50, pressureHpa: 941.0 },
    activeAnomaliesCount: 1,
    latestAnomaly: {
      type: 'Communication Failure',
      cause: 'Sensor',
      confidence: 99,
      timestamp: '2025-06-14 11:30',
    },
  },
];

export const MOCK_NETWORK_SUMMARY: NetworkSummary = {
  totalStations: 20,
  healthyCount: 11,
  watchCount: 6,
  criticalCount: 2,
  awaitingCount: 0,
  reportingStationsCount: 19,
  offlineCount: 1,
  dataQualityPct: 98.4,
  activeAnomalies: 8,
  weatherEventsCount: 4,
  sensorFaultsCount: 4,
  lastUpdated: '2025-06-14 14:45:00 UTC+5:30',
};

export const MOCK_ANOMALIES: AnomalyRecord[] = [
  {
    id: 'ANO-2025-0812',
    stationId: 'AWS-AP-07',
    stationName: 'Nellore',
    region: 'Coastal',
    timestamp: '2025-06-14 14:35',
    anomalyScore: 0.94,
    cause: 'Sensor',
    faultType: 'Spike',
    severity: 'High',
    confidence: 92,
    status: 'Active',
    evidence: {
      temporalScore: 0.91,
      spatialScore: 0.96,
      multivariateScore: 0.84,
      explanation:
        'Temperature spiked suddenly by +16.2°C within two 15-min intervals while all 3 neighbouring stations (Ongole, Tirupati, Machilipatnam) recorded 32–36°C with 0.1°C stability.',
      neighbourAgreementText:
        'Neighbours strongly disagree (spatial divergence z-score = +4.8σ).',
      affectedParameter: 'Temperature',
      physicalConsistencyNote:
        'Multivariate check failed: Rapid temperature spike occurred without expected relative humidity drop or pressure dip.',
    },
  },
  {
    id: 'ANO-2025-0811',
    stationId: 'AWS-AP-15',
    stationName: 'Anantapur',
    region: 'Rayalaseema',
    timestamp: '2025-06-14 13:45',
    anomalyScore: 0.96,
    cause: 'Sensor',
    faultType: 'Pressure Jump',
    severity: 'Critical',
    confidence: 96,
    status: 'Active',
    evidence: {
      temporalScore: 0.95,
      spatialScore: 0.98,
      multivariateScore: 0.79,
      explanation:
        'Barometric pressure stepped down by 38.4 hPa discontinuously. Neighbouring stations Kurnool and Kadapa recorded normal barometric gradients aligned with regional sea-level patterns.',
      neighbourAgreementText:
        'Neighbouring stations report barometric pressure within expected elevation-adjusted limits.',
      affectedParameter: 'Pressure',
      physicalConsistencyNote:
        'A 38 hPa pressure drop without gale-force winds or cyclonic disturbance is physically invalid.',
    },
  },
  {
    id: 'ANO-2025-0810',
    stationId: 'AWS-AP-02',
    stationName: 'Vijayawada',
    region: 'Coastal',
    timestamp: '2025-06-14 14:30',
    anomalyScore: 0.86,
    cause: 'Weather',
    faultType: 'Heatwave',
    severity: 'Medium',
    confidence: 89,
    status: 'Active',
    evidence: {
      temporalScore: 0.65,
      spatialScore: 0.15,
      multivariateScore: 0.22,
      explanation:
        'Observed temperature 41.2°C is abnormally elevated for season baseline, but closely matched by contiguous stations Guntur (41.6°C), Bapatla (34.0°C coastal breeze boundary), and Rajahmundry (36.5°C).',
      neighbourAgreementText:
        'Strong spatial agreement across Krishna/Guntur belt (spatial coherence = 0.85). Regional heatwave pattern confirmed.',
      affectedParameter: 'Temperature',
      physicalConsistencyNote:
        'Relative humidity correctly lowered to 48%, consistent with solar heating and dry land breeze advection.',
    },
  },
  {
    id: 'ANO-2025-0809',
    stationId: 'AWS-AP-03',
    stationName: 'Guntur',
    region: 'Coastal',
    timestamp: '2025-06-14 14:30',
    anomalyScore: 0.88,
    cause: 'Weather',
    faultType: 'Heatwave',
    severity: 'Medium',
    confidence: 91,
    status: 'Active',
    evidence: {
      temporalScore: 0.68,
      spatialScore: 0.12,
      multivariateScore: 0.18,
      explanation:
        'Temperature of 41.6°C exceeds 95th percentile historical threshold. High spatial coherence with Vijayawada (+41.2°C).',
      neighbourAgreementText:
        'Neighbouring stations confirm regional heat wave conditions across Coastal AP.',
      affectedParameter: 'Temperature',
      physicalConsistencyNote:
        'Consistent thermodynamic relationship between temperature and relative humidity depression.',
    },
  },
  {
    id: 'ANO-2025-0808',
    stationId: 'AWS-AP-14',
    stationName: 'Kurnool',
    region: 'Rayalaseema',
    timestamp: '2025-06-14 14:00',
    anomalyScore: 0.89,
    cause: 'Weather',
    faultType: 'Heatwave',
    severity: 'Medium',
    confidence: 93,
    status: 'Active',
    evidence: {
      temporalScore: 0.72,
      spatialScore: 0.18,
      multivariateScore: 0.25,
      explanation:
        'Rayalaseema inland high-temperature event. 42.1°C observed, confirmed by Nandyal station recording 41.8°C.',
      neighbourAgreementText:
        'Spatial agreement confirmed across upper Rayalaseema basin stations.',
      affectedParameter: 'Temperature',
      physicalConsistencyNote:
        'Consistent with regional synoptic pattern and clear sky radiation.',
    },
  },
  {
    id: 'ANO-2025-0807',
    stationId: 'AWS-AP-17',
    stationName: 'Nandyal',
    region: 'Rayalaseema',
    timestamp: '2025-06-14 14:00',
    anomalyScore: 0.85,
    cause: 'Weather',
    faultType: 'Heatwave',
    severity: 'Medium',
    confidence: 90,
    status: 'Active',
    evidence: {
      temporalScore: 0.7,
      spatialScore: 0.19,
      multivariateScore: 0.2,
      explanation:
        'Sustained temperature 41.8°C. Synchronous rise with Kurnool (42.1°C).',
      neighbourAgreementText:
        'Spatial coherence high with adjacent station AWS-AP-14.',
      affectedParameter: 'Temperature',
      physicalConsistencyNote:
        'Normal physical relationship with surface air mass characteristics.',
    },
  },
  {
    id: 'ANO-2025-0806',
    stationId: 'AWS-AP-19',
    stationName: 'Madanapalle',
    region: 'Rayalaseema',
    timestamp: '2025-06-14 12:30',
    anomalyScore: 0.87,
    cause: 'Sensor',
    faultType: 'Freeze/Stuck',
    severity: 'Medium',
    confidence: 91,
    status: 'Active',
    evidence: {
      temporalScore: 0.88,
      spatialScore: 0.75,
      multivariateScore: 0.81,
      explanation:
        'Temperature sensor reading remained exactly invariant at 32.000°C for 16 consecutive 15-minute cycles (4 hours) despite changing solar angle.',
      neighbourAgreementText:
        'Neighbours Chittoor and Tirupati demonstrated normal diurnal bell curves.',
      affectedParameter: 'Temperature',
      physicalConsistencyNote:
        'Variance across consecutive steps is zero (zero entropy sensor freeze failure).',
    },
  },
  {
    id: 'ANO-2025-0805',
    stationId: 'AWS-AP-12',
    stationName: 'Eluru',
    region: 'Coastal',
    timestamp: '2025-06-14 14:15',
    anomalyScore: 0.83,
    cause: 'Sensor',
    faultType: 'Drop',
    severity: 'Low',
    confidence: 88,
    status: 'Active',
    evidence: {
      temporalScore: 0.82,
      spatialScore: 0.85,
      multivariateScore: 0.72,
      explanation:
        'Relative humidity suddenly dropped to 15.0% while temperature remained 36.2°C in a coastal humid delta zone.',
      neighbourAgreementText:
        'Surrounding stations Vijayawada and Rajahmundry report 48% and 62% RH.',
      affectedParameter: 'Humidity',
      physicalConsistencyNote:
        'RH drop does not correspond to dewpoint psychrometric boundaries.',
    },
  },
  {
    id: 'ANO-2025-0804',
    stationId: 'AWS-AP-20',
    stationName: 'Hindupur',
    region: 'Rayalaseema',
    timestamp: '2025-06-14 11:30',
    anomalyScore: 0.99,
    cause: 'Sensor',
    faultType: 'Communication Failure',
    severity: 'Critical',
    confidence: 99,
    status: 'Active',
    evidence: {
      temporalScore: 0.99,
      spatialScore: 0.5,
      multivariateScore: 0.99,
      explanation:
        'Data telemetry stream interrupted. 13 consecutive expected observation intervals missed without transmission packet reception.',
      neighbourAgreementText:
        'Station communication link unresponsive; adjacent telemetry towers operating normally.',
      affectedParameter: 'Communication',
      physicalConsistencyNote:
        'Packet sequence timeout detected on GPRS/satellite modem interface.',
    },
  },
];

export const MOCK_ALERTS: AlertRecord[] = [
  {
    id: 'ALT-101',
    stationId: 'AWS-AP-07',
    stationName: 'Nellore',
    timestamp: '2025-06-14 14:35',
    severity: 'High',
    cause: 'Sensor',
    anomalyType: 'Spike',
    anomalyScore: 0.94,
    confidence: 92,
    shortExplanation:
      'Isolated temperature spike (+16.2°C). Neighbours disagree strongly.',
    isRead: false,
  },
  {
    id: 'ALT-102',
    stationId: 'AWS-AP-15',
    stationName: 'Anantapur',
    timestamp: '2025-06-14 13:45',
    severity: 'Critical',
    cause: 'Sensor',
    anomalyType: 'Pressure Jump',
    anomalyScore: 0.96,
    confidence: 96,
    shortExplanation:
      'Discontinuous barometric drop (-38.4 hPa). Physically implausible jump.',
    isRead: false,
  },
  {
    id: 'ALT-103',
    stationId: 'AWS-AP-02',
    stationName: 'Vijayawada',
    timestamp: '2025-06-14 14:30',
    severity: 'Medium',
    cause: 'Weather',
    anomalyType: 'Heatwave',
    anomalyScore: 0.86,
    confidence: 89,
    shortExplanation:
      'Regional temperature elevation (41.2°C). High coherence with Guntur.',
    isRead: true,
  },
  {
    id: 'ALT-104',
    stationId: 'AWS-AP-20',
    stationName: 'Hindupur',
    timestamp: '2025-06-14 11:30',
    severity: 'Critical',
    cause: 'Sensor',
    anomalyType: 'Communication Failure',
    anomalyScore: 0.99,
    confidence: 99,
    shortExplanation:
      'Telemetry stream offline >3 hours. No packets received.',
    isRead: false,
  },
];

export const MOCK_SENSOR_HEALTH: StationSensorHealth[] = MOCK_STATIONS.map(
  (station) => {
    let tempChannel: 'Normal' | 'Degraded' | 'Suspected fault' = 'Normal';
    let tempScore = 96;
    let humChannel: 'Normal' | 'Degraded' | 'Suspected fault' = 'Normal';
    let humScore = 95;
    let pressChannel: 'Normal' | 'Degraded' | 'Suspected fault' = 'Normal';
    let pressScore = 97;
    let missingPct = 0.4;
    let drift = false;
    let neighbourAgreement = 94;

    if (station.id === 'AWS-AP-07') {
      tempChannel = 'Suspected fault';
      tempScore = 32;
      neighbourAgreement = 46;
      drift = true;
    } else if (station.id === 'AWS-AP-15') {
      pressChannel = 'Suspected fault';
      pressScore = 28;
      neighbourAgreement = 52;
    } else if (station.id === 'AWS-AP-12') {
      humChannel = 'Degraded';
      humScore = 64;
      drift = true;
      neighbourAgreement = 71;
    } else if (station.id === 'AWS-AP-19') {
      tempChannel = 'Degraded';
      tempScore = 58;
      neighbourAgreement = 68;
    } else if (station.id === 'AWS-AP-20') {
      tempChannel = 'Suspected fault';
      humChannel = 'Suspected fault';
      pressChannel = 'Suspected fault';
      tempScore = 20;
      humScore = 20;
      pressScore = 20;
      missingPct = 12.8;
      neighbourAgreement = 0;
    }

    return {
      stationId: station.id,
      stationName: station.name,
      district: station.district,
      region: station.region,
      overallHealth: station.healthScore,
      temperatureChannel: tempChannel,
      temperatureScore: tempScore,
      humidityChannel: humChannel,
      humidityScore: humScore,
      pressureChannel: pressChannel,
      pressureScore: pressScore,
      missingDataPct: missingPct,
      driftDetected: drift,
      neighbourAgreementPct: neighbourAgreement,
      lastEvaluationTime: '2025-06-14 14:45',
    };
  },
);

export const MOCK_ACTIVITY_EVENTS: ActivityEvent[] = [
  {
    id: 'ACT-01',
    time: '14:45',
    stationId: 'AWS-AP-07',
    message: 'AWS-AP-07 telemetry received & Stage 1 anomaly flagged',
    type: 'anomaly',
    severity: 'High',
  },
  {
    id: 'ACT-02',
    time: '14:35',
    stationId: 'AWS-AP-07',
    message:
      'Stage 2 classified AWS-AP-07 as Sensor Fault (Confidence: 92%)',
    type: 'model',
    severity: 'High',
  },
  {
    id: 'ACT-03',
    time: '14:30',
    stationId: 'AWS-AP-02',
    message:
      'Regional Heatwave cluster identified across AWS-AP-02 & AWS-AP-03',
    type: 'anomaly',
    severity: 'Medium',
  },
  {
    id: 'ACT-04',
    time: '14:24',
    message: 'Full network model inference batch completed (20 stations)',
    type: 'model',
  },
  {
    id: 'ACT-05',
    time: '14:15',
    stationId: 'AWS-AP-12',
    message: 'AWS-AP-12 relative humidity sensor degradation alert raised',
    type: 'anomaly',
    severity: 'Low',
  },
  {
    id: 'ACT-06',
    time: '13:45',
    stationId: 'AWS-AP-15',
    message: 'AWS-AP-15 barometric pressure discontinuous step detected',
    type: 'anomaly',
    severity: 'Critical',
  },
  {
    id: 'ACT-07',
    time: '13:00',
    message: 'Network health index updated: 11 Healthy, 6 Watch, 2 Critical, 1 Offline',
    type: 'network',
  },
];

export const MOCK_SIMULATION_SCENARIOS: SimulationScenario[] = [
  {
    id: 'scen-temp-spike',
    name: 'Temperature Spike (Sensor)',
    category: 'Sensor',
    faultType: 'Spike',
    description:
      'Simulate an instantaneous unphysical temperature leap (+15°C) while neighbours remain stable.',
    defaultSeverity: 'High',
    affectedParameter: 'Temperature',
  },
  {
    id: 'scen-temp-drop',
    name: 'Temperature Sudden Drop (Sensor)',
    category: 'Sensor',
    faultType: 'Drop',
    description:
      'Simulate a sudden probe circuit drop (-20°C) without synoptic weather frontal movement.',
    defaultSeverity: 'High',
    affectedParameter: 'Temperature',
  },
  {
    id: 'scen-freeze-stuck',
    name: 'Frozen / Stuck Sensor (Sensor)',
    category: 'Sensor',
    faultType: 'Freeze/Stuck',
    description:
      'Simulate ADC quantization lock: output values repeat identically across multiple 15-minute cycles.',
    defaultSeverity: 'Medium',
    affectedParameter: 'Temperature / Humidity',
  },
  {
    id: 'scen-sensor-drift',
    name: 'Slow Sensor Drift (Sensor)',
    category: 'Sensor',
    faultType: 'Drift',
    description:
      'Simulate gradual calibration drift over time, diverging steadily from nearest spatial neighbours.',
    defaultSeverity: 'Medium',
    affectedParameter: 'Humidity / Pressure',
  },
  {
    id: 'scen-press-jump',
    name: 'Barometric Pressure Jump (Sensor)',
    category: 'Sensor',
    faultType: 'Pressure Jump',
    description:
      'Simulate diaphragm transducer failure causing an abrupt +35 hPa or -35 hPa jump.',
    defaultSeverity: 'Critical',
    affectedParameter: 'Pressure',
  },
  {
    id: 'scen-multivariate',
    name: 'Multivariate Inconsistency (Sensor)',
    category: 'Sensor',
    faultType: 'Multivariate Inconsistency',
    description:
      'Simulate physically impossible combination: 45°C temperature paired with 99% RH at sea level.',
    defaultSeverity: 'High',
    affectedParameter: 'Temperature + Humidity',
  },
  {
    id: 'scen-comm-fail',
    name: 'Communication / Telemetry Drop (Sensor)',
    category: 'Sensor',
    faultType: 'Communication Failure',
    description:
      'Simulate modem loss resulting in consecutive missing timestamps and null telemetry bursts.',
    defaultSeverity: 'Critical',
    affectedParameter: 'Telemetry Pipeline',
  },
  {
    id: 'scen-heatwave',
    name: 'Regional Heatwave (Genuine Weather)',
    category: 'Weather',
    faultType: 'Heatwave',
    description:
      'Simulate severe synoptic heatwave: target station and all surrounding neighbours elevate coherently.',
    defaultSeverity: 'Medium',
    affectedParameter: 'Regional Atmosphere',
  },
  {
    id: 'scen-cold-spell',
    name: 'Cold Spell / Winter Front (Genuine Weather)',
    category: 'Weather',
    faultType: 'Cold Spell',
    description:
      'Simulate widespread cold air incursion across multiple Rayalaseema districts.',
    defaultSeverity: 'Low',
    affectedParameter: 'Regional Atmosphere',
  },
];

export const MOCK_DATA_QUALITY: DataQualityMetrics = {
  totalObservationsExpected: 700800,
  missingObservationsCount: 4210,
  missingTempCount: 680,
  missingHumidityCount: 940,
  missingPressureCount: 710,
  duplicateObservationsCount: 124,
  outOfOrderTimestampsCount: 18,
  invalidValuesCount: 205,
  timestampGapsCount: 88,
  overallQualityPct: 98.4,
};

export const MOCK_MODEL_STATUS: ModelStatusInfo = {
  stage1: {
    name: 'Stage 1: Anomaly Detection',
    algorithm: 'Random Forest Classifier / Isolation Forest Ensemble',
    status: 'Available & Active',
    version: 'v1.4.0-AP-AWS',
    featuresCount: 67,
    trainingPeriod: 'Synthetic 2025 Jan-Jun (350,400 observations)',
    evaluationPeriod: 'Synthetic 2025 Jul-Dec (350,400 observations)',
    lastTrained: '2025-06-01 00:00:00 UTC',
    accuracy: 'Not available',
    f1Score: 'Not available',
  },
  stage2: {
    name: 'Stage 2: Weather vs Sensor Classification',
    algorithm: 'Spatial-Temporal Random Forest (Weather vs Sensor Fault)',
    status: 'Available & Active',
    version: 'v1.4.0-AP-AWS',
    featuresCount: 67,
    trainingPeriod: 'Synthetic 2025 Jan-Jun (350,400 observations)',
    evaluationPeriod: 'Synthetic 2025 Jul-Dec (350,400 observations)',
    lastTrained: '2025-06-01 00:00:00 UTC',
    accuracy: 'Not available',
    f1Score: 'Not available',
  },
};

export const FEATURE_GROUPS = [
  {
    name: 'Raw Telemetry',
    count: 3,
    description: 'Instantaneous sensor outputs from AWS acquisition bus',
    features: ['temperature_c', 'relative_humidity_pct', 'pressure_hpa'],
  },
  {
    name: 'Temporal Lags & Deltas',
    count: 12,
    description: 'Time-lagged differences across recent sampling intervals',
    features: [
      'temp_diff_15m',
      'temp_diff_1h',
      'temp_diff_3h',
      'rh_diff_15m',
      'rh_diff_1h',
      'pressure_diff_15m',
      'pressure_diff_3h',
      'rate_of_change_temp',
      'rate_of_change_rh',
      'rate_of_change_pressure',
      'lag_1',
      'lag_2',
    ],
  },
  {
    name: 'Rolling Window Statistics',
    count: 14,
    description: 'Mean, standard deviation, min, max across 1h, 6h, 24h',
    features: [
      'rolling_mean_temp_1h',
      'rolling_std_temp_1h',
      'rolling_mean_temp_6h',
      'rolling_std_temp_6h',
      'rolling_mean_rh_1h',
      'rolling_std_rh_1h',
      'rolling_mean_pressure_1h',
      'rolling_std_pressure_1h',
      'rolling_min_temp_24h',
      'rolling_max_temp_24h',
      'rolling_range_temp_24h',
      'rolling_range_rh_24h',
      'rolling_range_pressure_24h',
      'window_skewness',
    ],
  },
  {
    name: 'Z-Scores & Dispersion',
    count: 8,
    description: 'Standardized deviations relative to station historical baseline',
    features: [
      'z_score_temp_station',
      'z_score_temp_hourly_climatology',
      'z_score_rh_station',
      'z_score_pressure_station',
      'mad_dispersion_temp',
      'mad_dispersion_rh',
      'iqr_outlier_score_temp',
      'iqr_outlier_score_pressure',
    ],
  },
  {
    name: 'Sensor Stuck Indicators',
    count: 6,
    description: 'Zero-variance entropy counters and repeat value detectors',
    features: [
      'stuck_count_temp',
      'stuck_count_rh',
      'stuck_count_pressure',
      'temp_consecutive_identical',
      'rh_consecutive_identical',
      'quantization_step_entropy',
    ],
  },
  {
    name: 'Physical Consistency (Multivariate)',
    count: 8,
    description: 'Thermodynamic bounds and cross-variable correlations',
    features: [
      'dewpoint_c',
      'dewpoint_depression',
      'vapor_pressure_deficit',
      'temp_rh_correlation_window',
      'barometric_hypsometric_residual',
      'superheated_vapor_flag',
      'supersaturation_check',
      'lapse_rate_deviation',
    ],
  },
  {
    name: 'Spatial & Neighbor Features',
    count: 10,
    description: 'Cross-station distances, neighbor means, spatial deltas',
    features: [
      'nearest_neighbour_mean_temp',
      'nearest_neighbour_delta_temp',
      'neighbour_temp_zscore',
      'nearest_neighbour_mean_rh',
      'nearest_neighbour_delta_rh',
      'nearest_neighbour_mean_pressure',
      'neighbour_pressure_gradient',
      'spatial_inconsistency_metric',
      'cluster_variance_ratio',
      'spatial_k_nearest_agreement',
    ],
  },
  {
    name: 'Regional Context',
    count: 6,
    description: 'Coastal vs Rayalaseema topography and regional cluster metrics',
    features: [
      'region_coastal_flag',
      'region_rayalaseema_flag',
      'elevation_m',
      'distance_to_coastline_km',
      'regional_mean_temp',
      'regional_mean_pressure',
    ],
  },
];

// Helper to generate 24h telemetry series for a station
export function generateTimeSeriesData(
  stationId: string,
  hours: number = 24,
): TelemetryPoint[] {
  const station =
    MOCK_STATIONS.find((s) => s.id === stationId) || MOCK_STATIONS[0];
  const points: TelemetryPoint[] = [];

  const baseTemp = station.telemetry.temperatureC;
  const baseHum = station.telemetry.humidityPct;
  const basePress = station.telemetry.pressureHpa;

  const now = new Date('2025-06-14T14:45:00Z');

  for (let i = hours * 4; i >= 0; i--) {
    const time = new Date(now.getTime() - i * 15 * 60 * 1000);
    const hourOfDay = time.getUTCHours() + 5.5; // Indian Standard Time approx

    // Diurnal variation sine curve
    const diurnalFactor = Math.sin(((hourOfDay - 9) / 24) * 2 * Math.PI);
    const tempVariation = diurnalFactor * 4.5;
    const humVariation = -diurnalFactor * 14;

    let temp = Math.round((baseTemp + tempVariation + (Math.random() * 0.4 - 0.2)) * 10) / 10;
    let hum = Math.round(Math.max(10, Math.min(100, baseHum + humVariation + (Math.random() * 1.5 - 0.75))));
    let press = Math.round((basePress + Math.cos(((hourOfDay - 3) / 24) * 2 * Math.PI) * 1.8 + (Math.random() * 0.2 - 0.1)) * 10) / 10;

    let isAnomaly = false;
    let anomalyType: any = undefined;
    let anomalyCause: any = undefined;

    // Inject historical anomaly if it matches station's state
    if (station.id === 'AWS-AP-07' && i <= 8 && i >= 1) {
      temp += 14.5;
      isAnomaly = true;
      anomalyType = 'Spike';
      anomalyCause = 'Sensor';
    } else if (station.id === 'AWS-AP-02' && i <= 16 && i >= 4) {
      temp += 4.8;
      isAnomaly = true;
      anomalyType = 'Heatwave';
      anomalyCause = 'Weather';
    } else if (station.id === 'AWS-AP-15' && i <= 6) {
      press -= 38.0;
      isAnomaly = true;
      anomalyType = 'Pressure Jump';
      anomalyCause = 'Sensor';
    } else if (station.id === 'AWS-AP-19' && i <= 16 && i >= 0) {
      temp = 32.0; // frozen
      if (i <= 10) {
        isAnomaly = true;
        anomalyType = 'Freeze/Stuck';
        anomalyCause = 'Sensor';
      }
    }

    points.push({
      timestamp: time.toISOString().substring(11, 16),
      stationId,
      temperatureC: temp,
      humidityPct: hum,
      pressureHpa: press,
      isAnomaly,
      anomalyType,
      anomalyCause,
    });
  }

  return points;
}

export const STATION_NOMINAL_BASELINES: Record<string, { temperatureC: number; humidityPct: number; pressureHpa: number }> = {
  'AWS-AP-01': { temperatureC: 32.4, humidityPct: 76, pressureHpa: 1008.2 },
  'AWS-AP-02': { temperatureC: 33.0, humidityPct: 68, pressureHpa: 1006.0 },
  'AWS-AP-03': { temperatureC: 33.2, humidityPct: 67, pressureHpa: 1006.0 },
  'AWS-AP-04': { temperatureC: 33.8, humidityPct: 72, pressureHpa: 1007.4 },
  'AWS-AP-05': { temperatureC: 34.5, humidityPct: 65, pressureHpa: 1006.1 },
  'AWS-AP-06': { temperatureC: 32.1, humidityPct: 81, pressureHpa: 1008.9 },
  'AWS-AP-07': { temperatureC: 32.5, humidityPct: 70, pressureHpa: 1008.0 },
  'AWS-AP-08': { temperatureC: 31.9, humidityPct: 78, pressureHpa: 1008.5 },
  'AWS-AP-09': { temperatureC: 33.1, humidityPct: 74, pressureHpa: 1007.8 },
  'AWS-AP-10': { temperatureC: 33.5, humidityPct: 70, pressureHpa: 1006.8 },
  'AWS-AP-11': { temperatureC: 34.0, humidityPct: 75, pressureHpa: 1008.0 },
  'AWS-AP-12': { temperatureC: 32.8, humidityPct: 73, pressureHpa: 1008.1 },
  'AWS-AP-13': { temperatureC: 34.2, humidityPct: 60, pressureHpa: 991.4 },
  'AWS-AP-14': { temperatureC: 35.0, humidityPct: 58, pressureHpa: 978.6 },
  'AWS-AP-15': { temperatureC: 35.5, humidityPct: 55, pressureHpa: 1009.2 },
  'AWS-AP-16': { temperatureC: 35.0, humidityPct: 56, pressureHpa: 994.5 },
  'AWS-AP-17': { temperatureC: 34.8, humidityPct: 60, pressureHpa: 1006.9 },
  'AWS-AP-18': { temperatureC: 34.5, humidityPct: 62, pressureHpa: 1007.8 },
  'AWS-AP-19': { temperatureC: 33.5, humidityPct: 65, pressureHpa: 1008.0 },
  'AWS-AP-20': { temperatureC: 34.2, humidityPct: 68, pressureHpa: 1007.5 },
};

