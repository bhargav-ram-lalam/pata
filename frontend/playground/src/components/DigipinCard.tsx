import React, { useState } from 'react';
import { QrCode, Copy, Check, Info, Grid, ShieldCheck } from 'lucide-react';

interface DigipinCardProps {
  digipin: string | null;
  latitude: number | null;
  longitude: number | null;
}

export const DigipinCard: React.FC<DigipinCardProps> = ({ digipin, latitude, longitude }) => {
  const [copied, setCopied] = useState(false);
  const [showTooltip, setShowTooltip] = useState(false);

  const handleCopy = () => {
    if (!digipin) return;
    navigator.clipboard.writeText(digipin);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Format 10-char DIGIPIN into standard readable blocks (e.g. 4-4-2 or 3-3-4)
  const formattedPin = digipin
    ? `${digipin.slice(0, 3)}-${digipin.slice(3, 6)}-${digipin.slice(6)}`
    : null;

  return (
    <div className="rounded-2xl bg-gradient-to-br from-slate-900 via-slate-900 to-indigo-950/40 border border-slate-800 p-4 sm:p-5 shadow-xl space-y-3 relative">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <Grid className="h-5 w-5 text-indigo-400" />
          <h3 className="text-sm font-bold text-white tracking-wide">DIGIPIN Digital Postal Code</h3>
        </div>

        {/* Factual Tooltip Trigger */}
        <div className="relative">
          <button
            onMouseEnter={() => setShowTooltip(true)}
            onMouseLeave={() => setShowTooltip(false)}
            onClick={() => setShowTooltip(!showTooltip)}
            className="flex items-center gap-1 text-[11px] text-slate-400 hover:text-slate-200 bg-slate-950 px-2 py-1 rounded-lg border border-slate-800 transition-colors"
          >
            <Info className="h-3.5 w-3.5 text-indigo-400" />
            <span className="hidden sm:inline">What is DIGIPIN?</span>
          </button>

          {showTooltip && (
            <div className="absolute right-0 top-8 z-50 w-72 p-3 rounded-xl bg-slate-900 border border-indigo-500/30 text-xs text-slate-300 shadow-2xl space-y-1.5 animate-fade-in">
              <div className="flex items-center gap-1.5 font-bold text-indigo-300">
                <ShieldCheck className="h-4 w-4" />
                <span>India Post & IIT Hyderabad Standard</span>
              </div>
              <p className="text-[11px] text-slate-300 leading-relaxed">
                DIGIPIN is a 10-character alphanumeric geo-spatial grid code dividing India into hierarchical ~4m × 4m cells. Unlike legacy street names, it provides an exact, language-neutral physical location anchor for delivery navigation.
              </p>
            </div>
          )}
        </div>
      </div>

      {digipin ? (
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 p-3.5 rounded-xl bg-slate-950 border border-slate-800">
          <div>
            <span className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 block mb-0.5">
              10-Character Postal Grid Identifier
            </span>
            <div className="flex items-center gap-2">
              <span className="text-xl sm:text-2xl font-mono font-black text-indigo-300 tracking-wider">
                {digipin}
              </span>
              <span className="text-xs font-mono text-slate-500 hidden sm:inline">
                ({formattedPin})
              </span>
            </div>
          </div>

          <button
            onClick={handleCopy}
            className="w-full sm:w-auto px-3.5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700 text-xs font-semibold text-slate-200 flex items-center justify-center gap-1.5 transition-colors shadow-sm"
          >
            {copied ? (
              <>
                <Check className="h-3.5 w-3.5 text-emerald-400" />
                <span className="text-emerald-400">Copied</span>
              </>
            ) : (
              <>
                <Copy className="h-3.5 w-3.5 text-slate-400" />
                <span>Copy Code</span>
              </>
            )}
          </button>
        </div>
      ) : (
        <div className="p-3.5 rounded-xl bg-slate-950/40 border border-slate-800/40 text-center text-xs text-slate-500 italic">
          DIGIPIN code requires valid coordinates to compute grid cell.
        </div>
      )}
    </div>
  );
};
