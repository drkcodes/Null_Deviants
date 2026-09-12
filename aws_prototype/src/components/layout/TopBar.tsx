import React, { useState } from 'react';
import { NetworkSummary, AlertRecord } from '../../types';
import { Menu, Search, Bell, Clock, X, CheckCircle2 } from 'lucide-react';
import { SeverityBadge, CauseBadge } from '../common/Badges';

interface TopBarProps {
  networkSummary: NetworkSummary;
  alerts: AlertRecord[];
  onOpenMobileMenu: () => void;
  onSearch?: (term: string) => void;
  onSelectAlert?: (alert: AlertRecord) => void;
}

export const TopBar: React.FC<TopBarProps> = ({
  networkSummary,
  alerts,
  onOpenMobileMenu,
  onSearch,
  onSelectAlert,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [showAlertsPopover, setShowAlertsPopover] = useState(false);
  const unreadAlerts = alerts.filter((a) => !a.isRead);

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setSearchTerm(val);
    if (onSearch) onSearch(val);
  };

  return (
    <header className="sticky top-0 z-30 h-14 bg-white/70 backdrop-blur-xl border-b border-slate-200/50 px-4 sm:px-6 flex items-center justify-between gap-4 transition-all">
      {/* Left: Mobile Toggle & Minimal Operational Status */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onOpenMobileMenu}
          className="lg:hidden p-1.5 text-slate-600 hover:text-slate-900 rounded-lg hover:bg-slate-100 transition-colors cursor-pointer"
          aria-label="Open navigation menu"
        >
          <Menu className="w-5 h-5" />
        </button>

        {/* Apple-like Compact Operational Status Pill */}
        <div className="hidden sm:inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/80 border border-slate-200/70 shadow-2xs text-xs text-slate-700 font-medium backdrop-blur-xs">
          {networkSummary.reportingStationsCount > 0 ? (
            <>
              <span className="flex h-2 w-2 relative">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              <span className="font-semibold text-slate-900">Network Operational</span>
              <span className="text-slate-300">·</span>
              <span className="text-slate-500 font-normal">{networkSummary.reportingStationsCount} AWS Online</span>
            </>
          ) : (
            <>
              <span className="flex h-2 w-2 relative">
                <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500"></span>
              </span>
              <span className="font-semibold text-slate-900">Network Connected</span>
              <span className="text-slate-300">·</span>
              <span className="text-slate-500 font-normal">{networkSummary.totalStations} Configured · Awaiting Telemetry</span>
            </>
          )}
        </div>
      </div>

      {/* Center: Minimalist Search */}
      <div className="flex-1 max-w-md mx-2">
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            type="text"
            placeholder="Search stations, anomalies, districts (e.g. Nellore, Heatwave)..."
            value={searchTerm}
            onChange={handleSearchChange}
            className="w-full pl-8 pr-8 py-1.5 text-xs bg-slate-100/60 hover:bg-slate-100/90 focus:bg-white border border-slate-200/60 focus:border-blue-500/80 rounded-full focus:outline-none focus:ring-2 focus:ring-blue-500/20 text-slate-900 placeholder:text-slate-400 transition-all"
          />
          {searchTerm && (
            <button
              type="button"
              onClick={() => {
                setSearchTerm('');
                if (onSearch) onSearch('');
              }}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 cursor-pointer"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Right: Updated time & Alert Notifications */}
      <div className="flex items-center gap-3">
        <div className="hidden md:flex items-center gap-1.5 text-[11px] text-slate-400 font-mono">
          <Clock className="w-3 h-3 text-slate-400" />
          <span>Updated {networkSummary.lastUpdated}</span>
        </div>

        {/* Alerts Popover Button */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setShowAlertsPopover(!showAlertsPopover)}
            className="relative p-1.5 text-slate-600 hover:text-slate-900 hover:bg-slate-100/80 rounded-full transition-colors cursor-pointer"
            aria-label="Active Anomaly Alerts"
          >
            <Bell className="w-4 h-4" />
            {unreadAlerts.length > 0 && (
              <span className="absolute top-0.5 right-0.5 flex h-3.5 min-w-3.5 items-center justify-center rounded-full bg-rose-500 px-1 text-[9px] font-bold text-white shadow-2xs">
                {unreadAlerts.length}
              </span>
            )}
          </button>

          {/* Alerts Dropdown Drawer */}
          {showAlertsPopover && (
            <>
              <div
                className="fixed inset-0 z-40"
                onClick={() => setShowAlertsPopover(false)}
              />
              <div className="absolute right-0 mt-2 w-80 sm:w-96 apple-glass-floating rounded-2xl z-50 overflow-hidden border border-white/80 shadow-[0_16px_40px_rgba(15,23,42,0.12)]">
                <div className="p-3.5 bg-white/70 border-b border-slate-200/50 flex items-center justify-between backdrop-blur-md">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-xs text-slate-900">Active Anomaly Alerts</span>
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-500/10 text-rose-700 border border-rose-400/20">
                      {alerts.length} Total
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setShowAlertsPopover(false)}
                    className="text-slate-400 hover:text-slate-600 p-1 rounded-full cursor-pointer"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>

                <div className="max-h-80 overflow-y-auto divide-y divide-slate-100">
                  {alerts.length === 0 ? (
                    <div className="p-6 text-center text-slate-500">
                      <CheckCircle2 className="w-5 h-5 text-emerald-500 mx-auto mb-1.5" />
                      <p className="text-xs font-semibold text-slate-800">No active alerts</p>
                      <p className="text-[11px] text-slate-400 mt-0.5">
                        {networkSummary.reportingStationsCount > 0
                          ? 'All AWS stations report nominal telemetry.'
                          : 'No anomaly alerts logged in backend. Awaiting live observation streams.'}
                      </p>
                    </div>
                  ) : (
                    alerts.map((alert) => (
                      <div
                        key={alert.id}
                        onClick={() => {
                          setShowAlertsPopover(false);
                          if (onSelectAlert) onSelectAlert(alert);
                        }}
                        className="p-3.5 hover:bg-blue-50/40 cursor-pointer transition-colors"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-semibold text-xs text-slate-900">
                            {alert.stationId} • {alert.stationName}
                          </span>
                          <SeverityBadge severity={alert.severity} />
                        </div>
                        <div className="mt-1 flex items-center gap-1.5 text-xs">
                          <CauseBadge cause={alert.cause} showIcon={false} />
                          <span className="font-medium text-slate-800">{alert.anomalyType}</span>
                          <span className="text-[11px] text-slate-400 font-mono ml-auto">
                            {alert.confidence}% conf
                          </span>
                        </div>
                        <p className="mt-1 text-[11px] text-slate-500 line-clamp-2 leading-relaxed">
                          {alert.shortExplanation}
                        </p>
                      </div>
                    ))
                  )}
                </div>

                <div className="p-2.5 bg-slate-50/70 border-t border-slate-200/50 text-center">
                  <span className="text-[10px] text-slate-400 font-medium">
                    Automated real-time ML detection · Stage 1 & 2
                  </span>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
};
