import React from 'react';
import { AnomalyRecord } from '../../types';
import { CauseBadge, SeverityBadge } from '../common/Badges';
import {
  X,
  BrainCircuit,
  TrendingUp,
  MapPin,
  GitFork,
  ArrowRight,
  Info,
} from 'lucide-react';

interface AnomalyDetailModalProps {
  anomaly: AnomalyRecord | null;
  onClose: () => void;
  onViewStation?: (stationId: string) => void;
}

export const AnomalyDetailModal: React.FC<AnomalyDetailModalProps> = ({
  anomaly,
  onClose,
  onViewStation,
}) => {
  if (!anomaly) return null;

  const isSensor = anomaly.cause === 'Sensor';
  const { evidence } = anomaly;

  // Helper for rendering scientific evidence bars
  const renderEvidenceBar = (
    label: string,
    score: number,
    description: string,
    icon: React.ReactNode,
    barColor: string
  ) => {
    const percentage = Math.round(score * 100);

    return (
      <div className="bg-white/70 p-4 rounded-xl border border-slate-200/50 shadow-2xs">
        <div className="flex items-center justify-between gap-2 mb-2">
          <div className="flex items-center gap-1.5 font-semibold text-xs text-slate-900">
            {icon}
            <span>{label}</span>
          </div>
          <div className="font-mono text-xs font-semibold text-slate-800">
            {percentage}%
          </div>
        </div>

        {/* Progress meter */}
        <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${barColor}`}
            style={{ width: `${percentage}%` }}
          />
        </div>

        <p className="mt-2 text-[11px] text-slate-500 leading-relaxed">{description}</p>
      </div>
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/30 backdrop-blur-md overflow-y-auto">
      <div className="relative w-full max-w-2xl apple-glass-floating rounded-2xl shadow-[0_24px_50px_rgba(15,23,42,0.14)] border border-white/90 overflow-hidden my-8 animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="px-6 py-4.5 bg-white/60 border-b border-slate-200/50 flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-mono text-xs font-semibold text-slate-400">{anomaly.id}</span>
              <CauseBadge cause={anomaly.cause} />
              <SeverityBadge severity={anomaly.severity} />
            </div>
            <h2 className="text-xl font-bold text-slate-900 mt-1 tracking-tight">
              {anomaly.faultType} at {anomaly.stationName} ({anomaly.stationId})
            </h2>
            <div className="mt-1 flex items-center gap-2 text-xs text-slate-500">
              <span>{anomaly.timestamp} IST</span>
              <span>•</span>
              <span>{anomaly.region}</span>
              <span>•</span>
              <span className="font-mono font-medium text-slate-700">
                Confidence: {anomaly.confidence}%
              </span>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-full text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer"
            aria-label="Close modal"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-5 max-h-[75vh] overflow-y-auto">
          {/* Root Cause Diagnosis Banner */}
          <div
            className={`p-4 rounded-xl border ${
              isSensor
                ? 'bg-amber-500/10 border-amber-400/25 text-amber-950'
                : 'bg-sky-500/10 border-sky-400/25 text-sky-950'
            }`}
          >
            <div className="flex items-center gap-2 font-semibold text-xs mb-1">
              <BrainCircuit className="w-4 h-4 text-blue-600" />
              <span>
                {isSensor
                  ? 'Stage 2 Diagnosis: Detected Sensor Fault'
                  : 'Stage 2 Diagnosis: Genuine Regional Weather Event'}
              </span>
            </div>

            <div className="mt-2.5 grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
              <div className="p-2 bg-white/60 rounded-lg border border-slate-200/40">
                <div className="text-[10px] text-slate-400 uppercase font-medium">Classification</div>
                <div className="font-semibold text-slate-900 mt-0.5">
                  {isSensor ? 'Sensor Fault' : 'Weather Event'}
                </div>
              </div>
              <div className="p-2 bg-white/60 rounded-lg border border-slate-200/40">
                <div className="text-[10px] text-slate-400 uppercase font-medium">Affected Param</div>
                <div className="font-semibold text-slate-900 mt-0.5">{evidence.affectedParameter}</div>
              </div>
              <div className="p-2 bg-white/60 rounded-lg border border-slate-200/40">
                <div className="text-[10px] text-slate-400 uppercase font-medium">Fault Pattern</div>
                <div className="font-semibold text-slate-900 mt-0.5 truncate">{anomaly.faultType}</div>
              </div>
              <div className="p-2 bg-white/60 rounded-lg border border-slate-200/40">
                <div className="text-[10px] text-slate-400 uppercase font-medium">Anomaly Score</div>
                <div className="font-mono font-semibold text-slate-900 mt-0.5">{anomaly.anomalyScore.toFixed(2)}</div>
              </div>
            </div>

            {/* Core Differentiator Callout */}
            <div className="mt-3 pt-2.5 border-t border-slate-200/60 text-xs text-slate-700 leading-relaxed">
              <span className="font-semibold text-slate-900">Diagnostic Basis: </span>
              {isSensor ? (
                <span>
                  Neighbour disagreement confirms this anomaly is <strong>spatially isolated</strong> to {anomaly.stationName}. Adjacent AWS stations continue to record normal baseline telemetry.
                </span>
              ) : (
                <span>
                  Spatial coherence confirms this reading is part of a <strong>regional weather pattern</strong> simultaneously recorded by contiguous AWS stations across the {anomaly.region} cluster.
                </span>
              )}
            </div>
          </div>

          {/* Section: Why was this flagged? (Three Evidence Vectors) */}
          <div>
            <div className="flex items-center justify-between mb-2 px-0.5">
              <h3 className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
                Why was this flagged? Multi-Vector Evidence
              </h3>
              <span className="text-[11px] text-slate-400 font-mono">50 Model Inputs</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {renderEvidenceBar(
                'Temporal Evidence',
                evidence.temporalScore,
                'Analyzes 15m rate of change, rolling standard deviations, and lag differences against diurnal baselines.',
                <TrendingUp className="w-3.5 h-3.5 text-blue-600" />,
                'bg-blue-600'
              )}

              {renderEvidenceBar(
                'Spatial Evidence',
                evidence.spatialScore,
                'Compares target station against contiguous k-nearest neighbour stations across Andhra Pradesh.',
                <MapPin className="w-3.5 h-3.5 text-emerald-600" />,
                'bg-emerald-600'
              )}

              {renderEvidenceBar(
                'Multivariate Evidence',
                evidence.multivariateScore,
                'Evaluates psychrometric bounds (dewpoint deficit, hypsometric lapse rate, and VPD consistency).',
                <GitFork className="w-3.5 h-3.5 text-indigo-600" />,
                'bg-indigo-600'
              )}
            </div>
          </div>

          {/* Model Explanation Context */}
          <div className="bg-white/60 p-4 rounded-xl border border-slate-200/50">
            <h4 className="text-xs font-semibold text-slate-900 uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
              <Info className="w-3.5 h-3.5 text-blue-600" />
              <span>Synthesized ML Reasoning & Spatial Context</span>
            </h4>
            <p className="text-xs text-slate-600 leading-relaxed">{evidence.explanation}</p>

            <div className="mt-3 pt-2.5 border-t border-slate-200/50 grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
              <div>
                <span className="font-semibold text-slate-800">Spatial Agreement: </span>
                <span className="text-slate-600">{evidence.neighbourAgreementText}</span>
              </div>
              <div>
                <span className="font-semibold text-slate-800">Physical Consistency: </span>
                <span className="text-slate-600">{evidence.physicalConsistencyNote}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-4 bg-white/60 border-t border-slate-200/50 flex items-center justify-between gap-3">
          <span className="text-[11px] text-slate-400">
            SkyGuardAI Automated Decision Engine • Two-Stage ML Architecture
          </span>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-3.5 py-1.5 border border-slate-200 hover:bg-slate-100 text-slate-700 rounded-xl text-xs font-medium cursor-pointer transition-colors"
            >
              Dismiss
            </button>
            {onViewStation && (
              <button
                type="button"
                onClick={() => {
                  onViewStation(anomaly.stationId);
                  onClose();
                }}
                className="px-4 py-1.5 apple-btn-primary rounded-xl text-xs font-semibold cursor-pointer inline-flex items-center gap-1"
              >
                <span>Inspect {anomaly.stationId}</span>
                <ArrowRight className="w-3 h-3" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
