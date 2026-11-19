from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MeetingContext(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    role: str = Field(default='', max_length=160)
    offering: str = Field(default='', max_length=400)
    desired_outcome: str = Field(default='', max_length=400)


class ResearchRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    entity: str = Field(min_length=2, max_length=120)
    entity_type: Literal['company', 'person'] = 'company'
    meeting_at: datetime
    timezone: str = 'Europe/Warsaw'
    purpose: Literal['business', 'recruitment', 'partnership', 'general'] = 'business'
    context: str = Field(default='', max_length=1200)
    identity_hint: str = Field(default='', max_length=200)
    identity_confirmed: bool = False
    meeting_context: MeetingContext = Field(default_factory=MeetingContext)
    mode: Literal['demo', 'live'] = 'demo'

    @field_validator('meeting_at')
    @classmethod
    def aware_meeting(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError('Meeting date must include a timezone offset.')
        if not 2000 <= value.year <= 2100:
            raise ValueError('Meeting year must be between 2000 and 2100.')
        return value

    @field_validator('timezone')
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError('Use a valid IANA timezone, for example Europe/Warsaw.')
        return value


class Source(BaseModel):
    id: str
    title: str
    url: str
    content: str
    published_at: datetime | None = None
    provider_date: datetime | None = None
    retrieved_at: datetime | None = None
    date_origin: Literal['provider_estimate', 'explicit_page', 'fixture', 'unknown'] = 'unknown'
    date_evidence: str = ''
    content_origin: Literal['search_snippet', 'extracted_page', 'fixture'] = 'search_snippet'
    content_hash: str = ''
    search_content: str = ''
    search_hash: str = ''
    identity_match: bool = True
    date_precision: Literal['day', 'instant', 'unknown'] = 'unknown'
    temporal_status: Literal['in_window', 'estimated', 'undated'] = 'undated'


class Claim(BaseModel):
    text: str = Field(min_length=5, max_length=300)
    category: Literal['news', 'product', 'organization', 'other'] = 'news'
    relevance: str = Field(min_length=5, max_length=220)
    source_ids: list[str] = Field(min_length=1, max_length=3)
    evidence: dict[str, str]
    # "excerpt_matched" is a mechanical check, not a truth or entailment verdict.
    evidence_status: Literal['unchecked', 'excerpt_matched'] = 'unchecked'
    priority: int = Field(default=3, ge=1, le=5)
    discussion_question: str = Field(default='', max_length=180)
    occurred_at: datetime | None = None
    date_evidence: str = Field(default='', max_length=250)
    temporal_note: str = ''


class Synthesis(BaseModel):
    claims: list[Claim] = Field(default_factory=list, max_length=5)
    questions: list[str] = Field(min_length=3, max_length=5)
    open_questions: list[str] = Field(default_factory=list, max_length=4)
    gaps: list[str] = Field(default_factory=list, max_length=2)

    @field_validator('questions', 'open_questions')
    @classmethod
    def bounded_lines(cls, values):
        if any(not v.strip() or len(v) > 220 for v in values):
            raise ValueError('Questions must be nonempty and at most 220 characters.')
        return values


class Metrics(BaseModel):
    elapsed_seconds: float = 0
    search_calls: int = 0
    llm_calls: int = 0
    extract_calls: int = 0
    research_rounds: int = 0
    tavily_credits: float = 0
    tavily_usage_complete: bool = True
    sources_extracted: int = 0
    sources_identity_rejected: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    usage_complete: bool = True
    sources_found: int = 0
    sources_eligible: int = 0
    claims_removed: int = 0
    estimated_llm_cost_usd: float | None = None


class Briefing(BaseModel):
    schema_version: int = 2
    entity: str
    entity_type: str
    meeting_at: datetime
    timezone: str
    purpose: str
    mode: str
    generated_at: datetime
    window_start: datetime
    window_end: datetime
    summary: str
    claims: list[Claim]
    uncertain_claims: list[Claim] = Field(default_factory=list)
    summary_source_ids: list[str] = Field(default_factory=list)
    meeting_context: MeetingContext = Field(default_factory=MeetingContext)
    identity_status: str = 'unconfirmed'
    questions: list[str]
    open_questions: list[str]
    sources: list[Source]
    warnings: list[str]
    metrics: Metrics
