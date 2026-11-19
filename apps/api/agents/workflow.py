import asyncio
import time
from datetime import datetime, timezone
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from apps.api.schemas.briefing import Briefing, Metrics, Synthesis
from apps.api.services.demo import demo_rows, demo_synthesis
from apps.api.services.research_plan import enrich_sources, rank_sources, search_plan
from apps.api.services.tavily_service import ProviderError, qualify_sources, research_window
from apps.api.services.verification import assess_claims


class State(TypedDict, total=False):
    queries: list
    sources: list
    warnings: list
    synthesis: Synthesis
    claims: list
    uncertain: list
    gaps: list
    research_round: int
    result: dict


def neutral_questions(request):
    goal = request.meeting_context.desired_outcome
    return [f'What would make {goal[:100].rstrip(".?")} successful?' if goal else 'What would make this meeting successful?',
            'Which current priorities and constraints should we understand?',
            'Who should participate in the next discussion, and what should we prepare?']


def brief_summary(claims, purpose):
    if not claims:
        return 'No findings with explicit timing evidence were retained. Review the candidates requiring date confirmation and use the questions to clarify priorities.'
    # Extractive composition after verification: never summarize rejected or uncertain findings as facts.
    selected = claims[:2]
    return f'For your {purpose} meeting: ' + ' '.join(f'“{c.text}” [{c.source_ids[0]}]' for c in selected)


