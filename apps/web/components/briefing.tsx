'use client';
import { useState } from 'react';
import { ArrowUpRight, Check, Copy, Download, FileText, Printer, X } from 'lucide-react';
import type { Briefing, Claim, Source, Ticket } from '@/lib/types';
import { api, formatDate } from '@/lib/api';

function sourceDate(source: Source) {
  if (source.published_at) return `${formatDate(source.published_at)} · ${source.date_origin === 'fixture' ? 'fictional date' : source.date_origin === 'explicit_page' ? 'explicit publication date' : 'legacy date, origin unrecorded'}`;
  if (source.provider_date) return `${formatDate(source.provider_date)} · provider estimate (publication/update)`;
  return 'Publication date unknown';
}

function sourceHost(url: string) {
  try { return new URL(url).hostname.slice(0,60); } catch { return 'Source'; }
}

export default function BriefingView({ report, ticket }: { report: Briefing; ticket: Ticket }) {
  const [selected, setSelected] = useState<Source | null>(null);
  const [notice, setNotice] = useState('');
  const uncertain = report.uncertain_claims || [];
  const allClaims = [...report.claims, ...uncertain];
  const usedSources = report.sources.filter(s => allClaims.some(c => c.source_ids.includes(s.id)));
  function citation(id: string, labeled = true) {
    return <button className="citation" key={id} aria-label={labeled ? `Show source ${id}` : undefined} onClick={() => setSelected(report.sources.find(s => s.id === id) || null)}>[{id}]</button>;
  }
  async function exportReport(copy: boolean) {
    try {
      const text = await (await api(`/api/research/${ticket.id}/export`, ticket)).text();
      if (copy) { await navigator.clipboard.writeText(text); setNotice('Briefing copied.'); }
      else {
        const url = URL.createObjectURL(new Blob([text], { type:'text/markdown' }));
        const link = document.createElement('a'); link.href = url; link.download = 'meetingintel-briefing.md'; link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000); setNotice('Markdown downloaded.');
      }
    } catch (e) { setNotice(e instanceof Error ? e.message : 'Export failed.'); }
  }
  function finding(claim: Claim, index: number, isUncertain = false) {
    return <section className="development" key={`${index}-${claim.text}`}>
      <span className="event-number">0{index+1}</span><div>
        <div className="event-meta"><span>{claim.category}</span><span className="matched"><Check size={12}/> Excerpt matched</span></div>
        <p className="claim-text">“{claim.text}” {claim.source_ids.map(id => citation(id))}</p>
        <p className="relevance"><strong>Suggested implication</strong> {claim.relevance}</p>
        {claim.discussion_question && !isUncertain && <p className="linked-question"><strong>Ask:</strong> {claim.discussion_question}</p>}
        {claim.temporal_note && <p className="timing-note">{claim.temporal_note}</p>}
      </div>
    </section>;
  }
  return <section className="report-area" aria-label="Generated briefing">
    <div className="report-toolbar no-print"><span className="eyebrow"><Check size={14}/> BRIEFING READY</span><div className="actions"><button onClick={() => exportReport(true)}><Copy size={15}/> Copy</button><button onClick={() => exportReport(false)}><Download size={15}/> Markdown</button><button onClick={() => window.print()}><Printer size={15}/> Save as PDF</button></div></div>
    {notice && <p role="status" className="notice no-print">{notice}</p>}
    <article className="report-paper">
      <div className="report-heading"><div><p className="eyebrow">MEETING INTELLIGENCE / {report.mode === 'demo' ? 'FICTIONAL DEMO' : 'LIVE RESEARCH'}</p><h2>{report.entity}</h2><p className="muted">{formatDate(report.meeting_at, report.timezone)} · {new Intl.DateTimeFormat('en-GB', {hour:'2-digit', minute:'2-digit', timeZone:report.timezone}).format(new Date(report.meeting_at))} · {report.timezone} · {report.purpose}</p></div><FileText className="paper-icon" size={34}/></div>
      {report.meeting_context?.desired_outcome && <p className="report-context"><strong>Your goal:</strong> {report.meeting_context.desired_outcome}</p>}
      {report.mode === 'demo' && <p className="demo-banner">Fictional demonstration. Northstar Labs and its announcements are invented; no live research was performed.</p>}
      <p className="research-range">RESEARCH WINDOW <strong>{formatDate(report.window_start)} — {formatDate(report.window_end)}</strong><span> · Updated {formatDate(report.generated_at)}</span></p>
      <section className="summary-block"><h3>Executive summary</h3><p>{report.summary.split(/(\[S\d+\])/g).map((part,index) => /^\[S\d+\]$/.test(part) ? <span key={index}>{citation(part.slice(1,-1), false)}</span> : part)}</p></section>
      <div className="section-label"><h3>Evidence in your date window</h3><span>{report.claims.length} DATED EXCERPTS</span></div>
      {!report.claims.length && <p className="empty-message">No findings with explicit timing evidence. Review the candidates below or clarify recent developments directly.</p>}
      <div className="developments">{report.claims.map((claim,index) => finding(claim,index))}</div>
      {!!uncertain.length && <section className="uncertain-block"><h3>Developments to verify</h3><p className="muted">Source wording is matched, but recency is unconfirmed. These candidates are excluded from the factual summary.</p>{uncertain.map((claim,index) => finding(claim,index,true))}</section>}
      <section className="questions-block"><h3>Bring these questions</h3><ol>{report.questions.map(q => <li key={q}>{q}</li>)}</ol></section>
      {!!report.open_questions.length && <section className="open-questions"><h3>Still to clarify</h3>{report.open_questions.map(q => <p key={q}>{q}</p>)}</section>}
      <section className="source-list"><h3>Sources</h3>{usedSources.map(s => <div key={s.id}>{citation(s.id,false)}<a href={s.url} data-print-label={sourceHost(s.url)} target="_blank" rel="noreferrer">{s.title} <ArrowUpRight size={12}/></a><span>{sourceDate(s)}</span></div>)}</section>
      <footer className="report-footer"><strong>MEETINGINTEL AI</strong><span>Evidence before assumptions.</span></footer>
    </article>
    <div className="metrics no-print"><span><strong>{report.metrics.elapsed_seconds}s</strong> generation</span><span><strong>{report.metrics.sources_eligible}</strong> explicitly dated sources</span><span><strong>{report.metrics.search_calls}</strong> search calls</span><span><strong>{report.metrics.extract_calls || 0}</strong> extract calls</span><span><strong>{report.metrics.research_rounds || 1}</strong> research rounds</span><span><strong>{report.metrics.llm_calls}</strong> LLM calls</span><span><strong>{report.metrics.tavily_usage_complete === false ? '—' : report.metrics.tavily_credits ?? '—'}</strong> reported Tavily credits</span><span><strong>{report.metrics.estimated_llm_cost_usd === null ? '—' : `$${report.metrics.estimated_llm_cost_usd}`}</strong> LLM cost {report.metrics.estimated_llm_cost_usd === null ? '(unavailable)' : '(estimated)'}</span></div>
    <details className="limitations no-print"><summary>Research notes & limitations ({report.warnings.length})</summary><ul>{report.warnings.map(w => <li key={w}>{w}</li>)}</ul><p>Matched excerpts confirm retrieved wording, not factual truth. Identity: {report.identity_status === 'user_confirmed' ? 'confirmed by you; not independently verified' : report.identity_status === 'fictional_demo' ? 'fictional demo' : 'legacy report, confirmation not recorded'}. Suggestions require your judgment.</p></details>
    <p className="print-only print-caveat">Quoted wording matched; truth and identity require review. Implications/questions are suggestions. Provider date estimates may reflect updates. {report.mode === 'demo' ? 'FICTIONAL DEMO.' : ''}</p>
    {selected && <div className="evidence-backdrop no-print" onClick={() => setSelected(null)}><aside role="dialog" aria-modal="true" aria-labelledby="evidence-title" className="evidence-panel" onClick={e => e.stopPropagation()} onKeyDown={e => {
      if(e.key === 'Escape') setSelected(null);
      if(e.key === 'Tab') {
        const focusable = e.currentTarget.querySelectorAll<HTMLElement>('button,a[href]');
        const first = focusable[0], last = focusable[focusable.length-1];
        if(e.shiftKey && document.activeElement === first) {e.preventDefault();last?.focus();}
        if(!e.shiftKey && document.activeElement === last) {e.preventDefault();first?.focus();}
      }
    }}><button className="close-button" autoFocus aria-label="Close evidence" onClick={() => setSelected(null)}><X/></button><p className="eyebrow">SOURCE {selected.id}</p><h2 id="evidence-title">{selected.title}</h2><p className="muted">{sourceDate(selected)}</p><div className="source-provenance"><p><strong>Material:</strong> {selected.content_origin === 'extracted_page' ? 'Retrieved page content' : selected.content_origin === 'fixture' ? 'Fictional fixture' : 'Search excerpt'}</p>{selected.retrieved_at && <p><strong>Retrieved:</strong> {new Date(selected.retrieved_at).toLocaleString()}</p>}{selected.date_evidence && <p><strong>Publication evidence:</strong> {selected.date_evidence}</p>}<p>Provider date estimates and explicit page dates are recorded separately.</p></div><a className="source-link" href={selected.url} target="_blank" rel="noreferrer">Open original source <ArrowUpRight size={16}/></a><h3>Retrieved excerpt</h3><blockquote>{selected.content}</blockquote><h3>Evidence used in this briefing</h3>{allClaims.filter(c => c.source_ids.includes(selected.id)).map((c,i) => <blockquote key={i}>{c.evidence[selected.id]}</blockquote>)}<p className="muted">Retrieved pages are untrusted material. Review the original publication before relying on a claim.</p></aside></div>}
  </section>;
}
