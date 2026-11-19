'use client';

import { useEffect, useRef } from 'react';
import { Check, LoaderCircle } from 'lucide-react';
import type { Briefing, ResearchRequest, ResearchResult } from '@/lib/types';
import { BriefingPreview } from './briefing-preview';
import BriefingView from './briefing-view';
import { ResearchForm } from './research-form';
import { useResearchJob } from './use-research-job';

const stages = [
  { id: 'planning', label: 'Planning focused searches' },
  { id: 'researching', label: 'Researching official pages and news' },
  { id: 'extracting', label: 'Reading selected publications' },
  { id: 'synthesizing', label: 'Prioritizing for your meeting' },
  { id: 'verifying', label: 'Checking identity, quotes and dates' },
  { id: 'composing', label: 'Composing your briefing' },
];

function ResearchProgress({ stage }: { stage?: string }) {
  const current = stages.findIndex(item => item.id === stage);
  const label = stages[current]?.label ?? (stage === 'closing_gaps'
    ? 'Researching remaining evidence gaps'
    : 'Waiting for a research slot');

  return (
    <section className="progress-card no-print" aria-live="polite">
      <LoaderCircle className="spin progress-icon" size={25}/>
      <h2>{label}</h2>
      <ol>
        {stages.map((item, index) => (
          <li key={item.id} className={current >= index ? 'active' : ''}>
            <span>{current > index ? <Check size={14}/> : index + 1}</span>{item.label}
          </li>
        ))}
      </ol>
    </section>
  );
}

function hasReport(result: ResearchResult | null): result is Briefing {
  return !!result && typeof result.meeting_at === 'string' && typeof result.summary === 'string' &&
    typeof result.window_start === 'string' && typeof result.window_end === 'string' &&
    typeof result.generated_at === 'string' && Array.isArray(result.claims) &&
    Array.isArray(result.sources) && Array.isArray(result.questions) && Array.isArray(result.open_questions) &&
    Array.isArray(result.warnings) && !!result.metrics;
}

export function ResearchWorkspace() {
  const research = useResearchJob();
  const { health, ticket, job, result, busy, submissionError, pollingError, pollingStopped, submit, retryPolling } = research;
  const resultColumn = useRef<HTMLDivElement>(null);
  const focusNextReport = useRef(false);
  const report = hasReport(result) ? result : null;

  useEffect(() => {
    if (!report || !focusNextReport.current) return;
    focusNextReport.current = false;
    resultColumn.current?.focus({ preventScroll: !window.matchMedia('(max-width: 700px)').matches });
  }, [report]);

  async function start(request: ResearchRequest) {
    focusNextReport.current = await submit(request);
  }

  return (
    <div className={`work-grid ${report ? 'has-report' : ''}`}>
      <ResearchForm busy={busy} connected={health !== null} ready={health?.live_ready ?? false} onSubmit={start}/>
      <div className="result-column" ref={resultColumn} tabIndex={-1}>
        {submissionError && <div className="error-banner no-print" role="alert">{submissionError}</div>}
        {pollingError && (
          <div className="error-banner no-print" role="alert">
            {pollingError}
            {pollingStopped && <button onClick={retryPolling}>Retry loading</button>}
          </div>
        )}
        {job?.status === 'failed' && (
          <div className="error-banner no-print" role="alert">
            <strong>We couldn’t complete this briefing.</strong><p>{job.error}</p>
          </div>
        )}
        {job?.status === 'completed' && !report && (
          <div className="error-banner no-print" role="status">This older briefing cannot be displayed. Create a new briefing to continue.</div>
        )}
        {busy && <ResearchProgress stage={job?.stage}/>}
        {report && ticket ? <BriefingView key={ticket.id} report={report} ticket={ticket}/> : !busy && <BriefingPreview/>}
      </div>
    </div>
  );
}
