import React from 'react';
import { ShieldAlert, AlertTriangle, AlertOctagon, ChevronLeft, ChevronRight, ArrowUpDown, Search, CheckCircle2, Eye } from 'lucide-react';
import type { ReviewQueueItem } from '../types/api';

interface ReviewQueueTableProps {
  items: ReviewQueueItem[];
  total: number;
  page: number;
  pageSize: number;
  pages: number;
  sortBy: 'confidence' | 'timestamp';
  onPageChange: (newPage: number) => void;
  onSortChange: (newSort: 'confidence' | 'timestamp') => void;
  onSelectItem: (item: ReviewQueueItem) => void;
  isLoading: boolean;
}

export const ReviewQueueTable: React.FC<ReviewQueueTableProps> = ({
  items,
  total,
  page,
  pageSize,
  pages,
  sortBy,
  onPageChange,
  onSortChange,
  onSelectItem,
  isLoading,
}) => {
  const [searchQuery, setSearchQuery] = React.useState('');

  const filteredItems = items.filter((item) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    const city = item.parsed?.city?.toLowerCase() || '';
    const landmark = item.parsed?.landmark?.toLowerCase() || '';
    const reqId = item.request_id.toLowerCase();
    return reqId.includes(q) || city.includes(q) || landmark.includes(q);
  });

  const getReasonBadge = (item: ReviewQueueItem) => {
    if (item.evidence?.timeout) {
      return <span className="text-[10px] font-mono bg-rose-50 dark:bg-rose-950 text-rose-700 dark:text-rose-300 px-2 py-0.5 rounded border border-rose-200 dark:border-rose-800">Pipeline Timeout</span>;
    }
    if (item.confidence < 0.5) {
      return <span className="text-[10px] font-mono bg-rose-50 dark:bg-rose-950 text-rose-700 dark:text-rose-300 px-2 py-0.5 rounded border border-rose-200 dark:border-rose-800">Low Confidence (&lt;0.50)</span>;
    }
    if (item.confidence < 0.8) {
      return <span className="text-[10px] font-mono bg-amber-50 dark:bg-amber-950 text-amber-700 dark:text-amber-300 px-2 py-0.5 rounded border border-amber-200 dark:border-amber-800">Medium Ambiguity</span>;
    }
    return <span className="text-[10px] font-mono bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 px-2 py-0.5 rounded border border-slate-200 dark:border-slate-700">Manual Flag</span>;
  };

  return (
    <div className="rounded-2xl bg-white dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800 shadow-lg dark:shadow-xl overflow-hidden space-y-4 p-4 sm:p-5 transition-colors duration-200">
      
      {/* Table Toolbar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-slate-100 dark:border-slate-800 pb-4">
        
        {/* Search Input */}
        <div className="relative w-full sm:w-80">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400 dark:text-slate-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Filter by Request ID, City, Landmark..."
            className="w-full pl-9 pr-4 py-2 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-xs font-mono text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:border-brand-500"
          />
        </div>

        {/* Sorting & Counter */}
        <div className="flex items-center gap-3 w-full sm:w-auto justify-between sm:justify-end">
          <div className="flex items-center gap-1.5 text-xs text-slate-600 dark:text-slate-400">
            <ArrowUpDown className="h-3.5 w-3.5 text-slate-400 dark:text-slate-500" />
            <span className="hidden sm:inline">Sort:</span>
            <button
              onClick={() => onSortChange(sortBy === 'confidence' ? 'timestamp' : 'confidence')}
              className="px-2.5 py-1 rounded-lg bg-slate-50 hover:bg-slate-100 dark:bg-slate-950 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-800 text-brand-700 dark:text-brand-300 font-mono font-semibold transition-colors"
            >
              {sortBy === 'confidence' ? 'Confidence (Lowest First)' : 'Timestamp (Oldest First)'}
            </button>
          </div>

          <span className="text-xs font-mono text-slate-500">
            Total: <strong className="text-slate-900 dark:text-white">{total}</strong> items
          </span>
        </div>

      </div>

      {/* Table Content */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-50 dark:bg-slate-950/60 text-slate-500 dark:text-slate-400 font-mono uppercase text-[10px] tracking-wider border-b border-slate-200 dark:border-slate-800">
            <tr>
              <th className="py-3 px-3">Request ID</th>
              <th className="py-3 px-3">Resolved Location</th>
              <th className="py-3 px-3 text-center">Confidence</th>
              <th className="py-3 px-3">Flagged Reason</th>
              <th className="py-3 px-3">Status</th>
              <th className="py-3 px-3 text-right">Action</th>
            </tr>
          </thead>

          <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
            {isLoading ? (
              <tr>
                <td colSpan={6} className="py-12 text-center text-slate-500">
                  <div className="flex flex-col items-center justify-center gap-2">
                    <div className="h-6 w-6 rounded-full border-2 border-brand-500/40 border-t-brand-600 dark:border-t-brand-400 animate-spin" />
                    <span>Loading review backlog...</span>
                  </div>
                </td>
              </tr>
            ) : filteredItems.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-12 text-center text-slate-500">
                  <div className="flex flex-col items-center justify-center gap-2">
                    <CheckCircle2 className="h-10 w-10 text-emerald-500 dark:text-emerald-400/80 mb-1" />
                    <span className="text-slate-900 dark:text-slate-300 font-bold text-sm">Review Queue Empty!</span>
                    <span className="text-xs text-slate-500 max-w-sm">
                      All addresses have been processed or auto-confirmed. New low-confidence resolutions will appear here automatically.
                    </span>
                  </div>
                </td>
              </tr>
            ) : (
              filteredItems.map((item) => {
                const confPct = Math.round(item.confidence * 100);
                const city = item.parsed?.city || 'Unknown City';
                const state = item.parsed?.state || '';
                const landmark = item.parsed?.landmark || item.parsed?.locality || '';

                return (
                  <tr
                    key={item.request_id}
                    className="hover:bg-slate-50 dark:hover:bg-slate-950/50 transition-colors group cursor-pointer"
                    onClick={() => onSelectItem(item)}
                  >
                    {/* Request ID */}
                    <td className="py-3 px-3 font-mono text-slate-700 dark:text-slate-300">
                      <span className="text-brand-600 dark:text-brand-300 font-semibold group-hover:text-brand-700 dark:group-hover:text-brand-200">
                        {item.request_id.slice(0, 8)}...
                      </span>
                    </td>

                    {/* Resolved Location */}
                    <td className="py-3 px-3">
                      <div className="font-semibold text-slate-900 dark:text-slate-200 truncate max-w-[220px]">
                        {landmark ? `${landmark}, ` : ''}{city}
                      </div>
                      <div className="text-[11px] text-slate-500 font-mono truncate max-w-[220px]">
                        {state} {item.parsed?.pincode ? `(${item.parsed.pincode})` : ''}
                      </div>
                    </td>

                    {/* Confidence */}
                    <td className="py-3 px-3 text-center font-mono">
                      <span
                        className={`inline-block px-2 py-0.5 rounded-full text-[11px] font-bold border ${
                          item.confidence >= 0.5
                            ? 'bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-500/30'
                            : 'bg-rose-50 dark:bg-rose-500/10 text-rose-700 dark:text-rose-300 border-rose-200 dark:border-rose-500/30'
                        }`}
                      >
                        {confPct}%
                      </span>
                    </td>

                    {/* Reason */}
                    <td className="py-3 px-3">
                      {getReasonBadge(item)}
                    </td>

                    {/* Status */}
                    <td className="py-3 px-3 font-mono text-[11px] text-slate-600 dark:text-slate-400">
                      <span className="px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-950 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-800">
                        {item.review_status}
                      </span>
                    </td>

                    {/* Action */}
                    <td className="py-3 px-3 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectItem(item);
                        }}
                        className="px-3 py-1.5 rounded-lg bg-brand-50 hover:bg-brand-600 dark:bg-brand-600/20 dark:hover:bg-brand-600 border border-brand-200 hover:border-brand-600 dark:border-brand-500/30 dark:hover:border-brand-500 text-brand-700 hover:text-white dark:text-brand-300 dark:hover:text-white font-bold text-xs inline-flex items-center gap-1.5 transition-all shadow-sm"
                      >
                        <Eye className="h-3.5 w-3.5" />
                        <span>Review</span>
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Footer */}
      {pages > 1 && (
        <div className="flex items-center justify-between border-t border-slate-100 dark:border-slate-800 pt-3 text-xs text-slate-500 dark:text-slate-400">
          <span>
            Page <strong className="text-slate-900 dark:text-white">{page}</strong> of <strong className="text-slate-900 dark:text-white">{pages}</strong>
          </span>

          <div className="flex items-center gap-2">
            <button
              onClick={() => onPageChange(page - 1)}
              disabled={page <= 1 || isLoading}
              className="p-1.5 rounded-lg bg-slate-50 hover:bg-slate-100 dark:bg-slate-950 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-800 disabled:opacity-40 transition-colors"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <button
              onClick={() => onPageChange(page + 1)}
              disabled={page >= pages || isLoading}
              className="p-1.5 rounded-lg bg-slate-50 hover:bg-slate-100 dark:bg-slate-950 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-800 disabled:opacity-40 transition-colors"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
