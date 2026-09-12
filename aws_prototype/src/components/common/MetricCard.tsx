import React from 'react';

interface MetricCardProps {
  label: string;
  value: string | number | null | undefined;
  subtitle?: string;
  icon?: React.ReactNode;
  badge?: React.ReactNode;
  trend?: {
    direction: 'up' | 'down' | 'neutral';
    text: string;
  };
  indicatorColor?: 'emerald' | 'amber' | 'rose' | 'blue' | 'slate';
  onClick?: () => void;
  className?: string;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  subtitle,
  icon,
  badge,
  trend,
  indicatorColor,
  onClick,
  className = '',
}) => {
  return (
    <div
      onClick={onClick}
      className={`group relative rounded-2xl p-4 transition-all duration-200 apple-glass-card hover:border-blue-300/80 hover:shadow-[0_8px_24px_rgba(0,113,227,0.06)] ${
        onClick ? 'cursor-pointer' : ''
      } ${className}`}
    >
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-1.5">
          {indicatorColor && (
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                indicatorColor === 'emerald'
                  ? 'bg-emerald-500 ring-2 ring-emerald-400/20'
                  : indicatorColor === 'amber'
                  ? 'bg-amber-500 ring-2 ring-amber-400/20'
                  : indicatorColor === 'rose'
                  ? 'bg-rose-500 ring-2 ring-rose-400/20'
                  : indicatorColor === 'blue'
                  ? 'bg-blue-500 ring-2 ring-blue-400/20'
                  : 'bg-slate-400'
              }`}
            />
          )}
          <span className="text-[11px] font-medium uppercase tracking-wider text-slate-500">
            {label}
          </span>
        </div>
        {icon && (
          <div className="text-slate-400 group-hover:text-blue-600 transition-colors">
            {icon}
          </div>
        )}
      </div>

      <div className="flex items-baseline justify-between gap-2">
        <span className="text-2xl sm:text-[26px] font-normal tracking-tight text-slate-900 leading-none">
          {value !== null && value !== undefined ? value : '—'}
        </span>
        {badge && <div>{badge}</div>}
      </div>

      {(subtitle || trend) && (
        <div className="mt-2 flex items-center gap-1.5 text-[11px] text-slate-500 leading-tight">
          {trend && (
            <span
              className={`font-medium ${
                trend.direction === 'up'
                  ? 'text-emerald-700'
                  : trend.direction === 'down'
                  ? 'text-rose-700'
                  : 'text-slate-600'
              }`}
            >
              {trend.text}
            </span>
          )}
          {subtitle && <span className="truncate">{subtitle}</span>}
        </div>
      )}
    </div>
  );
};