async def run_workflow(request, research, llm, metrics: Metrics, progress):
    began = time.monotonic()
    now = datetime.now(timezone.utc)
    start, end = research_window(request, now)

    async def plan(state):
        progress('planning')
        return {'queries': search_plan(request), 'sources': [], 'warnings': [], 'research_round': 0}

    async def search(state):
        followup = state['research_round'] > 0
        progress('closing_gaps' if followup else 'researching')
        queries = search_plan(request, state['gaps']) if followup else state['queries']
        warnings = list(state['warnings'])
        if request.mode == 'demo':
            await asyncio.sleep(0.2)
            rows = demo_rows(start, end) if start < end else []
        else:
            try:
                rows = await research.search(queries, start, end) if start < end else []
            except ProviderError:
                if not followup:
                    raise
                rows = []
                warnings.append('The single follow-up research round was unavailable. Existing evidence was retained; gaps remain open.')
        fresh, notes = qualify_sources(rows, start, end, fixture=request.mode == 'demo')
        metrics.sources_found += len(rows)
        metrics.research_rounds += 1
        merged = {s.url: s for s in state['sources']}
        next_id = max([int(s.id[1:]) for s in merged.values()] + [0]) + 1
        for source in fresh:
            if source.url not in merged:
                source.id = f'S{next_id}'
                next_id += 1
                merged[source.url] = source
        sources, _ = enrich_sources(request, list(merged.values()), {}, start, end)
        return {'sources': sources, 'warnings': warnings + notes, 'research_round': state['research_round'] + 1}

    async def extract(state):
        progress('extracting')
        warnings = list(state['warnings'])
        candidates = [s for s in rank_sources(request, state['sources'])
                      if s.identity_match and s.content_origin == 'search_snippet'][:5]
        extracted = {}
        if request.mode == 'live' and candidates:
            try:
                extracted, notes = await research.extract(candidates)
                warnings.extend(notes)
            except ProviderError:
                warnings.append('Page extraction unavailable. Search snippets are retained with estimated dates and explicit limitations.')
        sources, notes = enrich_sources(request, state['sources'], extracted, start, end)
        sources = rank_sources(request, sources)[:12]
        metrics.sources_extracted = sum(s.content_origin == 'extracted_page' for s in sources)
        metrics.sources_identity_rejected = sum(not s.identity_match for s in sources)
        metrics.sources_eligible = sum(s.identity_match and s.temporal_status == 'in_window' for s in sources)
        return {'sources': sources, 'warnings': warnings + notes}

    async def synthesize(state):
        progress('synthesizing')
        usable = [s for s in state['sources'] if s.identity_match and s.temporal_status != 'undated']
        if request.mode == 'demo':
            result = demo_synthesis(state['sources'], request)
        elif not usable:
            result = Synthesis(questions=neutral_questions(request),
                               open_questions=['No matching dated evidence found. Confirm identity and recent developments directly.'],
                               gaps=['official recent announcements and developments'] if start < end else [])
        else:
            try:
                result = await llm.synthesize(request, usable[:8])
            except ProviderError:
                if state['research_round'] < 2 or 'synthesis' not in state:
                    raise
                return {'synthesis': state['synthesis'], 'warnings': state['warnings'] + [
                    'Follow-up synthesis unavailable. The earlier findings were retained and checked again.']}
        return {'synthesis': result}

    async def verify(state):
        progress('verifying')
        result = state['synthesis']
        accepted, uncertain, removed = assess_claims(result.claims, state['sources'], start, end)
        metrics.claims_removed = removed
        gaps = result.gaps[:2]
        if not accepted and not gaps and request.mode == 'live' and start < end:
            gaps = ['official dated announcement relevant to the meeting']
        return {'claims': accepted, 'uncertain': uncertain, 'gaps': gaps}

    def route(state):
        if request.mode == 'live' and state['research_round'] < 2 and state['gaps'] and start < end:
            return 'search'
        return 'compose'

    async def compose(state):
        progress('composing')
        synthesis = state['synthesis']
        claims = state['claims'][:4]
        uncertain = state['uncertain'][:max(0, 4-len(claims))]
        # Keep the compact report to at most four findings and six reference sources.
        by_id = {s.id: s for s in state['sources']}
        for collection in (claims, uncertain):
            for claim in collection:
                ids = sorted(claim.source_ids, key=lambda sid: (
                    bool(claim.date_evidence and claim.date_evidence in by_id[sid].content),
                    by_id[sid].temporal_status == 'in_window'), reverse=True)[:1]
                claim.source_ids = ids
                claim.evidence = {sid: claim.evidence[sid] for sid in ids}
        warnings = list(state['warnings'])
        if request.meeting_at > now:
            warnings.append('Research ends at generation time. Future developments before the meeting are not yet available.')
        if metrics.claims_removed:
            warnings.append(f'{metrics.claims_removed} findings removed: missing quotes, mismatched identity, duplicates or unsupported dates.')
        if uncertain:
            warnings.append('Date-unconfirmed candidates are separate from findings with explicit timing evidence. Provider dates may reflect page updates.')
        if request.mode == 'demo':
            warnings.insert(0, 'FICTIONAL DEMO — no web search or language model calls were made. example.com links are placeholders.')
        if state['gaps'] and state['research_round'] >= 2:
            warnings.append('The one permitted follow-up research round is complete. Remaining coverage gaps require discussion.')
        warnings.append('Quotes confirm retrieved wording, not factual truth or independent identity. Questions and implications are suggestions. Event dates can differ from publication dates.')
        questions = synthesis.questions if not metrics.claims_removed and not uncertain else neutral_questions(request)
        # Supported discussion points first; avoid questions based on rejected or date-uncertain events.
        targeted = [c.discussion_question for c in claims if c.discussion_question]
        questions = list(dict.fromkeys(targeted + questions + neutral_questions(request)))[:4]
        metrics.elapsed_seconds = round(time.monotonic()-began, 2)
        open_questions = list(dict.fromkeys(synthesis.open_questions +
                              (['Confirm the event dates for the date-unconfirmed candidates.'] if uncertain else []) +
                              [f'Research gap: {g}' for g in state['gaps']]))[:3]
        report = Briefing(entity=request.entity, entity_type=request.entity_type, meeting_at=request.meeting_at,
                          timezone=request.timezone, purpose=request.purpose, mode=request.mode,
                          generated_at=now, window_start=start, window_end=end,
                          summary=brief_summary(claims, request.purpose),
                          summary_source_ids=[c.source_ids[0] for c in claims[:2]],
                          claims=claims, uncertain_claims=uncertain, questions=questions,
                          meeting_context=request.meeting_context,
                          identity_status='fictional_demo' if request.mode == 'demo' else 'user_confirmed',
                          open_questions=open_questions, sources=state['sources'],
                          warnings=list(dict.fromkeys(warnings)), metrics=metrics)
        return {'result': report.model_dump(mode='json')}

    graph = StateGraph(State)
    for name, fn in [('plan', plan), ('search', search), ('extract', extract),
                     ('synthesize', synthesize), ('verify', verify), ('compose', compose)]:
        graph.add_node(name, fn)
    graph.add_edge(START, 'plan')
    graph.add_edge('plan', 'search')
    graph.add_edge('search', 'extract')
    graph.add_edge('extract', 'synthesize')
    graph.add_edge('synthesize', 'verify')
    graph.add_conditional_edges('verify', route, {'search': 'search', 'compose': 'compose'})
    graph.add_edge('compose', END)
    return (await graph.compile().ainvoke({}, config={'recursion_limit': 16}))['result']
