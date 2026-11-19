import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field

from apps.api.services.tavily_service import canonical_url, parse_publication


class SearchQuery(BaseModel):
    query: str = Field(max_length=600)
    topic: Literal['general', 'news']
    domains: list[str] = Field(default_factory=list)
    purpose: str


def identity_domain(hint):
    candidate = hint.strip()
    if ' ' in candidate or not candidate:
        return None
    url = canonical_url(candidate if '://' in candidate else f'https://{candidate}')
    return urlsplit(url).hostname if url else None


def search_plan(request, gaps=None):
    entity = request.entity.replace('"', '')
    context = request.meeting_context
    focus = {'partnership': 'integrations technology partners ecosystem',
             'recruitment': 'team hiring leadership engineering',
             'business': 'strategy customers product expansion',
             'general': 'announcements leadership products'}[request.purpose]
    identity = f'"{entity}" {request.identity_hint}'
    tailored = f'{context.offering} {context.desired_outcome} {request.context}'[:220]
    if gaps:
        return [SearchQuery(query=f'{identity} {gap} {focus}'[:600], topic='general', purpose='close evidence gap')
                for gap in gaps[:2]]
    domain = identity_domain(request.identity_hint)
    return [SearchQuery(query=f'{identity} announcements newsroom product launches'[:600], topic='general',
                        domains=[domain] if domain else [], purpose='official developments'),
            SearchQuery(query=f'{identity} recent news leadership launches hiring'[:600], topic='news', purpose='external coverage'),
            SearchQuery(query=f'{identity} {focus} {tailored}'[:600], topic='general', purpose='meeting relevance')]


def entity_matches(request, source):
    text = re.sub(r'\s+', ' ', f'{source.title} {source.content}').casefold()
    name = re.sub(r'\s+', ' ', request.entity).casefold()
    # Conservative lexical screen, not independent identity proof.
    if name not in text:
        return False
    domain = identity_domain(request.identity_hint)
    host = urlsplit(source.url).hostname or ''
    if request.entity_type == 'company' or not request.identity_hint:
        return True
    if domain:
        return host == domain or host.endswith('.' + domain) or domain in text
    words = [w.casefold() for w in re.findall(r'\w+', request.identity_hint) if len(w) > 2]
    return bool(words) and any(w in text for w in words)


def explicit_publication(content):
    """Only accept labeled page dates. Provider dates and naked dates are not publication proof."""
    pattern = r'(?im)^\s*(?:\*\*)?(?:published(?:\s+on)?|publication date|date published)\s*:?\s*(?:\*\*)?\s*(.+?)\s*$'
    for match in re.finditer(pattern, content):
        value = match.group(1).strip().strip('*')
        date, precision = parse_publication(value)
        if date is None:
            for fmt in ('%B %d, %Y', '%b %d, %Y', '%d %B %Y', '%d %b %Y'):
                try:
                    date = datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
                    precision = 'day'
                    break
                except ValueError:
                    pass
        if date is not None:
            return date, precision, match.group(0).strip()
    return None, 'unknown', ''


def in_window(date, precision, start, end):
    return start <= date and (date + timedelta(days=1) <= end if precision == 'day' else date <= end)


def enrich_sources(request, sources, extracted, start, end):
    kept, warnings = [], []
    for source in sources:
        content = extracted.get(source.url)
        if content:
            source = source.model_copy(update={'content': content, 'content_origin': 'extracted_page',
                                      'content_hash': hashlib.sha256(content.encode()).hexdigest(),
                                      'retrieved_at': datetime.now(timezone.utc)})
            date, precision, quote = explicit_publication(content)
            if date:
                if not in_window(date, precision, start, end):
                    warnings.append('A selected page was excluded after its explicit publication date fell outside the window.')
                    continue
                source = source.model_copy(update={'published_at': date, 'date_origin': 'explicit_page',
                                                   'date_precision': precision, 'date_evidence': quote,
                                                   'temporal_status': 'in_window'})
        source.identity_match = entity_matches(request, source)
        kept.append(source)
    return kept, warnings


def rank_sources(request, sources):
    focus = set(re.findall(r'\w{4,}', f'{request.meeting_context.offering} {request.meeting_context.desired_outcome} {request.context}'.casefold()))
    domain = identity_domain(request.identity_hint)

    def score(source):
        host = urlsplit(source.url).hostname or ''
        official = domain and (host == domain or host.endswith('.' + domain))
        text = (source.title + ' ' + source.content).casefold()
        return (source.identity_match, source.temporal_status == 'in_window', bool(official), sum(w in text for w in focus))

    return sorted(sources, key=score, reverse=True)
