import React from 'react';
import { Layers, Building, Landmark, Compass, Map, Home, Hash } from 'lucide-react';
import { ParsedAddress } from '../types/api';

interface ParsedFieldsCardProps {
  parsed: ParsedAddress;
}

const FIELD_CONFIGS = [
  { key: 'pincode', label: 'Pincode', icon: Hash, color: 'text-brand-400 bg-brand-500/10 border-brand-500/20' },
  { key: 'city', label: 'City / Taluk', icon: Building, color: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/20' },
  { key: 'district', label: 'District', icon: Map, color: 'text-indigo-400 bg-indigo-500/10 border-indigo-500/20' },
  { key: 'state', label: 'State', icon: Compass, color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20' },
  { key: 'landmark', label: 'Landmark', icon: Landmark, color: 'text-amber-400 bg-amber-500/10 border-amber-500/20' },
  { key: 'locality', label: 'Locality / Sector', icon: Compass, color: 'text-purple-400 bg-purple-500/10 border-purple-500/20' },
  { key: 'building_name', label: 'Building / Society', icon: Home, color: 'text-rose-400 bg-rose-500/10 border-rose-500/20' },
  { key: 'road', label: 'Road / Street', icon: Compass, color: 'text-blue-400 bg-blue-500/10 border-blue-500/20' },
];

export const ParsedFieldsCard: React.FC<ParsedFieldsCardProps> = ({ parsed }) => {
  return (
    <div className="rounded-2xl bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 p-4 sm:p-5 shadow-lg dark:shadow-xl space-y-4 transition-colors duration-200">
      <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <Layers className="h-5 w-5 text-cyan-600 dark:text-cyan-400" />
          <h3 className="text-sm font-bold text-slate-900 dark:text-white tracking-wide">Standardized Address Hierarchy</h3>
        </div>
        <span className="text-[11px] font-mono text-slate-600 dark:text-slate-400 bg-slate-100 dark:bg-slate-950 px-2 py-0.5 rounded border border-slate-200 dark:border-slate-800">
          ISO / India Post Schema
        </span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
        {FIELD_CONFIGS.map((field) => {
          const value = parsed[field.key];
          const Icon = field.icon;
          const hasValue = value !== undefined && value !== null && String(value).trim() !== '';

          return (
            <div
              key={field.key}
              className={`p-2.5 rounded-xl border flex flex-col justify-between transition-all ${
                hasValue
                  ? 'bg-slate-50 dark:bg-slate-950 border-slate-200 dark:border-slate-800 shadow-sm hover:border-slate-300 dark:hover:border-slate-700'
                  : 'bg-slate-50/40 dark:bg-slate-950/40 border-slate-200/40 dark:border-slate-800/40 opacity-40'
              }`}
            >
              <div className="flex items-center justify-between gap-1 mb-1">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  {field.label}
                </span>
                <Icon className="h-3 w-3 text-slate-400 dark:text-slate-500" />
              </div>

              <div className="mt-0.5">
                {hasValue ? (
                  <span className="text-xs font-bold text-slate-900 dark:text-slate-100 font-mono break-words">
                    {String(value)}
                  </span>
                ) : (
                  <span className="text-xs text-slate-400 dark:text-slate-600 font-mono italic">
                    Not extracted
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
