import type { Ticket } from './types';
export async function api(path: string, ticket?: Ticket, init?: RequestInit) {
  const response = await fetch(`/backend${path}`, { ...init, headers: {
    ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
    ...(ticket ? { Authorization: `Bearer ${ticket.access_token}` } : {}), ...init?.headers,
  }, cache: 'no-store' });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    const detail = data?.detail;
    throw new Error(typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((x: {msg: string}) => x.msg).join(' ') : 'Cannot reach the research service. Check that the backend is running.');
  }
  return response;
}
export function localDateInput(date: Date) {
  const shifted = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return shifted.toISOString().slice(0,16);
}
export function formatDate(value: string, timezone = 'UTC') {
  return new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: timezone }).format(new Date(value));
}
