import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from apps.api.schemas.briefing import ResearchRequest
from apps.api.schemas.jobs import ResearchJob, ResearchResult, ResearchStatus, ResearchTicket
from apps.api.services.export import markdown
from apps.api.services.jobs import (
    InvalidResearchRequest,
    JobCapacityExceeded,
    LiveResearchUnavailable,
    ResearchJobs,
    ResultUnavailable,
    SubmissionConflict,
)

router = APIRouter(prefix='/api/research', tags=['research'])
bearer = HTTPBearer(auto_error=False)


def get_jobs(request: Request) -> ResearchJobs:
    return request.app.state.jobs


Jobs = Annotated[ResearchJobs, Depends(get_jobs)]


def access_token(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> str:
    if credentials is None:
        raise HTTPException(401, 'A briefing access token is required.')
    return credentials.credentials


AccessToken = Annotated[str, Depends(access_token)]


def require_job(job):
    if job is None:
        raise HTTPException(404, 'Briefing not found or token invalid.')
    return job


def authorized_job(job_id: str, jobs: Jobs, token: AccessToken):
    return require_job(jobs.read_job(job_id, token))


def authorized_result(job_id: str, jobs: Jobs, token: AccessToken):
    try:
        return require_job(jobs.read_result(job_id, token))
    except ResultUnavailable as exc:
        raise HTTPException(409, str(exc)) from exc


AuthorizedJob = Annotated[dict, Depends(authorized_job)]
AuthorizedResult = Annotated[dict, Depends(authorized_result)]


@router.post('', status_code=202)
async def create_research(
    request: ResearchRequest,
    jobs: Jobs,
    idempotency_key: Annotated[str | None, Header(
        pattern=r'^[a-f0-9]{64}$', min_length=64, max_length=64,
        description='A private key generated from 32 random bytes and encoded as lowercase hex.',
    )] = None,
) -> ResearchTicket:
    try:
        return await jobs.submit(request, idempotency_key)
    except InvalidResearchRequest as exc:
        raise HTTPException(422, str(exc)) from exc
    except LiveResearchUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except JobCapacityExceeded as exc:
        raise HTTPException(429, str(exc)) from exc
    except SubmissionConflict as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get('/{job_id}', response_model=ResearchJob, response_model_exclude_unset=True)
def get_research(job: AuthorizedJob):
    return job


@router.get('/{job_id}/status', response_model=ResearchStatus)
def get_status(job_id: str, jobs: Jobs, token: AccessToken):
    return require_job(jobs.read_status(job_id, token))


@router.get('/{job_id}/result', response_model=ResearchResult, response_model_exclude_unset=True)
def get_result(result: AuthorizedResult):
    return result


@router.get('/{job_id}/events', response_class=StreamingResponse,
            responses={200: {'content': {'text/event-stream': {'schema': {'type': 'string'}}}}})
async def events(job: AuthorizedJob, jobs: Jobs, token: AccessToken):
    async def stream():
        current = job
        last_revision = -1
        while current is not None:
            if current['revision'] != last_revision:
                data = ResearchJob.model_validate(current).model_dump_json(exclude_unset=True)
                yield f'event: status\ndata: {data}\n\n'
                last_revision = current['revision']
            else:
                yield ': keepalive\n\n'
            if current['status'] in ('completed', 'failed'):
                break
            await asyncio.sleep(0.7)
            current = await asyncio.to_thread(jobs.read_job, job['id'], token)

    return StreamingResponse(stream(), media_type='text/event-stream',
                             headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@router.get('/{job_id}/export', response_class=Response,
            responses={200: {'content': {'text/markdown': {'schema': {'type': 'string'}}}}})
def export(result: AuthorizedResult):
    return Response(markdown(result), media_type='text/markdown',
                    headers={'Content-Disposition': 'attachment; filename="meetingintel-briefing.md"'})
