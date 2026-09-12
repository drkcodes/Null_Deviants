import React, { useState } from 'react';
import { DataQualityMetrics, ModelStatusInfo } from '../../types';
import {
  Database,
  Cpu,
  BrainCircuit,
  FileCheck,
  Layers,
  Sparkles,
  Info,
  CheckCircle2,
  TrendingUp,
} from 'lucide-react';


const FEATURE_GROUPS = [
  { name: 'Raw Telemetry', count: 3, description: 'Instantaneous sensor outputs from AWS acquisition bus', features: ['temperature_c', 'relative_humidity_pct', 'pressure_hpa'] },
  { name: 'Temporal Lags & Deltas', count: 12, description: 'Time-lagged differences across recent sampling intervals', features: ['temperature_lag_15min', 'temperature_lag_1h', 'temperature_lag_3h', 'temperature_roc_15min', 'temperature_roc_1h', 'humidity_lag_15min', 'humidity_lag_1h', 'humidity_lag_3h', 'humidity_roc_15min', 'humidity_roc_1h', 'pressure_lag_15min', 'pressure_lag_1h'] },
  { name: 'Rolling Window Statistics', count: 14, description: 'Mean and standard deviation across 1h and 6h windows', features: ['temperature_rollmean_1h', 'temperature_rollstd_1h', 'temperature_rollmean_6h', 'temperature_rollstd_6h', 'humidity_rollmean_1h', 'humidity_rollstd_1h', 'humidity_rollmean_6h', 'humidity_rollstd_6h', 'pressure_rollmean_1h', 'pressure_rollstd_1h', 'pressure_rollmean_6h', 'pressure_rollstd_6h', 'temperature_dev_24h', 'pressure_dev_24h'] },
  { name: 'Z-Scores & Dispersion', count: 8, description: 'Standardized deviations relative to station historical baseline', features: ['temperature_zscore_6h', 'humidity_zscore_6h', 'pressure_zscore_6h', 'temperature_dev_24h', 'humidity_dev_24h', 'pressure_dev_24h', 'temperature_rollstd_6h', 'pressure_rollstd_6h'] },
  { name: 'Sensor Stuck Indicators', count: 6, description: 'Repeat-value and zero-variance indicators for sensor channels', features: ['temperature_stuck_count', 'humidity_stuck_count', 'pressure_stuck_count', 'is_missing_temperature', 'is_missing_humidity', 'is_missing_pressure'] },
  { name: 'Physical Consistency (Multivariate)', count: 8, description: 'Thermodynamic and cross-variable consistency checks', features: ['dew_point_deficit_c', 'physically_implausible_flag', 'temperature_roc_15min', 'humidity_roc_15min', 'pressure_roc_15min', 'temperature_zscore_6h', 'humidity_zscore_6h', 'pressure_zscore_6h'] },
  { name: 'Spatial & Neighbor Features', count: 10, description: 'Cross-station differences and spatial consistency signals', features: ['spatial_temp_diff', 'spatial_humidity_diff', 'spatial_pressure_diff', 'regional_temp_zscore', 'timestamp_gap_seconds', 'timestamp_gap_flag', 'regional_temp_zscore', 'spatial_temp_diff', 'spatial_humidity_diff', 'spatial_pressure_diff'] },
  { name: 'Regional Context', count: 6, description: 'Regional and climatological context used by the inference pipeline', features: ['regional_temp_zscore', 'temperature_dev_24h', 'humidity_dev_24h', 'pressure_dev_24h', 'timestamp_gap_seconds', 'timestamp_gap_flag'] },
];

interface DataMonitoringViewProps {
  quality: DataQualityMetrics;
  modelStatus: ModelStatusInfo;
}

