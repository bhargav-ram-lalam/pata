import React from 'react';
import { Inbox, CheckCircle2, Edit3, Clock, Activity, RefreshCw } from 'lucide-react';
import type { OpsMetrics } from '../types/api';

interface StatsHeaderProps {
  metrics: OpsMetrics;
  onRefresh: () => void;
  isLoading: boolean;
}

export const StatsHeader: React.FC<StatsHeaderProps> = ({ metrics, onRefresh, isLoading }) => {
  const formatSeconds = (sec: number | null) => {
    if (sec === null || isNaN(sec)) return 'N/A';
    if (sec < 60) return `${sec}s`;
    if (sec < 3600) return `${Math.round(sec / 60)}m`;
    return `${(sec / 3600).toFixed(1)}h`;
  };

  return (
    <div className="space-y-4">
      {/* Top Title & Refresh */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <span>Operational Verification Backlog</span>
            <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
              Prometheus Telemetry Live
            </span>
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Resolutions flagged with <code className="text-rose-600 dark:text-rose-300">needs_human_review=true</code> awaiting operator action.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs text-slate-700 dark:text-slate-300 shadow-sm">
            <div className={`h-2 w-2 rounded-full ${metrics.backendHealthy ? 'bg-emerald-500 dark:bg-emerald-400 animate-pulse' : 'bg-rose-500'}`} />
            <span className="font-mono text-[11px]">
              {metrics.backendHealthy ? 'Engine Healthy' : 'Engine Offline'}
            </span>
          </div>

          <button
            onClick={onRefresh}
            disabled={isLoading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white hover:bg-slate-100 dark:bg-slate-900 dark:hover:bg-slate-800 border border-slate-300 dark:border-slate-700 text-xs font-semibold text-slate-700 dark:text-slate-200 transition-colors shadow-sm disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* 4 Stats Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        
        {/* Card 1: Queue Backlog */}
        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800 shadow-sm dark:shadow-lg space-y-1 transition-colors duration-200">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400">
            <span className="text-xs font-bold uppercase tracking-wider">Queue Backlog</span>
            <Inbox className="h-4 w-4 text-amber-500 dark:text-amber-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl sm:text-3xl font-black font-mono text-slate-900 dark:text-white">
              {metrics.queueSize}
            </span>
            <span className="text-[11px] text-amber-600 dark:text-amber-400/80 font-medium">pending</span>
          </div>
          <p className="text-[10px] text-slate-400 dark:text-slate-500 font-mono">pata_review_queue_size</p>
        </div>

        {/* Card 2: Confirmed Correct */}
        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800 shadow-sm dark:shadow-lg space-y-1 transition-colors duration-200">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400">
            <span className="text-xs font-bold uppercase tracking-wider">Confirmed</span>
            <CheckCircle2 className="h-4 w-4 text-emerald-500 dark:text-emerald-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl sm:text-3xl font-black font-mono text-emerald-600 dark:text-emerald-400">
              {metrics.reviewsConfirmed}
            </span>
            <span className="text-[11px] text-emerald-600/80 dark:text-emerald-400/80 font-medium">auto-verified</span>
          </div>
          <p className="text-[10px] text-slate-400 dark:text-slate-500 font-mono">outcome="confirmed"</p>
        </div>

        {/* Card 3: Corrected by Ops */}
        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800 shadow-sm dark:shadow-lg space-y-1 transition-colors duration-200">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400">
            <span className="text-xs font-bold uppercase tracking-wider">Corrected</span>
            <Edit3 className="h-4 w-4 text-cyan-600 dark:text-cyan-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl sm:text-3xl font-black font-mono text-cyan-600 dark:text-cyan-400">
              {metrics.reviewsCorrected}
            </span>
            <span className="text-[11px] text-cyan-600/80 dark:text-cyan-400/80 font-medium">fine-tune rows</span>
          </div>
          <p className="text-[10px] text-slate-400 dark:text-slate-500 font-mono">outcome="corrected"</p>
        </div>

        {/* Card 4: Avg Turnaround */}
        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800 shadow-sm dark:shadow-lg space-y-1 transition-colors duration-200">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400">
            <span className="text-xs font-bold uppercase tracking-wider">Avg Turnaround</span>
            <Clock className="h-4 w-4 text-purple-500 dark:text-purple-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl sm:text-3xl font-black font-mono text-purple-600 dark:text-purple-300">
              {formatSeconds(metrics.avgTurnaroundSec)}
            </span>
            <span className="text-[11px] text-purple-600/80 dark:text-purple-400/80 font-medium">SLA</span>
          </div>
          <p className="text-[10px] text-slate-400 dark:text-slate-500 font-mono">pata_review_turnaround</p>
        </div>

      </div>
    </div>
  );
};
