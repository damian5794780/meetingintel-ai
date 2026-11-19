import { useEffect, useRef, useState } from 'react';
import { ApiError, createResearch, readHealth, readResearchResult, readResearchStatus } from '@/lib/api';
import type { Health, JobStatus, ResearchRequest, ResearchResult, Ticket } from '@/lib/types';

const storageKey = 'meetingintel-ticket';
const pollingInterval = 700;
const retryInterval = 2000;
const maxPollingFailures = 5;

function newSubmissionKey() {
  return Array.from(crypto.getRandomValues(new Uint8Array(32)), value => value.toString(16).padStart(2, '0')).join('');
}

function saveTicket(ticket: Ticket | null) {
  try {
    if (ticket) sessionStorage.setItem(storageKey, JSON.stringify(ticket));
    else sessionStorage.removeItem(storageKey);
  } catch {
    // The in-memory ticket still works when browser storage is unavailable.
  }
}

function restoreTicket(): Ticket | null {
  try {
    const saved = JSON.parse(sessionStorage.getItem(storageKey) ?? 'null');
    if (typeof saved?.id === 'string' && typeof saved?.access_token === 'string') {
      return { id: saved.id, access_token: saved.access_token };
    }
  } catch {
    // Invalid or unavailable storage does not prevent new research.
  }
  return null;
}

export function useResearchJob() {
  const [health, setHealth] = useState<Health | null>(null);
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [result, setResult] = useState<ResearchResult | null>(null);
  const pendingSubmission = useRef<{ body: string; key: string } | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submissionError, setSubmissionError] = useState('');
  const [pollingError, setPollingError] = useState('');
  const [pollingStopped, setPollingStopped] = useState(false);
  const [retry, setRetry] = useState(0);
  const busy = submitting || (!!ticket && !pollingStopped &&
    (!job || job.status === 'queued' || job.status === 'running'));

  useEffect(() => {
    const controller = new AbortController();
    setTicket(restoreTicket());
    readHealth(controller.signal).then(setHealth).catch(() => {
      if (!controller.signal.aborted) setHealth(null);
    });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!ticket) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let failures = 0;

    async function poll(access: Ticket) {
      try {
        const current = await readResearchStatus(access, controller.signal);
        const report = current.status === 'completed' ? await readResearchResult(access, controller.signal) : null;
        if (controller.signal.aborted) return;
        failures = 0;
        setJob(current);
        setResult(report);
        setPollingError('');
        if (current.status === 'queued' || current.status === 'running') {
          timer = setTimeout(() => poll(access), pollingInterval);
        }
      } catch (error) {
        if (controller.signal.aborted) return;
        if (error instanceof ApiError && (error.status === 401 || error.status === 404)) {
          saveTicket(null);
          setTicket(null);
          setJob(null);
          setResult(null);
          setPollingError('This saved briefing is unavailable. You can create a new one.');
          return;
        }
        if (++failures < maxPollingFailures) {
          timer = setTimeout(() => poll(access), retryInterval);
        } else {
          setPollingStopped(true);
          setPollingError(error instanceof Error ? error.message : 'Could not load the briefing.');
        }
      }
    }

    void poll(ticket);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [ticket, retry]);

  async function submit(request: ResearchRequest) {
    setSubmissionError('');
    setSubmitting(true);
    try {
      const body = JSON.stringify(request);
      const prior = pendingSubmission.current;
      const key = prior?.body === body ? prior.key : newSubmissionKey();
      pendingSubmission.current = { body, key };
      const { id, access_token } = await createResearch(request, key);
      pendingSubmission.current = null;
      const access = { id, access_token };
      saveTicket(access);
      setJob(null);
      setResult(null);
      setPollingStopped(false);
      setPollingError('');
      setTicket(access);
      return true;
    } catch (error) {
      setSubmissionError(error instanceof Error ? error.message : 'Could not start research.');
      return false;
    } finally {
      setSubmitting(false);
    }
  }

  function retryPolling() {
    setPollingStopped(false);
    setPollingError('');
    setRetry(value => value + 1);
  }

  return { health, ticket, job, result, busy, submissionError, pollingError, pollingStopped, submit, retryPolling };
}
