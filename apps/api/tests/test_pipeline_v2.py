import asyncio
import hashlib
import json
from datetime import timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from apps.api.agents.workflow import run_workflow
from apps.api.application import create_app
from apps.api.config import Settings
from apps.api.schemas.briefing import Claim, Metrics, Source, Synthesis
from apps.api.services.llm_service import LLMService, ResearchOutput
from apps.api.services.research_plan import enrich_sources, explicit_publication, search_plan
from apps.api.services.provider_http import ProviderError
from apps.api.services.sources import canonical_url, qualify_sources
from apps.api.services.tavily_service import TavilyService
from apps.api.services.verification import assess_claims
from apps.api.store import Store
from apps.api.tests.test_research import NOW, payload, request, row, wait_for_job


def test_context_changes_query_plan_and_preserves_official_branch():
    req = request(identity_hint='https://example.org', meeting_context={
        'role':'Founder', 'offering':'robotics integration', 'desired_outcome':'technical pilot'})
    plan=search_plan(req)
    assert len(plan)==3
    assert plan[0].domains==['example.org'] and plan[0].topic=='general'
    assert plan[1].topic=='news' and plan[1].domains==[]
    assert 'robotics integration' in plan[2].query and 'technical pilot' in plan[2].query
    assert len(search_plan(req,['gap1','gap2','gap3']))==2


def test_provider_date_is_not_a_verified_publication():
    sources,_=qualify_sources([row()],NOW-timedelta(days=30),NOW)
    source=sources[0]
    assert source.published_at is None and source.provider_date==NOW
    assert source.date_origin=='provider_estimate' and source.temporal_status=='estimated'
    assert source.content_hash==hashlib.sha256(source.content.encode()).hexdigest()


@pytest.mark.parametrize('label', ['Published: 2026-11-10', 'Published on November 10, 2026', '**Publication date:** 10 November 2026'])
def test_labeled_page_dates(label):
    date,precision,evidence=explicit_publication(label+'\nExample body')
    assert date and date.day==10 and precision=='day' and evidence==label


@pytest.mark.parametrize('content',['Updated: 2026-11-10', '2026-11-10', 'The event happened in 2026.', 'Published: unknown'])
def test_unlabeled_or_update_dates_are_not_publication_proof(content):
    assert explicit_publication(content)[0] is None


def test_extract_enrichment_keeps_original_snippet_and_explicit_date_evidence():
    sources,_=qualify_sources([row()],NOW-timedelta(days=30),NOW)
    original=sources[0].content
    body='Published: 2026-11-10\n'+original+' More full-page material.'
    enriched,notes=enrich_sources(request(entity='Example Corp'),sources,{sources[0].url:body},NOW-timedelta(days=30),NOW)
    source=enriched[0]
    assert source.content_origin=='extracted_page' and source.content==body
    assert source.search_content==original and source.search_hash!=source.content_hash
    assert source.date_origin=='explicit_page' and source.temporal_status=='in_window'
    assert source.date_evidence=='Published: 2026-11-10' and not notes


def test_explicit_old_page_date_overrides_recent_provider_estimate():
    sources,_=qualify_sources([row()],NOW-timedelta(days=30),NOW)
    enriched,notes=enrich_sources(request(),sources,{sources[0].url:'Published: 2020-01-01\nOld material'},NOW-timedelta(days=30),NOW)
    assert not enriched and notes


def test_wrong_identity_is_not_used_as_evidence():
    sources,_=qualify_sources([row()],NOW-timedelta(days=30),NOW,fixture=True)
    sources,_=enrich_sources(request(entity='Different Company'),sources,{},NOW-timedelta(days=30),NOW)
    source=sources[0]
    claim=Claim(text=source.content,relevance='Discuss next steps.',source_ids=['S1'],evidence={'S1':source.content})
    accepted,uncertain,removed=assess_claims([claim],sources)
    assert not source.identity_match and not accepted and not uncertain and removed==1


def test_estimated_date_goes_to_uncertain_section_not_facts():
    sources,_=qualify_sources([row()],NOW-timedelta(days=30),NOW)
    source=sources[0]
    claim=Claim(text=source.content,relevance='Explore a pilot.',source_ids=['S1'],evidence={'S1':source.content})
    accepted,uncertain,removed=assess_claims([claim],sources)
    assert not accepted and len(uncertain)==1 and removed==0


def test_old_event_is_excluded_even_in_recent_publication():
    text='Example Corp launched the product on 2020-01-01.'
    sources,_=qualify_sources([row(content=text)],NOW-timedelta(days=30),NOW,fixture=True)
    claim=Claim(text=text,relevance='Discuss the roadmap.',source_ids=['S1'],evidence={'S1':text},
                occurred_at='2020-01-01T00:00:00Z',date_evidence=text)
    accepted,uncertain,removed=assess_claims([claim],sources,NOW-timedelta(days=30),NOW)
    assert not accepted and not uncertain and removed==1


@pytest.mark.parametrize('url',['http://127.0.0.1/a','http://10.0.0.1/a','http://localhost/a','http://service.internal/a','http://169.254.169.254/metadata'])
def test_nonpublic_extraction_urls_rejected(url):
    assert canonical_url(url) is None