export const DataMonitoringView: React.FC<DataMonitoringViewProps> = ({
  quality,
  modelStatus,
}) => {
  const q = quality;

  const [selectedFeatureGroup, setSelectedFeatureGroup] = useState<string>(
    FEATURE_GROUPS && FEATURE_GROUPS[0] ? FEATURE_GROUPS[0].name : 'Raw Telemetry',
  );

  const activeGroup =
    (FEATURE_GROUPS && FEATURE_GROUPS.find((g) => g?.name === selectedFeatureGroup)) ||
    (FEATURE_GROUPS && FEATURE_GROUPS[0]) ||
    { name: '', count: 0, description: '', features: [] };

  const stage1TopFeatures = [
    { name: 'temperature_rollmean_6h', importance: 0.090028, role: '6-hour rolling mean of station temperature' },
    { name: 'temperature_c', importance: 0.071977, role: 'Current station temperature' },
    { name: 'temperature_rollmean_1h', importance: 0.063326, role: '1-hour rolling mean of station temperature' },
    { name: 'temperature_lag_15min', importance: 0.059715, role: 'Temperature observed 15 minutes earlier' },
    { name: 'temperature_lag_3h', importance: 0.053477, role: 'Temperature observed 3 hours earlier' },
  ];

  const stage2TopFeatures = [
    { name: 'pressure_dev_24h', importance: 0.097109, role: "Deviation from the station's 24-hour lagged pressure" },
    { name: 'temperature_rollmean_6h', importance: 0.062712, role: '6-hour rolling mean of station temperature' },
    { name: 'pressure_rollstd_6h', importance: 0.053437, role: '6-hour rolling standard deviation of station pressure' },
    { name: 'dew_point_deficit_c', importance: 0.050667, role: 'Estimated difference between temperature and dew point' },
    { name: 'temperature_lag_3h', importance: 0.045824, role: 'Temperature observed 3 hours earlier' },
  ];

  const maxStage1Importance = Math.max(...stage1TopFeatures.map(f => f.importance));
  const maxStage2Importance = Math.max(...stage2TopFeatures.map(f => f.importance));

  return (
    <div className="space-y-6">
      {/* 1. Dataset Overview Card */}
      <div className="apple-glass-card rounded-2xl p-6 shadow-[0_8px_30px_rgba(15,23,42,0.04)]">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-200/50">
          <div>
            <div className="flex items-center gap-2">
              <Database className="w-4 h-4 text-blue-600" />
              <h2 className="text-base font-semibold text-slate-900 tracking-tight">
                Dataset Corpus Specifications
              </h2>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              Standardized telemetry dataset designed for Automatic Weather Station anomaly detection and diagnosis across Andhra Pradesh.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-blue-500/10 text-blue-700 border border-blue-400/20">
              Synthetic Benchmark Dataset
            </span>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 text-xs">
          <div className="p-3.5 bg-white/70 rounded-xl border border-slate-200/50">
            <span className="text-[10px] text-slate-400 uppercase font-medium">Total Observations</span>
            <div className="text-xl font-semibold font-mono text-slate-900 mt-1">700,800</div>
            <div className="text-[10px] text-slate-500 mt-0.5">Year 2025 corpus</div>
          </div>

          <div className="p-3.5 bg-white/70 rounded-xl border border-slate-200/50">
            <span className="text-[10px] text-slate-400 uppercase font-medium">Station Fleet</span>
            <div className="text-xl font-semibold font-mono text-slate-900 mt-1">20 Stations</div>
            <div className="text-[10px] text-slate-500 mt-0.5">12 Coastal, 8 Rayalaseema</div>
          </div>

          <div className="p-3.5 bg-white/70 rounded-xl border border-slate-200/50">
            <span className="text-[10px] text-slate-400 uppercase font-medium">Sampling Cadence</span>
            <div className="text-xl font-semibold font-mono text-slate-900 mt-1">15-Minute</div>
            <div className="text-[10px] text-slate-500 mt-0.5">96 samples/day/station</div>
          </div>

          <div className="p-3.5 bg-white/70 rounded-xl border border-slate-200/50">
            <span className="text-[10px] text-slate-400 uppercase font-medium">Samples Per Station</span>
            <div className="text-xl font-semibold font-mono text-slate-900 mt-1">35,040</div>
            <div className="text-[10px] text-slate-500 mt-0.5">Aligned timestamps</div>
          </div>

          <div className="p-3.5 bg-white/70 rounded-xl border border-slate-200/50">
            <span className="text-[10px] text-slate-400 uppercase font-medium">67 Allowed Features</span>
            <div className="text-xl font-semibold font-mono text-blue-600 mt-1">67 Features</div>
            <div className="text-[10px] text-slate-500 mt-0.5">50 model inputs (post-engineering)</div>
          </div>
        </div>
        <div className="mt-3 p-3 bg-blue-50/60 rounded-xl border border-blue-100 text-xs text-blue-900 flex items-start gap-2">
          <Info className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold">Pipeline & Model Inputs:</span> 67 features are available in the feature-engineering pipeline; 50 post-engineering features are used by the trained Random Forest models. Ground-truth and target fields are excluded from model inputs.
          </div>
        </div>
      </div>

      {/* 2. Model Status: Stage 1 and Stage 2 Ensembles */}
      <div className="apple-glass-card rounded-2xl p-6 shadow-[0_8px_30px_rgba(15,23,42,0.04)]">
        <div className="pb-4 border-b border-slate-200/50 mb-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Cpu className="w-4 h-4 text-blue-600" />
              <h3 className="text-base font-semibold text-slate-900 tracking-tight">
                Production Model Status & Evaluation
              </h3>
            </div>
            <span className="text-[11px] font-mono text-slate-500 bg-slate-100 px-2.5 py-1 rounded-lg">
              Feature pipeline: 67 allowed features → feature engineering → 50 model inputs → Random Forest inference
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Two-stage Random Forest classifier architecture validated against test observations
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {/* Stage 1 */}
          <div className="p-4 rounded-xl border border-slate-200/60 bg-white/70 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                <div>
                  <span className="text-[10px] uppercase font-semibold text-blue-600 tracking-wider">
                    Gate 1
                  </span>
                  <div className="font-semibold text-sm text-slate-900">Stage 1: Anomaly Detection</div>
                </div>
                <span className="px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-800 border border-emerald-400/20">
                  Random Forest
                </span>
              </div>

              <div className="mt-3 grid grid-cols-2 gap-3 text-xs">
                <div className="p-2.5 bg-slate-50/70 rounded-lg border border-slate-100">
                  <span className="text-[10px] uppercase text-slate-400 font-medium">Accuracy</span>
                  <div className="text-lg font-mono font-semibold text-slate-900 mt-0.5">95.88%</div>
                  <div className="text-[10px] text-slate-500">Holdout validation</div>
                </div>
                <div className="p-2.5 bg-slate-50/70 rounded-lg border border-slate-100">
                  <span className="text-[10px] uppercase text-slate-400 font-medium">Anomaly F1 Score</span>
                  <div className="text-lg font-mono font-semibold text-blue-600 mt-0.5">75.37%</div>
                  <div className="text-[10px] text-slate-500">Prec 71.07% · Rec 80.23%</div>
                </div>
              </div>
            </div>
            <div className="mt-3 pt-2 border-t border-slate-100 text-[11px] text-slate-500">
              Evaluated on a chronological holdout from Nov 1–Dec 31, 2025 (117,120 test observations; 9,204 actual anomalies).
            </div>
          </div>

          {/* Stage 2 */}
          <div className="p-4 rounded-xl border border-slate-200/60 bg-white/70 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                <div>
                  <span className="text-[10px] uppercase font-semibold text-amber-700 tracking-wider">
                    Gate 2
                  </span>
                  <div className="font-semibold text-sm text-slate-900">
                    Stage 2: Weather vs Sensor Fault
                  </div>
                </div>
                <span className="px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-800 border border-emerald-400/20">
                  Random Forest
                </span>
              </div>

              <div className="mt-3 grid grid-cols-3 gap-2.5 text-xs">
                <div className="p-2.5 bg-slate-50/70 rounded-lg border border-slate-100">
                  <span className="text-[10px] uppercase text-slate-400 font-medium">Accuracy</span>
                  <div className="text-lg font-mono font-semibold text-slate-900 mt-0.5">93.49%</div>
                  <div className="text-[10px] text-slate-500">Multivariate</div>
                </div>
                <div className="p-2.5 bg-slate-50/70 rounded-lg border border-slate-100">
                  <span className="text-[10px] uppercase text-slate-400 font-medium">Sensor F1</span>
                  <div className="text-lg font-mono font-semibold text-amber-800 mt-0.5">86%</div>
                  <div className="text-[10px] text-slate-500">Isolated drift</div>
                </div>
                <div className="p-2.5 bg-slate-50/70 rounded-lg border border-slate-100">
                  <span className="text-[10px] uppercase text-slate-400 font-medium">Weather F1</span>
                  <div className="text-lg font-mono font-semibold text-sky-700 mt-0.5">96%</div>
                  <div className="text-[10px] text-slate-500">Spatial sync</div>
                </div>
              </div>
            </div>
            <div className="mt-3 pt-2 border-t border-slate-100 text-[11px] text-slate-500">
              Evaluated on anomalies identified within the held-out test period (9,204 anomaly observations).
            </div>
          </div>
        </div>
      </div>

      {/* 3. Top Features Breakdown (Stage 1 and Stage 2) */}
      <div className="apple-glass-card rounded-2xl p-6 shadow-[0_8px_30px_rgba(15,23,42,0.04)]">
        <div className="pb-4 border-b border-slate-200/50 mb-4">
          <div className="flex items-center gap-2">
            <BrainCircuit className="w-4 h-4 text-blue-600" />
            <h3 className="text-base font-semibold text-slate-900 tracking-tight">
              Top Predictive Features (Gini Importance)
            </h3>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Feature importance derived from Random Forest impurity (Gini) importance
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Stage 1 Top Features */}
          <div className="p-4 rounded-xl border border-slate-200/60 bg-white/70">
            <div className="font-semibold text-xs text-slate-900 mb-3 flex items-center justify-between">
              <span>Stage 1: Anomaly Detection Top Features</span>
              <span className="text-[11px] font-mono text-slate-400">Gini Importance %</span>
            </div>

            <div className="space-y-3">
              {stage1TopFeatures.map((feat) => {
                const pct = feat.importance * 100;
                const barWidth = (feat.importance / maxStage1Importance) * 100;
                return (
                  <div key={feat.name} className="text-xs">
                    <div className="flex items-center justify-between font-mono text-slate-800 mb-1">
                      <span className="font-semibold text-slate-900">{feat.name}</span>
                      <span className="text-slate-600">{pct.toFixed(2)}%</span>
                    </div>
                    <div className="w-full bg-slate-100 h-1.5 rounded-full overflow-hidden">
                      <div
                        className="bg-blue-600 h-full rounded-full transition-all duration-300"
                        style={{ width: `${barWidth}%` }}
                      />
                    </div>
                    <span className="text-[10px] text-slate-400 mt-0.5 block">{feat.role}</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Stage 2 Top Features */}
          <div className="p-4 rounded-xl border border-slate-200/60 bg-white/70">
            <div className="font-semibold text-xs text-slate-900 mb-3 flex items-center justify-between">
              <span>Stage 2: Weather vs Sensor Top Features</span>
              <span className="text-[11px] font-mono text-slate-400">Gini Importance %</span>
            </div>

            <div className="space-y-3">
              {stage2TopFeatures.map((feat) => {
                const pct = feat.importance * 100;
                const barWidth = (feat.importance / maxStage2Importance) * 100;
                return (
                  <div key={feat.name} className="text-xs">
                    <div className="flex items-center justify-between font-mono text-slate-800 mb-1">
                      <span className="font-semibold text-slate-900">{feat.name}</span>
                      <span className="text-slate-600">{pct.toFixed(2)}%</span>
                    </div>
                    <div className="w-full bg-slate-100 h-1.5 rounded-full overflow-hidden">
                      <div
                        className="bg-amber-600 h-full rounded-full transition-all duration-300"
                        style={{ width: `${barWidth}%` }}
                      />
                    </div>
                    <span className="text-[10px] text-slate-400 mt-0.5 block">{feat.role}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* 4. Dataset Quality Baseline */}
      <div className="apple-glass-card rounded-2xl p-6 shadow-[0_8px_30px_rgba(15,23,42,0.04)]">
        <div className="flex items-center justify-between pb-3 border-b border-slate-200/50 mb-4">
          <div>
            <div className="flex items-center gap-2">
              <FileCheck className="w-4 h-4 text-emerald-600" />
              <h3 className="text-base font-semibold text-slate-900 tracking-tight">
                Dataset Quality Baseline
              </h3>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Automated validation against null fields, out-of-order packets, duplicates, and physical limits
            </p>
          </div>
          <div className="text-xs text-right">
            <span className="text-slate-500 font-medium">Overall Integrity: </span>
            <span className="font-mono font-semibold text-slate-800 text-sm">
              {q.overallQualityPct !== null ? `${q.overallQualityPct}%` : 'Awaiting data'}
            </span>
          </div>
        </div>
        <div className="mb-4 p-3 bg-slate-50 rounded-xl border border-slate-200/60 text-xs text-slate-700 flex items-center gap-2">
          <Info className="w-4 h-4 text-slate-500 shrink-0" />
          <span>Static validation statistics from the synthetic benchmark dataset; not live station telemetry.</span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
          <div className="p-3 border border-slate-200/60 rounded-xl bg-white/70">
            <span className="text-slate-500 font-medium">Missing Obs Intervals</span>
            <div className="font-mono font-semibold text-slate-900 text-base mt-1">
              {q.missingObservationsCount.toLocaleString()}
            </div>
            <span className="text-[10px] text-slate-400">0.6% of dataset</span>
          </div>

          <div className="p-3 border border-slate-200/60 rounded-xl bg-white/70">
            <span className="text-slate-500 font-medium">Missing Temp Fields</span>
            <div className="font-mono font-semibold text-slate-900 text-base mt-1">
              {q.missingTempCount.toLocaleString()}
            </div>
            <span className="text-[10px] text-slate-400">Sensor null packets</span>
          </div>

          <div className="p-3 border border-slate-200/60 rounded-xl bg-white/70">
            <span className="text-slate-500 font-medium">Missing Humidity Fields</span>
            <div className="font-mono font-semibold text-slate-900 text-base mt-1">
              {q.missingHumidityCount.toLocaleString()}
            </div>
            <span className="text-[10px] text-slate-400">Probe dropouts</span>
          </div>

          <div className="p-3 border border-slate-200/60 rounded-xl bg-white/70">
            <span className="text-slate-500 font-medium">Duplicate Observations</span>
            <div className="font-mono font-semibold text-slate-900 text-base mt-1">
              {q.duplicateObservationsCount}
            </div>
            <span className="text-[10px] text-slate-400">GPRS retransmissions</span>
          </div>
        </div>
      </div>

      {/* 5. Feature Groups Breakdown (67 Allowed Features) */}
      <div className="apple-glass-card rounded-2xl p-6 shadow-[0_8px_30px_rgba(15,23,42,0.04)]">
        <div className="pb-3 border-b border-slate-200/50 mb-4">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-blue-600" />
            <h3 className="text-base font-semibold text-slate-900 tracking-tight">
              Engineered Feature Families (67 Allowed Features)
            </h3>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            67 features are available in the feature-engineering pipeline; 50 post-engineering features are used by the trained Random Forest models. Ground-truth and target fields are excluded from model inputs.
          </p>
        </div>

        {/* Group Selector Pills */}
        <div className="flex flex-wrap gap-2 mb-4">
          {FEATURE_GROUPS.map((group) => (
            <button
              key={group.name}
              type="button"
              onClick={() => setSelectedFeatureGroup(group.name)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium cursor-pointer transition-all border ${
                selectedFeatureGroup === group.name
                  ? 'bg-blue-600 text-white border-blue-600 font-semibold shadow-2xs'
                  : 'bg-white/70 text-slate-700 border-slate-200/80 hover:bg-slate-100'
              }`}
            >
              <span>{group.name}</span>
              <span className="ml-1.5 text-[10px] opacity-75 font-mono">({group.count})</span>
            </button>
          ))}
        </div>

        {/* Active Group Details */}
        <div className="p-4 rounded-xl bg-white/70 border border-slate-200/60">
          <div className="flex items-center justify-between mb-2">
            <h4 className="font-semibold text-sm text-slate-900">{activeGroup.name}</h4>
            <span className="text-xs font-mono text-slate-500">
              {activeGroup.features.length} feature variables
            </span>
          </div>
          <p className="text-xs text-slate-600 mb-3 leading-relaxed">{activeGroup.description}</p>

          <div className="flex flex-wrap gap-2">
            {activeGroup.features.map((feat) => (
              <span
                key={feat}
                className="px-2.5 py-1 rounded-lg bg-slate-50 border border-slate-200/70 font-mono text-xs text-slate-800"
              >
                {feat}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
