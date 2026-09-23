import React, { useState } from 'react';
import { Station, AnomalyCause, AnomalySeverity, Region } from '../../types';
import { FileText, Download, Printer, CheckCircle2, Calendar, Filter, FileSpreadsheet } from 'lucide-react';

interface ReportsViewProps {
  stations: Station[];
}

export const ReportsView: React.FC<ReportsViewProps> = ({ stations }) => {
  const [reportType, setReportType] = useState<string>('network-health');
  const [selectedStation, setSelectedStation] = useState<string>('All');
  const [selectedRegion, setSelectedRegion] = useState<Region | 'All'>('All');
  const [dateRange, setDateRange] = useState<string>('2025-06-01 to 2025-06-14');
  const [isGenerated, setIsGenerated] = useState<boolean>(false);
  const [exportNotice, setExportNotice] = useState<string | null>(null);

  const reportTypes = [
    {
      id: 'network-health',
      name: 'Network Fleet Health & Reliability Report',
      desc: 'Operational summary of all 20 AWS stations across Coastal and Rayalaseema AP.',
    },
    {
      id: 'anomaly-summary',
      name: 'Anomaly Detection & Diagnosis Summary',
      desc: 'Chronological breakdown of flagged observation deviations, causes, and confidence.',
    },
    {
      id: 'weather-events',
      name: 'Regional Weather Event Analysis',
      desc: 'Spatially coherent atmospheric anomalies (heatwaves, cold spells, rain fronts).',
    },
    {
      id: 'sensor-reliability',
      name: 'Sensor Hardware Degradation Audit',
      desc: 'Channel integrity audit for temperature (RTD), humidity, and pressure transducers.',
    },
    {
      id: 'data-quality',
      name: 'Telemetry Stream Quality & Gaps Audit',
      desc: 'Transmission continuity, packet drops, duplicate stamps, and calibration drift.',
    },
    {
      id: 'model-eval',
      name: 'Two-Stage ML Performance Report',
      desc: 'Inference latency, Stage 1 detection stats, and Stage 2 classification metrics.',
    },
  ];

  const handleGenerate = () => {
    setIsGenerated(true);
    setExportNotice(null);
  };

  const handleExport = (format: 'PDF' | 'CSV') => {
    setExportNotice(`Report export triggered in ${format} format. Ready for backend streaming.`);
    setTimeout(() => setExportNotice(null), 4000);
  };

  return (
    <div className="space-y-6">
      {/* Configuration Card */}
      <div className="bg-white rounded-lg border border-slate-200 p-6 shadow-xs">
        <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wide mb-4 flex items-center gap-2">
          <FileText className="w-4 h-4 text-blue-600" />
          <span>Report Configuration & Filtering</span>
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
          {/* Report Type */}
          <div>
            <label className="block font-semibold text-slate-700 mb-1">Report Template:</label>
            <select
              value={reportType}
              onChange={(e) => {
                setReportType(e.target.value);
                setIsGenerated(false);
              }}
              className="w-full bg-white border border-slate-300 rounded px-3 py-2 text-slate-900 focus:ring-2 focus:ring-blue-500 focus:outline-none"
            >
              {reportTypes.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </div>

          {/* Region */}
          <div>
            <label className="block font-semibold text-slate-700 mb-1">Target Region:</label>
            <select
              value={selectedRegion}
              onChange={(e) => setSelectedRegion(e.target.value as any)}
              className="w-full bg-white border border-slate-300 rounded px-3 py-2 text-slate-900 focus:ring-2 focus:ring-blue-500 focus:outline-none"
            >
              <option value="All">All AP (20 Stations)</option>
              <option value="Coastal">Coastal AP (12 Stations)</option>
              <option value="Rayalaseema">Rayalaseema (8 Stations)</option>
            </select>
          </div>

          {/* Station */}
          <div>
            <label className="block font-semibold text-slate-700 mb-1">Specific AWS Station:</label>
            <select
              value={selectedStation}
              onChange={(e) => setSelectedStation(e.target.value)}
              className="w-full bg-white border border-slate-300 rounded px-3 py-2 text-slate-900 focus:ring-2 focus:ring-blue-500 focus:outline-none"
            >
              <option value="All">All Stations</option>
              {stations.map((st) => (
                <option key={st.id} value={st.id}>
                  {st.id} — {st.name}
                </option>
              ))}
            </select>
          </div>

          {/* Date Range */}
          <div>
            <label className="block font-semibold text-slate-700 mb-1">Date Timeframe:</label>
            <div className="relative">
              <input
                type="text"
                value={dateRange}
                onChange={(e) => setDateRange(e.target.value)}
                className="w-full bg-white border border-slate-300 rounded px-3 py-2 text-slate-900 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              />
            </div>
          </div>
        </div>

        <div className="mt-4 pt-4 border-t border-slate-100 flex items-center justify-between">
          <p className="text-xs text-slate-500">
            {reportTypes.find((r) => r.id === reportType)?.desc}
          </p>

          <button
            type="button"
            onClick={handleGenerate}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded text-xs font-bold flex items-center gap-1.5 cursor-pointer shadow-xs transition-colors"
          >
            <span>Generate Report Preview</span>
          </button>
        </div>
      </div>

      {/* Export Notice Notification */}
      {exportNotice && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-md text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          <span>{exportNotice}</span>
        </div>
      )}

      {/* Generated Report Preview Area */}
      {isGenerated ? (
        <div className="bg-white rounded-lg border border-slate-200 p-6 shadow-xs space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-200">
            <div>
              <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400">
                SkyGuardAI System Generated Document • SIH26073
              </div>
              <h3 className="text-lg font-bold text-slate-900 mt-0.5">
                {reportTypes.find((r) => r.id === reportType)?.name}
              </h3>
              <div className="text-xs text-slate-500 mt-1">
                Scope: {selectedRegion} Region • Station: {selectedStation} • Period: {dateRange}
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => handleExport('PDF')}
                className="px-3 py-1.5 border border-slate-300 hover:bg-slate-50 rounded text-xs font-semibold text-slate-700 flex items-center gap-1.5 cursor-pointer shadow-2xs"
              >
                <Printer className="w-3.5 h-3.5 text-slate-600" />
                <span>Export PDF</span>
              </button>
              <button
                type="button"
                onClick={() => handleExport('CSV')}
                className="px-3 py-1.5 bg-slate-900 hover:bg-slate-800 text-white rounded text-xs font-semibold flex items-center gap-1.5 cursor-pointer shadow-2xs"
              >
                <FileSpreadsheet className="w-3.5 h-3.5" />
                <span>Export CSV</span>
              </button>
            </div>
          </div>

          {/* Report Executive Summary */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
            <div className="p-3 bg-slate-50 rounded border border-slate-100">
              <span className="text-slate-500 font-medium">Stations Audited</span>
              <div className="text-lg font-bold font-mono text-slate-900 mt-1">20 Stations</div>
              <div className="text-[10px] text-slate-400">100% network coverage</div>
            </div>

            <div className="p-3 bg-slate-50 rounded border border-slate-100">
              <span className="text-slate-500 font-medium">Flagged Anomalies</span>
              <div className="text-lg font-bold font-mono text-slate-900 mt-1">8 Events</div>
              <div className="text-[10px] text-slate-400">4 Weather, 4 Sensor</div>
            </div>

            <div className="p-3 bg-slate-50 rounded border border-slate-100">
              <span className="text-slate-500 font-medium">Data Integrity Rate</span>
              <div className="text-lg font-bold font-mono text-emerald-700 mt-1">98.4%</div>
              <div className="text-[10px] text-slate-400">Nominal transmission</div>
            </div>

            <div className="p-3 bg-slate-50 rounded border border-slate-100">
              <span className="text-slate-500 font-medium">Hardware Readiness</span>
              <div className="text-lg font-bold font-mono text-blue-700 mt-1">85.0%</div>
              <div className="text-[10px] text-slate-400">2 calibration alerts</div>
            </div>
          </div>

          {/* Sample Tabular Preview */}
          <div>
            <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wide mb-2">
              Preview Data Records
            </h4>
            <div className="overflow-x-auto border border-slate-200 rounded-md">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase text-[10px] font-semibold">
                    <th className="p-2.5">Station ID</th>
                    <th className="p-2.5">Name</th>
                    <th className="p-2.5">Region</th>
                    <th className="p-2.5">Mean Temp</th>
                    <th className="p-2.5">Mean RH</th>
                    <th className="p-2.5">Health Score</th>
                    <th className="p-2.5">Anomaly Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {stations.slice(0, 6).map((st) => (
                    <tr key={st.id} className="hover:bg-slate-50">
                      <td className="p-2.5 font-mono font-medium">{st.id}</td>
                      <td className="p-2.5 font-semibold text-slate-900">{st.name}</td>
                      <td className="p-2.5 text-slate-600">{st.region}</td>
                      <td className="p-2.5 font-mono">
                        {st.telemetry.temperatureC !== null ? `${st.telemetry.temperatureC}°C` : '—'}
                      </td>
                      <td className="p-2.5 font-mono">
                        {st.telemetry.humidityPct !== null ? `${st.telemetry.humidityPct}%` : '—'}
                      </td>
                      <td className="p-2.5 font-mono font-bold">{st.healthScore}%</td>
                      <td className="p-2.5 text-slate-600">
                        {st.latestAnomaly ? st.latestAnomaly.type : 'Nominal'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : (
        <div className="p-12 text-center bg-white rounded-lg border border-dashed border-slate-300 text-xs text-slate-500">
          <FileText className="w-8 h-8 text-slate-300 mx-auto mb-2" />
          <p className="font-semibold text-slate-700">No report generated yet</p>
          <p className="mt-1">
            Select template parameters above and click &quot;Generate Report Preview&quot; to review before exporting.
          </p>
        </div>
      )}
    </div>
  );
};
