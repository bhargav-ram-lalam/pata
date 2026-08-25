import React, { useState, useEffect } from 'react';
import { Cpu, CheckCircle, Slash, Clock, ArrowRight, Zap, Info } from 'lucide-react';
import { PipelineTraceStep } from '../types/api';

interface LiveTracePanelProps {
  trace: PipelineTraceStep[];
  isLoading: boolean;
  totalLatencyMs?: number;
  confidence?: number;
}

/**
 * LiveTracePanel:
 * Renders the multi-agent pipeline trace.
 *
 * ARCHITECTURAL NOTE:
 * The backend currently executes the pipeline synchronously inside FastAPI and
 * returns the full `pipeline_trace` array in the JSON response.
 * To provide a responsive, live-updating feel without a single static spinner,
 * this component simulates a staged progressive reveal client-side driven by the
 * real per-agent latencies returned in `pipeline_trace`.
 *
 * FUTURE ENHANCEMENT ROADMAP:
 * A future version can add Server-Sent Events (SSE) or WebSocket streaming at
 * `GET /v1/resolve/stream` to stream each agent event in real-time.
 */

const AGENT_DEFINITIONS = [
  {
    key: 'Agent1_DeterministicParser',
    displayName: 'A1: Deterministic Parser',
    tag: 'BharatAddress & Pincode DB',
    description: 'Rule-based postal parsing, pincode centroid geocoding, and phonetic alias normalizer.',
    defaultLatency: '< 1ms',
  },
  {
    key: 'Agent2_LandmarkNER',
    displayName: 'A2: IndicBERT Address NER',
    tag: 'Shiprocket IndicBERT',
    description: 'Transformer token classification isolating informal landmarks, road cues, and localities.',
    defaultLatency: '~35–60ms',
  },
  {
    key: 'Agent3_LandmarkResolution',
    displayName: 'A3: OSM Landmark Resolution',
    tag: 'Overpass API & Redis Cache',
    description: 'Spatial radius POI search around pincode centroid with circuit breaker & Redis cache.',
    defaultLatency: '~300–1200ms',
  },
  {
    key: 'Agent4_ConfidenceArbitration',
    displayName: 'A4: Confidence Arbitration',
    tag: 'Multi-Tier Logic / LLM',
    description: 'Multi-tier confidence gating (HIGH/MEDIUM/LOW) with Claude Haiku fallback on ambiguous cases.',
    defaultLatency: '< 1ms (or 400ms LLM)',
  },
  {
    key: 'Agent5_SelfCheck',
    displayName: 'A5: Self-Check & Audit',
    tag: 'Quality Guardrail',
    description: 'Verifies state/pincode bounds, checks deliverability, and assigns needs_human_review flag.',
    defaultLatency: '1–3ms',
  },
];