def test_extract_partial_failure_and_out_of_order_results():
    async def run():
        sources,_=qualify_sources([row(),row(url='https://example.org/second')],NOW-timedelta(days=30),NOW)
        def handler(req):
            data=json.loads(req.content)
            assert len(data['urls'])==2
            return httpx.Response(200,json={'results':[{'url':'https://example.org/second','raw_content':'Full second page'}],
                                           'failed_results':[{'url':'https://example.org/news','error':'unavailable'}],
                                           'usage':{'credits':1}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            metrics=Metrics()
            extracted,notes=await TavilyService(Settings(),client,metrics).extract(sources)
            assert extracted=={'https://example.org/second':'Full second page'}
            assert notes and metrics.extract_calls==1 and metrics.tavily_credits==1
    asyncio.run(run())


def wire_output():
    text='Example Corp launched a new research product.'
    return {'claims':[{'text':text,'category':'product','relevance':'Explore a pilot.',
                       'evidence':[{'source_id':'S1','quote':text}],'priority':1,
                       'discussion_question':'What pilot would be useful?','occurred_at':None,'date_evidence':''}],
            'questions':['What are the goals?','What is the scope?','What happens next?'],
            'open_questions':[],'gaps':[]}


def test_native_schema_and_usage_mapping():
    async def run():
        def handler(req):
            data=json.loads(req.content)
            assert data['response_format']['type']=='json_schema'
            schema=data['response_format']['json_schema']
            assert schema['strict'] is True
            assert schema['schema']['additionalProperties'] is False
            return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(wire_output())}}],
                                           'usage':{'prompt_tokens':100,'completion_tokens':20}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            metrics=Metrics()
            result=await LLMService(Settings(input_rate=1,output_rate=2),client,metrics).synthesize(request(),[])
            assert result.claims[0].source_ids==['S1']
            assert metrics.estimated_llm_cost_usd==0.00014
    asyncio.run(run())


@pytest.mark.parametrize('mode',['json_schema','json_object'])
def test_model_refusal_does_not_trigger_silent_fallback(mode):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req:httpx.Response(200,json={'choices':[{'message':{'refusal':'No'}}]}))) as client:
            metrics=Metrics()
            with pytest.raises(ProviderError,match='declined'):
                await LLMService(Settings(llm_output_mode=mode),client,metrics).synthesize(request(),[])
            assert metrics.llm_calls==1
    asyncio.run(run())


def test_missing_usage_is_not_zero_cost():
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req:httpx.Response(200,json={
                'choices':[{'message':{'content':json.dumps(wire_output())}}]}))) as client:
            metrics=Metrics()
            await LLMService(Settings(input_rate=1,output_rate=2),client,metrics).synthesize(request(),[])
            assert not metrics.usage_complete and metrics.estimated_llm_cost_usd is None
    asyncio.run(run())


def test_gap_loop_is_bounded_and_candidates_do_not_leak_into_summary():
    async def run():
        class Research:
            calls=0
            async def search(self,queries,start,end):
                self.calls+=1
                return [row(published_date=(end-timedelta(days=2)).isoformat())]
            async def extract(self,sources): return {}, ['Extraction unavailable in test.']
        class Model:
            calls=0
            async def synthesize(self,req,sources):
                self.calls+=1
                source=sources[0]
                return Synthesis(claims=[Claim(text=source.content,relevance='Explore pilot options.',source_ids=[source.id],evidence={source.id:source.content})],
                                 questions=['What are the goals?','What is the scope?','What happens next?'],gaps=['partner requirements'])
        metrics=Metrics(); research=Research(); model=Model(); stages=[]
        async def progress(stage):
            stages.append(stage)

        report=await run_workflow(request(entity='Example Corp',mode='live'),research,model,metrics,progress)
        assert research.calls==2 and model.calls==2 and metrics.research_rounds==2
        assert report['claims']==[] and len(report['uncertain_claims'])==1
        assert 'launched' not in report['summary']
        assert 'closing_gaps' in stages and stages[-1]=='composing'
        assert len({s['id'] for s in report['sources']})==len(report['sources'])
    asyncio.run(run())


def test_live_identity_confirmation_and_legacy_database_survive(tmp_path):
    path = str(tmp_path / 'test.db')
    store = Store(path)
    store.create('legacy', 'token', {})
    store.update('legacy', status='completed', result={'entity': 'Legacy', 'sources': []})
    app=create_app(Settings(database_path=path,tavily_key='test',llm_key='test'))
    with TestClient(app) as client:
        data=payload(); data.update(mode='live',identity_confirmed=False)
        assert client.post('/api/research',json=data).status_code==422
        legacy=client.get('/api/research/legacy',headers={'Authorization':'Bearer token'})
        assert legacy.status_code==200 and legacy.json()['result']['entity']=='Legacy'
        assert client.get('/api/research/legacy/result', headers={'Authorization': 'Bearer token'}).json() == legacy.json()['result']
        store.create('pending', 'token', {})
        for endpoint in ('result', 'export'):
            response = client.get(f'/api/research/pending/{endpoint}', headers={'Authorization': 'Bearer token'})
            assert response.status_code == 409


def test_new_jobs_persist_evidence_and_stage_trace(tmp_path):
    path = str(tmp_path / 'test.db')
    app=create_app(Settings(database_path=path))
    with TestClient(app) as client:
        ticket=client.post('/api/research',json=payload()).json()
        job=wait_for_job(client,ticket)
        assert job['status']=='completed'
        with Store(path).connect() as db:
            assert db.execute('SELECT COUNT(*) FROM evidence_snapshots WHERE job_id=?',(ticket['id'],)).fetchone()[0]==3
            assert db.execute('SELECT COUNT(*) FROM job_stages WHERE job_id=?',(ticket['id'],)).fetchone()[0]>=6
