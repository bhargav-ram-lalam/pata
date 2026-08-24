import type { ReviewQueueResponse, OpsMetrics, CorrectSubmission } from '../types/api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const DEFAULT_API_KEY = import.meta.env.VITE_DEFAULT_API_KEY || 'pata_dev_key';

export class ApiError extends Error {
  public status: number;
  public statusText: string;
  public detail: string;

  constructor(status: number, statusText: string, detail: string) {
    super(`API Error ${status}: ${detail}`);
    this.name = 'ApiError';
    this.status = status;
    this.statusText = statusText;
    this.detail = detail;
  }
}

export function getSessionApiKey(): string | null {
  return sessionStorage.getItem('pata_review_api_key');
}

export function setSessionApiKey(key: string): void {
  if (key.trim()) {
    sessionStorage.setItem('pata_review_api_key', key.trim());
  } else {
    sessionStorage.removeItem('pata_review_api_key');
  }
}

export function clearSessionApiKey(): void {
  sessionStorage.removeItem('pata_review_api_key');
}

export async function fetchReviewQueue(
  apiKey: string,
  page: number = 1,
  pageSize: number = 20,
  sortBy: 'confidence' | 'timestamp' = 'confidence'
): Promise<ReviewQueueResponse> {
  const url = `${API_BASE_URL}/v1/review/queue?page=${page}&page_size=${pageSize}&sort_by=${sortBy}`;

  const response = await fetch(url, {
    headers: {
      'X-API-Key': apiKey,
    },
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const err = await response.json();
      detail = err.detail || err.message || JSON.stringify(err);
    } catch {}
    throw new ApiError(response.status, response.statusText, detail);
  }

  return response.json();
}

export async function confirmResolution(
  apiKey: string,
  requestId: string,
  reviewerId: string = 'ops_reviewer'
): Promise<{ status: string; request_id: string; updated: any }> {
  const url = `${API_BASE_URL}/v1/review/${requestId}/confirm`;

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': apiKey,
    },
    body: JSON.stringify({ reviewer_id: reviewerId }),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new ApiError(response.status, response.statusText, err.detail || 'Failed to confirm resolution');
  }

  return response.json();
}

export async function submitCorrection(
  apiKey: string,
  requestId: string,
  submission: CorrectSubmission
): Promise<{ status: string; request_id: string; updated: any }> {
  const url = `${API_BASE_URL}/v1/review/${requestId}/resolve`;

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': apiKey,
    },
    body: JSON.stringify(submission),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new ApiError(response.status, response.statusText, err.detail || 'Failed to submit correction');
  }

  return response.json();
}

export async function fetchOpsMetrics(): Promise<OpsMetrics> {
  let metrics: OpsMetrics = {
    queueSize: 0,
    reviewsConfirmed: 0,
    reviewsCorrected: 0,
    reviewsTotal: 0,
    avgTurnaroundSec: null,
    backendHealthy: false,
  };

  try {
    // 1. Check health
    const healthRes = await fetch(`${API_BASE_URL}/v1/health/ready`, { signal: AbortSignal.timeout(3000) });
    metrics.backendHealthy = healthRes.ok;

    // 2. Scrape Prometheus metrics
    const metricsRes = await fetch(`${API_BASE_URL}/v1/metrics`, { signal: AbortSignal.timeout(3000) });
    if (metricsRes.ok) {
      const text = await metricsRes.text();
      
      // Parse pata_review_queue_size
      const queueMatch = text.match(/pata_review_queue_size\s+([\d\.]+)/);
      if (queueMatch) metrics.queueSize = parseInt(queueMatch[1], 10);

      // Parse pata_reviews_completed_total{outcome="confirmed"}
      const confirmedMatch = text.match(/pata_reviews_completed_total\{outcome="confirmed"\}\s+([\d\.]+)/);
      if (confirmedMatch) metrics.reviewsConfirmed = parseInt(confirmedMatch[1], 10);

      // Parse pata_reviews_completed_total{outcome="corrected"}
      const correctedMatch = text.match(/pata_reviews_completed_total\{outcome="corrected"\}\s+([\d\.]+)/);
      if (correctedMatch) metrics.reviewsCorrected = parseInt(correctedMatch[1], 10);

      metrics.reviewsTotal = metrics.reviewsConfirmed + metrics.reviewsCorrected;

      // Parse turnaround histogram sum & count
      const sumMatch = text.match(/pata_review_turnaround_seconds_sum\s+([\d\.]+)/);
      const countMatch = text.match(/pata_review_turnaround_seconds_count\s+([\d\.]+)/);
      if (sumMatch && countMatch) {
        const sum = parseFloat(sumMatch[1]);
        const count = parseFloat(countMatch[1]);
        if (count > 0) {
          metrics.avgTurnaroundSec = Math.round(sum / count);
        }
      }
    }
  } catch (err) {
    // Non-blocking metrics degradation
  }

  return metrics;
}
