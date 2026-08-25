import React, { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { AddressInput } from './components/AddressInput';
import { LiveTracePanel } from './components/LiveTracePanel';
import { ConfidenceBadge } from './components/ConfidenceBadge';
import { MapViewer } from './components/MapViewer';
import { ParsedFieldsCard } from './components/ParsedFieldsCard';
import { resolveAddress, ApiError } from './services/api';
import { AddressResolution, ResolveRequestPayload } from './types/api';
import { GOLD_EXAMPLES } from './data/examples';

export function App() {
  const [resolution, setResolution] = useState<AddressResolution | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<{ status: number; message: string; retryAfter?: number } | null>(null);
  const [totalLatency, setTotalLatency] = useState<number | undefined>(undefined);

  // Auto-resolve the first gold example on initial load for instant demo display
  useEffect(() => {
    handleResolve({
      address: GOLD_EXAMPLES[0].address,
      hint_lat: GOLD_EXAMPLES[0].hint_lat,
      hint_lng: GOLD_EXAMPLES[0].hint_lng,
    });
  }, []);

  const handleResolve = async (payload: ResolveRequestPayload) => {
    setIsLoading(true);
    setError(null);
    const t0 = performance.now();

    try {
      const data = await resolveAddress(payload);
      const elapsed = performance.now() - t0;
      setResolution(data);
      setTotalLatency(elapsed);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError({
          status: err.status,
          message: err.detail,
          retryAfter: err.retryAfterSec,
        });
      } else {
        setError({
          status: 0,
          message: err.message || 'An unexpected error occurred.',
        });
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleLocationUpdated = (newLat: number, newLng: number) => {
    if (resolution) {
      setResolution({
        ...resolution,
        latitude: newLat,
        longitude: newLng,
      });
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 flex flex-col font-sans transition-colors duration-200">
      <Navbar />

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        
        {/* Page Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-200 dark:border-slate-800/80 pb-4">
          <div>
            <h1 className="text-xl sm:text-2xl font-black tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
              Address Resolution Playground
            </h1>
            <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 mt-0.5">
              Live deterministic postal parsing, IndicBERT NER, and Overpass POI spatial geocoding for Indian last-mile delivery.
            </p>
          </div>

          {/* Quick Stats Pill */}
          <div className="flex items-center gap-3 text-xs font-mono text-slate-600 dark:text-slate-400 shrink-0">
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 px-3 py-1.5 rounded-xl shadow-sm">
              <span className="text-slate-500">Pipeline: </span>
              <span className="text-brand-600 dark:text-brand-400 font-bold">5-Agent Engine</span>
            </div>
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 px-3 py-1.5 rounded-xl shadow-sm">
              <span className="text-slate-500">Region: </span>
              <span className="text-emerald-600 dark:text-emerald-400 font-bold">ap-south-1 (India)</span>
            </div>
          </div>
        </div>

        {/* Input & Examples Section */}
        <AddressInput
          onResolve={handleResolve}
          isLoading={isLoading}
          error={error}
        />

        {/* Resolution Results Grid */}
        {resolution && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 animate-fade-in pt-2">
            
            {/* Left Column: Parsed Structure, Live Trace (7 cols) */}
            <div className="lg:col-span-7 space-y-6">
              
              {/* Standardized Address Hierarchy */}
              <ParsedFieldsCard parsed={resolution.parsed} />

              {/* Multi-Agent Execution Pipeline Trace */}
              <LiveTracePanel
                trace={resolution.pipeline_trace}
                isLoading={isLoading}
                totalLatencyMs={totalLatency}
                confidence={resolution.confidence}
              />
            </div>

            {/* Right Column: Confidence Tier & Leaflet Map (5 cols) */}
            <div className="lg:col-span-5 space-y-4">
              
              {/* Confidence Tier Card */}
              <div className="p-4 sm:p-5 rounded-2xl bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 shadow-lg dark:shadow-xl space-y-2 transition-colors duration-200">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Decision Arbitration
                  </span>
                  <span className="text-[11px] font-mono text-slate-400 dark:text-slate-500">
                    Agent 4 Output
                  </span>
                </div>

                <ConfidenceBadge
                  confidence={resolution.confidence}
                  needsHumanReview={resolution.needs_human_review}
                  tier={resolution.evidence?.agent4_tier}
                  anchorType={resolution.anchor_type || resolution.evidence?.anchor_type}
                  accuracyRadiusMeters={resolution.accuracy_radius_meters || resolution.evidence?.accuracy_radius_meters}
                  size="lg"
                />
              </div>

              {/* Leaflet OSM Map */}
              <div className="space-y-2">
                <div className="flex items-center justify-between px-1">
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400">
                    Spatial Geolocation Preview
                  </span>
                  <span className="text-[11px] font-mono text-cyan-600 dark:text-cyan-400">
                    OpenStreetMap / Leaflet
                  </span>
                </div>

                <MapViewer
                  latitude={resolution.latitude}
                  longitude={resolution.longitude}
                  confidence={resolution.confidence}
                  needsHumanReview={resolution.needs_human_review}
                  anchorType={resolution.anchor_type || resolution.evidence?.anchor_type}
                  accuracyRadiusMeters={resolution.accuracy_radius_meters || resolution.evidence?.accuracy_radius_meters}
                  requestId={resolution.evidence?.request_id}
                  landmarkMatch={resolution.evidence?.agent3_landmark_match}
                  onLocationUpdated={handleLocationUpdated}
                />
              </div>
            </div>

          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 dark:border-slate-900 bg-white dark:bg-slate-950 py-6 mt-12 transition-colors duration-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-slate-500">
          <div className="flex items-center gap-2">
            <span className="font-bold text-slate-700 dark:text-slate-400">Pata</span>
            <span>—</span>
            <span>AI Address Resolution Engine for India</span>
          </div>
          <div className="flex items-center gap-4 text-slate-400 dark:text-slate-500 font-mono text-[11px]">
            <span>DPDP 24h Purge Active</span>
            <span>•</span>
            <span>India Post DIGIPIN</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;
