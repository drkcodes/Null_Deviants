import React from 'react';
import { AnomalyRecord, NetworkSummary } from '../../types';
import { MetricCard } from '../common/MetricCard';
import { AnomalyTable } from './AnomalyTable';
import { AnomalyDetailModal } from './AnomalyDetailModal';
import {
  BrainCircuit,
  CloudSun,
  Wrench,
  ShieldAlert,
  ArrowRight,
  CheckCircle2,
  Cpu,
  Layers,
} from 'lucide-react';

interface AnomalyViewProps {
  anomalies: AnomalyRecord[];
  summary: NetworkSummary;
  selectedAnomaly: AnomalyRecord | null;
  onSelectAnomaly: (anomaly: AnomalyRecord | null) => void;
  onViewStation: (stationId: string) => void;
}

export const AnomalyView: React.FC<AnomalyViewProps> = ({
  anomalies,
  summary,
  selectedAnomaly,
  onSelectAnomaly,
  onViewStation,
}) => {
  const criticalCount = anomalies.filter((a) => a.severity === 'Critical').length;
  const weatherCount = anomalies.filter((a) => a.cause === 'Weather').length;
  const sensorCount = anomalies.filter((a) => a.cause === 'Sensor').length;

  return (
    <div className="space-y-6">
      {/* 14.1 Two-Stage Architecture Visual Pipeline (Scientific, Minimal, Elegant) */}
      <div className="apple-glass-card rounded-2xl p-5 sm:p-6 shadow-[0_8px_30px_rgba(15,23,42,0.04)]">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-slate-200/50">
          <div>
            <div className="flex items-center gap-2">
              <BrainCircuit className="w-4 h-4 text-blue-600" />
              <h2 className="text-sm font-semibold text-slate-900 tracking-tight">
                Two-Stage Hierarchical ML Architecture
              </h2>
            </div>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Decoupled anomaly detection followed by spatial-coherence root-cause attribution
            </p>
          </div>
          <span className="text-[10px] font-mono px-2.5 py-1 rounded-full bg-blue-500/10 text-blue-700 border border-blue-400/20 font-medium">
            Random Forest Ensembles
          </span>
        </div>

        {/* Visual Pipeline Flow */}
        <div className="mt-5 grid grid-cols-1 md:grid-cols-5 gap-3 items-center">
          {/* Step 1: Raw Observation */}
          <div className="p-3.5 rounded-xl bg-white/70 border border-slate-200/60 shadow-2xs text-center">
            <div className="text-[10px] uppercase font-semibold text-slate-400 tracking-wider">
              Telemetry Ingestion
            </div>
            <div className="text-xs font-bold text-slate-900 mt-1">Raw Observation</div>
            <div className="text-[10px] text-slate-500 mt-0.5">Temp, Hum, Press</div>
          </div>

          <div className="hidden md:flex justify-center text-slate-300">
            <ArrowRight className="w-4 h-4 text-blue-500" />
          </div>

          {/* Step 2: Stage 1 Gate */}
          <div className="p-3.5 rounded-xl bg-blue-500/10 border border-blue-400/25 shadow-2xs text-center">
            <div className="text-[10px] uppercase font-semibold text-blue-600 tracking-wider">
              Stage 1
            </div>
            <div className="text-xs font-bold text-slate-900 mt-1">Anomaly Detector</div>
            <div className="text-[10px] text-blue-700 mt-0.5 font-medium">
              Normal vs Anomalous
            </div>
          </div>

          <div className="hidden md:flex justify-center text-slate-300">
            <ArrowRight className="w-4 h-4 text-blue-500" />
          </div>

          {/* Step 3: Stage 2 Diagnosis */}
          <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-400/25 shadow-2xs text-center">
            <div className="text-[10px] uppercase font-semibold text-amber-700 tracking-wider">
              Stage 2
            </div>
            <div className="text-xs font-bold text-slate-900 mt-1">Attribution Engine</div>
            <div className="text-[10px] text-amber-800 mt-0.5 font-medium">
              Weather vs Sensor Fault
            </div>
          </div>
        </div>

        {/* Model Performance Validated Metrics */}
        <div className="mt-5 pt-4 border-t border-slate-200/50 grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Stage 1 Metrics */}
          <div className="p-3.5 rounded-xl bg-slate-50/60 border border-slate-200/50">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-900">
                Stage 1: Anomaly Detection
              </span>
              <span className="text-[11px] font-mono font-bold text-blue-600">96% Accuracy</span>
            </div>
            <div className="mt-2.5 grid grid-cols-3 gap-2 text-center text-xs">
              <div className="p-1.5 rounded-lg bg-white border border-slate-100">
                <div className="text-[10px] text-slate-400 uppercase font-medium">Precision</div>
                <div className="font-mono font-semibold text-slate-900 mt-0.5">71%</div>
              </div>
              <div className="p-1.5 rounded-lg bg-white border border-slate-100">
                <div className="text-[10px] text-slate-400 uppercase font-medium">Recall</div>
                <div className="font-mono font-semibold text-slate-900 mt-0.5">80%</div>
              </div>
              <div className="p-1.5 rounded-lg bg-white border border-slate-100">
                <div className="text-[10px] text-slate-400 uppercase font-medium">Anomaly F1</div>
                <div className="font-mono font-semibold text-blue-600 mt-0.5">75%</div>
              </div>
            </div>
          </div>

          {/* Stage 2 Metrics */}
          <div className="p-3.5 rounded-xl bg-slate-50/60 border border-slate-200/50">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-900">
                Stage 2: Weather vs Sensor Fault
              </span>
              <span className="text-[11px] font-mono font-bold text-amber-700">93% Accuracy</span>
            </div>
            <div className="mt-2.5 grid grid-cols-2 gap-2 text-center text-xs">
              <div className="p-1.5 rounded-lg bg-white border border-slate-100">
                <div className="text-[10px] text-slate-400 uppercase font-medium">Sensor F1</div>
                <div className="font-mono font-semibold text-slate-900 mt-0.5">86%</div>
              </div>
              <div className="p-1.5 rounded-lg bg-white border border-slate-100">
                <div className="text-[10px] text-slate-400 uppercase font-medium">Weather F1</div>
                <div className="font-mono font-semibold text-sky-700 mt-0.5">96%</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <MetricCard
          label="Total Anomalies"
          value={anomalies.length}
          subtitle="Identified by Stage 1 gate"
          icon={<BrainCircuit className="w-4 h-4 text-blue-600" />}
          indicatorColor="blue"
        />
        <MetricCard
          label="Weather Events"
          value={weatherCount}
          subtitle="Spatially coherent events"
          icon={<CloudSun className="w-4 h-4 text-sky-600" />}
          indicatorColor="blue"
        />
        <MetricCard
          label="Sensor Faults"
          value={sensorCount}
          subtitle="Spatially isolated failures"
          icon={<Wrench className="w-4 h-4 text-amber-700" />}
          indicatorColor="amber"
        />
        <MetricCard
          label="Critical Severity"
          value={criticalCount}
          subtitle="Immediate dispatch priority"
          icon={<ShieldAlert className="w-4 h-4 text-rose-600" />}
          indicatorColor="rose"
        />
      </div>

      {/* Interactive Anomaly Table */}
      <AnomalyTable anomalies={anomalies} onSelectAnomaly={onSelectAnomaly} />

      {/* Detail Investigation Modal */}
      <AnomalyDetailModal
        anomaly={selectedAnomaly}
        onClose={() => onSelectAnomaly(null)}
        onViewStation={onViewStation}
      />
    </div>
  );
};
