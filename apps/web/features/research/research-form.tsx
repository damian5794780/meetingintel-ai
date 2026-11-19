import { useEffect, useState, type FormEvent } from 'react';
import { ArrowRight, Building2, LoaderCircle, Search, UserRound } from 'lucide-react';
import { localDateInput } from '@/lib/dates';
import type { ResearchRequest } from '@/lib/types';

type Props = {
  busy: boolean;
  connected: boolean;
  ready: boolean;
  onSubmit: (request: ResearchRequest) => void;
};

function formText(data: FormData, field: string) {
  const value = data.get(field);
  return typeof value === 'string' ? value : '';
}

export function ResearchForm({ busy, connected, ready, onSubmit }: Props) {
  const [mode, setMode] = useState<'demo' | 'live'>('demo');
  const [kind, setKind] = useState<'company' | 'person'>('company');
  const [entity, setEntity] = useState('');
  const [meeting, setMeeting] = useState('');
  const [timezone, setTimezone] = useState('Europe/Warsaw');
  const [purpose, setPurpose] = useState<NonNullable<ResearchRequest['purpose']>>('partnership');

  useEffect(() => {
    setMeeting(localDateInput(new Date(Date.now() + 86_400_000)));
    setTimezone(Intl.DateTimeFormat().resolvedOptions().timeZone);
  }, []);

  function start(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    onSubmit({
      entity: mode === 'demo' ? 'Northstar Labs' : entity,
      entity_type: mode === 'demo' ? 'company' : kind,
      meeting_at: new Date(meeting).toISOString(),
      timezone,
      purpose,
      context: formText(data, 'context'),
      identity_hint: mode === 'live' ? formText(data, 'identity_hint') : '',
      identity_confirmed: mode === 'live' && data.get('identity_confirmed') === 'on',
      meeting_context: {
        role: formText(data, 'role'),
        offering: formText(data, 'offering'),
        desired_outcome: formText(data, 'desired_outcome'),
      },
      mode,
    });
  }

  return (
    <aside className="setup-column no-print">
      <section className="form-card" aria-labelledby="setup-title">
        <h2 id="setup-title">New briefing</h2>
        <div className="mode-switch" aria-label="Research mode">
          <button aria-pressed={mode === 'demo'} onClick={() => setMode('demo')} disabled={busy}>Try a demo</button>
          <button aria-pressed={mode === 'live'} onClick={() => setMode('live')} disabled={busy}>Live research</button>
        </div>
        <p className="mode-help">
          {mode === 'demo' ? 'Uses fictional data. No API keys required.' : ready ? 'Search the web with your configured providers.' : 'Live research requires Tavily and LLM keys in the backend .env file.'}
        </p>

        <form onSubmit={start}>
          <fieldset disabled={busy}>
            <legend className="sr-only">Meeting details</legend>
            {mode === 'live' && (
              <div className="entity-switch">
                <button type="button" aria-pressed={kind === 'company'} onClick={() => setKind('company')}><Building2 size={16}/> Company</button>
                <button type="button" aria-pressed={kind === 'person'} onClick={() => setKind('person')}><UserRound size={16}/> Person</button>
              </div>
            )}

            <label htmlFor="entity">{kind === 'person' && mode === 'live' ? 'Full name' : 'Company name'}</label>
            <div className="input-icon">
              <Search size={16}/>
              <input id="entity" name="entity" placeholder={kind === 'person' ? 'e.g. Alex Morgan' : 'e.g. Acme'} minLength={2} maxLength={120} value={mode === 'demo' ? 'Northstar Labs' : entity} onChange={e => setEntity(e.target.value)} readOnly={mode === 'demo'} required/>
            </div>

            {mode === 'live' && (
              <>
                <label htmlFor="identity_hint">{kind === 'person' ? 'Organization or role' : 'Official company website'}</label>
                <input id="identity_hint" name="identity_hint" maxLength={200} placeholder={kind === 'person' ? 'e.g. CTO at Acme' : 'e.g. acme.com'} required/>
                <label className="identity-confirm"><input type="checkbox" name="identity_confirmed" required/>I confirm this is the company or person I intend to meet.</label>
                <p className="field-hint">This information guides the search and requires your confirmation.</p>
              </>
            )}

            <label htmlFor="meeting">Meeting date &amp; time</label>
            <input id="meeting" type="datetime-local" value={meeting} onChange={e => setMeeting(e.target.value)} required/>
            <p className="field-hint">{timezone} · Research covers the 30 days before the meeting, up to today.</p>

            <label htmlFor="purpose">Meeting purpose</label>
            <select id="purpose" name="purpose" value={purpose} onChange={e => setPurpose(e.target.value as typeof purpose)}>
              <option value="business">Business discussion</option>
              <option value="recruitment">Recruitment / interview</option>
              <option value="partnership">Explore a partnership</option>
              <option value="general">General introduction</option>
            </select>

            <details className="context-fields">
              <summary>Add meeting context <span>Optional</span></summary>
              <label htmlFor="role">Your organization / role</label>
              <input id="role" name="role" maxLength={160} placeholder="e.g. Founder of an AI software studio"/>
              <label htmlFor="offering">What you bring to the conversation</label>
              <input id="offering" name="offering" maxLength={400} placeholder="e.g. AI workflow integrations"/>
              <label htmlFor="desired_outcome">Desired outcome</label>
              <input id="desired_outcome" name="desired_outcome" maxLength={400} placeholder="e.g. Agree on a small integration pilot"/>
              <label htmlFor="context">Additional notes</label>
              <textarea id="context" name="context" maxLength={1200} rows={3}/>
            </details>

            <button className="primary-button" type="submit" disabled={busy || !connected || mode === 'live' && !ready}>
              {busy ? <><LoaderCircle className="spin" size={17}/> Preparing briefing</> : <>Create {mode === 'demo' ? 'demo ' : ''}briefing <ArrowRight size={18}/></>}
            </button>
            {!connected && <p className="field-hint" role="status">Waiting for the local research service.</p>}
          </fieldset>
        </form>
      </section>
    </aside>
  );
}
