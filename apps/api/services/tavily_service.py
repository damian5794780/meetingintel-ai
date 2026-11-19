import asyncio
import hashlib
import ipaddress
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from apps.api.schemas.briefing import ResearchRequest, Source


class ProviderError(Exception):
    """Safe user-facing error: never include response bodies or credentials."""


async def post_json(client, url, **kwargs):
    for attempt in range(2):
        try:
            response = await client.post(url, **kwargs)
            if response.status_code in (401, 403):
                raise ProviderError('Provider rejected the API key. Check backend configuration.')
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == 0:
                    await asyncio.sleep(0.4)
                    continue
                raise ProviderError('Provider is busy or quota is exhausted. Please try again later.')
            if not response.is_success:
                raise ProviderError('Provider rejected the request. Check the model and endpoint configuration.')
            return response.json()
        except (httpx.TimeoutException, httpx.NetworkError):
            if attempt == 1:
                raise ProviderError('Provider connection timed out or is unavailable.') from None
        except ValueError:
            raise ProviderError('Provider returned an unreadable response.') from None
    raise ProviderError('Provider unavailable.')


def research_window(request: ResearchRequest, now: datetime):
    meeting = request.meeting_at.astimezone(timezone.utc)
    return meeting - timedelta(days=30), min(meeting, now)


def canonical_url(value: str):
    try:
        parts = urlsplit(value)
        if parts.scheme not in ('https', 'http') or not parts.hostname or parts.username or parts.password:
            return None
        host = parts.hostname.lower().rstrip('.')
        if '.' not in host or host.endswith(('.local', '.localhost', '.internal')) or host == 'localhost':
            return None
        try:
            if not ipaddress.ip_address(host).is_global:
                return None
        except ValueError:
            pass
        query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query)
                                 if not k.lower().startswith('utm_') and k.lower() not in ('fbclid', 'gclid')))
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip('/'), query, ''))
    except ValueError:
        return None


def parse_publication(value):
    if not isinstance(value, str) or not value.strip():
        return None, 'unknown'
    value = value.strip()
    try:
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            return datetime.fromisoformat(value).replace(tzinfo=timezone.utc), 'day'
        try:
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            return None, 'unknown'
        return dt.astimezone(timezone.utc), 'instant'
    except (ValueError, TypeError, OverflowError):
        return None, 'unknown'


def qualify_sources(rows, start, end, *, fixture=False):
    candidates = {}
    excluded = 0
    for row in rows:
        url = canonical_url(str(row.get('url', '')))
        content = str(row.get('content') or '').strip()[:6000]
        if not url or not content:
            excluded += 1
            continue
        date, precision = parse_publication(row.get('published_date'))
        # A day-only date must fall wholly within the window; do not invent a publication time.
        outside = date and ((precision == 'instant' and not start <= date <= end) or
                            (precision == 'day' and (date < start or date + timedelta(days=1) > end)))
        if outside:
            excluded += 1
            continue
        source = Source(id='', title=str(row.get('title') or 'Untitled source')[:250], url=url,
                        content=content, published_at=date if fixture else None, provider_date=date,
                        retrieved_at=datetime.now(timezone.utc), date_precision=precision,
                        content_hash=hashlib.sha256(content.encode()).hexdigest(),
                        search_content=content, search_hash=hashlib.sha256(content.encode()).hexdigest(),
                        content_origin='fixture' if fixture else 'search_snippet',
                        date_origin=('fixture' if fixture else 'provider_estimate') if date else 'unknown',
                        temporal_status=('in_window' if fixture else 'estimated') if date else 'undated')
        prior = candidates.get(url)
        if prior is None or (prior.provider_date is None and date is not None):
            candidates[url] = source
    selected = sorted(candidates.values(), key=lambda s: s.provider_date or datetime.min.replace(tzinfo=timezone.utc), reverse=True)[:12]
    for i, source in enumerate(selected, 1):
        source.id = f'S{i}'
    warnings = []
    if excluded:
        warnings.append(f'{excluded} results excluded: outside the exact date window or missing usable content/URL.')
    undated = sum(s.temporal_status == 'undated' for s in selected)
    if undated:
        warnings.append(f'Search returned {undated} undated sources. They remain background unless extraction establishes explicit timing evidence.')
    if not any(s.temporal_status in ('in_window', 'estimated') for s in selected):
        warnings.append('Search returned no usable date estimates. Selected pages will be checked for explicit publication dates.')
    return selected, warnings


