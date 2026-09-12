import React, { useState } from 'react';
import { Station, NetworkSummary } from '../../types';
import { AndhraPradeshMap } from '../maps/AndhraPradeshMap';
import { StationTable } from '../stations/StationTable';
import { MetricCard } from '../common/MetricCard';
import { Radio, CheckCircle2, AlertTriangle, XCircle } from 'lucide-react';

interface NetworkViewProps {
  stations: Station[];
  summary: NetworkSummary;
  selectedStationId: string;
  onSelectStation: (id: string) => void;
  onViewStationDetails: (id: string) => void;
}

export const NetworkView: React.FC<NetworkViewProps> = ({
  stations,
  summary,
  selectedStationId,
  onSelectStation,
  onViewStationDetails,
}) => {
  return (
    <div className="space-y-6">
      {/* Network Quick Metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <MetricCard
          label="Total AWS Fleet"
          value={summary.totalStations}
          subtitle="20 AP Districts Configured"
          icon={<Radio className="w-4 h-4 text-blue-600" />}
          indicatorColor="blue"
        />
        <MetricCard
          label="Healthy Stations"
          value={summary.healthyCount !== null ? summary.healthyCount : 'N/A'}
          subtitle={summary.healthyCount !== null ? 'Hardware & telemetry nominal' : 'Awaiting observation telemetry'}
          icon={<CheckCircle2 className={`w-4 h-4 ${summary.healthyCount !== null ? 'text-emerald-600' : 'text-slate-400'}`} />}
          indicatorColor={summary.healthyCount !== null ? 'emerald' : 'slate'}
        />
        <MetricCard
          label="Watch Stations"
          value={summary.watchCount !== null ? summary.watchCount : 'N/A'}
          subtitle={summary.watchCount !== null ? 'Heatwave or mild drift' : 'Awaiting observation telemetry'}
          icon={<AlertTriangle className={`w-4 h-4 ${summary.watchCount !== null ? 'text-amber-600' : 'text-slate-400'}`} />}
          indicatorColor={summary.watchCount !== null ? 'amber' : 'slate'}
        />
        <MetricCard
          label="Critical Stations"
          value={summary.criticalCount !== null ? summary.criticalCount : 'N/A'}
          subtitle={summary.criticalCount !== null ? 'Sensor or comms fault' : 'Awaiting observation telemetry'}
          icon={<XCircle className={`w-4 h-4 ${summary.criticalCount !== null ? 'text-rose-600' : 'text-slate-400'}`} />}
          indicatorColor={summary.criticalCount !== null ? 'rose' : 'slate'}
        />
      </div>

      {/* Map & Station Table Layout */}
      <div className="space-y-5">
        {/* Interactive Map */}
        <div>
          <div className="flex items-center justify-between mb-2 px-1">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
              <Radio className="w-3.5 h-3.5 text-blue-600" />
              <span>Spatial Telemetry & Sensor Network</span>
            </h2>
            <span className="text-[11px] text-slate-400">
              Interactive Leaflet · Click station marker to inspect
            </span>
          </div>
          <AndhraPradeshMap
            stations={stations}
            selectedStationId={selectedStationId}
            onSelectStation={onSelectStation}
            onViewStationDetails={onViewStationDetails}
            height="440px"
          />
        </div>

        {/* Operational Stations Table */}
        <div>
          <div className="flex items-center justify-between mb-2 px-1">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Station Telemetry & Diagnostics Directory
            </h2>
            <span className="text-[11px] text-slate-400 font-mono">
              20 Stations (12 Coastal • 8 Rayalaseema)
            </span>
          </div>

          <StationTable
            stations={stations}
            onSelectStation={onViewStationDetails}
            selectedStationId={selectedStationId}
          />
        </div>
      </div>
    </div>
  );
};
