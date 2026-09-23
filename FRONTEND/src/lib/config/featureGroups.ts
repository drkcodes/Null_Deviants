export interface FeatureGroup {
  name: string;
  count: number;
  description: string;
  features: string[];
}

/**
 * Authoritative feature groups matching the 50 inputs used by the trained
 * Random Forest models in the FastAPI backend.
 *
 * These are UI metadata, not telemetry/mock observations.
 */
export const FEATURE_GROUPS: FeatureGroup[] = [
  {
    name: 'Raw Telemetry',
    count: 3,
    description: 'Instantaneous Automatic Weather Station sensor outputs.',
    features: ['temperature_c', 'relative_humidity_pct', 'pressure_hpa'],
  },
  {
    name: 'Temporal Lags & Rates',
    count: 15,
    description: 'Recent lagged observations and rates of change.',
    features: [
      'temperature_lag_15min',
      'temperature_lag_1h',
      'temperature_lag_3h',
      'temperature_roc_15min',
      'temperature_roc_1h',
      'humidity_lag_15min',
      'humidity_lag_1h',
      'humidity_lag_3h',
      'humidity_roc_15min',
      'humidity_roc_1h',
      'pressure_lag_15min',
      'pressure_lag_1h',
      'pressure_lag_3h',
      'pressure_roc_15min',
      'pressure_roc_1h',
    ],
  },
  {
    name: 'Rolling Window Statistics',
    count: 12,
    description: '1-hour and 6-hour rolling means and standard deviations.',
    features: [
      'temperature_rollmean_1h',
      'temperature_rollstd_1h',
      'temperature_rollmean_6h',
      'temperature_rollstd_6h',
      'humidity_rollmean_1h',
      'humidity_rollstd_1h',
      'humidity_rollmean_6h',
      'humidity_rollstd_6h',
      'pressure_rollmean_1h',
      'pressure_rollstd_1h',
      'pressure_rollmean_6h',
      'pressure_rollstd_6h',
    ],
  },
  {
    name: 'Z-Scores & Dispersion',
    count: 3,
    description: 'Six-hour standardized deviations for temperature, humidity, and pressure.',
    features: [
      'temperature_zscore_6h',
      'humidity_zscore_6h',
      'pressure_zscore_6h',
    ],
  },
  {
    name: 'Sensor Stuck Indicators',
    count: 3,
    description: 'Repeat-value counters used to identify potentially stuck channels.',
    features: [
      'temperature_stuck_count',
      'humidity_stuck_count',
      'pressure_stuck_count',
    ],
  },
  {
    name: 'Physical Consistency',
    count: 2,
    description: 'Psychrometric and physical-plausibility checks.',
    features: [
      'dew_point_deficit_c',
      'physically_implausible_flag',
    ],
  },
  {
    name: 'Spatial & Regional Context',
    count: 4,
    description: 'Cross-station divergence and regional temperature context.',
    features: [
      'spatial_temp_diff',
      'spatial_humidity_diff',
      'spatial_pressure_diff',
      'regional_temp_zscore',
    ],
  },
  {
    name: 'Missingness & Timestamp Quality',
    count: 5,
    description: 'Missing-channel and telemetry timestamp continuity indicators.',
    features: [
      'is_missing_temperature',
      'is_missing_humidity',
      'is_missing_pressure',
      'timestamp_gap_seconds',
      'timestamp_gap_flag',
    ],
  },
  {
    name: '24-Hour Baseline Deviations',
    count: 3,
    description: 'Deviation from each station’s 24-hour lagged baseline.',
    features: [
      'temperature_dev_24h',
      'humidity_dev_24h',
      'pressure_dev_24h',
    ],
  },
];