def build_queries(request):
    # No user-supplied instructions are executed; all values are search text.
    name = f'"{request.entity.replace(chr(34), "")}" {request.identity_hint}'.strip()
    return [f'{name} latest announcements news', f'{name} product launch leadership hiring',
            f'{name} {request.purpose} developments']


class TavilyService:
    def __init__(self, settings, client, metrics):
        self.settings, self.client, self.metrics = settings, client, metrics

    async def search(self, queries, start, end):
        async def one(query):
            async def counted_post(*args, **kwargs):
                if self.metrics.search_calls >= 10:
                    raise ProviderError('Search request budget exhausted.')
                self.metrics.search_calls += 1
                return await self.client.post(*args, **kwargs)

            class CountedClient:
                post = staticmethod(counted_post)

            plan = query.model_dump() if hasattr(query, 'model_dump') else {'query': query, 'topic': 'news', 'domains': []}
            data = await post_json(CountedClient(), 'https://api.tavily.com/search',
                                   headers={'Authorization': f'Bearer {self.settings.tavily_key}'},
                                   json={'query': plan['query'], 'topic': plan['topic'], 'search_depth': 'advanced',
                                         'max_results': 5, 'start_date': start.date().isoformat(),
                                         'end_date': end.date().isoformat(), 'include_answer': False,
                                         'include_published_date': True, 'include_usage': True,
                                         'include_domains': plan['domains']})
            self.record_usage(data)
            rows = data.get('results')
            if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
                raise ProviderError('Search provider returned an invalid result list.')
            return rows

        results = await asyncio.gather(*(one(q) for q in queries))
        return [row for group in results for row in group]

    def record_usage(self, data):
        usage = data.get('usage') or {}
        credits = usage.get('credits')
        if isinstance(credits, (int, float)) and credits >= 0:
            self.metrics.tavily_credits += credits
        else:
            self.metrics.tavily_usage_complete = False

    async def extract(self, sources):
        urls = [s.url for s in sources if canonical_url(s.url)][:5]
        if not urls:
            return {}, []

        async def counted_post(*args, **kwargs):
            if self.metrics.extract_calls >= 4:
                raise ProviderError('Extraction request budget exhausted.')
            self.metrics.extract_calls += 1
            return await self.client.post(*args, **kwargs)

        class CountedClient:
            post = staticmethod(counted_post)

        data = await post_json(CountedClient(), 'https://api.tavily.com/extract',
                               headers={'Authorization': f'Bearer {self.settings.tavily_key}'},
                               json={'urls': urls, 'extract_depth': 'basic', 'format': 'markdown',
                                     'include_usage': True, 'timeout': 15})
        self.record_usage(data)
        results, failures = data.get('results'), data.get('failed_results', [])
        if not isinstance(results, list) or not isinstance(failures, list):
            raise ProviderError('Extraction provider returned invalid results.')
        allowed = set(urls)
        extracted = {}
        for row in results:
            if not isinstance(row, dict):
                continue
            url = canonical_url(str(row.get('url', '')))
            content = row.get('raw_content')
            if url in allowed and isinstance(content, str) and content.strip():
                extracted[url] = content.strip()[:12000]
        missing = len(allowed - set(extracted))
        warnings = [f'{missing} selected pages could not be extracted; their search snippets are labeled as fallback evidence.'] if missing else []
        return extracted, warnings
