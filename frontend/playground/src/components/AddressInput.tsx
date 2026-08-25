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
          <label className="text-xs font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400 flex items-center gap-1.5">
            <Sparkles className="h-3.5 w-3.5 text-amber-500 dark:text-amber-400" />
            <span>Benchmark Indian Addresses (One-Click Demo)</span>
          </label>
          <span className="text-[11px] text-slate-400 dark:text-slate-500 hidden sm:inline">
            From tests/test_pipeline.py Gold Test Set
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
          {GOLD_EXAMPLES.map((ex) => {
            const isSelected = selectedExampleId === ex.id;
            const badgeColor =
              ex.category === 'HIGH'
                ? 'text-emerald-600 dark:text-emerald-400 border-emerald-500/30 bg-emerald-50 dark:bg-emerald-500/10'
                : ex.category === 'MEDIUM'
                ? 'text-amber-600 dark:text-amber-400 border-amber-500/30 bg-amber-50 dark:bg-amber-500/10'
                : 'text-rose-600 dark:text-rose-400 border-rose-500/30 bg-rose-50 dark:bg-rose-500/10';

            return (
              <button
                key={ex.id}
                type="button"
                onClick={() => handleSelectExample(ex)}
                disabled={isLoading}
                className={`p-2.5 rounded-xl border text-left flex flex-col justify-between transition-all duration-200 ${
                  isSelected
                    ? 'bg-white dark:bg-slate-900 border-brand-500 shadow-lg shadow-brand-500/10 ring-1 ring-brand-500'
                    : 'bg-white/80 hover:bg-white dark:bg-slate-900/60 dark:hover:bg-slate-900 border-slate-200 hover:border-slate-300 dark:border-slate-800 dark:hover:border-slate-700 shadow-sm'
                }`}
              >
                <div>
                  <span className={`text-[9px] font-black uppercase tracking-wider px-1.5 py-0.5 rounded border ${badgeColor} inline-block mb-1`}>
                    {ex.category} TIER
                  </span>
                  <h4 className="text-xs font-bold text-slate-900 dark:text-slate-200 line-clamp-1">
                    {ex.title}
                  </h4>
                </div>
                <p className="text-[10px] text-slate-500 dark:text-slate-400 line-clamp-2 mt-1 font-mono">
                  {ex.address}
                </p>
              </button>
            );
          })}
        </div>
      </div>

      {/* Main Address Input Box */}
      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="relative rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-2 sm:p-3 shadow-lg dark:shadow-2xl focus-within:border-brand-500 focus-within:ring-2 focus-within:ring-brand-500/20 transition-all">
          <div className="flex items-start gap-2 sm:gap-3">
            <div className="p-2 sm:p-2.5 rounded-xl bg-slate-100 dark:bg-slate-950 text-brand-600 dark:text-brand-400 mt-1 shrink-0">
              <MapPin className="h-5 w-5" />
            </div>

            <div className="flex-1 min-w-0">
              <textarea
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                placeholder="Paste or type any unstructured Indian address (e.g. Near old temple, Behind post office, Koramangala 5th block, Bengaluru 560095)..."
                rows={2}
                className="w-full bg-transparent text-sm sm:text-base font-medium text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none resize-none"
              />
            </div>
          </div>

          {/* Bottom Bar inside Input: GPS Hint trigger + Resolve CTA */}
          <div className="flex items-center justify-between border-t border-slate-100 dark:border-slate-800/80 pt-2 mt-2 px-1">
            <button
              type="button"
              onClick={() => setShowGpsHints(!showGpsHints)}
              className="flex items-center gap-1.5 text-xs text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 font-medium py-1 px-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            >
              <Navigation className="h-3.5 w-3.5 text-cyan-500 dark:text-cyan-400" />
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
          <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800 flex flex-col sm:flex-row gap-3 animate-fade-in">
            <div className="flex-1 space-y-1">
              <label className="text-[11px] font-mono text-slate-600 dark:text-slate-400">Device GPS Latitude (India: 2.5 to 38.5)</label>
              <input
                type="number"
                step="any"
                value={hintLat}
                onChange={(e) => setHintLat(e.target.value)}
                placeholder="e.g. 12.9003"
                className="w-full px-3 py-1.5 rounded-lg bg-white dark:bg-slate-950 border border-slate-300 dark:border-slate-800 text-xs font-mono text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-600 focus:outline-none focus:border-brand-500"
              />
            </div>
            <div className="flex-1 space-y-1">
              <label className="text-[11px] font-mono text-slate-600 dark:text-slate-400">Device GPS Longitude (India: 63.5 to 99.5)</label>
              <input
                type="number"
                step="any"
                value={hintLng}
                onChange={(e) => setHintLng(e.target.value)}
                placeholder="e.g. 77.5981"
                className="w-full px-3 py-1.5 rounded-lg bg-white dark:bg-slate-950 border border-slate-300 dark:border-slate-800 text-xs font-mono text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-600 focus:outline-none focus:border-brand-500"
              />
            </div>
          </div>
        )}

        {/* Error Alert */}
        {error && (
          <div className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-700 dark:text-rose-300 text-xs flex items-start gap-2.5 animate-fade-in shadow-sm">
            <AlertCircle className="h-4 w-4 text-rose-500 dark:text-rose-400 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <p className="font-bold">Address Resolution Failed {error.status ? `(HTTP ${error.status})` : ''}</p>
              <p>{error.message}</p>
              {error.retryAfter && (
                <p className="font-mono text-[11px] text-rose-500 dark:text-rose-400">
                  Rate limit active. Retry available in {error.retryAfter} seconds.
                </p>
              )}
            </div>
          </div>
        )}
      </form>
    </div>
  );
};
