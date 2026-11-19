import asyncio
import hashlib
import json
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from apps.api.application import create_app
from apps.api.config import Settings
from apps.api.schemas.briefing import Claim, Metrics, ResearchRequest, Synthesis
from apps.api.services.llm_service import LLMService
from apps.api.services.provider_http import ProviderError
from apps.api.services.sources import parse_publication, qualify_sources, research_window
from apps.api.services.tavily_service import TavilyService
from apps.api.services.verification import verify_claims
from apps.api.store import Store

NOW = datetime(2026, 11, 14, 12, tzinfo=timezone.utc)


def payload(**changes):
    return dict(entity='Northstar Labs', entity_type='company', meeting_at=NOW.isoformat(),
                timezone='Europe/Warsaw', purpose='partnership', mode='demo',
                identity_hint='example.org', identity_confirmed=True, **changes)


def request(**changes):
    data = payload()
    data.update(changes)
    return ResearchRequest(**data)


def row(**changes):
    data = dict(title='Announcement', url='https://example.org/news',
                content='Example Corp launched a new research product.', published_date=NOW.isoformat())
    data.update(changes)
    return data


def test_window_is_relative_to_meeting_and_capped_at_now():
    start, end = research_window(request(meeting_at=NOW+timedelta(days=2)), NOW)
    assert start == NOW-timedelta(days=28)
    assert end == NOW
    meeting = NOW-timedelta(days=10)
    assert research_window(request(meeting_at=meeting), NOW) == (meeting-timedelta(days=30), meeting)


@pytest.mark.parametrize('changes', [dict(entity=' '), dict(meeting_at='2026-11-14T10:00:00'),
                                    dict(timezone='Invalid/Zone'), dict(entity_type='unknown'), dict(context='x'*1201)])
def test_input_validation(changes):
    with pytest.raises(ValidationError):
        request(**changes)


def test_deduplication_removes_tracking_and_fragment():
    sources, _ = qualify_sources([row(url='https://example.org/news?utm_source=mail#fragment'), row()], NOW-timedelta(days=30), NOW)
    assert len(sources) == 1
    assert sources[0].url == 'https://example.org/news'


def test_rfc2822_news_dates_are_supported():
    date, precision = parse_publication('Sat, 14 Nov 2026 12:00:00 GMT')
    assert date == NOW
    assert precision == 'instant'


@pytest.mark.parametrize('date', ['not a date', '2026-11-14T12:00:00', '', None])
def test_unconfirmed_dates_remain_unknown(date):
    assert parse_publication(date) == (None, 'unknown')


def test_dates_unknown_and_outside_window():
    start = NOW-timedelta(days=30)
    sources, warnings = qualify_sources([row(published_date=(start-timedelta(seconds=1)).isoformat()),
                                         row(url='https://example.org/future', published_date=(NOW+timedelta(seconds=1)).isoformat()),
                                         row(url='https://example.org/unknown', published_date=None)], start, NOW)
    assert len(sources) == 1
    assert sources[0].temporal_status == 'undated'
    assert warnings


def test_day_precision_does_not_invent_boundary_times():
    start = NOW-timedelta(days=30)
    sources, _ = qualify_sources([row(published_date=start.date().isoformat()),
                                  row(url='https://example.org/interior', published_date=(start+timedelta(days=1)).date().isoformat()),
                                  row(url='https://example.org/today', published_date=NOW.date().isoformat())], start, NOW)
    assert [s.url for s in sources] == ['https://example.org/interior']


@pytest.mark.parametrize('url', ['javascript:alert(1)', 'file:///etc/passwd', 'https://user:pass@example.org/a'])
def test_nonweb_and_credential_urls_rejected(url):
    assert qualify_sources([row(url=url)], NOW-timedelta(days=30), NOW)[0] == []


