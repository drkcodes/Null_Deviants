import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import { Station, StationStatus, Region } from '../../types';
import { formatISTTime } from '../../lib/formatters';
import { StatusBadge, CauseBadge } from '../common/Badges';
import { Navigation } from 'lucide-react';
import { ArrowRight } from 'lucide-react';

interface AndhraPradeshMapProps {
  stations: Station[];
  selectedStationId?: string;
  onSelectStation: (stationId: string) => void;
  onViewStationDetails?: (stationId: string) => void;
  regionFilter?: Region | 'All';
  statusFilter?: StationStatus | 'All';
  height?: string;
  showNeighborLines?: boolean;
}

export const AndhraPradeshMap: React.FC<AndhraPradeshMapProps> = ({
  stations,
  selectedStationId,
  onSelectStation,
  onViewStationDetails,
  regionFilter = 'All',
  statusFilter = 'All',
  height = '520px',
  showNeighborLines = true,
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markersRef = useRef<Record<string, L.Marker>>({});
  const linesGroupRef = useRef<L.LayerGroup | null>(null);

  const [activeRegionFilter, setActiveRegionFilter] =
    useState<Region | 'All'>(regionFilter);

  const [toggleNeighbors, setToggleNeighbors] =
    useState(showNeighborLines);

  /*
   * Keep the latest callback without making the Leaflet map
   * initialization effect depend on the callback identity.
   */
  const onSelectStationRef = useRef(onSelectStation);

  useEffect(() => {
    onSelectStationRef.current = onSelectStation;
  }, [onSelectStation]);

  /*
   * Filter stations for the currently selected region/status.
   */
  const filteredStations = stations.filter((station) => {
    const matchesRegion =
      activeRegionFilter === 'All' ||
      station.region === activeRegionFilter;

    const matchesStatus =
      statusFilter === 'All' ||
      station.status === statusFilter;

    return matchesRegion && matchesStatus;
  });

  const selectedStation = stations.find(
    (station) => station.id === selectedStationId,
  );

  /*
   * IMPORTANT:
   * Initialize Leaflet exactly once.
   *
   * The previous implementation depended on onSelectStation.
   * Since the parent recreated that function during every polling
   * render, Leaflet was repeatedly destroyed and recreated.
   */
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) {
      return;
    }

    const map = L.map(mapContainerRef.current, {
      center: [15.9129, 80.1],
      zoom: 7,
      minZoom: 6,
      maxZoom: 14,
      zoomControl: false,
      preferCanvas: true,
    });

    const cartoApiKey = import.meta.env.VITE_CARTO_BASEMAP_KEY;

    const cartoTileUrl = cartoApiKey
      ? `https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png?key=${encodeURIComponent(cartoApiKey)}`
      : 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png';

    L.tileLayer(cartoTileUrl, {
      attribution: '&copy; OpenStreetMap &copy; CARTO',
      subdomains: 'abcd',
      maxZoom: 19,
    }).addTo(map);

    L.control.zoom({ position: 'bottomright' }).addTo(map);

    linesGroupRef.current = L.layerGroup().addTo(map);
    mapInstanceRef.current = map;

    map.on('click', () => {
      onSelectStationRef.current('');
    });

    /*
     * Give Leaflet one frame to calculate its container size.
     */
    window.setTimeout(() => {
      map.invalidateSize({ animate: false });
    }, 0);

    return () => {
      /*
       * This only runs when the component itself unmounts.
       * It will NOT run every time telemetry updates.
       */
      Object.values(markersRef.current).forEach((marker) => {
        marker.remove();
      });

      markersRef.current = {};

      if (linesGroupRef.current) {
        linesGroupRef.current.clearLayers();
      }

      map.remove();

      mapInstanceRef.current = null;
      linesGroupRef.current = null;
    };
  }, []);

  /*
   * Update markers and neighbour lines WITHOUT recreating the map.
   *
   * The map itself remains stationary while live telemetry updates.
   */
  useEffect(() => {
    const map = mapInstanceRef.current;

    if (!map) {
      return;
    }

    /*
     * Remove only the old marker/layer objects.
     * The Leaflet map instance remains intact.
     */
    Object.values(markersRef.current).forEach((marker) => {
      marker.remove();
    });

    markersRef.current = {};

    if (linesGroupRef.current) {
      linesGroupRef.current.clearLayers();
    }

    /*
     * Spatial neighbour links.
     */
    if (toggleNeighbors && linesGroupRef.current) {
      const drawnPairs = new Set<string>();

      filteredStations.forEach((station) => {
        station.neighbours.forEach((neighbourId) => {
          const neighbour = stations.find(
            (candidate) => candidate.id === neighbourId,
          );

          if (!neighbour) {
            return;
          }

          const pairKey = [station.id, neighbour.id]
            .sort()
            .join('-');

          if (drawnPairs.has(pairKey)) {
            return;
          }

          drawnPairs.add(pairKey);

          const isSelectedRelation =
            selectedStationId === station.id ||
            selectedStationId === neighbour.id;

          const polyline = L.polyline(
            [
              [station.latitude, station.longitude],
              [neighbour.latitude, neighbour.longitude],
            ],
            {
              color: isSelectedRelation
                ? '#0071e3'
                : '#cbd5e1',
              weight: isSelectedRelation ? 2 : 1,
              dashArray: isSelectedRelation
                ? '4, 4'
                : '3, 6',
              opacity: isSelectedRelation
                ? 0.95
                : 0.4,
            },
          );

          linesGroupRef.current?.addLayer(polyline);
        });
      });
    }

    /*
     * Station markers.
     */
    filteredStations.forEach((station) => {
      const isSelected =
        station.id === selectedStationId;

      const markerColor =
        station.status === 'Healthy'
          ? '#10b981'
          : station.status === 'Watch'
            ? '#f59e0b'
            : station.status === 'Critical'
              ? '#f43f5e'
              : station.status === 'Awaiting Data'
                ? '#94a3b8'
                : '#64748b';

      const haloColor =
        station.status === 'Healthy'
          ? 'rgba(16, 185, 129, 0.22)'
          : station.status === 'Watch'
            ? 'rgba(245, 158, 11, 0.25)'
            : station.status === 'Critical'
              ? 'rgba(244, 63, 94, 0.28)'
              : 'rgba(148, 163, 184, 0.2)';

      const isCritical =
        station.status === 'Critical';

      const size = isSelected ? 26 : 18;

      const customIcon = L.divIcon({
        className: 'apple-map-marker',
        html: `
          <div style="
            position: relative;
            display: flex;
            align-items: center;
            justify-content: center;
            width: ${size}px;
            height: ${size}px;
            background-color: ${markerColor};
            border: ${isSelected ? '3px solid #0071e3' : '2px solid #ffffff'};
            border-radius: 50%;
            box-shadow:
              0 0 0 ${isSelected ? '5px' : '3px'} ${haloColor},
              0 2px 8px rgba(15,23,42,0.18);
            cursor: pointer;
          ">
            ${
              isCritical
                ? `
                  <div style="
                    position: absolute;
                    inset: -4px;
                    border-radius: 50%;
                    border: 1.5px solid #f43f5e;
                    opacity: 0.8;
                    animation: ping 2s cubic-bezier(0, 0, 0.2, 1) infinite;
                  "></div>
                `
                : ''
            }

            ${
              isSelected
                ? `
                  <div style="
                    width: 6px;
                    height: 6px;
                    background-color: #ffffff;
                    border-radius: 50%;
                  "></div>
                `
                : ''
            }
          </div>
        `,
        iconSize: [size, size],
        iconAnchor: [size / 2, size / 2],
      });

      const marker = L.marker(
        [station.latitude, station.longitude],
        {
          icon: customIcon,
          title: `${station.id}: ${station.name} (${station.status})`,
        },
      ).addTo(map);

      marker.on('click', (event) => {
        L.DomEvent.stopPropagation(event);
        onSelectStationRef.current(station.id);
      });

      markersRef.current[station.id] = marker;
    });
  }, [
    filteredStations,
    selectedStationId,
    toggleNeighbors,
    stations,
  ]);

  /*
   * PAN ONLY WHEN THE USER ACTUALLY CHANGES THE SELECTED STATION.
   *
   * Previously `stations` was in this dependency list.
   * Because stations refresh every 2 seconds, this was repeatedly
   * calling animated panTo() and produced the visible shaking.
   */
  useEffect(() => {
    if (!selectedStationId) {
      return;
    }

    const map = mapInstanceRef.current;

    if (!map) {
      return;
    }

    const target = stations.find(
      (station) =>
        station.id === selectedStationId,
    );

    if (!target) {
      return;
    }

    /*
     * Do not animate the map when telemetry merely refreshes.
     * This effect only runs when selectedStationId changes.
     */
    map.panTo(
      [target.latitude, target.longitude],
      {
        animate: true,
        duration: 0.6,
      },
    );
  }, [selectedStationId]);

  return (
    <div className="flex flex-col lg:flex-row gap-4 items-stretch w-full">
      {/* Map Container */}
      <div
        className="relative rounded-2xl border border-slate-200/70 bg-white/70 backdrop-blur-xl overflow-hidden shadow-[0_8px_30px_rgba(15,23,42,0.04)] flex flex-col flex-1 min-w-0"
        style={{ minHeight: height }}
      >
        {/* Floating Controls */}
        <div className="absolute top-4 left-4 z-20 flex flex-wrap items-center gap-2 max-w-[calc(100%-32px)]">
          <div className="inline-flex rounded-full apple-glass p-0.5 shadow-sm text-xs">
            {(
              ['All', 'Coastal', 'Rayalaseema'] as const
            ).map((region) => (
              <button
                key={region}
                type="button"
                onClick={() =>
                  setActiveRegionFilter(region)
                }
                className={`px-3 py-1 rounded-full text-xs font-medium cursor-pointer transition-all ${
                  activeRegionFilter === region
                    ? 'bg-white text-slate-900 shadow-xs font-semibold'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {region === 'All'
                  ? 'All (20)'
                  : region === 'Coastal'
                    ? 'Coastal (12)'
                    : 'Rayalaseema (8)'}
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={() =>
              setToggleNeighbors((current) => !current)
            }
            className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium apple-glass shadow-sm transition-colors cursor-pointer ${
              toggleNeighbors
                ? 'text-blue-700 font-semibold border-blue-300'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                toggleNeighbors
                  ? 'bg-blue-600'
                  : 'bg-slate-400'
              }`}
            />
            <span>Spatial Neighbors</span>
          </button>

          <button
            type="button"
            onClick={() => {
              if (mapInstanceRef.current) {
                mapInstanceRef.current.setView(
                  [15.9129, 80.1],
                  7,
                  { animate: true },
                );
              }
            }}
            className="p-1.5 rounded-full apple-glass shadow-sm text-slate-600 hover:text-slate-900 transition-colors cursor-pointer"
            title="Reset map perspective"
          >
            <Navigation className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Map Canvas */}
        <div className="relative flex-1 w-full h-full">
          <div
            ref={mapContainerRef}
            className="absolute inset-0 z-10"
          />
        </div>

        {/* Legend */}
        <div className="absolute bottom-4 left-4 z-20 apple-glass rounded-xl p-2.5 text-[11px] shadow-sm flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500 ring-2 ring-emerald-400/20" />
            <span className="text-slate-600 font-medium">
              Healthy
            </span>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-amber-500 ring-2 ring-amber-400/20" />
            <span className="text-slate-600 font-medium">
              Watch
            </span>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-rose-500 ring-2 ring-rose-400/20" />
            <span className="text-slate-600 font-medium">
              Critical
            </span>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-slate-400 ring-2 ring-slate-400/20" />
            <span className="text-slate-600 font-medium">
              Offline
            </span>
          </div>
        </div>
      </div>

      {/* Selected Station Side Panel */}
      {selectedStation && (
        <div className="w-full lg:w-[320px] shrink-0 rounded-2xl border border-slate-200/70 bg-white shadow-[0_8px_30px_rgba(15,23,42,0.04)] p-4 flex flex-col justify-between">
          <div>
            <div className="flex items-start justify-between gap-2 pb-3 border-b border-slate-200">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs font-semibold text-slate-500">
                    {selectedStation.id}
                  </span>

                  <StatusBadge
                    status={selectedStation.status}
                    size="sm"
                  />
                </div>

                <h3 className="text-base font-semibold text-slate-900 tracking-tight mt-0.5">
                  {selectedStation.name}
                </h3>

                <p className="text-[11px] text-slate-500">
                  {selectedStation.district} District •{' '}
                  {selectedStation.region}
                </p>
              </div>

              <button
                type="button"
                onClick={() =>
                  onSelectStation('')
                }
                className="text-slate-400 hover:text-slate-700 p-1 rounded-lg hover:bg-slate-100 transition-colors cursor-pointer"
                title="Close panel"
              >
                ✕
              </button>
            </div>

            <div className="mt-3 grid grid-cols-3 gap-2 text-center bg-slate-50 p-2.5 rounded-xl border border-slate-200/60">
              <div>
                <div className="text-[10px] uppercase tracking-wider text-slate-400 font-medium">
                  Temp
                </div>
                <div className="text-sm font-semibold text-slate-900 mt-0.5">
                  {selectedStation.telemetry.temperatureC !== null
                    ? `${selectedStation.telemetry.temperatureC}°C`
                    : '—'}
                </div>
              </div>

              <div>
                <div className="text-[10px] uppercase tracking-wider text-slate-400 font-medium">
                  Humidity
                </div>
                <div className="text-sm font-semibold text-slate-900 mt-0.5">
                  {selectedStation.telemetry.humidityPct !== null
                    ? `${selectedStation.telemetry.humidityPct}%`
                    : '—'}
                </div>
              </div>

              <div>
                <div className="text-[10px] uppercase tracking-wider text-slate-400 font-medium">
                  Pressure
                </div>
                <div className="text-sm font-semibold text-slate-900 mt-0.5">
                  {selectedStation.telemetry.pressureHpa !== null
                    ? selectedStation.telemetry.pressureHpa
                    : '—'}
                </div>

                <div className="text-[9px] text-slate-400 leading-none">
                  {selectedStation.telemetry.pressureHpa !== null
                    ? 'hPa'
                    : ''}
                </div>
              </div>
            </div>

            {selectedStation.latestAnomaly ? (
              <div className="mt-3 p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs">
                <div className="flex items-center justify-between font-medium text-amber-950">
                  <span>Detected Anomaly</span>
                  <CauseBadge
                    cause={
                      selectedStation.latestAnomaly
                        .cause
                    }
                    showIcon={false}
                  />
                </div>

                <div className="mt-1 flex items-center justify-between text-slate-700">
                  <span className="font-semibold text-xs">
                    {selectedStation.latestAnomaly.type}
                  </span>

                  <span className="font-mono text-[11px] text-slate-500">
                    {selectedStation.latestAnomaly.confidence}% Conf
                  </span>
                </div>
              </div>
            ) : !selectedStation.hasTelemetry ? (
              <div className="mt-3 p-2.5 rounded-xl bg-slate-100 border border-slate-200 text-xs text-slate-700 flex items-center justify-between">
                <span>Observation Status</span>
                <span className="font-medium text-[11px] text-slate-500">
                  Awaiting Observation
                </span>
              </div>
            ) : (
              <div className="mt-3 p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-900 flex items-center justify-between">
                <span>Observation Status</span>
                <span className="font-semibold text-[11px] text-emerald-700">
                  Nominal
                </span>
              </div>
            )}
          </div>

          <div>
            <div className="mt-3 pt-3 border-t border-slate-200 text-[11px] text-slate-500 flex items-center justify-between">
              <span className="truncate max-w-[190px]">
                {selectedStation.neighbours.length > 0
                  ? `Neighbours: ${selectedStation.neighbours.join(', ')}`
                  : 'Neighbour: Inferred'}
              </span>

              <span>
                {selectedStation.hasTelemetry
                  ? formatISTTime(selectedStation.lastObservationTime, true)
                  : 'Telemetry unavailable'}
              </span>
            </div>

            {onViewStationDetails && (
              <button
                type="button"
                onClick={() =>
                  onViewStationDetails(
                    selectedStation.id,
                  )
                }
                className="mt-3 w-full py-2 px-3 apple-btn-primary rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 cursor-pointer"
              >
                <span>View Station Details</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
};