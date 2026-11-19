export type Source = { id: string; title: string; url: string; content: string; published_at: string | null; temporal_status: 'in_window' | 'estimated' | 'undated'; date_precision: string; provider_date?: string | null; date_origin?: string; date_evidence?: string; content_origin?: string; retrieved_at?: string | null; content_hash?: string; identity_match?: boolean };
export type Claim = { text: string; category: string; relevance: string; source_ids: string[]; evidence: Record<string,string>; evidence_status: string; discussion_question?: string; temporal_note?: string };
export type Briefing = {
  entity: string; entity_type: string; meeting_at: string; timezone: string; purpose: string; mode: string;
  generated_at: string; window_start: string; window_end: string; summary: string;
  claims: Claim[]; questions: string[]; open_questions: string[]; sources: Source[]; warnings: string[];
  uncertain_claims?: Claim[]; summary_source_ids?: string[]; identity_status?: string;
  meeting_context?: {role:string; offering:string; desired_outcome:string};
  metrics: { elapsed_seconds: number; search_calls: number; llm_calls: number; sources_found: number; sources_eligible: number; claims_removed: number; estimated_llm_cost_usd: number | null; extract_calls?: number; sources_extracted?: number; research_rounds?: number; tavily_credits?: number; tavily_usage_complete?: boolean };
};
export type Job = { id: string; status: 'queued' | 'running' | 'completed' | 'failed'; stage: string; result: Briefing | null; error: string | null };
export type Ticket = { id: string; access_token: string };
