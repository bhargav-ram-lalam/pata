import React, { useState } from 'react';
import { FileText, ShieldAlert, Clock, Database, ChevronDown, ChevronUp, Lock } from 'lucide-react';
import { AddressResolution } from '../types/api';

interface AuditEvidenceCardProps {
  resolution: AddressResolution;
}

export const AuditEvidenceCard: React.FC<AuditEvidenceCardProps> = ({ resolution }) => {
  const [showFullJson, setShowFullJson] = useState(false);

  const { raw_address, evidence, needs_human_review, confidence, timestamp, ttl_for_raw_retention } = resolution;
  const requestId = evidence?.request_id || 'N/A';
  const tier = evidence?.agent4_tier || (confidence >= 0.8 ? 'high' : confidence >= 0.5 ? 'medium' : 'low');

  return (
    <div className="rounded-2xl bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 p-4 sm:p-5 shadow-lg dark:shadow-xl space-y-4 transition-colors duration-200">
      <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <FileText className="h-5 w-5 text-purple-600 dark:text-purple-400" />
          <h3 className="text-sm font-bold text-slate-900 dark:text-white tracking-wide">Audit Trail & DPDP Compliance</h3>
        </div>
        <div className="flex items-center gap-1.5 text-[11px] font-mono text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 px-2.5 py-0.5 rounded-full border border-emerald-200 dark:border-emerald-500/20">
          <Lock className="h-3 w-3" />
          <span>India DPDP 2023 Compliant</span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
        {/* Request Metadata */}
        <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 space-y-1.5 font-mono">
          <div className="flex justify-between text-slate-500 dark:text-slate-400">
            <span>Request ID:</span>
            <span className="text-slate-900 dark:text-slate-200 font-bold truncate max-w-[180px]">{requestId}</span>
          </div>
          <div className="flex justify-between text-slate-500 dark:text-slate-400">
            <span>Arbitration Tier:</span>
            <span className="uppercase text-brand-700 dark:text-brand-300 font-bold">{tier}</span>
          </div>
          <div className="flex justify-between text-slate-500 dark:text-slate-400">
            <span>Human Review Req:</span>
            <span className={needs_human_review ? 'text-rose-600 dark:text-rose-400 font-bold' : 'text-emerald-600 dark:text-emerald-400 font-bold'}>
              {needs_human_review ? 'YES (Flagged)' : 'NO (Automated)'}
            </span>
          </div>
          {timestamp && (
            <div className="flex justify-between text-slate-500 dark:text-slate-400">
              <span>Timestamp:</span>
              <span className="text-slate-700 dark:text-slate-300">{timestamp}</span>
            </div>
          )}
        </div>

        {/* DPDP Retention Guardrail Notice */}
        <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 space-y-1.5 text-[11px]">
          <div className="flex items-center gap-1.5 text-amber-600 dark:text-amber-400 font-bold">
            <Clock className="h-3.5 w-3.5" />
            <span>Raw PII 24h Retention TTL</span>
          </div>
          <p className="text-slate-600 dark:text-slate-400 leading-relaxed">
            Raw address text is staged in a short-lived table and automatically purged after 24h. The permanent record contains zero PII.
          </p>
          {ttl_for_raw_retention && (
            <div className="font-mono text-[10px] text-slate-400 dark:text-slate-500 truncate pt-1 border-t border-slate-200 dark:border-slate-800">
              Purge deadline: {ttl_for_raw_retention}
            </div>
          )}
        </div>
      </div>

      {/* Raw Input Excerpt (In-Memory Display Only) */}
      <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800/80 space-y-1">
        <div className="flex items-center justify-between">
          <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">
            Raw Address Input (Session Memory Only — Not Stored in LocalStorage)
          </span>
        </div>
        <p className="text-xs font-mono text-slate-800 dark:text-slate-300 bg-white dark:bg-slate-900/60 p-2 rounded-lg border border-slate-200 dark:border-slate-800/60 break-words">
          {raw_address}
        </p>
      </div>

      {/* Raw Evidence Payload Accordion */}
      <div className="border-t border-slate-100 dark:border-slate-800 pt-2">
        <button
          onClick={() => setShowFullJson(!showFullJson)}
          className="w-full flex items-center justify-between text-xs text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 py-1 transition-colors"
        >
          <span className="font-mono">Inspect Evidence JSON Payload</span>
          {showFullJson ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </button>

        {showFullJson && (
          <pre className="mt-2 p-3 rounded-xl bg-slate-900 dark:bg-slate-950 border border-slate-800 text-[11px] font-mono text-cyan-300 overflow-x-auto max-h-60">
            {JSON.stringify(evidence, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
};
