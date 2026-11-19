import asyncio
import json
import logging
import secrets
from contextlib import asynccontextmanager
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from apps.api.agents.workflow import run_workflow
from apps.api.config import Settings
from apps.api.schemas.briefing import Metrics, ResearchRequest
from apps.api.services.demo import DEMO_ENTITY
from apps.api.services.export import markdown
from apps.api.services.llm_service import LLMService
from apps.api.services.tavily_service import ProviderError, TavilyService
from apps.api.store import Store

logger = logging.getLogger('meetingintel')
bearer = HTTPBearer(auto_error=False)


def create_app(settings=None, research_factory=None, llm_factory=None):
    config = settings or Settings.from_env()
    store = Store(config.database_path)
    tasks = set()
    creation_lock = asyncio.Lock()

    @asynccontextmanager
    async def lifespan(app):
        store.recover()
        yield
        pending = list(tasks)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)

    app = FastAPI(title='MeetingIntel AI', version='0.1.0', lifespan=lifespan)
    app.state.store = store
    app.add_middleware(CORSMiddleware, allow_origins=[config.web_origin],
                       allow_methods=['GET', 'POST'], allow_headers=['Authorization', 'Content-Type'])

    def authorized_job(job_id: str, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if not credentials:
            raise HTTPException(401, 'A briefing access token is required.')
        job = store.get(job_id, credentials.credentials)
        if job is None:
            raise HTTPException(404, 'Briefing not found or token invalid.')
        return job

    async def execute(job_id, request):
        metrics = Metrics()
        try:
            store.update(job_id, status='running')
            async with httpx.AsyncClient(timeout=httpx.Timeout(25.0, connect=8.0)) as client:
                research = (research_factory or TavilyService)(config, client, metrics)
                llm = (llm_factory or LLMService)(config, client, metrics)
                result = await asyncio.wait_for(
                    run_workflow(request, research, llm, metrics,
                                 lambda stage: store.update(job_id, stage=stage)),
                    timeout=config.job_timeout)
            store.update(job_id, status='completed', stage='completed', result=result)
        except asyncio.TimeoutError:
            store.update(job_id, status='failed', stage='failed', error='Research exceeded its time budget. Please retry.')
        except ProviderError as exc:
            store.update(job_id, status='failed', stage='failed', error=str(exc))
        except asyncio.CancelledError:
            store.update(job_id, status='failed', stage='failed', error='Server stopped before the briefing was complete. Please retry.')
            raise
        except Exception as exc:
            # Do not log user input, provider bodies, headers or exceptions containing secrets.
            logger.error('Job %s failed: %s', job_id, type(exc).__name__)
            store.update(job_id, status='failed', stage='failed', error='Briefing could not be completed. Please retry.')

    @app.get('/health')
    async def health():
        return {'status': 'ok', 'live_ready': config.live_ready, 'demo_available': True}

    @app.post('/api/research', status_code=202)
    async def create_research(request: ResearchRequest):
        if request.mode == 'demo' and (request.entity != DEMO_ENTITY or request.entity_type != 'company'):
            raise HTTPException(422, f'Fictional demo supports only company {DEMO_ENTITY}. Use live mode for other entities.')
        if request.mode == 'live' and not config.live_ready:
            raise HTTPException(503, 'Live research requires TAVILY_API_KEY and LLM_API_KEY in the backend .env.')
        if request.mode == 'live' and (not request.identity_confirmed or not request.identity_hint):
            raise HTTPException(422, 'Confirm the intended company website or person’s organization/role before live research.')
        async with creation_lock:
            if store.active_count() >= config.max_active:
                raise HTTPException(429, 'All research slots are busy. Try again after a briefing finishes.')
            job_id, token = str(uuid4()), secrets.token_urlsafe(32)
            job = store.create(job_id, token, request.model_dump(mode='json'))
            task = asyncio.create_task(execute(job_id, request))
            tasks.add(task)
            task.add_done_callback(tasks.discard)
        return {'id': job_id, 'access_token': token, 'status': job['status']}

    @app.get('/api/research/{job_id}')
    async def get_research(job=Depends(authorized_job)):
        return job

    @app.get('/api/research/{job_id}/events')
    async def events(job=Depends(authorized_job)):
        async def stream():
            last_revision = -1
            while True:
                current = store.get(job['id'])
                if current['revision'] != last_revision:
                    yield f"event: status\ndata: {json.dumps(current)}\n\n"
                    last_revision = current['revision']
                else:
                    yield ': keepalive\n\n'
                if current['status'] in ('completed', 'failed'):
                    break
                await asyncio.sleep(0.7)
        return StreamingResponse(stream(), media_type='text/event-stream',
                                 headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

    @app.get('/api/research/{job_id}/export')
    async def export(job=Depends(authorized_job)):
        if not job['result']:
            raise HTTPException(409, 'Briefing is not complete.')
        return Response(markdown(job['result']), media_type='text/markdown',
                        headers={'Content-Disposition': 'attachment; filename="meetingintel-briefing.md"'})

    return app


app = create_app()