@pytest.mark.parametrize('case', ['valid', 'missing_id', 'fabricated_quote', 'unsupported_claim', 'undated'])
def test_evidence_gate(case):
    sources, _ = qualify_sources([row(published_date=None if case=='undated' else NOW.isoformat())], NOW-timedelta(days=30), NOW, fixture=True)
    sid = 'S99' if case=='missing_id' else 'S1'
    text = 'Example Corp launched a new research product.'
    quote = 'This quotation does not exist in the source.' if case=='fabricated_quote' else text
    claim = Claim(text='Revenue doubled last week.' if case=='unsupported_claim' else text,
                  relevance='Consider discussing integration possibilities.', source_ids=[sid], evidence={sid: quote})
    accepted, removed = verify_claims([claim], sources)
    assert bool(accepted) == (case == 'valid')
    assert removed == (case != 'valid')


def test_report_length_validation():
    with pytest.raises(ValidationError):
        Synthesis(questions=['x'*221]*3)


@pytest.mark.parametrize('status', [401, 403, 429, 500])
def test_search_provider_errors_are_safe_and_bounded(status):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(status, text='SECRET'))) as client:
            metrics = Metrics()
            with pytest.raises(ProviderError) as exc:
                await TavilyService(Settings(tavily_key='SECRET'), client, metrics).search(['test'], NOW-timedelta(days=30), NOW)
            assert 'SECRET' not in str(exc.value)
            assert metrics.search_calls == (1 if status in (401,403) else 2)
    asyncio.run(run())


def test_timeout_is_bounded():
    async def run():
        def fail(req):
            raise httpx.ReadTimeout('secret', request=req)
        async with httpx.AsyncClient(transport=httpx.MockTransport(fail)) as client:
            metrics=Metrics()
            with pytest.raises(ProviderError):
                await TavilyService(Settings(), client, metrics).search(['test'], NOW-timedelta(days=30), NOW)
            assert metrics.search_calls == 2
    asyncio.run(run())


def test_invalid_llm_json_has_one_repair_attempt():
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200,json={'choices':[{'message':{'content':'not json'}}]}))) as client:
            metrics=Metrics()
            with pytest.raises(ProviderError):
                await LLMService(Settings(),client,metrics).synthesize(request(), [])
            assert metrics.llm_calls == 2
    asyncio.run(run())


def wait_for_job(client, ticket):
    headers={'Authorization': f"Bearer {ticket['access_token']}"}
    for _ in range(100):
        response=client.get(f"/api/research/{ticket['id']}", headers=headers)
        assert response.status_code == 200
        job=response.json()
        if job['status'] in ('completed','failed'):
            return job
        time.sleep(0.02)
    pytest.fail('Job never reached terminal status')


def test_demo_full_path_auth_export_and_sse(tmp_path):
    app=create_app(Settings(database_path=str(tmp_path/'test.db')))
    with TestClient(app) as client:
        assert client.get('/health').json()['live_ready'] is False
        created=client.post('/api/research',json=payload())
        assert created.status_code == 202
        ticket=created.json()
        path=f"/api/research/{ticket['id']}"
        assert client.get(path).status_code == 401
        assert client.get(path,headers={'Authorization':'Bearer wrong'}).status_code == 404
        job=wait_for_job(client,ticket)
        assert job['status'] == 'completed', job
        assert len(job['result']['claims']) == 2
        assert job['result']['metrics']['search_calls'] == 0
        assert 'FICTIONAL' in job['result']['warnings'][0]
        headers={'Authorization': f"Bearer {ticket['access_token']}"}
        status = client.get(path + '/status', headers=headers)
        assert status.json() == {field: job[field] for field in ('id', 'status', 'stage', 'revision', 'created_at', 'error')}
        assert client.get(path + '/result', headers=headers).json() == job['result']
        assert client.get(path + '/status').status_code == 401
        assert client.get(path + '/result', headers={'Authorization': 'Bearer wrong'}).status_code == 404
        export=client.get(path+'/export',headers=headers)
        assert export.status_code == 200 and 'Northstar Labs' in export.text
        events=client.get(path+'/events',headers=headers)
        assert 'event: status' in events.text and 'completed' in events.text
        event_data = next(line.removeprefix('data: ') for line in events.text.splitlines() if line.startswith('data: '))
        assert json.loads(event_data) == job


