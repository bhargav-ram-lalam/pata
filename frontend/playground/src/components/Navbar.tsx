import React, { useState, useEffect } from 'react';
import { MapPin, Key, Activity, Sparkles, ExternalLink, ShieldCheck } from 'lucide-react';
import { getStoredApiKey, setStoredApiKey, checkBackendHealth } from '../services/api';

interface NavbarProps {
  onApiKeyChange?: (key: string) => void;
}

export const Navbar: React.FC<NavbarProps> = ({ onApiKeyChange }) => {
  const [apiKey, setApiKey] = useState(getStoredApiKey());
  const [showKeyModal, setShowKeyModal] = useState(false);
  const [tempKey, setTempKey] = useState(apiKey);
  const [health, setHealth] = useState<{ live: boolean; ready: boolean }>({ live: false, ready: false });

  useEffect(() => {
    const probe = async () => {
      const h = await checkBackendHealth();
      setHealth(h);
    };
    probe();
    const interval = setInterval(probe, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleSaveKey = () => {
    setStoredApiKey(tempKey);
    setApiKey(tempKey);
    setShowKeyModal(false);
    if (onApiKeyChange) onApiKeyChange(tempKey);
  };

  return (
    <header className="sticky top-0 z-50 border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        
        {/* Brand Logo & Name */}
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-brand-600 via-indigo-500 to-cyan-400 p-0.5 shadow-lg shadow-brand-500/20">
            <div className="h-full w-full bg-slate-950 rounded-[10px] flex items-center justify-center">
              <MapPin className="h-5 w-5 text-cyan-400 animate-pulse-subtle" />
            </div>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xl font-black tracking-tight text-white">
                Pata <span className="text-brand-400 font-medium">(पता)</span>
              </span>
              <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                v0.4.0 Live
              </span>
            </div>
            <p className="text-xs text-slate-400 font-medium hidden sm:block">
              AI Address Resolution & Geocoding for Indian Last-Mile Logistics
            </p>
          </div>
        </div>

        {/* Right Actions: Health, Ops Dashboard Link, API Key */}
        <div className="flex items-center gap-3">
          {/* Service Health Indicator */}
          <div 
            className="flex items-center gap-2 px-2.5 py-1 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-300"
            title={`Backend Service: ${health.ready ? 'Ready & Warmed' : health.live ? 'Live (Warming Up)' : 'Offline / Standalone'}`}
          >
            <div className={`h-2 w-2 rounded-full ${health.ready ? 'bg-emerald-400 animate-pulse' : health.live ? 'bg-amber-400' : 'bg-rose-500'}`} />
            <span className="font-mono text-[11px] hidden md:inline">
              {health.ready ? 'Engine Ready' : health.live ? 'Warming Models' : 'API Standalone'}
            </span>
          </div>

          {/* Review Dashboard Link */}
          <a
            href="http://localhost:5174"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700 text-xs font-semibold text-slate-200 transition-colors shadow-sm"
          >
            <ShieldCheck className="h-3.5 w-3.5 text-brand-400" />
            <span className="hidden sm:inline">Ops Review Dashboard</span>
            <ExternalLink className="h-3 w-3 text-slate-400" />
          </a>

          {/* API Key Configure Button */}
          <button
            onClick={() => {
              setTempKey(apiKey);
              setShowKeyModal(true);
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-brand-600/10 hover:bg-brand-600/20 border border-brand-500/30 text-xs font-semibold text-brand-300 transition-colors"
          >
            <Key className="h-3.5 w-3.5 text-brand-400" />
            <span className="font-mono hidden md:inline">{apiKey ? `${apiKey.slice(0, 8)}...` : 'Set Key'}</span>
            <span className="md:hidden">Key</span>
          </button>
        </div>
      </div>

      {/* API Key Modal */}
      {showKeyModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-fade-in">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-xl bg-brand-500/10 border border-brand-500/20 text-brand-400">
                <Key className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">API Authentication Key</h3>
                <p className="text-xs text-slate-400">Sent via X-API-Key header to Pata backend</p>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-300 block">
                X-API-Key Token
              </label>
              <input
                type="text"
                value={tempKey}
                onChange={(e) => setTempKey(e.target.value)}
                placeholder="pata_dev_key"
                className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm font-mono text-white placeholder-slate-600 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
              />
              <p className="text-[11px] text-slate-500">
                Default local dev key: <code className="text-brand-300">pata_dev_key</code> or <code className="text-brand-300">test_api_key_stage3</code>
              </p>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
              <button
                type="button"
                onClick={() => setShowKeyModal(false)}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-300 transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSaveKey}
                className="px-4 py-2 rounded-xl bg-brand-600 hover:bg-brand-500 text-xs font-semibold text-white transition-colors shadow-lg shadow-brand-600/30"
              >
                Save Key
              </button>
            </div>
          </div>
        </div>
      )}
    </header>
  );
};
