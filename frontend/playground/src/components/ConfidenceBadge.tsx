import React from 'react';
import { CheckCircle2, AlertTriangle, AlertOctagon, HelpCircle, ShieldAlert } from 'lucide-react';

interface ConfidenceBadgeProps {
  confidence: number;
  needsHumanReview: boolean;
  tier?: string;
  size?: 'sm' | 'md' | 'lg';
}

export const ConfidenceBadge: React.FC<ConfidenceBadgeProps> = ({
  confidence,
  needsHumanReview,
  tier: propTier,
  size = 'md',
}) => {
  // Determine tier based on confidence score or explicit tier prop
  const tier = (propTier || (confidence >= 0.8 ? 'high' : confidence >= 0.5 ? 'medium' : 'low')).toLowerCase();

  const percentage = Math.round(confidence * 100);

  if (tier === 'high') {
    return (
      <div className="flex flex-col gap-1">
        <div className={`inline-flex items-center gap-2 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-bold ${
          size === 'lg' ? 'px-4 py-2.5 text-base' : size === 'sm' ? 'px-2 py-1 text-xs' : 'px-3 py-1.5 text-sm'
        } shadow-lg shadow-emerald-950/40`}>
          <CheckCircle2 className={`${size === 'lg' ? 'h-5 w-5' : size === 'sm' ? 'h-3.5 w-3.5' : 'h-4 w-4'} text-emerald-400`} />
          <span>HIGH CONFIDENCE</span>
          <span className="font-mono bg-emerald-500/20 px-2 py-0.5 rounded-lg text-xs font-black">
            {percentage}%
          </span>
        </div>
        <span className="text-[11px] text-emerald-400/80 font-medium">
          ✅ Verified delivery anchor — Auto-confirmed for immediate order creation
        </span>
      </div>
    );
  }

  if (tier === 'medium') {
    return (
      <div className="flex flex-col gap-1">
        <div className={`inline-flex items-center gap-2 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400 font-bold ${
          size === 'lg' ? 'px-4 py-2.5 text-base' : size === 'sm' ? 'px-2 py-1 text-xs' : 'px-3 py-1.5 text-sm'
        } shadow-lg shadow-amber-950/40`}>
          <AlertTriangle className={`${size === 'lg' ? 'h-5 w-5' : size === 'sm' ? 'h-3.5 w-3.5' : 'h-4 w-4'} text-amber-400`} />
          <span>MEDIUM CONFIDENCE</span>
          <span className="font-mono bg-amber-500/20 px-2 py-0.5 rounded-lg text-xs font-black">
            {percentage}%
          </span>
        </div>
        <span className="text-[11px] text-amber-300 font-medium flex items-center gap-1">
          <span>⚠️ Ambiguous landmark / postal boundary — Customer pin confirmation enabled below</span>
        </span>
      </div>
    );
  }

  // LOW TIER
  return (
    <div className="flex flex-col gap-1.5">
      <div className={`inline-flex items-center gap-2 rounded-xl bg-rose-500/15 border border-rose-500/40 text-rose-400 font-bold ${
        size === 'lg' ? 'px-4 py-2.5 text-base' : size === 'sm' ? 'px-2 py-1 text-xs' : 'px-3 py-1.5 text-sm'
      } shadow-lg shadow-rose-950/50 animate-pulse-subtle`}>
        <AlertOctagon className={`${size === 'lg' ? 'h-5 w-5' : size === 'sm' ? 'h-3.5 w-3.5' : 'h-4 w-4'} text-rose-400`} />
        <span>LOW CONFIDENCE</span>
        <span className="font-mono bg-rose-500/20 px-2 py-0.5 rounded-lg text-xs font-black">
          {percentage}%
        </span>
      </div>
      {needsHumanReview && (
        <div className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-rose-950/60 border border-rose-800 text-rose-300 text-xs font-semibold">
          <ShieldAlert className="h-3.5 w-3.5 text-rose-400 shrink-0" />
          <span>FLAGGED FOR HUMAN REVIEW — Held from automatic fulfillment</span>
        </div>
      )}
    </div>
  );
};