def test_research_responses_are_declared_in_openapi(tmp_path):
    app = create_app(Settings(database_path=str(tmp_path / 'contract.db')))
    paths = app.openapi()['paths']
    for path, method, status, schema in [
        ('/health', 'get', '200', 'HealthResponse'),
        ('/api/research', 'post', '202', 'ResearchTicket'),
        ('/api/research/{job_id}', 'get', '200', 'ResearchJob'),
        ('/api/research/{job_id}/status', 'get', '200', 'ResearchStatus'),
    ]:
        response = paths[path][method]['responses'][status]['content']['application/json']
        assert response['schema']['$ref'] == f'#/components/schemas/{schema}'


def test_database_is_initialized_only_when_application_starts(tmp_path):
    path = tmp_path / 'database' / 'jobs.db'
    app = create_app(Settings(database_path=str(path)))
    assert app.openapi()['paths']['/api/research']
    assert not path.parent.exists()

    with TestClient(app) as client:
        assert path.is_file()
        assert client.get('/health').status_code == 200


@pytest.mark.parametrize('kind', ['company','person'])
def test_live_workflow_with_injected_providers(tmp_path, kind):
    class Research:
        def __init__(self,*args): pass
        async def search(self, queries, start, end):
            assert 'Example' in queries[0].query
            return [row(published_date=(end-timedelta(days=2)).isoformat())]
        async def extract(self, sources):
            return {s.url: 'Published: 2026-11-10T10:00:00+00:00\n' + s.content for s in sources}, []
    class LLM:
        def __init__(self,*args): pass
        async def synthesize(self, req, sources):
            text=sources[0].content.split('\n')[-1]
            return Synthesis(claims=[Claim(text=text, relevance='Discuss the potential pilot.',source_ids=['S1'],evidence={'S1':text})],
                             questions=['What are your priorities?','What should we explore?','What happens next?'])
    app=create_app(Settings(database_path=str(tmp_path/'live.db'),tavily_key='test',llm_key='test'),Research,LLM)
    with TestClient(app) as client:
        data=payload();data.update(mode='live',entity='Example',entity_type=kind)
        ticket=client.post('/api/research',json=data).json()
        job=wait_for_job(client,ticket)
        assert job['status']=='completed'
        assert job['result']['claims'][0]['evidence_status']=='excerpt_matched'


def test_no_sources_does_not_call_llm(tmp_path):
    class Empty:
        def __init__(self,*args): pass
        async def search(self,*args): return []
    class NoLLM:
        def __init__(self,*args): pass
        async def synthesize(self,*args): raise AssertionError('Must not call LLM')
    app=create_app(Settings(database_path=str(tmp_path/'empty.db'),tavily_key='test',llm_key='test'),Empty,NoLLM)
    with TestClient(app) as client:
        data=payload();data['mode']='live'
        job=wait_for_job(client,client.post('/api/research',json=data).json())
        assert job['status']=='completed'
        assert job['result']['claims']==[]


def test_live_requires_keys_and_demo_rejects_real_entity(tmp_path):
    with TestClient(create_app(Settings(database_path=str(tmp_path/'test.db')))) as client:
        data=payload();data['mode']='live'
        assert client.post('/api/research',json=data).status_code==503
        data.update(mode='demo',entity='Actual Corp')
        assert client.post('/api/research',json=data).status_code==422


def test_capacity_limit(tmp_path):
    app=create_app(Settings(database_path=str(tmp_path/'test.db'),max_active=1))
    with TestClient(app) as client:
        assert client.post('/api/research',json=payload()).status_code==202
        assert client.post('/api/research',json=payload()).status_code==429


