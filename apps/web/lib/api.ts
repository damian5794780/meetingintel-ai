import type { Health, JobStatus, ResearchRequest, ResearchResult, ResearchTicket, Ticket } from './types';

export class ApiError extends Error {
  constructor(readonly status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

async function api(path: string, init: RequestInit = {}, ticket?: Ticket) {
  const headers = new Headers(init.headers);
  if (init.body) headers.set('Content-Type', 'application/json');
  if (ticket) headers.set('Authorization', `Bearer ${ticket.access_token}`);

  const response = await fetch(`/backend${path}`, { ...init, headers, cache: 'no-store' });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    const detail = data?.detail;
    const message = typeof detail === 'string' ? detail
      : Array.isArray(detail) ? detail.map((item: { msg: string }) => item.msg).join(' ')
      : 'Cannot reach the research service. Check that the backend is running.';
    throw new ApiError(response.status, message);
  }
  return response;
}

function researchPath(ticket: Ticket) {
  return `/api/research/${encodeURIComponent(ticket.id)}`;
}

export async function readHealth(signal: AbortSignal): Promise<Health> {
  return (await api('/health', { signal })).json();
}

export async function createResearch(request: ResearchRequest, idempotencyKey: string): Promise<ResearchTicket> {
  return (await api('/api/research', {
    method: 'POST', body: JSON.stringify(request), headers: { 'Idempotency-Key': idempotencyKey },
  })).json();
}

export async function readResearchStatus(ticket: Ticket, signal?: AbortSignal): Promise<JobStatus> {
  return (await api(`${researchPath(ticket)}/status`, { signal }, ticket)).json();
}

export async function readResearchResult(ticket: Ticket, signal?: AbortSignal): Promise<ResearchResult> {
  return (await api(`${researchPath(ticket)}/result`, { signal }, ticket)).json();
}

export async function downloadMarkdown(ticket: Ticket): Promise<string> {
  return (await api(`${researchPath(ticket)}/export`, {}, ticket)).text();
}
