import React, { useState } from 'react';
import { Settings, Bell, Sliders, MapPin, Database, RefreshCw, CheckCircle2, ShieldCheck } from 'lucide-react';

export const SettingsView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'general' | 'network' | 'alerts' | 'ml' | 'data'>('general');
  const [alertThreshold, setAlertThreshold] = useState<number>(85);
  const [refreshInterval, setRefreshInterval] = useState<string>('60');
  const [defaultRegion, setDefaultRegion] = useState<string>('All');
  const [defaultRange, setDefaultRange] = useState<string>('24h');
  const [spatialValidation, setSpatialValidation] = useState<boolean>(true);
  const [savedNotice, setSavedNotice] = useState<boolean>(false);

  const handleSave = () => {
    setSavedNotice(true);
    setTimeout(() => setSavedNotice(false), 3000);
  };

  return (
    <div className="space-y-6">
      {savedNotice && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-md text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          <span>Operational settings saved successfully.</span>
        </div>
      )}

      {/* Tabs */}
      <div className="bg-white rounded-lg border border-slate-200 shadow-xs overflow-hidden">
        <div className="flex border-b border-slate-200 bg-slate-50 overflow-x-auto text-xs">
          {[
            { id: 'general', label: 'General & Display', icon: Settings },
            { id: 'network', label: 'Network & Map', icon: MapPin },
            { id: 'alerts', label: 'Alert Thresholds', icon: Bell },
            { id: 'ml', label: 'Anomaly Detection ML', icon: Sliders },
            { id: 'data', label: 'Data Source Disclosure', icon: Database },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;

            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center gap-2 px-4 py-3 font-medium cursor-pointer transition-colors border-b-2 whitespace-nowrap ${
                  isActive
                    ? 'border-blue-600 text-blue-600 bg-white font-semibold'
                    : 'border-transparent text-slate-600 hover:text-slate-900 hover:bg-slate-100/60'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        <div className="p-6 text-xs space-y-6">
          {/* General Tab */}
          {activeTab === 'general' && (
            <div className="space-y-4 max-w-xl">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Telemetry Auto-Refresh Rate:
                </label>
                <select
                  value={refreshInterval}
                  onChange={(e) => setRefreshInterval(e.target.value)}
                  className="w-full bg-white border border-slate-300 rounded px-3 py-2 text-slate-900 focus:ring-2 focus:ring-blue-500 focus:outline-none"
                >
                  <option value="15">Every 15 seconds (Simulation Fast Polling)</option>
                  <option value="60">Every 60 seconds (Standard Operations)</option>
                  <option value="300">Every 5 minutes</option>
                  <option value="900">Every 15 minutes (Dataset Native Interval)</option>
                </select>
                <p className="mt-1 text-[11px] text-slate-500">
                  Controls browser polling interval against the SkyGuardAI station telemetry stream.
                </p>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Default Time-Series Range:
                </label>
                <select
                  value={defaultRange}
                  onChange={(e) => setDefaultRange(e.target.value)}
                  className="w-full bg-white border border-slate-300 rounded px-3 py-2 text-slate-900 focus:ring-2 focus:ring-blue-500 focus:outline-none"
                >
                  <option value="1h">Past 1 Hour</option>
                  <option value="6h">Past 6 Hours</option>
                  <option value="24h">Past 24 Hours (Standard)</option>
                  <option value="7d">Past 7 Days</option>
                </select>
              </div>
            </div>
          )}

          {/* Network Tab */}
          {activeTab === 'network' && (
            <div className="space-y-4 max-w-xl">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Default Map Initial Region:
                </label>
                <select
                  value={defaultRegion}
                  onChange={(e) => setDefaultRegion(e.target.value)}
                  className="w-full bg-white border border-slate-300 rounded px-3 py-2 text-slate-900 focus:ring-2 focus:ring-blue-500 focus:outline-none"
                >
                  <option value="All">All Andhra Pradesh (Full 20 Stations)</option>
                  <option value="Coastal">Coastal AP (12 Stations)</option>
                  <option value="Rayalaseema">Rayalaseema AP (8 Stations)</option>
                </select>
              </div>

              <div className="pt-2">
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={spatialValidation}
                    onChange={(e) => setSpatialValidation(e.target.checked)}
                    className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="font-semibold text-slate-800">
                    Render spatial neighbour triangulation overlays on map
                  </span>
                </label>
                <p className="mt-1 text-[11px] text-slate-500 ml-5">
                  Displays k-nearest spatial neighbor links across AP districts to help operators immediately verify regional coherence.
                </p>
              </div>
            </div>
          )}

          {/* Alerts Tab */}
          {activeTab === 'alerts' && (
            <div className="space-y-4 max-w-xl">
              <div>
                <div className="flex justify-between font-semibold text-slate-700 mb-1">
                  <span>Minimum Anomaly Confidence to Trigger Operational Alert:</span>
                  <span className="font-mono text-blue-600">{alertThreshold}%</span>
                </div>
                <input
                  type="range"
                  min="60"
                  max="99"
                  value={alertThreshold}
                  onChange={(e) => setAlertThreshold(Number(e.target.value))}
                  className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                />
                <p className="mt-1 text-[11px] text-slate-500">
                  Detections with ML confidence below this percentage remain in the diagnostics log without dispatching critical alerts.
                </p>
              </div>
            </div>
          )}

          {/* ML Tab */}
          {activeTab === 'ml' && (
            <div className="space-y-3 max-w-xl">
              <div className="p-3 bg-slate-50 rounded border border-slate-200">
                <span className="font-bold text-slate-900">Stage 1: Anomaly Gate Algorithm</span>
                <p className="text-[11px] text-slate-600 mt-1">
                  Ensemble Random Forest using 50 post-engineering model inputs from the 67-feature pipeline.
                </p>
              </div>

              <div className="p-3 bg-slate-50 rounded border border-slate-200">
                <span className="font-bold text-slate-900">Stage 2: Weather vs Sensor Classifier</span>
                <p className="text-[11px] text-slate-600 mt-1">
                  Spatial coherence evaluator comparing target variance ratio against contiguous AP neighbor clusters.
                </p>
              </div>
            </div>
          )}

          {/* Data Sources Disclosure Tab */}
          {activeTab === 'data' && (
            <div className="space-y-3 max-w-2xl bg-blue-50/60 p-4 rounded-lg border border-blue-200 text-blue-950">
              <div className="flex items-center gap-2 font-bold text-sm text-blue-900">
                <ShieldCheck className="w-4 h-4 text-blue-600" />
                <span>Synthetic Data Compliance Disclosure</span>
              </div>
              <p className="text-xs leading-relaxed">
                In compliance with SIH26073 specifications, all observations rendered within the SkyGuardAI demonstration interface originate from the synthetic Andhra Pradesh 2025 benchmark dataset (700,800 rows across 20 AWS stations). This data is provided exclusively for model evaluation and architecture demonstration. It does not represent live operational feeds from the India Meteorological Department (IMD) or DES-AP.
              </p>
            </div>
          )}

          {/* Save Button */}
          <div className="pt-4 border-t border-slate-200 flex justify-end">
            <button
              type="button"
              onClick={handleSave}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded text-xs font-bold cursor-pointer transition-colors shadow-xs"
            >
              Save Configuration
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
