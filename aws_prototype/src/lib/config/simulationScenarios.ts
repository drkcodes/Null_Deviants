import { SimulationScenario } from '../../types';

/**
 * Simulator scenario definitions are UI configuration only.
 * The observation and ML prediction are supplied by the FastAPI backend.
 */
export const SIMULATION_SCENARIOS: SimulationScenario[] = [
  {
    id: 'scen-temp-spike',
    name: 'Temperature Spike (Sensor)',
    category: 'Sensor',
    faultType: 'Spike',
    description: 'Evaluate a benchmark observation representing an abrupt temperature sensor deviation.',
    defaultSeverity: 'High',
    affectedParameter: 'Temperature',
  },
  {
    id: 'scen-temp-drop',
    name: 'Temperature Sudden Drop (Sensor)',
    category: 'Sensor',
    faultType: 'Drop',
    description: 'Evaluate a benchmark observation representing a sudden temperature probe drop.',
    defaultSeverity: 'High',
    affectedParameter: 'Temperature',
  },
  {
    id: 'scen-freeze-stuck',
    name: 'Frozen / Stuck Sensor (Sensor)',
    category: 'Sensor',
    faultType: 'Freeze/Stuck',
    description: 'Evaluate a benchmark observation associated with repeated/stuck sensor values.',
    defaultSeverity: 'Medium',
    affectedParameter: 'Temperature / Humidity',
  },
  {
    id: 'scen-sensor-drift',
    name: 'Slow Sensor Drift (Sensor)',
    category: 'Sensor',
    faultType: 'Drift',
    description: 'Evaluate a benchmark observation associated with gradual calibration drift.',
    defaultSeverity: 'Medium',
    affectedParameter: 'Humidity / Pressure',
  },
  {
    id: 'scen-press-jump',
    name: 'Barometric Pressure Jump (Sensor)',
    category: 'Sensor',
    faultType: 'Pressure Jump',
    description: 'Evaluate a benchmark observation associated with an abrupt pressure transducer deviation.',
    defaultSeverity: 'Critical',
    affectedParameter: 'Pressure',
  },
  {
    id: 'scen-multivariate',
    name: 'Multivariate Inconsistency (Sensor)',
    category: 'Sensor',
    faultType: 'Multivariate Inconsistency',
    description: 'Evaluate a benchmark observation with inconsistent multivariate atmospheric relationships.',
    defaultSeverity: 'High',
    affectedParameter: 'Temperature + Humidity',
  },
  {
    id: 'scen-comm-fail',
    name: 'Communication / Telemetry Drop (Sensor)',
    category: 'Sensor',
    faultType: 'Communication Failure',
    description: 'Evaluate a benchmark observation associated with missing or interrupted telemetry.',
    defaultSeverity: 'Critical',
    affectedParameter: 'Telemetry Pipeline',
  },
  {
    id: 'scen-heatwave',
    name: 'Regional Heatwave (Genuine Weather)',
    category: 'Weather',
    faultType: 'Heatwave',
    description: 'Evaluate a benchmark observation representing a regionally coherent heat event.',
    defaultSeverity: 'Medium',
    affectedParameter: 'Regional Atmosphere',
  },
  {
    id: 'scen-cold-spell',
    name: 'Cold Spell / Winter Front (Genuine Weather)',
    category: 'Weather',
    faultType: 'Cold Spell',
    description: 'Evaluate a benchmark observation representing a regional cold event.',
    defaultSeverity: 'Low',
    affectedParameter: 'Regional Atmosphere',
  },
];
