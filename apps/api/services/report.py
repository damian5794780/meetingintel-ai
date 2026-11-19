from datetime import datetime

from apps.api.schemas.briefing import Briefing, Claim, Metrics, ResearchRequest, Source, Synthesis


def neutral_questions(request: ResearchRequest) -> list[str]:
    goal = request.meeting_context.desired_outcome
    first = f'What would make {goal[:100].rstrip(".?")} successful?' if goal else 'What would make this meeting successful?'
    return [
        first,
        'Which current priorities and constraints should we understand?',
        'Who should participate in the next discussion, and what should we prepare?',
    ]


def _brief_summary(claims: list[Claim], purpose: str) -> str:
    if not claims:
        return ('No findings with explicit timing evidence were retained. Review the candidates requiring date confirmation '
                'and use the questions to clarify priorities.')
    return f'For your {purpose} meeting: ' + ' '.join(f'“{claim.text}” [{claim.source_ids[0]}]' for claim in claims[:2])


def _with_primary_citation(claim: Claim, sources: dict[str, Source]) -> Claim:
    def citation_priority(source_id: str) -> tuple[bool, bool]:
        source = sources[source_id]
        return (bool(claim.date_evidence and claim.date_evidence in source.content),
                source.temporal_status == 'in_window')

    primary = max(claim.source_ids, key=citation_priority)
    return claim.model_copy(update={'source_ids': [primary], 'evidence': {primary: claim.evidence[primary]}})


def compose_briefing(
    request: ResearchRequest,
    *,
    generated_at: datetime,
    window: tuple[datetime, datetime],
    synthesis: Synthesis,
    accepted: list[Claim],
    uncertain: list[Claim],
    sources: list[Source],
    warnings: list[str],
    gaps: list[str],
    research_rounds: int,
    metrics: Metrics,
) -> Briefing:
    """Compose a briefing from verified findings and their evidence."""
    by_id = {source.id: source for source in sources}
    claims = [_with_primary_citation(claim, by_id) for claim in accepted[:4]]
    candidates = [_with_primary_citation(claim, by_id) for claim in uncertain[:4 - len(claims)]]

    warnings = list(warnings)
    if request.meeting_at > generated_at:
        warnings.append('Research ends at generation time. Future developments before the meeting are not yet available.')
    if metrics.claims_removed:
        warnings.append(f'{metrics.claims_removed} findings removed: missing quotes, mismatched identity, duplicates or unsupported dates.')
    if candidates:
        warnings.append('Date-unconfirmed candidates are separate from findings with explicit timing evidence. Provider dates may reflect page updates.')
    if request.mode == 'demo':
        warnings.insert(0, 'FICTIONAL DEMO — no web search or language model calls were made. example.com links are placeholders.')
    if gaps and research_rounds >= 2:
        warnings.append('The one permitted follow-up research round is complete. Remaining coverage gaps require discussion.')
    warnings.append('Quotes confirm retrieved wording, not factual truth or independent identity. Questions and implications are suggestions. Event dates can differ from publication dates.')

    neutral = neutral_questions(request)
    suggested = synthesis.questions if not metrics.claims_removed and not candidates else neutral
    targeted = [claim.discussion_question for claim in claims if claim.discussion_question]
    open_questions = list(synthesis.open_questions)
    if candidates:
        open_questions.append('Confirm the event dates for the date-unconfirmed candidates.')
    open_questions.extend(f'Research gap: {gap}' for gap in gaps)

    return Briefing(
        entity=request.entity,
        entity_type=request.entity_type,
        meeting_at=request.meeting_at,
        timezone=request.timezone,
        purpose=request.purpose,
        mode=request.mode,
        generated_at=generated_at,
        window_start=window[0],
        window_end=window[1],
        summary=_brief_summary(claims, request.purpose),
        summary_source_ids=[claim.source_ids[0] for claim in claims[:2]],
        claims=claims,
        uncertain_claims=candidates,
        questions=list(dict.fromkeys(targeted + suggested + neutral))[:4],
        meeting_context=request.meeting_context,
        identity_status='fictional_demo' if request.mode == 'demo' else 'user_confirmed',
        open_questions=list(dict.fromkeys(open_questions))[:3],
        sources=sources,
        warnings=list(dict.fromkeys(warnings)),
        metrics=metrics,
    )
