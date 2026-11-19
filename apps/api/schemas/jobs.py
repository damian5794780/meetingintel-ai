from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from apps.api.schemas.briefing import Briefing

JobStatus = Literal['queued', 'running', 'completed', 'failed']


class HealthResponse(BaseModel):
    status: Literal['ok']
    live_ready: bool
    demo_available: bool


class ResearchTicket(BaseModel):
    id: str
    access_token: str
    status: JobStatus


class LegacyBriefing(BaseModel):
    """Preserve historical snapshots that predate the complete briefing schema."""

    model_config = ConfigDict(extra='allow')
    entity: str
    schema_version: Literal[1] = 1


ResearchResult = Annotated[Briefing | LegacyBriefing, Field(union_mode='left_to_right')]


class ResearchStatus(BaseModel):
    id: str
    status: JobStatus
    stage: str
    revision: int
    created_at: str
    error: str | None


class ResearchJob(ResearchStatus):
    request: dict[str, Any]
    result: ResearchResult | None
