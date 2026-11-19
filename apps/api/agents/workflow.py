import asyncio
import time
from datetime import datetime, timezone
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from apps.api.schemas.briefing import Claim, Metrics, ResearchRequest, Source, Synthesis
from apps.api.services.demo import demo_rows, demo_synthesis
from apps.api.services.report import compose_briefing, neutral_questions
from apps.api.services.research_plan import SearchQuery, enrich_sources, rank_sources, search_plan
from apps.api.services.provider_http import ProviderError
from apps.api.services.sources import qualify_sources, research_window
from apps.api.services.verification import assess_claims


class State(TypedDict, total=False):
    queries: list[SearchQuery]
    sources: list[Source]
    warnings: list[str]
    synthesis: Synthesis
    claims: list[Claim]
    uncertain: list[Claim]
    gaps: list[str]
    research_round: int
    result: dict


async def run_workflow(request: ResearchRequest, research, llm, metrics: Metrics, progress):
    began = time.monotonic()
    now = datetime.now(timezone.utc)
    start, end = research_window(request, now)

    async def plan(state):
        await progress('planning')
        return {'queries': search_plan(request), 'sources': [], 'warnings': [], 'research_round': 0}

    async def search(state):
        followup = state['research_round'] > 0
        await progress('closing_gaps' if followup else 'researching')
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
        await progress('extracting')
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
        await progress('synthesizing')
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
        await progress('verifying')
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

    async def compose(state: State):
        await progress('composing')
        metrics.elapsed_seconds = round(time.monotonic() - began, 2)
        report = compose_briefing(
            request,
            generated_at=now,
            window=(start, end),
            synthesis=state['synthesis'],
            accepted=state['claims'],
            uncertain=state['uncertain'],
            sources=state['sources'],
            warnings=state['warnings'],
            gaps=state['gaps'],
            research_rounds=state['research_round'],
            metrics=metrics,
        )
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
