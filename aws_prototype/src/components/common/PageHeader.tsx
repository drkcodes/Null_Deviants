import React from 'react';
import { ChevronRight, Radio } from 'lucide-react';

interface PageHeaderProps {
  title: string;
  subtitle: string;
  breadcrumbs?: { label: string; onClick?: () => void }[];
  actions?: React.ReactNode;
  showDemoBadge?: boolean;
}

export const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  subtitle,
  breadcrumbs,
  actions,
  showDemoBadge = true,
}) => {
  return (
    <div className="mb-6 pb-4 border-b border-slate-200/60">
      {breadcrumbs && breadcrumbs.length > 0 && (
        <nav aria-label="Breadcrumb" className="mb-2 flex items-center gap-1.5 text-xs text-slate-500">
          {breadcrumbs.map((crumb, idx) => (
            <React.Fragment key={crumb.label}>
              {idx > 0 && <ChevronRight className="w-3 h-3 text-slate-400" />}
              {crumb.onClick ? (
                <button
                  type="button"
                  onClick={crumb.onClick}
                  className="hover:text-blue-600 transition-colors cursor-pointer rounded"
                >
                  {crumb.label}
                </button>
              ) : (
                <span className="text-slate-800 font-medium">{crumb.label}</span>
              )}
            </React.Fragment>
          ))}
        </nav>
      )}

      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-2xl sm:text-[28px] font-semibold text-slate-900 tracking-tight leading-tight">
              {title}
            </h1>
            {showDemoBadge && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-blue-500/10 text-blue-700 border border-blue-400/20 backdrop-blur-xs">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
                <span>Synthetic Demonstration Network</span>
              </span>
            )}
          </div>
          <p className="mt-1 text-xs sm:text-sm text-slate-500 max-w-3xl leading-relaxed">
            {subtitle}
          </p>
        </div>

        {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
      </div>
    </div>
  );
};
