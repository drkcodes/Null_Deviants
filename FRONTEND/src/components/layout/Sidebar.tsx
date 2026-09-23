import React from 'react';
import { ActivePage } from '../../types';
import {
  LayoutDashboard,
  Radio,
  BrainCircuit,
  Activity,
  Cpu,
  FileText,
  Settings,
  FlaskConical,
  Wind,
} from 'lucide-react';

interface SidebarProps {
  activePage: ActivePage;
  onNavigate: (page: ActivePage) => void;
  isOpenMobile?: boolean;
  onCloseMobile?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activePage,
  onNavigate,
  isOpenMobile,
  onCloseMobile,
}) => {
  const navItems: {
    id: ActivePage;
    label: string;
    icon: React.ComponentType<{ className?: string }>;
  }[] = [
    { id: 'overview', label: 'Overview', icon: LayoutDashboard },
    { id: 'network', label: 'AWS Network', icon: Radio },
    { id: 'anomalies', label: 'Anomaly Intelligence', icon: BrainCircuit },
    { id: 'health', label: 'Sensor Health', icon: Activity },
    { id: 'monitoring', label: 'Data & ML Monitoring', icon: Cpu },
    { id: 'reports', label: 'Reports', icon: FileText },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  const handleNav = (page: ActivePage) => {
    onNavigate(page);
    if (onCloseMobile) onCloseMobile();
  };

  return (
    <aside
      className={`fixed inset-y-0 left-0 z-40 w-64 bg-white/75 backdrop-blur-2xl text-slate-800 flex flex-col border-r border-slate-200/60 shadow-[4px_0_24px_rgba(15,23,42,0.02)] transition-transform lg:translate-x-0 ${
        isOpenMobile ? 'translate-x-0' : '-translate-x-full'
      }`}
    >
      {/* Brand Header */}
      <div className="p-5 border-b border-slate-200/50">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center text-white shadow-[0_2px_8px_rgba(0,113,227,0.3)]">
            <Wind className="w-4 h-4 text-white" />
          </div>
          <div>
            <div className="text-base font-semibold tracking-tight text-slate-900 leading-none">
              SkyGuardAI
            </div>
            <div className="text-[10px] font-medium tracking-wider text-slate-500 uppercase mt-1">
              Reliable Data • Resilient Tomorrow
            </div>
          </div>
        </div>
      </div>

      {/* Main Navigation */}
      <div className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        <div className="px-3 pb-2 text-[10px] font-semibold tracking-widest text-slate-400 uppercase">
          Monitoring & Diagnostics
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive =
            activePage === item.id || (activePage === 'station-detail' && item.id === 'network');

          return (
            <button
              key={item.id}
              type="button"
              onClick={() => handleNav(item.id)}
              className={`group w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs font-medium transition-all duration-150 text-left cursor-pointer ${
                isActive
                  ? 'bg-blue-500/10 text-blue-700 font-semibold border border-blue-400/25 shadow-2xs backdrop-blur-xs'
                  : 'text-slate-600 hover:bg-slate-100/70 hover:text-slate-900 border border-transparent'
              }`}
            >
              <div
                className={`flex items-center justify-center transition-colors ${
                  isActive ? 'text-blue-600' : 'text-slate-400 group-hover:text-slate-600'
                }`}
              >
                {isActive ? (
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-600 mr-0.5" />
                ) : (
                  <Icon className="w-4 h-4 shrink-0" />
                )}
              </div>
              <span className="truncate">{item.label}</span>
            </button>
          );
        })}

        {/* Dedicated Evaluation / Simulator Area */}
        <div className="pt-6 px-3 pb-2 text-[10px] font-semibold tracking-widest text-slate-400 uppercase flex items-center justify-between">
          <span>Evaluator Demo</span>
          <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-blue-500/10 text-blue-700 font-medium">
            Pipeline
          </span>
        </div>
        <button
          type="button"
          onClick={() => handleNav('simulator')}
          className={`group w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs font-medium transition-all duration-150 text-left cursor-pointer border ${
            activePage === 'simulator'
              ? 'bg-blue-600 text-white font-semibold border-blue-600 shadow-sm'
              : 'text-slate-700 border-slate-200/80 bg-white/70 hover:bg-blue-50/60 hover:text-blue-700 hover:border-blue-300'
          }`}
        >
          <FlaskConical
            className={`w-4 h-4 shrink-0 transition-colors ${
              activePage === 'simulator' ? 'text-white' : 'text-blue-600'
            }`}
          />
          <span className="truncate">Simulation / Demo Center</span>
        </button>
      </div>

      {/* Footer Branding Area */}
      <div className="p-3.5 mx-3 mb-3 rounded-xl border border-slate-200/60 bg-white/60 text-xs text-slate-500">
        <div className="flex items-center justify-between text-[11px]">
          <span className="font-semibold text-slate-700">SIH26073</span>
          <span className="px-1.5 py-0.2 rounded-full bg-slate-100 text-[10px] font-medium text-slate-600">
            Andhra Pradesh
          </span>
        </div>
        <p className="mt-1 text-[10px] text-slate-400 leading-tight">
          AWS Anomaly Detection & Diagnosis Platform
        </p>
      </div>
    </aside>
  );
};
