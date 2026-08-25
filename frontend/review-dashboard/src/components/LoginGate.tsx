import React, { useState } from 'react';
import { ShieldCheck, Key, ArrowRight, Lock, Sparkles, MapPin } from 'lucide-react';
import { setSessionApiKey } from '../services/api';
import { ThemeToggle } from './ThemeToggle';

interface LoginGateProps {
  onLogin: (apiKey: string) => void;
}

export const LoginGate: React.FC<LoginGateProps> = ({ onLogin }) => {
  const [apiKey, setApiKey] = useState('');
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!apiKey.trim()) {
      setError('Please enter a valid API key');
      return;
    }

    setSessionApiKey(apiKey.trim());
    onLogin(apiKey.trim());
  };

  const handleQuickFill = (key: string) => {
    setApiKey(key);
    setSessionApiKey(key);
    onLogin(key);
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex flex-col items-center justify-center p-4 relative transition-colors duration-200">
      {/* Top Bar with ThemeToggle */}
      <div className="absolute top-4 right-4 z-50">
        <ThemeToggle />
      </div>

      {/* Background Glow */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -left-40 w-96 h-96 bg-brand-500/10 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 -right-40 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl" />
      </div>

      <div className="relative w-full max-w-md bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl p-8 shadow-xl dark:shadow-2xl space-y-6 animate-slide-up transition-colors duration-200">
        
        {/* Brand Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex h-14 w-14 rounded-2xl bg-gradient-to-tr from-brand-600 via-indigo-500 to-cyan-400 p-0.5 shadow-xl shadow-brand-500/20 mb-2">
            <div className="h-full w-full bg-white dark:bg-slate-950 rounded-[14px] flex items-center justify-center">
              <ShieldCheck className="h-7 w-7 text-cyan-500 dark:text-cyan-400" />
            </div>
          </div>
          <h1 className="text-2xl font-black tracking-tight text-slate-900 dark:text-white">
            Pata Ops Review Dashboard
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Human-in-the-Loop Address Verification & Correction Engine
          </p>
        </div>

        {/* Auth Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400 flex items-center gap-1.5">
              <Key className="h-3.5 w-3.5 text-brand-600 dark:text-brand-400" />
              <span>Enter API Key</span>
            </label>

            <div className="relative">
              <input
                type="password"
                value={apiKey}
                onChange={(e) => {
                  setApiKey(e.target.value);
                  setError(null);
                }}
                placeholder="Paste X-API-Key token..."
                className="w-full px-4 py-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-800 text-sm font-mono text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-600 focus:outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 transition-all"
              />
            </div>

            {error && (
              <p className="text-xs text-rose-600 dark:text-rose-400 font-medium">
                {error}
              </p>
            )}
          </div>

          <button
            type="submit"
            className="w-full py-3 px-4 rounded-xl bg-gradient-to-r from-brand-600 via-indigo-600 to-cyan-500 hover:from-brand-500 hover:to-cyan-400 text-white font-bold text-sm flex items-center justify-center gap-2 transition-all shadow-lg shadow-brand-500/25"
          >
            <span>Access Review Dashboard</span>
            <ArrowRight className="h-4 w-4" />
          </button>
        </form>

        {/* Quick Dev Key Helpers */}
        <div className="border-t border-slate-200 dark:border-slate-800 pt-4 space-y-2">
          <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block text-center">
            Development Quick Access
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => handleQuickFill('pata_dev_key')}
              className="flex-1 py-2 px-3 rounded-xl bg-slate-50 hover:bg-slate-100 dark:bg-slate-950 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-800 text-xs font-mono text-brand-700 dark:text-brand-300 transition-colors text-center font-semibold"
            >
              pata_dev_key
            </button>
            <button
              type="button"
              onClick={() => handleQuickFill('test_api_key_stage3')}
              className="flex-1 py-2 px-3 rounded-xl bg-slate-50 hover:bg-slate-100 dark:bg-slate-950 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-800 text-xs font-mono text-cyan-700 dark:text-cyan-300 transition-colors text-center font-semibold"
            >
              test_api_key_stage3
            </button>
          </div>
        </div>

        {/* Security / Privacy Footnote */}
        <div className="flex items-center justify-center gap-1.5 text-[11px] text-slate-500">
          <Lock className="h-3 w-3" />
          <span>Keys are stored in session memory only (DPDP 2023 Guardrail)</span>
        </div>
      </div>
    </div>
  );
};
