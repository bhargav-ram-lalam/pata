import React, { useState } from 'react';
import { X, Check, Edit, ShieldAlert, AlertTriangle, ArrowRight, User, FileText, Info, HelpCircle } from 'lucide-react';
import { MapViewer } from './MapViewer';
import { confirmResolution, submitCorrection, ApiError } from '../services/api';
import type { ReviewQueueItem, ParsedAddress } from '../types/api';

interface ReviewDetailModalProps {
  item: ReviewQueueItem;
  apiKey: string;
  onClose: () => void;
  onActionComplete: (requestId: string, outcome: 'confirmed' | 'corrected') => void;
}

export const ReviewDetailModal: React.FC<ReviewDetailModalProps> = ({
  item,
  apiKey,
  onClose,
  onActionComplete,
}) => {
  const [activeTab, setActiveTab] = useState<'inspect' | 'correct'>('inspect');
  const [reviewerId, setReviewerId] = useState('ops_reviewer_01');
  const [notes, setNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Editable coordinates & parsed fields
  const [currentLat, setCurrentLat] = useState<number | null>(item.latitude);
  const [currentLng, setCurrentLng] = useState<number | null>(item.longitude);
  const [editableParsed, setEditableParsed] = useState<ParsedAddress>({ ...item.parsed });

  const handleFieldChange = (key: string, value: string) => {
    setEditableParsed((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  // 1. Confirm resolution action
  const handleConfirm = async () => {
    setIsSubmitting(true);
    setError(null);
    try {
      await confirmResolution(apiKey, item.request_id, reviewerId);
      onActionComplete(item.request_id, 'confirmed');
    } catch (err: any) {
      setError(err instanceof ApiError ? err.detail : err.message);
      setIsSubmitting(false);
    }
  };

  // 2. Submit correction action
  const handleCorrection = async () => {
    setIsSubmitting(true);
    setError(null);
    try {
      await submitCorrection(apiKey, item.request_id, {
        reviewer_id: reviewerId,
        corrected_lat: currentLat ?? undefined,
        corrected_lng: currentLng ?? undefined,
        corrected_parsed: editableParsed,
        notes: notes.trim() || undefined,
      });
      onActionComplete(item.request_id, 'corrected');
    } catch (err: any) {
      setError(err instanceof ApiError ? err.detail : err.message);
      setIsSubmitting(false);
    }
  };

  const confidencePct = Math.round(item.confidence * 100);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 dark:bg-black/80 backdrop-blur-sm p-3 sm:p-6 animate-fade-in">
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl max-w-4xl w-full max-h-[90vh] flex flex-col shadow-2xl overflow-hidden animate-slide-up transition-colors duration-200">
        
        {/* Modal Header */}
        <div className="p-4 sm:p-5 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between bg-slate-50 dark:bg-slate-950/60">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-xl border ${
              item.confidence >= 0.5 ? 'bg-amber-50 dark:bg-amber-500/10 border-amber-200 dark:border-amber-500/30 text-amber-600 dark:text-amber-400' : 'bg-rose-50 dark:bg-rose-500/10 border-rose-200 dark:border-rose-500/30 text-rose-600 dark:text-rose-400'
            }`}>
              <ShieldAlert className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-slate-900 dark:text-white">Review Request</h3>
                <span className="text-xs font-mono text-slate-600 dark:text-slate-400 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded border border-slate-200 dark:border-slate-700">
                  {item.request_id}
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Confidence: <strong className={item.confidence >= 0.5 ? 'text-amber-600 dark:text-amber-400' : 'text-rose-600 dark:text-rose-400'}>{confidencePct}%</strong> • Status: <span className="text-amber-600 dark:text-amber-300 font-mono">{item.review_status}</span>
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-2 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Modal Body: Scrollable */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
          
          {/* Tabs: Inspect vs Correct Mode */}
          <div className="flex rounded-xl bg-slate-100 dark:bg-slate-950 p-1 border border-slate-200 dark:border-slate-800">
            <button
              onClick={() => setActiveTab('inspect')}
              className={`flex-1 py-2 rounded-lg text-xs font-bold transition-colors ${
                activeTab === 'inspect' ? 'bg-white dark:bg-slate-800 text-slate-900 dark:text-white shadow-sm' : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
              }`}
            >
              1. Inspect Resolved Output & Map
            </button>
            <button
              onClick={() => setActiveTab('correct')}
              className={`flex-1 py-2 rounded-lg text-xs font-bold transition-colors ${
                activeTab === 'correct' ? 'bg-brand-600 text-white shadow-sm' : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
              }`}
            >
              2. Edit & Submit Corrections (Training Feedback)
            </button>
          </div>

          {/* Grid Layout: Map & Fields */}
          <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
            
            {/* Left: Map Preview (6 cols) */}
            <div className="md:col-span-6 space-y-2">
              <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
                <span className="font-semibold uppercase tracking-wider">Spatial Coordinate</span>
                <span className="font-mono text-cyan-600 dark:text-cyan-400">
                  {currentLat?.toFixed(4)}, {currentLng?.toFixed(4)}
                </span>
              </div>

              <MapViewer
                latitude={currentLat}
                longitude={currentLng}
                anchorType={item.anchor_type || item.evidence?.anchor_type}
                accuracyRadiusMeters={item.accuracy_radius_meters || item.evidence?.accuracy_radius_meters}
                onLocationChange={(lat, lng) => {
                  setCurrentLat(lat);
                  setCurrentLng(lng);
                }}
                isDraggable={true}
              />
              <p className="text-[11px] text-slate-400 dark:text-slate-500 italic">
                💡 Drag the marker to reposition coordinates to the accurate building entrance.
              </p>
            </div>

            {/* Right: Parsed Address Fields (6 cols) */}
            <div className="md:col-span-6 space-y-3">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 block">
                Structured Field Attributes
              </span>

              <div className="grid grid-cols-2 gap-2.5">
                {['landmark', 'locality', 'road', 'building_name', 'city', 'district', 'state', 'pincode'].map((fieldKey) => {
                  const val = editableParsed[fieldKey] || '';
                  const isEditing = activeTab === 'correct';

                  return (
                    <div key={fieldKey} className="space-y-1">
                      <label className="text-[10px] font-mono uppercase text-slate-500 dark:text-slate-400">
                        {fieldKey.replace('_', ' ')}
                      </label>
                      {isEditing ? (
                        <input
                          type="text"
                          value={val}
                          onChange={(e) => handleFieldChange(fieldKey, e.target.value)}
                          placeholder={`Enter ${fieldKey}...`}
                          className="w-full px-2.5 py-1.5 rounded-lg bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-800 text-xs font-mono text-slate-900 dark:text-white focus:outline-none focus:border-brand-500"
                        />
                      ) : (
                        <div className="px-2.5 py-1.5 rounded-lg bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800/80 text-xs font-mono text-slate-800 dark:text-slate-200 truncate">
                          {val || <span className="text-slate-400 dark:text-slate-600 italic">N/A</span>}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* DIGIPIN Card */}
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 flex items-center justify-between text-xs font-mono">
                <span className="text-slate-500 dark:text-slate-400">DIGIPIN:</span>
                <span className="font-bold text-indigo-700 dark:text-indigo-300">{item.digipin || 'N/A'}</span>
              </div>
            </div>

          </div>

          {/* Reviewer Details & Notes */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 border-t border-slate-100 dark:border-slate-800">
            <div className="space-y-1">
              <label className="text-xs font-mono text-slate-500 dark:text-slate-400 flex items-center gap-1">
                <User className="h-3.5 w-3.5 text-brand-600 dark:text-brand-400" />
                <span>Reviewer Identifier</span>
              </label>
              <input
                type="text"
                value={reviewerId}
                onChange={(e) => setReviewerId(e.target.value)}
                placeholder="ops_reviewer_id"
                className="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-800 text-xs font-mono text-slate-900 dark:text-white focus:outline-none focus:border-brand-500"
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs font-mono text-slate-500 dark:text-slate-400 flex items-center gap-1">
                <FileText className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400" />
                <span>Correction Notes (Optional)</span>
              </label>
              <input
                type="text"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="e.g. Landmark verified via customer call / map entrance..."
                className="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-800 text-xs font-sans text-slate-900 dark:text-white focus:outline-none focus:border-brand-500"
              />
            </div>
          </div>

          {/* Error display */}
          {error && (
            <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/60 border border-rose-200 dark:border-rose-800 text-rose-700 dark:text-rose-200 text-xs font-mono">
              {error}
            </div>
          )}
        </div>

        {/* Modal Footer: Action Buttons */}
        <div className="p-4 sm:p-5 border-t border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/80 flex flex-col sm:flex-row items-center justify-between gap-3">
          {/* Reject guidance note */}
          <div className="flex items-center gap-1.5 text-[11px] text-slate-500">
            <Info className="h-3.5 w-3.5 text-slate-400 shrink-0" />
            <span>Confirm retains ML output • Correct logs feedback dataset & triggers signed webhook</span>
          </div>

          <div className="flex items-center gap-3 w-full sm:w-auto">
            {/* Confirm Button */}
            <button
              onClick={handleConfirm}
              disabled={isSubmitting}
              className="flex-1 sm:flex-initial px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs flex items-center justify-center gap-1.5 transition-colors shadow-lg shadow-emerald-600/20 disabled:opacity-50"
            >
              <Check className="h-4 w-4" />
              <span>{isSubmitting ? 'Processing...' : 'Confirm ML Output'}</span>
            </button>

            {/* Submit Correction Button */}
            <button
              onClick={handleCorrection}
              disabled={isSubmitting}
              className="flex-1 sm:flex-initial px-5 py-2.5 rounded-xl bg-brand-600 hover:bg-brand-500 text-white font-bold text-xs flex items-center justify-center gap-1.5 transition-colors shadow-lg shadow-brand-600/30 disabled:opacity-50"
            >
              <Edit className="h-4 w-4" />
              <span>{isSubmitting ? 'Saving...' : 'Submit Correction'}</span>
            </button>
          </div>
        </div>

      </div>
    </div>
  );
};
