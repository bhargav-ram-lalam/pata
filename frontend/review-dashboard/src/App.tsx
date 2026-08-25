import React, { useState, useEffect, useCallback } from 'react';
import { ShieldCheck, LogOut, ExternalLink, MapPin, CheckCircle2, AlertCircle } from 'lucide-react';
import { LoginGate } from './components/LoginGate';
import { StatsHeader } from './components/StatsHeader';
import { ReviewQueueTable } from './components/ReviewQueueTable';
import { ReviewDetailModal } from './components/ReviewDetailModal';
import { ThemeToggle } from './components/ThemeToggle';
import { getSessionApiKey, clearSessionApiKey, fetchReviewQueue, fetchOpsMetrics, ApiError } from './services/api';
import type { ReviewQueueItem, OpsMetrics } from './types/api';

export function App() {
  const [apiKey, setApiKey] = useState<string | null>(getSessionApiKey());
  const [queueItems, setQueueItems] = useState<ReviewQueueItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [pages, setPages] = useState(1);
  const [sortBy, setSortBy] = useState<'confidence' | 'timestamp'>('confidence');
  const [selectedItem, setSelectedItem] = useState<ReviewQueueItem | null>(null);

  const [metrics, setMetrics] = useState<OpsMetrics>({
    queueSize: 0,
    reviewsConfirmed: 0,
    reviewsCorrected: 0,
    reviewsTotal: 0,
    avgTurnaroundSec: null,
    backendHealthy: false,
  });

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Load Queue & Metrics
  const loadData = useCallback(async () => {
    if (!apiKey) return;
    setIsLoading(true);
    setError(null);

    try {
      // 1. Fetch review queue items
      const queueRes = await fetchReviewQueue(apiKey, page, pageSize, sortBy);
      setQueueItems(queueRes.items);
      setTotal(queueRes.total);
      setPages(queueRes.pages);

      // 2. Fetch Prometheus metrics
      const opsMetrics = await fetchOpsMetrics();
      setMetrics(opsMetrics);
    } catch (err: any) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          setError('401 Unauthorized — Invalid API Key. Please re-authenticate.');
        } else {
          setError(`Error ${err.status}: ${err.detail}`);
        }
      } else {
        setError(err.message || 'Failed to connect to Pata review service.');
      }
    } finally {
      setIsLoading(false);
    }
  }, [apiKey, page, pageSize, sortBy]);

  useEffect(() => {
    if (apiKey) {
      loadData();
      const interval = setInterval(loadData, 30000); // 30s auto-refresh
      return () => clearInterval(interval);
    }
  }, [apiKey, loadData]);

  const handleLogin = (newKey: string) => {
    setApiKey(newKey);
    setPage(1);
  };

  const handleLogout = () => {
    clearSessionApiKey();
    setApiKey(null);
    setQueueItems([]);
  };

  const handleActionComplete = (requestId: string, outcome: 'confirmed' | 'corrected') => {
    setSelectedItem(null);
    setToastMessage(`Resolution ${requestId.slice(0, 8)}... successfully ${outcome}! ✓`);
    setTimeout(() => setToastMessage(null), 4000);
    loadData();
  };

  // If not logged in, render login gate
  if (!apiKey) {
    return <LoginGate onLogin={handleLogin} />;
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 flex flex-col font-sans transition-colors duration-200">
      {/* Top Ops Navigation Bar */}
      <header className="sticky top-0 z-40 border-b border-slate-200 dark:border-slate-800/80 bg-white/90 dark:bg-slate-950/90 backdrop-blur-md transition-colors duration-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          
          {/* Logo & Title */}
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-brand-600 via-indigo-500 to-cyan-400 p-0.5 shadow-lg shadow-brand-500/20">
              <div className="h-full w-full bg-white dark:bg-slate-950 rounded-[10px] flex items-center justify-center">
                <ShieldCheck className="h-5 w-5 text-cyan-500 dark:text-cyan-400" />
              </div>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xl font-black tracking-tight text-slate-900 dark:text-white">
                  Pata <span className="text-brand-600 dark:text-brand-400">Ops Review</span>
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 hidden sm:block">
                Human-Review & Feedback Loop Dashboard
              </p>
            </div>
          </div>

          {/* Right Actions: Switch to Playground, ThemeToggle, Key & Logout */}
          <div className="flex items-center gap-2.5">
            <a
              href="http://localhost:5173"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-900 dark:hover:bg-slate-800 border border-slate-300 dark:border-slate-700 text-xs font-semibold text-slate-700 dark:text-slate-200 transition-colors shadow-sm"
            >
              <MapPin className="h-3.5 w-3.5 text-cyan-600 dark:text-cyan-400" />
              <span className="hidden sm:inline">Playground (Port 5173)</span>
              <ExternalLink className="h-3 w-3 text-slate-400" />
            </a>

            <ThemeToggle />

            <div className="h-4 w-px bg-slate-300 dark:bg-slate-800" />

            <div className="flex items-center gap-2">
              <span className="text-xs font-mono text-slate-500 dark:text-slate-400 hidden md:inline">
                {apiKey.slice(0, 8)}...
              </span>
              <button
                onClick={handleLogout}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-rose-50 dark:bg-slate-900 dark:hover:bg-rose-950/40 border border-slate-300 hover:border-rose-300 dark:border-slate-800 dark:hover:border-rose-800 text-xs font-semibold text-slate-600 hover:text-rose-600 dark:text-slate-400 dark:hover:text-rose-300 transition-colors"
                title="Disconnect API session"
              >
                <LogOut className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Logout</span>
              </button>
            </div>
          </div>

        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        
        {/* Toast Notification */}
        {toastMessage && (
          <div className="p-3.5 rounded-2xl bg-emerald-50 dark:bg-emerald-950/90 border border-emerald-300 dark:border-emerald-500 text-emerald-800 dark:text-emerald-200 text-xs font-semibold flex items-center gap-2 shadow-lg dark:shadow-2xl animate-fade-in">
            <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
            <span>{toastMessage}</span>
          </div>
        )}

        {/* Global Error Banner */}
        {error && (
          <div className="p-4 rounded-2xl bg-rose-50 dark:bg-rose-950/80 border border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-200 text-xs flex items-center justify-between gap-3 shadow-lg dark:shadow-xl animate-fade-in">
            <div className="flex items-center gap-2">
              <AlertCircle className="h-4 w-4 text-rose-500 dark:text-rose-400 shrink-0" />
              <span>{error}</span>
            </div>
            <button
              onClick={loadData}
              className="px-3 py-1 rounded-lg bg-rose-600 hover:bg-rose-500 dark:bg-rose-900 dark:hover:bg-rose-800 text-xs font-semibold text-white shrink-0 shadow-sm"
            >
              Retry
            </button>
          </div>
        )}

        {/* Telemetry Stats Header */}
        <StatsHeader
          metrics={metrics}
          onRefresh={loadData}
          isLoading={isLoading}
        />

        {/* Paginated Review Queue Table */}
        <ReviewQueueTable
          items={queueItems}
          total={total}
          page={page}
          pageSize={pageSize}
          pages={pages}
          sortBy={sortBy}
          onPageChange={setPage}
          onSortChange={setSortBy}
          onSelectItem={setSelectedItem}
          isLoading={isLoading}
        />

      </main>

      {/* Modal Detail / Action View */}
      {selectedItem && (
        <ReviewDetailModal
          item={selectedItem}
          apiKey={apiKey}
          onClose={() => setSelectedItem(null)}
          onActionComplete={handleActionComplete}
        />
      )}

      {/* Footer */}
      <footer className="border-t border-slate-200 dark:border-slate-900 bg-white dark:bg-slate-950 py-6 mt-12 transition-colors duration-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-slate-500">
          <div className="flex items-center gap-2">
            <span className="font-bold text-slate-700 dark:text-slate-400">Pata Ops</span>
            <span>—</span>
            <span>Human-in-the-Loop Arbitration & Correction Training Logger</span>
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