def test_repeated_submission_returns_the_same_ticket_and_runs_once(tmp_path):
    settings = Settings(database_path=str(tmp_path / 'submissions.db'), max_active=1)
    key = 'ab' * 32
    headers = {'Idempotency-Key': key}
    with TestClient(create_app(settings)) as client:
        created = client.post('/api/research', json=payload(), headers=headers)
        assert created.status_code == 202
        ticket = created.json()
        replay = client.post('/api/research', json=payload(), headers=headers)
        assert replay.status_code == 202
        assert replay.json()['id'] == ticket['id']
        assert replay.json()['access_token'] == ticket['access_token']
        assert client.post('/api/research', json={**payload(), 'context': 'Changed context'}, headers=headers).status_code == 409
        assert client.post('/api/research', json=payload(), headers={'Idempotency-Key': 'short'}).status_code == 422
        assert wait_for_job(client, ticket)['status'] == 'completed'

    with TestClient(create_app(settings)) as client:
        replay = client.post('/api/research', json=payload(), headers=headers)
        assert replay.json() == {**ticket, 'status': 'completed'}
        with Store(settings.database_path).connect() as db:
            assert db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0] == 1
            stored = db.execute('SELECT key_hash FROM job_submissions').fetchone()[0]
            assert stored == hashlib.sha256(bytes.fromhex(key)).hexdigest()


def test_restart_recovery_and_persistence(tmp_path):
    path=str(tmp_path/'test.db')
    store=Store(path)
    store.create('test','token',{})
    store.update('test', status='running', stage='researching')
    store=Store(path)
    store.recover()
    store.recover()
    status = store.get_status('test', 'token')
    assert (status['status'], status['revision']) == ('failed', 2)
    with store.connect() as db:
        stages = db.execute('SELECT stage FROM job_stages WHERE job_id=? ORDER BY id', ('test',)).fetchall()
    assert [row[0] for row in stages] == ['researching', 'failed']
    assert store.get('test','invalid') is None


def test_migration_preserves_legacy_report_and_closes_the_connection(tmp_path):
    path = tmp_path / 'legacy.db'
    snapshot = dict(id='legacy', status='completed', stage='completed', revision=7,
                    created_at=NOW.isoformat(), request={'entity': 'Legacy'},
                    result={'entity': 'Legacy', 'sources': []}, error=None)
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('CREATE TABLE jobs (id TEXT PRIMARY KEY, token_hash TEXT NOT NULL, payload TEXT NOT NULL)')
        db.execute('INSERT INTO jobs VALUES (?, ?, ?)',
                   ('legacy', hashlib.sha256(b'token').hexdigest(), json.dumps(snapshot)))

    store = Store(str(path))
    assert store.get('legacy', 'token') == snapshot
    assert Store(str(path)).get_status('legacy', 'token')['revision'] == 7
    with store.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM job_metadata').fetchone()[0] == 1
    with pytest.raises(sqlite3.ProgrammingError, match='closed'):
        db.execute('SELECT 1')


def test_late_progress_does_not_change_a_terminal_job(tmp_path):
    store = Store(str(tmp_path / 'jobs.db'))
    store.create('test', 'token', {})
    store.update('test', status='failed', stage='failed')
    store.update('test', only_active=True, stage='composing')
    job = store.get('test', 'token')
    assert job['stage'] == 'failed'
    assert job['revision'] == 1


def test_parallel_search_cancels_pending_requests_before_raising():
    async def run():
        started = asyncio.Event()
        cancelled = asyncio.Event()

        class Client:
            async def post(self, url, *, json, **kwargs):
                if json['query'] == 'fail':
                    await started.wait()
                    return httpx.Response(401)
                started.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    cancelled.set()

        service = TavilyService(Settings(), Client(), Metrics())
        with pytest.raises(ProviderError, match='rejected the API key'):
            await asyncio.wait_for(service.search(['fail', 'pending'], NOW-timedelta(days=30), NOW), timeout=1)
        assert cancelled.is_set()

    asyncio.run(run())
