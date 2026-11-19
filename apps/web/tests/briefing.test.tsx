import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import BriefingView from '../components/briefing';
import type { Briefing } from '../lib/types';
import { api } from '../lib/api';

const report: Briefing = {
  entity:'Northstar Labs',entity_type:'company',meeting_at:'2026-11-14T12:00:00Z',timezone:'Europe/Warsaw',purpose:'partnership',mode:'demo',
  generated_at:'2026-11-14T10:00:00Z',window_start:'2026-10-15T12:00:00Z',window_end:'2026-11-14T10:00:00Z',summary:'A fictional briefing.',
  claims:[{text:'Northstar launched Atlas.',category:'product',relevance:'Explore a pilot.',source_ids:['S1'],evidence:{S1:'Northstar launched Atlas.'},evidence_status:'excerpt_matched'}],
  questions:['What are the goals?','What is the scope?','What happens next?'],open_questions:['Identity needs review.'],
  sources:[{id:'S1',title:'Launch announcement',url:'https://example.com/launch',content:'Northstar launched Atlas. More details.',published_at:'2026-11-10T10:00:00Z',temporal_status:'in_window',date_precision:'instant'}],
  warnings:['Fictional data.'],metrics:{elapsed_seconds:1,search_calls:0,llm_calls:0,sources_found:1,sources_eligible:1,claims_removed:0,estimated_llm_cost_usd:null},
};
describe('Evidence and demo boundaries', () => {
  it('labels fictional data and exposes the original evidence', () => {
    render(<BriefingView report={report} ticket={{id:'test',access_token:'token'}}/>);
    expect(screen.getByText(/Fictional demonstration/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Show source S1'}));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('Northstar launched Atlas. More details.')).toBeInTheDocument();
    expect(screen.getByRole('link',{name:/Open original source/})).toHaveAttribute('href','https://example.com/launch');
    fireEvent.click(screen.getByRole('button',{name:'Close evidence'}));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
  it('does not show a made-up cost when pricing is unknown', () => {
    render(<BriefingView report={report} ticket={{id:'test',access_token:'token'}}/>);
    expect(screen.getByText(/LLM cost \(unavailable\)/)).toBeInTheDocument();
  });
  it('sends result access tokens in headers', async () => {
    const fetchMock=vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response('{}'));
    await api('/api/research/test',{id:'test',access_token:'private-token'});
    expect(fetchMock).toHaveBeenCalledWith('/backend/api/research/test', expect.objectContaining({headers:{Authorization:'Bearer private-token'}}));
    fetchMock.mockRestore();
  });
  it('separates provider date estimates from dated evidence and exposes origin', () => {
    const estimated: Briefing = {...report, claims:[], uncertain_claims:report.claims,
      summary:'No findings with explicit timing evidence.',
      sources:[{...report.sources[0],published_at:null,provider_date:'2026-11-10T10:00:00Z',date_origin:'provider_estimate',content_origin:'search_snippet',temporal_status:'estimated'}]};
    render(<BriefingView report={estimated} ticket={{id:'test',access_token:'token'}}/>);
    expect(screen.getByRole('heading',{name:'Developments to verify'})).toBeInTheDocument();
    expect(screen.getByText(/excluded from the factual summary/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Show source S1'}));
    expect(screen.getByRole('dialog')).toHaveTextContent('provider estimate (publication/update)');
    expect(screen.getByRole('dialog')).toHaveTextContent('Search excerpt');
  });
});
