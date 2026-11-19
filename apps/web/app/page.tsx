'use client';
import { FormEvent, useEffect, useState } from 'react';
import { ArrowRight, ArrowUpRight, AudioLines, Building2, Check, ChevronRight, Clock3, Globe2, LoaderCircle, Search, ShieldCheck, Sparkles, UserRound } from 'lucide-react';
import BriefingView from '@/components/briefing';
import { api, localDateInput } from '@/lib/api';
import type { Job, Ticket } from '@/lib/types';

const stages = ['planning', 'researching', 'extracting', 'synthesizing', 'verifying', 'composing'];
const stageLabels: Record<string,string> = { queued:'Waiting for a research slot', planning:'Planning focused searches', researching:'Researching official pages and news', extracting:'Reading selected publications', synthesizing:'Prioritizing for your meeting', verifying:'Checking identity, quotes and dates', closing_gaps:'Researching remaining evidence gaps', composing:'Composing your briefing', completed:'Briefing ready', failed:'Research stopped' };

export default function Home() {
  const [mode, setMode] = useState<'demo'|'live'>('demo');
  const [kind, setKind] = useState('company');
  const [entity, setEntity] = useState('');
  const [meeting, setMeeting] = useState('');
  const [timezone, setTimezone] = useState('Europe/Warsaw');
  const [ready, setReady] = useState(false);
  const [connected, setConnected] = useState(false);
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const busy = submitting || !!ticket && !job || job?.status === 'queued' || job?.status === 'running';

  useEffect(() => {
    setMeeting(localDateInput(new Date(Date.now()+86400000)));
    setTimezone(Intl.DateTimeFormat().resolvedOptions().timeZone);
    try { const saved = sessionStorage.getItem('meetingintel-ticket'); if(saved) setTicket(JSON.parse(saved)); } catch { /* Ignore unavailable storage. */ }
    api('/health').then(r => r.json()).then(data => {setReady(data.live_ready);setConnected(true);}).catch(() => setConnected(false));
  }, []);

  useEffect(() => {
    if(!ticket) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    let failures = 0;
    const poll = async () => {
      try {
        const data: Job = await (await api(`/api/research/${ticket.id}`, ticket)).json();
        if(stopped) return;
        failures=0; setJob(data); setError('');
        if(data.status === 'queued' || data.status === 'running') timer=setTimeout(poll,700);
      } catch(e) {
        if(stopped) return;
        failures++;
        setError(e instanceof Error ? e.message : 'Could not load briefing.');
        if(failures<5) timer=setTimeout(poll,2000);
      }
    };
    poll();
    return () => {stopped=true;clearTimeout(timer);};
  }, [ticket, retry]);

  async function start(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(''); setSubmitting(true);
    const data = new FormData(event.currentTarget);
    try {
      const response = await api('/api/research', undefined, {method:'POST', body:JSON.stringify({
        entity: mode === 'demo' ? 'Northstar Labs' : entity, entity_type: mode === 'demo' ? 'company' : kind,
        meeting_at:new Date(meeting).toISOString(), timezone, purpose:data.get('purpose'),
        context:data.get('context') || '', identity_hint:mode === 'demo' ? '' : data.get('identity_hint') || '', mode,
        identity_confirmed: mode === 'live' && data.get('identity_confirmed') === 'on',
        meeting_context: {role:data.get('role') || '', offering:data.get('offering') || '', desired_outcome:data.get('desired_outcome') || ''},
      })});
      const created: Ticket = await response.json();
      setJob(null);setTicket(created);
      try {sessionStorage.setItem('meetingintel-ticket', JSON.stringify(created));} catch { /* Keep ticket in memory. */ }
    } catch(e) {setError(e instanceof Error ? e.message : 'Could not start research.');}
    finally {setSubmitting(false);}
  }

  return <><header className="site-header no-print"><a className="brand" href="/"><span className="brand-icon"><AudioLines size={23}/></span>MeetingIntel<span className="brand-ai">AI</span></a><div className="header-right"><span className="build-label">PRE-MEETING INTELLIGENCE</span><a href="https://github.com/damian5794780/meetingintel-ai" target="_blank" rel="noreferrer">View project <ArrowUpRight size={14}/></a></div></header>
    <main className="workspace">
      <section className="hero no-print"><div><p className="eyebrow"><span className="status-dot"/> A BETTER START TO EVERY CONVERSATION</p><h1>Walk in informed.<br/><span>Make the meeting count.</span></h1><p className="hero-description">Recent developments, clear evidence, and the right questions.<br className="desktop-break"/> Your next meeting starts with a sharper briefing.</p></div><div className="hero-note"><div className="note-icon"><ShieldCheck size={24}/></div><strong>Every insight has a trail.</strong><p>Follow citations back to the source.<br/>See what is known, and what to ask.</p><span>POWERED BY TAVILY</span></div></section>
      <div className={`work-grid ${job?.result ? 'has-report' : ''}`}><aside className="setup-column no-print"><section className="form-card"><div className="card-heading"><span className="step-tag">01</span><div><h2>Set the agenda</h2><p>Who are you meeting?</p></div><Sparkles size={19}/></div>
        <div className="mode-switch" aria-label="Research mode"><button aria-pressed={mode==='demo'} onClick={() => setMode('demo')} disabled={!!busy}>Try a demo</button><button aria-pressed={mode==='live'} onClick={() => setMode('live')} disabled={!!busy}>Live research</button></div>
        <p className="mode-help">{mode==='demo' ? 'Explore a fictional company briefing. No API keys needed.' : ready ? 'Search the web with your configured providers.' : 'Live mode needs Tavily and LLM keys in the backend .env.'}</p>
        <form onSubmit={start}><fieldset disabled={!!busy}><legend className="sr-only">Meeting details</legend>
          <div className="entity-switch"><button type="button" aria-pressed={kind==='company' || mode==='demo'} onClick={() => setKind('company')}><Building2 size={15}/> Company</button><button type="button" aria-pressed={kind==='person' && mode==='live'} onClick={() => setKind('person')} disabled={mode==='demo'}><UserRound size={15}/> Person</button></div>
          <label htmlFor="entity">{kind==='person' && mode==='live' ? 'Full name' : 'Company name'} <span>REQUIRED</span></label><div className="input-icon"><Search size={16}/><input id="entity" name="entity" placeholder="e.g. a company you’re meeting" minLength={2} maxLength={120} value={mode==='demo' ? 'Northstar Labs' : entity} onChange={e => setEntity(e.target.value)} readOnly={mode==='demo'} required/></div>
          {mode==='live' && <><label htmlFor="identity_hint">{kind==='person' ? 'Organization or role' : 'Official company website'} <span>REQUIRED</span></label><input id="identity_hint" name="identity_hint" maxLength={200} placeholder={kind==='person' ? 'e.g. CTO at Acme' : 'e.g. acme.com'} required/><label className="identity-confirm"><input type="checkbox" name="identity_confirmed" required/>I confirm this is the company or person I intend to meet.</label><p className="field-hint">This identity hint guides research; it is not independent identity verification.</p></>}
          <label htmlFor="meeting">Meeting date & time <span>REQUIRED</span></label><input id="meeting" type="datetime-local" value={meeting} onChange={e => setMeeting(e.target.value)} required/><p className="field-hint">Your device timezone: {timezone}. Research covers the preceding 30 days, up to now.</p>
          <label htmlFor="purpose">Meeting purpose</label><select id="purpose" name="purpose" defaultValue="partnership"><option value="business">Business discussion</option><option value="recruitment">Recruitment / interview</option><option value="partnership">Explore a partnership</option><option value="general">General introduction</option></select>
          <details className="context-fields" open><summary>Make it relevant to you</summary><label htmlFor="role">Your organization / role <span>OPTIONAL</span></label><input id="role" name="role" maxLength={160} placeholder="e.g. Founder of an AI software studio"/><label htmlFor="offering">What you bring to the conversation</label><input id="offering" name="offering" maxLength={400} placeholder="e.g. AI workflow integrations"/><label htmlFor="desired_outcome">Desired outcome</label><input id="desired_outcome" name="desired_outcome" maxLength={400} placeholder="e.g. Agree on a small integration pilot"/></details>
          <label htmlFor="context">A little context <span>OPTIONAL</span></label><textarea id="context" name="context" maxLength={1200} rows={3} placeholder="What would you like to get out of this meeting?"/>
          <button className="primary-button" type="submit" disabled={!!busy || !connected || mode==='live' && !ready}>{busy ? <><LoaderCircle className="spin" size={17}/> Preparing briefing</> : <>Create {mode==='demo' ? 'demo ' : ''}briefing <ArrowRight size={17}/></>}</button>
        </fieldset></form><div className="form-footer"><ShieldCheck size={14}/><span>{connected ? mode==='demo' ? 'Fictional data · No paid API calls' : 'Keys stay on the server' : 'Backend unavailable · Start the API on port 8000'}</span></div></section>
        <div className="workflow-note"><Globe2 size={17}/><p><strong>Research with a purpose.</strong> Dated evidence first. Meeting implications second. Useful questions always.</p></div></aside>
        <div className="result-column">{error && <div className="error-banner no-print" role="alert">{error}{ticket && <button onClick={() => setRetry(r => r+1)}>Retry loading</button>}</div>}
          {job?.status==='failed' && <div className="error-banner no-print" role="alert"><strong>We couldn’t complete this briefing.</strong><p>{job.error}</p><p>Update the meeting details or configuration, then create a new briefing.</p></div>}
          {busy && <section className="progress-card no-print" aria-live="polite"><div className="research-orb"><LoaderCircle className="spin" size={29}/></div><p className="eyebrow">{mode==='demo' ? 'PREPARING FICTIONAL DEMO' : 'RESEARCH IN PROGRESS'}</p><h2>{stageLabels[job?.stage || 'queued']}</h2><p className="muted">Checking what belongs in your briefing.</p><ol>{stages.map((s,i) => <li key={s} className={stages.indexOf(job?.stage || '')>=i ? 'active' : ''}><span>{stages.indexOf(job?.stage || '')>i ? <Check size={12}/> : i+1}</span>{stageLabels[s]}</li>)}</ol></section>}
          {job?.result && ticket ? <BriefingView report={job.result} ticket={ticket}/> : !busy && <section className="welcome-card no-print"><div className="welcome-top"><span className="eyebrow">YOUR NEXT CONVERSATION, IN FOCUS</span><span className="preview-tag">BRIEFING PREVIEW</span></div><div className="preview-document"><div className="preview-doc-head"><span className="tiny-brand"><AudioLines size={16}/> MEETINGINTEL</span><span>PRE-MEETING BRIEF</span></div><div className="preview-title">The context you need.<br/><span>Before you need it.</span></div><div className="preview-lines"><i/><i/><i/></div><div className="preview-insight"><span className="event-number">01</span><div><strong>What happened</strong><p>Recent developments with links to the evidence.</p></div><span className="mini-citation">[S1]</span></div><div className="preview-insight"><span className="event-number">02</span><div><strong>Why it matters</strong><p>Suggested implications for your conversation.</p></div><ChevronRight size={16}/></div><div className="preview-question"><span>THE NEXT GOOD QUESTION</span><p>“What would a successful first step look like?”</p></div></div><div className="welcome-bottom"><div><Clock3 size={18}/><strong>Less prep. More perspective.</strong></div><p>Create your first briefing to see the full picture.</p></div></section>}
        </div></div>
      <footer className="site-footer no-print"><span>MEETINGINTEL AI <span className="footer-divider">/</span> ARRIVE INFORMED.</span><span>Built for the Global AI Hackathon 2026</span></footer>
    </main></>;
}
