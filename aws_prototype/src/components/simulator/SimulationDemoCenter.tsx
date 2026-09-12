import React, { useState } from 'react';
import { Station, SimulationScenario, SimulationResult } from '../../types';
import { stationService } from '../../lib/api/stationService';
import { CauseBadge, SeverityBadge, ChannelBadge } from '../common/Badges';
import {
  FlaskConical,
  Play,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  BrainCircuit,
  Cpu,
  Layers,
  ShieldCheck,
  Radio,
  FileCheck,
} from 'lucide-react';

interface SimulationDemoCenterProps {
  stations: Station[];
  scenarios: SimulationScenario[];
  onViewStationDetails?: (stationId: string) => void;
}

export const SimulationDemoCenter: React.FC<SimulationDemoCenterProps> = ({
  stations,
  scenarios,
  onViewStationDetails,
}) => {
  const [selectedStationId, setSelectedStationId] = useState<string>(stations[6]?.id || 'AWS-AP-07'); // Default to Nellore
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>(scenarios[0]?.id || 'scen-temp-spike');
  const [intensity, setIntensity] = useState<number>(85);
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [activeStepIndex, setActiveStepIndex] = useState<number>(-1);
  const [simResult, setSimResult] = useState<SimulationResult | null>(null);

  const selectedStation = stations.find((s) => s.id === selectedStationId) || stations[0];
  const selectedScenario = scenarios.find((s) => s.id === selectedScenarioId) || scenarios[0];

  if (!selectedStation || !selectedScenario) {
    return <div className="p-8 text-center text-slate-500 text-sm">Simulation configuration is unavailable because the SkyGuardAI backend data has not loaded.</div>;
  }

  const pipelineSteps = [
    {
      id: 'step-1',
      name: 'Benchmark Observation',
      desc: 'Loads a real benchmark observation',
    },
    {
      id: 'step-2',
      name: 'Feature Engineering',
      desc: 'Uses 50 model inputs from the 67-feature engineering pipeline',
    },
    {
      id: 'step-3',
      name: 'Stage 1: Anomaly Detection',
      desc: 'Evaluates probability of abnormal deviation',
    },
    {
      id: 'step-4',
      name: simResult && !simResult.stage1AnomalyDetected
        ? 'Stage 2: Not Required'
        : 'Stage 2: Weather vs Sensor',
      desc: simResult && !simResult.stage1AnomalyDetected
        ? 'Skipped because Stage 1 found no anomaly'
        : 'Classifies genuine weather vs sensor malfunction',
    },
    {
      id: 'step-5',
      name: simResult && !simResult.stage1AnomalyDetected
        ? 'Root Cause: Not Required'
        : 'Root Cause & Evidence',
      desc: simResult && !simResult.stage1AnomalyDetected
        ? 'No anomaly requires cause attribution'
        : 'Synthesizes multi-vector reasoning & neighbors',
    },
    {
      id: 'step-6',
      name: simResult && !simResult.stage1AnomalyDetected
        ? 'Alert: Not Required'
        : 'Alert Evaluation',
      desc: simResult && !simResult.stage1AnomalyDetected
        ? 'No alert dispatched for a normal observation'
        : 'Dispatches severity alert if thresholds exceeded',
    },
    {
      id: 'step-7',
      name: simResult && !simResult.stage1AnomalyDetected
        ? 'Sensor Health: Unchanged'
        : 'Sensor Health Impact',
      desc: simResult && !simResult.stage1AnomalyDetected
        ? 'Sensor health remains unchanged'
        : 'Updates hardware channel health index if sensor fault',
    },
  ];

  const handleRunSimulation = async () => {
    if (isRunning) return;

    setIsRunning(true);
    setSimResult(null);
    setActiveStepIndex(-1);

    try {
      // Visual pipeline animation
      for (let i = 0; i < pipelineSteps.length; i++) {
        setActiveStepIndex(i);

        await new Promise((resolve) =>
          setTimeout(resolve, 350),
        );
      }

      const result = await stationService.runSimulation(
        selectedStationId,
        selectedScenarioId,
        intensity,
      );

      setSimResult(result);
    } catch (error) {
      console.error(
        'Simulation Demo Center failed:',
        error,
      );

      /*
       * Do not leave the UI stuck on "Processing Pipeline..."
       * if the backend rejects the request.
       */
      setSimResult(null);

      const message =
        error instanceof Error
          ? error.message
          : 'Simulation failed.';

      window.alert(
        `SkyGuardAI simulation failed:\n\n${message}`,
      );
    } finally {
      setIsRunning(false);
    }
  };

  const handleReset = () => {
    setActiveStepIndex(-1);
    setSimResult(null);
    setIsRunning(false);
  };

  return (
    <div className="space-y-6">
      {/* Demonstration Banner */}
      <div className="p-4 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-start gap-3">
        <FlaskConical className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
        <div className="text-xs text-amber-950">
          <span className="font-bold text-amber-900 uppercase tracking-wide">
            Controlled Evaluation Pipeline:
          </span>{' '}
          This controlled testbed selects benchmark observations from the 700,800-row AWS dataset and sends the complete feature vector through the backend Random Forest pipeline.
        </div>
      </div>

      {/* Simulation Controls Card */}
      <div className="bg-white rounded-lg border border-slate-200 p-6 shadow-xs">
        <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wide mb-4 flex items-center gap-2">
          <SlidersIcon className="w-4 h-4 text-blue-600" />
          <span>1. Scenario & Target Configuration</span>
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Target Station */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Target AWS Station (AP):
            </label>
            <select
              value={selectedStationId}
              onChange={(e) => setSelectedStationId(e.target.value)}
              disabled={isRunning}
              className="w-full bg-white border border-slate-300 rounded px-3 py-2 text-xs text-slate-900 focus:ring-2 focus:ring-blue-500 focus:outline-none"
            >
              {stations.map((st) => (
                <option key={st.id} value={st.id}>
                  {st.id} — {st.name} ({st.region}, {st.district})
                </option>
              ))}
            </select>
            <p className="mt-1 text-[11px] text-slate-500">
              Baseline:{' '}
              {(() => {
                const telemetry = selectedStation?.telemetry;
                return telemetry?.temperatureC != null
                  ? `${telemetry.temperatureC}°C, ${telemetry.humidityPct ?? '—'}%, ${telemetry.pressureHpa ?? '—'} hPa`
                  : 'No current telemetry';
              })()}
            </p>
          </div>

          {/* Scenario Selection */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Anomaly Scenario:
            </label>
            <select
              value={selectedScenarioId}
              onChange={(e) => setSelectedScenarioId(e.target.value)}
              disabled={isRunning}
              className="w-full bg-white border border-slate-300 rounded px-3 py-2 text-xs text-slate-900 focus:ring-2 focus:ring-blue-500 focus:outline-none"
            >
              <optgroup label="Sensor Hardware Faults">
                {scenarios
                  .filter((s) => s.category === 'Sensor')
                  .map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
              </optgroup>
              <optgroup label="Genuine Weather Events">
                {scenarios
                  .filter((s) => s.category === 'Weather')
                  .map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
              </optgroup>
            </select>
            <p className="mt-1 text-[11px] text-slate-500">{selectedScenario.description}</p>
          </div>

          {/* Intensity & Action */}
          <div className="flex flex-col justify-between">
            <div>
              <div className="flex justify-between text-xs font-semibold text-slate-700 mb-1">
                <span>Anomaly Severity / Intensity:</span>
                <span className="font-mono text-blue-600">{intensity}%</span>
              </div>
              <input
                type="range"
                min="40"
                max="100"
                value={intensity}
                onChange={(e) => setIntensity(Number(e.target.value))}
                disabled={isRunning}
                className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
              />
            </div>

            <div className="mt-4 flex items-center gap-2">
              <button
                type="button"
                onClick={handleRunSimulation}
                disabled={isRunning}
                className="flex-1 py-2 px-4 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded text-xs font-bold flex items-center justify-center gap-1.5 cursor-pointer shadow-xs transition-colors"
              >
                <Play className={`w-3.5 h-3.5 ${isRunning ? 'animate-spin' : ''}`} />
                <span>{isRunning ? 'Processing Pipeline...' : 'Run Simulation'}</span>
              </button>

              <button
                type="button"
                onClick={handleReset}
                disabled={isRunning}
                className="p-2 border border-slate-300 hover:bg-slate-100 rounded text-slate-600 cursor-pointer"
                title="Reset simulation"
              >
                <RotateCcw className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Visual Pipeline Flow */}
      <div className="bg-white rounded-lg border border-slate-200 p-6 shadow-xs">
        <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wide mb-4 flex items-center gap-2">
          <BrainCircuit className="w-4 h-4 text-blue-600" />
          <span>2. End-to-End Processing Pipeline</span>
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-7 gap-2">
          {pipelineSteps.map((step, idx) => {
            const normalResult =
              simResult !== null &&
              !simResult.stage1AnomalyDetected;

            const isSkipped =
              normalResult &&
              idx >= 3 &&
              idx <= 5;

            const isCompleted =
              !isSkipped &&
              ((simResult && !isRunning) || activeStepIndex > idx);

            const isActive =
              isRunning &&
              activeStepIndex === idx;

            return (
              <div
                key={step.id}
                className={`p-3 rounded-lg border flex flex-col justify-between transition-all ${
                  isActive
                    ? 'bg-blue-50 border-blue-500 shadow-sm ring-2 ring-blue-500/20'
                    : isCompleted
                    ? 'bg-emerald-50/60 border-emerald-300 text-slate-800'
                    : 'bg-slate-50 border-slate-200 text-slate-400'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between gap-1 mb-1">
                    <span className="text-[10px] font-mono font-bold uppercase">
                      Step 0{idx + 1}
                    </span>
                    {isSkipped ? (
                      <span className="text-[10px] font-bold text-slate-400">
                        —
                      </span>
                    ) : isCompleted ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                    ) : isActive ? (
                      <span className="w-2 h-2 rounded-full bg-blue-600 animate-ping" />
                    ) : null}
                  </div>
                  <div className="font-bold text-xs text-slate-900 leading-tight">{step.name}</div>
                  <div className="mt-1 text-[10px] text-slate-500 leading-tight">{step.desc}</div>
                </div>

                <div className="mt-2 pt-1 border-t border-slate-200/60 text-[10px] font-medium">
                  {isActive ? (
                    <span className="text-blue-700 font-semibold animate-pulse">
                      Running...
                    </span>
                  ) : isSkipped ? (
                    <span className="text-slate-500 font-semibold">
                      Not required
                    </span>
                  ) : isCompleted ? (
                    <span className="text-emerald-700 font-semibold">
                      Done
                    </span>
                  ) : (
                    <span className="text-slate-400">
                      Pending
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Simulation Result Output */}
      {simResult && (
        <div className="bg-white rounded-lg border border-slate-200 p-6 shadow-xs space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-slate-200">
            <div>
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                <h3 className="text-base font-bold text-slate-900">
                  Benchmark Evaluation Completed: {simResult.scenario.name}
                </h3>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                Target: {selectedStation.id} ({selectedStation.name}) • Timestamp: {simResult.timestamp}
              </p>
            </div>

            <div className="flex items-center gap-2">
              {simResult.stage1AnomalyDetected ? (
                <>
                  <CauseBadge cause={simResult.stage2Cause} />
                  <SeverityBadge severity={simResult.scenario.defaultSeverity} />
                </>
              ) : (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-emerald-200 bg-emerald-50 text-emerald-700 text-[11px] font-semibold">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  Normal Observation
                </span>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
            {/* Observation Output */}
            <div className="p-3.5 bg-slate-50 rounded-lg border border-slate-200">
              <div className="font-semibold text-slate-700 mb-2">Benchmark Observation</div>
              <div className="space-y-1 font-mono">
                <div className="flex justify-between">
                  <span className="text-slate-500">Temperature:</span>
                  <span className="font-bold text-slate-900">{simResult.observation.temperatureC}°C</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Humidity:</span>
                  <span className="font-bold text-slate-900">{simResult.observation.humidityPct}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Pressure:</span>
                  <span className="font-bold text-slate-900">{simResult.observation.pressureHpa} hPa</span>
                </div>
              </div>
              <div className="mt-2 text-[10px] text-slate-500 pt-2 border-t border-slate-200">
                {simResult.featuresComputedCount} ML feature variables engineered
              </div>
            </div>

            {/* Temporal & Seasonal Climatology Evidence */}
            <div className="p-3.5 bg-slate-50 rounded-lg border border-slate-200">
              <div className="font-semibold text-slate-700 mb-2">Seasonal Climatology Evidence</div>
              <div className="space-y-1 font-mono">
                <div className="flex justify-between">
                  <span className="text-slate-500">Seasonal Baseline:</span>
                  <span className="font-bold text-slate-900">{simResult.seasonalEvidence.baselineTemp}°C</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Observed:</span>
                  <span className="font-bold text-slate-900">{simResult.observation.temperatureC}°C</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Seasonal Deviation:</span>
                  <span className={`font-bold ${simResult.seasonalEvidence.tempDeviation >= 0 ? 'text-amber-600' : 'text-blue-600'}`}>
                    {simResult.seasonalEvidence.tempDeviation > 0 ? `+${simResult.seasonalEvidence.tempDeviation}` : simResult.seasonalEvidence.tempDeviation}°C
                  </span>
                </div>
              </div>
              <div className="mt-2 text-[10px] text-slate-600 pt-2 border-t border-slate-200 font-sans">
                {simResult.seasonalEvidence.status}
              </div>
            </div>

            {/* Stage 1 & 2 ML Decisions */}
            <div className="p-3.5 bg-slate-50 rounded-lg border border-slate-200">
              <div className="font-semibold text-slate-700 mb-2">
                Two-Stage Classification
              </div>

              <div className="space-y-1 text-xs">
                {/* Stage 1 */}
                <div className="flex justify-between">
                  <span className="text-slate-500">
                    Stage 1 Anomaly:
                  </span>

                  <span
                    className={`font-bold ${
                      simResult.stage1AnomalyDetected
                        ? 'text-rose-600'
                        : 'text-emerald-600'
                    }`}
                  >
                    {simResult.stage1AnomalyDetected
                      ? 'FLAGGED'
                      : 'NORMAL'}{' '}
                    (Score: {simResult.stage1Score})
                  </span>
                </div>

                {/* Stage 2 */}
                <div className="flex justify-between">
                  <span className="text-slate-500">
                    Stage 2 Decision:
                  </span>

                  {simResult.stage1AnomalyDetected ? (
                    <span className="font-bold text-slate-900">
                      {simResult.stage2Cause}
                    </span>
                  ) : (
                    <span className="font-semibold text-slate-400">
                      Not evaluated
                    </span>
                  )}
                </div>

                {/* Confidence */}
                <div className="flex justify-between">
                  <span className="text-slate-500">
                    Confidence:
                  </span>

                  {simResult.stage1AnomalyDetected ? (
                    <span className="font-mono font-bold text-blue-700">
                      {simResult.stage2Confidence}%
                    </span>
                  ) : (
                    <span className="font-mono font-semibold text-slate-400">
                      —
                    </span>
                  )}
                </div>
              </div>

              <div className="mt-2 text-[10px] text-slate-500 pt-2 border-t border-slate-200">
                {simResult.stage1AnomalyDetected
                  ? 'Stage 2 classifies the detected anomaly as weather or sensor fault.'
                  : 'Stage 1 found no anomaly; cause attribution is not required.'}
              </div>
            </div>

            {/* Sensor Health Impact */}
            <div className="p-3.5 bg-slate-50 rounded-lg border border-slate-200">
              <div className="font-semibold text-slate-700 mb-2">
                Hardware Health Impact
              </div>

              <div className="space-y-1 text-xs">
                {/* Channel Status */}
                <div className="flex justify-between">
                  <span className="text-slate-500">
                    Channel Status:
                  </span>

                  <ChannelBadge
                    status={
                      !simResult.stage1AnomalyDetected
                        ? 'Normal'
                        : simResult.stage2Cause === 'Weather'
                        ? 'Normal'
                        : simResult.sensorHealthImpact.status
                    }
                  />
                </div>

                {/* Score Delta */}
                <div className="flex justify-between">
                  <span className="text-slate-500">
                    Score Delta:
                  </span>

                  <span className="font-mono font-bold">
                    {simResult.stage1AnomalyDetected &&
                    simResult.stage2Cause !== 'Weather'
                      ? `${simResult.sensorHealthImpact.previousScore}% → ${simResult.sensorHealthImpact.newScore}%`
                      : `${simResult.sensorHealthImpact.previousScore}% → ${simResult.sensorHealthImpact.previousScore}%`}
                  </span>
                </div>
              </div>

              <div className="mt-2 text-[10px] text-slate-500 pt-2 border-t border-slate-200">
                {!simResult.stage1AnomalyDetected
                  ? 'No anomaly detected; sensor health remains unchanged.'
                  : simResult.stage2Cause === 'Weather'
                  ? 'Weather event detected; sensor hardware health remains unchanged.'
                  : 'Sensor fault detected; technician inspection/calibration recommended.'}
              </div>
            </div>
          </div>

          {/* Root Cause Summary */}
          <div className="p-4 rounded-lg bg-blue-50 border border-blue-200 text-xs">
            <span className="font-bold text-blue-900">Diagnosis Rationale: </span>
            <span className="text-blue-950">{simResult.rootCauseDetails.summary}</span>
          </div>
        </div>
      )}
    </div>
  );
};

function SlidersIcon(props: { className?: string }) {
  return <Layers className={props.className} />;
}
