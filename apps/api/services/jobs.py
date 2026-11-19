import asyncio
import hashlib
import hmac
import json
import logging
import secrets
from collections.abc import Callable
from uuid import uuid4

import httpx

from apps.api.agents.workflow import run_workflow
from apps.api.config import Settings
from apps.api.schemas.briefing import Metrics, ResearchRequest
from apps.api.schemas.jobs import ResearchTicket
from apps.api.services.demo import DEMO_ENTITY
from apps.api.services.llm_service import LLMService
from apps.api.services.provider_http import ProviderError
from apps.api.services.tavily_service import TavilyService
from apps.api.store import Store

logger = logging.getLogger('meetingintel')


class InvalidResearchRequest(Exception):
    pass


class LiveResearchUnavailable(Exception):
    pass


class JobCapacityExceeded(Exception):
    pass


class SubmissionConflict(Exception):
    pass


class ResultUnavailable(Exception):
    pass


def _submission_token(key: str, job_id: str) -> str:
    return hmac.digest(bytes.fromhex(key), f'meetingintel/job-access/v1/{job_id}'.encode(), 'sha256').hex()


class ResearchJobs:
    """Own the lifecycle of research tasks within a single API process."""

    def __init__(
        self,
        config: Settings,
        store: Store,
        research_factory: Callable | None = None,
        llm_factory: Callable | None = None,
    ):
        self.config = config
        self._store = store
        self.research_factory = research_factory or TavilyService
        self.llm_factory = llm_factory or LLMService
        self.tasks: set[asyncio.Task[None]] = set()
        self.creation_lock = asyncio.Lock()

    async def start(self) -> None:
        await asyncio.to_thread(self._store.recover)

    async def stop(self) -> None:
        pending = list(self.tasks)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        await asyncio.to_thread(self._store.recover)

    def read_job(self, job_id: str, token: str) -> dict | None:
        return self._store.get(job_id, token)

    def read_status(self, job_id: str, token: str) -> dict | None:
        return self._store.get_status(job_id, token)

    def read_result(self, job_id: str, token: str) -> dict | None:
        job = self.read_job(job_id, token)
        if job is None:
            return None
        if job['result'] is None:
            raise ResultUnavailable('Briefing is not complete.')
        return job['result']

    def _validate_new_request(self, request: ResearchRequest) -> None:
        if request.mode == 'demo' and (request.entity != DEMO_ENTITY or request.entity_type != 'company'):
            raise InvalidResearchRequest(f'Fictional demo supports only company {DEMO_ENTITY}. Use live mode for other entities.')
        if request.mode == 'live':
            if not self.config.live_ready:
                raise LiveResearchUnavailable('Live research requires TAVILY_API_KEY and LLM_API_KEY in the backend .env.')
            if not request.identity_confirmed or not request.identity_hint:
                raise InvalidResearchRequest('Confirm the intended company website or person’s organization/role before live research.')

    async def submit(self, request: ResearchRequest, idempotency_key: str | None = None) -> ResearchTicket:
        payload = request.model_dump(mode='json')
        submission = None
        if idempotency_key is not None:
            key_hash = hashlib.sha256(bytes.fromhex(idempotency_key)).hexdigest()
            request_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
            submission = (key_hash, request_hash)

        async with self.creation_lock:
            if submission is not None:
                prior = await asyncio.to_thread(self._store.find_submission, key_hash)
                if prior is not None:
                    if prior['request_hash'] != request_hash:
                        raise SubmissionConflict('This idempotency key was used for a different request.')
                    return ResearchTicket(id=prior['id'], status=prior['status'],
                                          access_token=_submission_token(idempotency_key, prior['id']))

            self._validate_new_request(request)
            if len(self.tasks) >= self.config.max_active:
                raise JobCapacityExceeded('All research slots are busy. Try again after a briefing finishes.')
            handoff = asyncio.create_task(self._create_and_schedule(request, payload, idempotency_key, submission))
            try:
                return await asyncio.shield(handoff)
            except asyncio.CancelledError:
                # Finish the handoff even if a caller cancels while SQLite is writing.
                await asyncio.gather(handoff, return_exceptions=True)
                raise

    async def _create_and_schedule(self, request, payload, idempotency_key, submission) -> ResearchTicket:
        job_id = str(uuid4())
        token = _submission_token(idempotency_key, job_id) if idempotency_key else secrets.token_urlsafe(32)
        await asyncio.to_thread(self._store.create, job_id, token, payload, submission=submission)
        task = asyncio.create_task(self._execute(job_id, request))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return ResearchTicket(id=job_id, access_token=token, status='queued')

    async def _execute(self, job_id: str, request: ResearchRequest) -> None:
        metrics = Metrics()

        async def progress(stage: str) -> None:
            await asyncio.to_thread(self._store.update, job_id, only_active=True, stage=stage)

        try:
            await asyncio.to_thread(self._store.update, job_id, only_active=True, status='running')
            async with httpx.AsyncClient(timeout=httpx.Timeout(25.0, connect=8.0)) as client:
                research = self.research_factory(self.config, client, metrics)
                llm = self.llm_factory(self.config, client, metrics)
                result = await asyncio.wait_for(
                    run_workflow(request, research, llm, metrics, progress),
                    timeout=self.config.job_timeout,
                )
            await asyncio.to_thread(self._store.update, job_id, only_active=True, status='completed', stage='completed', result=result)
        except asyncio.TimeoutError:
            await self._fail(job_id, 'Research exceeded its time budget. Please retry.')
        except ProviderError as exc:
            await self._fail(job_id, str(exc))
        except asyncio.CancelledError:
            await self._fail(job_id, 'Server stopped before the briefing was complete. Please retry.')
            raise
        except Exception as exc:
            logger.error('Job %s failed: %s', job_id, type(exc).__name__)
            await self._fail(job_id, 'Briefing could not be completed. Please retry.')

    async def _fail(self, job_id: str, error: str) -> None:
        await asyncio.to_thread(self._store.update, job_id, only_active=True, status='failed', stage='failed', error=error)
