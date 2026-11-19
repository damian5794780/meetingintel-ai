import re
from datetime import timezone


def normalized(text):
    return re.sub(r'\s+', ' ', text).strip().casefold()


def date_is_quoted(date, quote):
    variants = [date.strftime(fmt) for fmt in ('%Y-%m-%d', '%B %d, %Y', '%b %d, %Y', '%d %B %Y', '%d %b %Y')]
    clean = lambda text: re.sub(r'[^a-z0-9]', '', text.casefold())
    # Accept non-zero-padded day variants, but never infer a missing year.
    variants += [v.replace(' 0', ' ') for v in variants]
    return any(clean(v) in clean(quote) for v in variants)


def assess_claims(claims, sources, start=None, end=None):
    """Check provenance and timing; never claim independent factual or semantic truth."""
    by_id = {s.id: s for s in sources}
    accepted, uncertain, removed = [], [], 0
    seen = set()
    for claim in sorted(claims, key=lambda c: c.priority):
        ids = list(dict.fromkeys(claim.source_ids))
        valid = bool(ids)
        for sid in ids:
            source = by_id.get(sid)
            quote = claim.evidence.get(sid, '')
            if (source is None or not source.identity_match or source.temporal_status == 'undated'
                    or len(quote.strip()) < 12 or normalized(quote) not in normalized(source.content)
                    or normalized(claim.text) not in normalized(quote)):
                valid = False
                break
        key = normalized(claim.text)
        if not valid or key in seen:
            removed += 1
            continue
        seen.add(key)
        event = claim.occurred_at
        event_supported = False
        if event is not None:
            if event.tzinfo is None or not claim.date_evidence or not date_is_quoted(event, claim.date_evidence):
                removed += 1
                continue
            if not any(normalized(claim.date_evidence) in normalized(by_id[sid].content) for sid in ids):
                removed += 1
                continue
            event = event.astimezone(timezone.utc)
            if start and end and not start <= event <= end:
                removed += 1
                continue
            event_supported = True
        timed = event_supported or any(by_id[sid].temporal_status == 'in_window' for sid in ids)
        note = ('Event date appears in quoted evidence; interpretation still needs review.' if event_supported else
                'Publication date is explicit; event timing may differ.' if timed else
                'Timing unconfirmed: provider date may be publication or last update.')
        checked = claim.model_copy(update={'source_ids': ids, 'evidence': {sid: claim.evidence[sid] for sid in ids},
                                          'evidence_status': 'excerpt_matched', 'temporal_note': note})
        (accepted if timed else uncertain).append(checked)
    return accepted, uncertain, removed


def verify_claims(claims, sources):
    accepted, uncertain, removed = assess_claims(claims, sources)
    return accepted, removed + len(uncertain)
