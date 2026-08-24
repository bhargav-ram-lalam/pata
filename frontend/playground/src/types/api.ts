/**
 * TypeScript definitions matching Pata backend API v0.4.0
 */

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

export interface PipelineTraceStep {
  agent: string;
  latency_ms: number;
  ran: boolean;
  notes?: string;
  [key: string]: any;
}

export interface AddressResolution {
  raw_address: string;
  parsed: ParsedAddress;
  digipin: string | null;
  latitude: number | null;
  longitude: number | null;
  confidence: number;
  needs_human_review: boolean;
  evidence: {
    agent4_tier?: 'high' | 'medium' | 'low' | string;
    agent4_llm_choice?: string;
    agent1_confidence?: number;
    agent2_entities?: Record<string, any>;
    agent3_landmark_match?: {
      name?: string;
      lat?: number;
      lon?: number;
      osm_id?: number | string;
      osm_type?: string;
      distance_m?: number;
    } | null;
    agent3_candidates_count?: number;
    request_id?: string;
    timeout?: string;
    [key: string]: any;
  };
  pipeline_trace: PipelineTraceStep[];
  timestamp?: string;
  ttl_for_raw_retention?: string;
}

export interface ResolveRequestPayload {
  address: string;
  hint_lat?: number;
  hint_lng?: number;
}

export interface ExampleAddress {
  id: string;
  title: string;
  category: 'HIGH' | 'MEDIUM' | 'LOW';
  tierBadge: string;
  address: string;
  hint_lat?: number;
  hint_lng?: number;
  description: string;
  expectedBehavior: string;
}
