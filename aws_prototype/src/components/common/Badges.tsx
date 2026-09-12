import React from 'react';
import { StationStatus, AnomalySeverity, AnomalyCause, ChannelStatus } from '../../types';
import { CloudSun, Wrench, AlertTriangle, CheckCircle2, XCircle, Activity, Clock } from 'lucide-react';

export const StatusBadge: React.FC<{ status: StationStatus; size?: 'sm' | 'md' }> = ({
  status,
  size = 'md',
}) => {
  const configs: Record<
    StationStatus,
    { bg: string; text: string; dot: string; halo: string }
  > = {
    Healthy: {
      bg: 'bg-emerald-500/10 border-emerald-500/20 text-emerald-800',
      dot: 'bg-emerald-500',
      halo: 'ring-2 ring-emerald-400/20',
      text: 'Healthy',
    },
    Watch: {
      bg: 'bg-amber-500/10 border-amber-500/20 text-amber-900',
      dot: 'bg-amber-500',
      halo: 'ring-2 ring-amber-400/20',
      text: 'Watch',
    },
    Critical: {
      bg: 'bg-rose-500/10 border-rose-500/25 text-rose-800',
      dot: 'bg-rose-500',
      halo: 'ring-2 ring-rose-400/30 animate-pulse',
      text: 'Critical',
    },
    Offline: {
      bg: 'bg-slate-500/10 border-slate-400/20 text-slate-700',
      dot: 'bg-slate-400',
      halo: 'ring-2 ring-slate-400/15',
      text: 'Offline',
    },
    'Awaiting Data': {
      bg: 'bg-slate-500/10 border-slate-300/40 text-slate-700',
      dot: 'bg-slate-400',
      halo: 'ring-2 ring-slate-400/20',
      text: 'Awaiting Data',
    },
  };

  const config = configs[status] || configs.Offline;
  const sizeClasses =
    size === 'sm'
      ? 'px-2 py-0.5 text-[11px] font-medium'
      : 'px-2.5 py-0.5 text-xs font-medium tracking-tight';

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border backdrop-blur-xs ${config.bg} ${sizeClasses} whitespace-nowrap transition-all`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${config.dot} ${config.halo}`} aria-hidden="true" />
      <span>{status}</span>
    </span>
  );
};

export const SeverityBadge: React.FC<{ severity: AnomalySeverity }> = ({ severity }) => {
  const styles: Record<AnomalySeverity, string> = {
    Low: 'bg-blue-500/10 text-blue-700 border-blue-400/20',
    Medium: 'bg-amber-500/10 text-amber-800 border-amber-400/25',
    High: 'bg-orange-500/10 text-orange-800 border-orange-400/25',
    Critical: 'bg-rose-500/12 text-rose-800 border-rose-400/30 font-semibold',
  };

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium border backdrop-blur-xs ${
        styles[severity] || styles.Low
      }`}
    >
      {severity}
    </span>
  );
};

export const CauseBadge: React.FC<{ cause: AnomalyCause; showIcon?: boolean }> = ({
  cause,
  showIcon = true,
}) => {
  const isWeather = cause === 'Weather';

  return (
    <span
      className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium border backdrop-blur-xs transition-all ${
        isWeather
          ? 'bg-sky-500/10 text-sky-800 border-sky-400/25'
          : 'bg-amber-500/10 text-amber-900 border-amber-400/25'
      }`}
    >
      {showIcon && (
        isWeather ? (
          <CloudSun className="w-3.5 h-3.5 text-sky-600 shrink-0" aria-hidden="true" />
        ) : (
          <Wrench className="w-3.5 h-3.5 text-amber-700 shrink-0" aria-hidden="true" />
        )
      )}
      <span>{isWeather ? 'Weather Event' : 'Sensor Fault'}</span>
    </span>
  );
};

export const ChannelBadge: React.FC<{ status: ChannelStatus }> = ({ status }) => {
  if (status === 'Normal') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-500/10 text-emerald-800 border border-emerald-400/20">
        <CheckCircle2 className="w-3 h-3 text-emerald-600" />
        Normal
      </span>
    );
  }
  if (status === 'Degraded') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-500/10 text-amber-800 border border-amber-400/25">
        <AlertTriangle className="w-3 h-3 text-amber-600" />
        Degraded
      </span>
    );
  }
  if (status === 'Awaiting data') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-slate-100 text-slate-600 border border-slate-200">
        <Clock className="w-3 h-3 text-slate-400" />
        Awaiting data
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-rose-500/12 text-rose-800 border border-rose-400/30">
      <XCircle className="w-3 h-3 text-rose-600" />
      Fault
    </span>
  );
};