export const LiveTracePanel: React.FC<LiveTracePanelProps> = ({
  trace,
  isLoading,
  totalLatencyMs,
  confidence,
}) => {
  const [revealedCount, setRevealedCount] = useState<number>(0);

  // Progressive reveal effect when trace updates
  useEffect(() => {
    if (isLoading) {
      setRevealedCount(0);
      return;
    }

    if (trace && trace.length > 0) {
      setRevealedCount(0);
      const interval = setInterval(() => {
        setRevealedCount((prev) => {
          if (prev < trace.length) {
            return prev + 1;
          }
          clearInterval(interval);
          return prev;
        });
      }, 70); // Smooth stagger reveal

      return () => clearInterval(interval);
    }
  }, [trace, isLoading]);

  return (
    <div className="rounded-2xl bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 p-4 sm:p-5 shadow-lg dark:shadow-xl space-y-4 transition-colors duration-200">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <Cpu className="h-5 w-5 text-brand-600 dark:text-brand-400" />
          <h3 className="text-sm font-bold text-slate-900 dark:text-white tracking-wide">Multi-Agent Pipeline Trace</h3>
        </div>

        {/* Live Timing / Cost metrics */}
        <div className="flex items-center gap-2 text-xs font-mono text-slate-500 dark:text-slate-400">
          {isLoading ? (
            <span className="flex items-center gap-1.5 text-brand-600 dark:text-brand-400 animate-pulse">
              <Zap className="h-3.5 w-3.5" /> Running Pipeline Agents...
            </span>
          ) : totalLatencyMs !== undefined ? (
            <div className="flex items-center gap-2 bg-slate-100 dark:bg-slate-950 px-2.5 py-1 rounded-lg border border-slate-200 dark:border-slate-800">
              <Clock className="h-3 w-3 text-slate-400 dark:text-slate-500" />
              <span className="text-slate-700 dark:text-slate-300 font-semibold">{totalLatencyMs.toFixed(1)}ms</span>
            </div>
          ) : null}
        </div>
      </div>

      {/* Agents List */}
      <div className="space-y-2.5">
        {AGENT_DEFINITIONS.map((def, idx) => {
          // Find matching actual trace step from backend response
          const actualStep = trace.find(
            (t) => t.agent.toLowerCase() === def.key.toLowerCase() || t.agent.includes(def.key)
          );
          
          const isRevealed = !isLoading && idx < revealedCount;
          const hasRan = actualStep?.ran ?? false;
          const latency = actualStep?.latency_ms !== undefined ? `${actualStep.latency_ms.toFixed(1)}ms` : def.defaultLatency;

          return (
            <div
              key={def.key}
              className={`p-3 rounded-xl border transition-all duration-300 ${
                isLoading
                  ? 'bg-slate-50 dark:bg-slate-950/40 border-slate-200 dark:border-slate-800/60 opacity-60'
                  : isRevealed
                  ? hasRan
                    ? 'bg-slate-50 dark:bg-slate-950 border-brand-300 dark:border-brand-500/30 shadow-sm'
                    : 'bg-slate-50/60 dark:bg-slate-950/40 border-slate-200 dark:border-slate-800/40 opacity-60'
                  : 'bg-slate-50/40 dark:bg-slate-950/20 border-slate-200/60 dark:border-slate-800/30 opacity-40'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2.5 min-w-0">
                  {/* Status Indicator */}
                  {isLoading ? (
                    <div className="h-4 w-4 rounded-full border-2 border-brand-500/40 border-t-brand-600 dark:border-t-brand-400 animate-spin shrink-0" />
                  ) : isRevealed ? (
                    hasRan ? (
                      <CheckCircle className="h-4 w-4 text-emerald-500 dark:text-emerald-400 shrink-0" />
                    ) : (
                      <Slash className="h-4 w-4 text-slate-400 dark:text-slate-600 shrink-0" />
                    )
                  ) : (
                    <div className="h-4 w-4 rounded-full bg-slate-200 dark:bg-slate-800 shrink-0" />
                  )}

                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`text-xs font-bold ${hasRan ? 'text-slate-900 dark:text-white' : 'text-slate-500 dark:text-slate-400'}`}>
                        {def.displayName}
                      </span>
                      <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-300 dark:border-slate-700">
                        {def.tag}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400 truncate hidden sm:block">
                      {def.description}
                    </p>
                  </div>
                </div>

                {/* Agent Latency Badge */}
                <div className="text-right shrink-0">
                  <span
                    className={`font-mono text-xs font-semibold px-2 py-0.5 rounded ${
                      hasRan ? 'bg-brand-50 dark:bg-brand-500/10 text-brand-700 dark:text-brand-300 border border-brand-200 dark:border-brand-500/20' : 'text-slate-400 dark:text-slate-600'
                    }`}
                  >
                    {isRevealed && actualStep ? (hasRan ? latency : 'Skipped') : isLoading ? '...' : 'Standby'}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Info note */}
      <div className="flex items-center gap-1.5 pt-1 text-[11px] text-slate-500">
        <Info className="h-3 w-3 shrink-0 text-slate-400 dark:text-slate-500" />
        <span>Agents trigger selectively: A2/A3 run only when landmark cues require deep extraction.</span>
      </div>
    </div>
  );
};
