from datetime import datetime
from zoneinfo import ZoneInfo


def markdown(report):
    meeting = datetime.fromisoformat(report['meeting_at'].replace('Z', '+00:00')).astimezone(ZoneInfo(report['timezone']))
    lines = [f"# {report['entity']} — meeting briefing", '',
             f"Meeting: {meeting:%Y-%m-%d %H:%M} ({report['timezone']})", 
             f"Research: {report['window_start']} → {report['window_end']}",
             f"Mode: {report['mode'].upper()}", '', '## Executive summary', report['summary'], '', '## Key developments']
    for claim in report['claims']:
        refs = ' '.join(f'[{sid}]' for sid in claim['source_ids'])
        lines.extend([f"- {claim['text']} {refs}", f"  Suggested implication: {claim['relevance']}"])
        if claim.get('temporal_note'):
            lines.append(f"  Timing: {claim['temporal_note']}")
    if not report['claims']:
        lines.append('No qualifying factual excerpts.')
    if report.get('uncertain_claims'):
        lines.extend(['', '## Developments to verify — timing unconfirmed'])
        for claim in report['uncertain_claims']:
            refs = ' '.join(f'[{sid}]' for sid in claim['source_ids'])
            lines.extend([f"- {claim['text']} {refs}", f"  Timing: {claim.get('temporal_note', 'Unconfirmed')}"])
    lines.extend(['', '## Questions to ask', *[f'- {q}' for q in report['questions']], '',
                  '## Open questions', *[f'- {q}' for q in report['open_questions']], '', '## Sources'])
    used = {sid for c in report['claims'] + report.get('uncertain_claims', []) for sid in c['source_ids']}
    for s in report['sources']:
        if s['id'] in used:
            date = s.get('published_at') or s.get('provider_date') or 'date unknown'
            origin = s.get('date_origin', 'legacy date origin unknown')
            lines.append(f"- [{s['id']}] {s['title']} — {date} ({origin}) — {s['url']}")
    lines.extend(['', '## Limitations', *[f'- {w}' for w in report['warnings']]])
    return '\n'.join(lines) + '\n'
