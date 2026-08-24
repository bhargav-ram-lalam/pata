import type { AddressResolution, ResolveRequestPayload } from '../types/api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const DEFAULT_API_KEY = import.meta.env.VITE_DEFAULT_API_KEY || 'pata_dev_key';

export class ApiError extends Error {
  public status: number;
  public statusText: string;
  public detail: string;
  public retryAfterSec?: number;

  constructor(
    status: number,
    statusText: string,
    detail: string,
    retryAfterSec?: number
  ) {
    super(`API Error ${status}: ${detail}`);
    this.name = 'ApiError';
    this.status = status;
    this.statusText = statusText;
    this.detail = detail;
    this.retryAfterSec = retryAfterSec;
  }
}

export function getStoredApiKey(): string {
  // Session/memory fallback only — no persistent storage of keys
  return sessionStorage.getItem('pata_api_key') || DEFAULT_API_KEY;
}

export function setStoredApiKey(key: string): void {
  if (key.trim()) {
    sessionStorage.setItem('pata_api_key', key.trim());
  } else {
    sessionStorage.removeItem('pata_api_key');
  }
}

export async function resolveAddress(
  payload: ResolveRequestPayload,
  apiKey?: string
): Promise<AddressResolution> {
  const key = apiKey || getStoredApiKey();
  const url = `${API_BASE_URL}/v1/resolve`;

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': key,
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      let detail = response.statusText;
      try {
        const errorJson = await response.json();
        detail = errorJson.detail || errorJson.message || JSON.stringify(errorJson);
      } catch {
        // Fallback to statusText
      }

      const retryAfter = response.headers.get('Retry-After')
        ? parseInt(response.headers.get('Retry-After') || '1', 10)
        : undefined;

      throw new ApiError(response.status, response.statusText, detail, retryAfter);
    }

    const data: AddressResolution = await response.json();
    return data;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError(0, 'Network Error', (error as Error).message || 'Failed to connect to Pata API backend at ' + API_BASE_URL);
  }
}

export async function confirmResolution(
  requestId: string,
  reviewerId: string = 'playground_user',
  apiKey?: string
): Promise<{ status: string; request_id: string; updated: any }> {
  const key = apiKey || getStoredApiKey();
  const url = `${API_BASE_URL}/v1/review/${requestId}/confirm`;

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': key,
    },
    body: JSON.stringify({ reviewer_id: reviewerId }),
  });

  if (!response.ok) {
    const errorJson = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      response.statusText,
      errorJson.detail || 'Failed to confirm resolution'
    );
  }

  return response.json();
}

export async function resolveCorrection(
  requestId: string,
  params: {
    reviewerId: string;
    correctedLat?: number;
    correctedLng?: number;
    correctedParsed?: Record<string, any>;
    notes?: string;
  },
  apiKey?: string
): Promise<{ status: string; request_id: string; updated: any }> {
  const key = apiKey || getStoredApiKey();
  const url = `${API_BASE_URL}/v1/review/${requestId}/resolve`;

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': key,
    },
    body: JSON.stringify({
      reviewer_id: params.reviewerId,
      corrected_lat: params.correctedLat,
      corrected_lng: params.correctedLng,
      corrected_parsed: params.correctedParsed,
      notes: params.notes,
    }),
  });

  if (!response.ok) {
    const errorJson = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      response.statusText,
      errorJson.detail || 'Failed to submit correction'
    );
  }

  return response.json();
}

export async function checkBackendHealth(): Promise<{ ready: boolean; live: boolean; version?: string }> {
  try {
    const liveRes = await fetch(`${API_BASE_URL}/v1/health/live`, { signal: AbortSignal.timeout(3000) });
    const readyRes = await fetch(`${API_BASE_URL}/v1/health/ready`, { signal: AbortSignal.timeout(3000) });
    return {
      live: liveRes.ok,
      ready: readyRes.ok,
    };
  } catch {
    return { live: false, ready: false };
  }
}
