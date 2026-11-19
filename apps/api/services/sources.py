import hashlib
import ipaddress
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from apps.api.schemas.briefing import ResearchRequest, Source


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
