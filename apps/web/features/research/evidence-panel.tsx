import { useId, type KeyboardEvent } from 'react';
import { ArrowUpRight, X } from 'lucide-react';
import { formatDate } from '@/lib/dates';
import type { Claim, Source } from '@/lib/types';

export function sourceDate(source: Source) {
  if (source.published_at) return `${formatDate(source.published_at)} · ${source.date_origin === 'fixture' ? 'fictional date' : source.date_origin === 'explicit_page' ? 'explicit publication date' : 'legacy date, origin unrecorded'}`;
  if (source.provider_date) return `${formatDate(source.provider_date)} · provider estimate (publication/update)`;
  return 'Publication date unknown';
}

type Props = {
  source: Source;
  claims: Claim[];
  onClose: () => void;
};

export function EvidencePanel({ source, claims, onClose }: Props) {
  const titleId = useId();
  const excerpts = claims.flatMap(claim => claim.evidence[source.id] ? [claim.evidence[source.id]] : []);

  function handleKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (event.key === 'Escape') {
      onClose();
      return;
    }
    if (event.key !== 'Tab') return;
    const controls = event.currentTarget.querySelectorAll<HTMLElement>('button, a[href]');
    const first = controls[0];
    const last = controls[controls.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last?.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first?.focus();
    }
  }

  return (
    <div className="evidence-backdrop no-print" onClick={event => {
      if (event.target === event.currentTarget) onClose();
    }}>
      <aside role="dialog" aria-modal="true" aria-labelledby={titleId} className="evidence-panel" onKeyDown={handleKeyDown}>
        <button className="close-button" autoFocus aria-label="Close evidence" onClick={onClose}><X/></button>
        <p className="eyebrow">SOURCE {source.id}</p>
        <h2 id={titleId}>{source.title}</h2>
        <p className="muted">{sourceDate(source)}</p>
        <div className="source-provenance">
          <p><strong>Material:</strong> {source.content_origin === 'extracted_page' ? 'Retrieved page content' : source.content_origin === 'fixture' ? 'Fictional fixture' : 'Search excerpt'}</p>
          {source.retrieved_at && <p><strong>Retrieved:</strong> {new Date(source.retrieved_at).toLocaleString()}</p>}
          {source.date_evidence && <p><strong>Publication evidence:</strong> {source.date_evidence}</p>}
          <p>Provider date estimates and explicit page dates are recorded separately.</p>
        </div>
        <a className="source-link" href={source.url} target="_blank" rel="noreferrer">Open original source <ArrowUpRight size={16}/></a>
        <h3>Retrieved excerpt</h3>
        <blockquote>{source.content}</blockquote>
        <h3>Evidence used in this briefing</h3>
        {excerpts.map((excerpt, index) => <blockquote key={index}>{excerpt}</blockquote>)}
        <p className="muted">Retrieved pages are untrusted material. Review the original publication before relying on a claim.</p>
      </aside>
    </div>
  );
}
