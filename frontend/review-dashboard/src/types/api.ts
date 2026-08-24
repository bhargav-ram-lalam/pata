export interface ParsedAddress {
  pincode?: string | null;
  city?: string | null;
  district?: string | null;
  state?: string | null;
  landmark?: string | null;
  locality?: string | null;
  building_name?: string | null;
  road?: string | null;
  street?: string | null;
  house_details?: string | null;
  subdistrict?: string | null;
  [key: string]: any;
}

export interface ReviewQueueItem {
  request_id: string;
  confidence: number;
  latitude: number | null;
  longitude: number | null;
  parsed: ParsedAddress;
  digipin: string | null;
  evidence: Record<string, any>;
  review_status: 'pending_review' | 'confirmed' | 'corrected' | 'rejected' | 'auto_confirmed' | string;
  created_at?: string | null;
}

export interface ReviewQueueResponse {
  total: number;
  page: number;
  page_size: number;
  pages: number;
  items: ReviewQueueItem[];
}

export interface OpsMetrics {
  queueSize: number;
  reviewsConfirmed: number;
  reviewsCorrected: number;
  reviewsTotal: number;
  avgTurnaroundSec: number | null;
  backendHealthy: boolean;
}

export interface CorrectSubmission {
  reviewer_id: string;
  corrected_lat?: number;
  corrected_lng?: number;
  corrected_parsed?: ParsedAddress;
  notes?: string;
}
