from datetime import timedelta

from apps.api.schemas.briefing import Claim, Synthesis

DEMO_ENTITY = 'Northstar Labs'


def demo_rows(start, end):
    day = min(end - timedelta(days=2), start + timedelta(days=10))
    return [
        {'title': 'Fictional demo: Northstar introduces Atlas', 'url': 'https://example.com/northstar/atlas',
         'published_date': day.isoformat(),
         'content': 'Northstar Labs introduced Atlas, a workspace for teams to organize and review AI research. The fictional product is available through a limited pilot program.'},
        {'title': 'Fictional demo: partner program', 'url': 'https://example.com/northstar/partners',
         'published_date': (day + timedelta(days=1)).isoformat(),
         'content': 'Northstar Labs opened applications for its technology partner program. The fictional program focuses on integrations and shared customer pilots.'},
        {'title': 'Fictional demo: company background', 'url': 'https://example.com/northstar/about',
         'content': 'Northstar Labs is a fictional company used to demonstrate MeetingIntel AI. No real-world research has been performed.'},
    ]


def demo_synthesis(sources, request=None):
    claims = []
    for source in sources:
        if source.temporal_status != 'in_window':
            continue
        text = source.content.split('. ')[0] + '.'
        context = request.meeting_context if request else None
        offering = context.offering[:80] if context and context.offering else 'your integration'
        purpose = request.purpose if request else 'partnership'
        implication = (f'Explore whether {offering} could fit a small partner pilot.' if purpose == 'partnership' else
                       'Ask how this initiative affects team priorities and the role.' if purpose == 'recruitment' else
                       'Ask which priorities and constraints this initiative creates for the discussion.')
        question = ('Which technical constraints would a partner pilot need to address?' if 'Atlas' in text else
                    'What are the entry criteria and next steps for a technology partner?')
        claims.append(Claim(text=text, category='product' if 'Atlas' in text else 'organization',
                            relevance=implication, priority=1 if 'Atlas' in text else 2,
                            discussion_question=question if purpose == 'partnership' else '',
                            source_ids=[source.id], evidence={source.id: text}))
    return Synthesis(claims=claims, questions=[
        'What would make an initial collaboration successful?',
        'Which integration use cases are the highest priority?',
        'What technical and commercial constraints should a pilot address?',
        'Who should participate in a follow-up technical discussion?',
    ], open_questions=['This is a fictional demonstration. Validate the live pipeline with real API keys before submission.'])
