import React, { useState } from 'react';
import { Search, Sparkles, Navigation, AlertCircle, RefreshCw, ChevronDown, ChevronUp, MapPin } from 'lucide-react';
import { GOLD_EXAMPLES } from '../data/examples';
import { ExampleAddress, ResolveRequestPayload } from '../types/api';

interface AddressInputProps {
  onResolve: (payload: ResolveRequestPayload) => void;
  isLoading: boolean;
  error: { status: number; message: string; retryAfter?: number } | null;
}

export const AddressInput: React.FC<AddressInputProps> = ({ onResolve, isLoading, error }) => {
  const [address, setAddress] = useState(GOLD_EXAMPLES[0].address);
  const [hintLat, setHintLat] = useState<string>(GOLD_EXAMPLES[0].hint_lat ? String(GOLD_EXAMPLES[0].hint_lat) : '');
  const [hintLng, setHintLng] = useState<string>(GOLD_EXAMPLES[0].hint_lng ? String(GOLD_EXAMPLES[0].hint_lng) : '');
  const [showGpsHints, setShowGpsHints] = useState(false);
  const [selectedExampleId, setSelectedExampleId] = useState<string>(GOLD_EXAMPLES[0].id);

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!address.trim() || isLoading) return;

    const payload: ResolveRequestPayload = {
      address: address.trim(),
      hint_lat: hintLat.trim() ? parseFloat(hintLat.trim()) : undefined,
      hint_lng: hintLng.trim() ? parseFloat(hintLng.trim()) : undefined,
    };
    onResolve(payload);
  };

  const handleSelectExample = (ex: ExampleAddress) => {
    setSelectedExampleId(ex.id);
    setAddress(ex.address);
    setHintLat(ex.hint_lat !== undefined ? String(ex.hint_lat) : '');
    setHintLng(ex.hint_lng !== undefined ? String(ex.hint_lng) : '');
    
    // Automatically trigger resolve for one-click demo flow
    const payload: ResolveRequestPayload = {
      address: ex.address,
      hint_lat: ex.hint_lat,
      hint_lng: ex.hint_lng,
    };
    onResolve(payload);
  };

  return (
    <div className="space-y-4">
      {/* Example Chips Carousel / Selector */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
            <Sparkles className="h-3.5 w-3.5 text-amber-400" />
            <span>Benchmark Indian Addresses (One-Click Demo)</span>
          </label>
          <span className="text-[11px] text-slate-500 hidden sm:inline">
            From tests/test_pipeline.py Gold Test Set
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
          {GOLD_EXAMPLES.map((ex) => {
            const isSelected = selectedExampleId === ex.id;
            const badgeColor =
              ex.category === 'HIGH'
                ? 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10'
                : ex.category === 'MEDIUM'
                ? 'text-amber-400 border-amber-500/30 bg-amber-500/10'
                : 'text-rose-400 border-rose-500/30 bg-rose-500/10';

            return (
              <button
                key={ex.id}
                type="button"
                onClick={() => handleSelectExample(ex)}
                disabled={isLoading}
                className={`p-2.5 rounded-xl border text-left flex flex-col justify-between transition-all duration-200 ${
                  isSelected
                    ? 'bg-slate-900 border-brand-500 shadow-lg shadow-brand-500/10 ring-1 ring-brand-500'
                    : 'bg-slate-900/60 hover:bg-slate-900 border-slate-800 hover:border-slate-700'
                }`}
              >
                <div>
                  <span className={`text-[9px] font-black uppercase tracking-wider px-1.5 py-0.5 rounded border ${badgeColor} inline-block mb-1`}>
                    {ex.category} TIER
                  </span>
                  <h4 className="text-xs font-bold text-slate-200 line-clamp-1">
                    {ex.title}
                  </h4>
                </div>
                <p className="text-[10px] text-slate-400 line-clamp-2 mt-1 font-mono">
                  {ex.address}
                </p>
              </button>
            );
          })}
        </div>
      </div>

      {/* Main Address Input Box */}
      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="relative rounded-2xl bg-slate-900 border border-slate-800 p-2 sm:p-3 shadow-2xl focus-within:border-brand-500 focus-within:ring-2 focus-within:ring-brand-500/20 transition-all">
          <div className="flex items-start gap-2 sm:gap-3">
            <div className="p-2 sm:p-2.5 rounded-xl bg-slate-950 text-brand-400 mt-1 shrink-0">
              <MapPin className="h-5 w-5" />
            </div>

            <div className="flex-1 min-w-0">
              <textarea
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                placeholder="Paste or type any unstructured Indian address (e.g. Near old temple, Behind post office, Koramangala 5th block, Bengaluru 560095)..."
                rows={2}
                className="w-full bg-transparent text-sm sm:text-base font-medium text-white placeholder-slate-500 focus:outline-none resize-none"
              />
            </div>
          </div>

          {/* Bottom Bar inside Input: GPS Hint trigger + Resolve CTA */}
          <div className="flex items-center justify-between border-t border-slate-800/80 pt-2 mt-2 px-1">
            <button
              type="button"
              onClick={() => setShowGpsHints(!showGpsHints)}
              className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 font-medium py-1 px-2 rounded-lg hover:bg-slate-800 transition-colors"
            >
              <Navigation className="h-3.5 w-3.5 text-cyan-400" />
              <span>{showGpsHints ? 'Hide GPS Device Hints' : '+ Add GPS Lat/Lng Hint'}</span>
              {showGpsHints ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
            </button>

            <button
              type="submit"
              disabled={isLoading || !address.trim()}
              className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-brand-600 via-indigo-600 to-cyan-500 hover:from-brand-500 hover:to-cyan-400 text-white font-bold text-xs sm:text-sm flex items-center gap-2 transition-all duration-200 shadow-lg shadow-brand-500/25 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <>
                  <RefreshCw className="h-4 w-4 animate-spin" />
                  <span>Resolving Address...</span>
                </>
              ) : (
                <>
                  <Search className="h-4 w-4" />
                  <span>Resolve Address</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* GPS Hints Accordion */}
        {showGpsHints && (
          <div className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 flex flex-col sm:flex-row gap-3 animate-fade-in">
            <div className="flex-1 space-y-1">
              <label className="text-[11px] font-mono text-slate-400">Device GPS Latitude (India: 2.5 to 38.5)</label>
              <input
                type="number"
                step="any"
                value={hintLat}
                onChange={(e) => setHintLat(e.target.value)}
                placeholder="e.g. 12.9003"
                className="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono text-white placeholder-slate-600 focus:outline-none focus:border-brand-500"
              />
            </div>
            <div className="flex-1 space-y-1">
              <label className="text-[11px] font-mono text-slate-400">Device GPS Longitude (India: 63.5 to 99.5)</label>
              <input
                type="number"
                step="any"
                value={hintLng}
                onChange={(e) => setHintLng(e.target.value)}
                placeholder="e.g. 77.5981"
                className="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono text-white placeholder-slate-600 focus:outline-none focus:border-brand-500"
              />
            </div>
          </div>
        )}
      </form>

      {/* Error Alert Display */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-950/60 border border-rose-800/80 text-rose-200 text-xs space-y-1 animate-fade-in shadow-xl">
          <div className="flex items-center gap-2 font-bold text-rose-300">
            <AlertCircle className="h-4 w-4 text-rose-400" />
            <span>
              {error.status === 401
                ? '401 Unauthorized — Invalid or Missing API Key'
                : error.status === 429
                ? `429 Rate Limit Exceeded (Retry in ${error.retryAfter || 1}s)`
                : `Error ${error.status || 'Network'}: Request Failed`}
            </span>
          </div>
          <p className="text-rose-300/80 font-mono text-[11px]">
            {error.message}
          </p>
        </div>
      )}
    </div>
  );
};
