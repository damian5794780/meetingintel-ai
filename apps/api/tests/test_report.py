from datetime import datetime, timedelta, timezone

from apps.api.schemas.briefing import Claim, Metrics, ResearchRequest, Source, Synthesis
from apps.api.services.report import compose_briefing


def test_compose_briefing_uses_verified_citations_without_mutating_findings():
    now = datetime(2026, 11, 19, tzinfo=timezone.utc)
    request = ResearchRequest(entity='Example Corp', meeting_at=now, mode='live')
    claim_text = 'Example Corp expanded its partner programme.'
    date_evidence = 'Published on 16 November 2026'
    candidate_text = 'Example Corp announced plans for a new office.'
    sources = [
        Source(id='S1', title='Partner update', url='https://example.org/1', content=claim_text,
               temporal_status='in_window'),
        Source(id='S2', title='Dated partner update', url='https://example.org/2',
               content=f'{date_evidence}. {claim_text}', temporal_status='in_window'),
        Source(id='S3', title='Office plans', url='https://example.org/3', content=candidate_text,
               temporal_status='estimated'),
    ]
    accepted = Claim(text=claim_text, relevance='Discuss the partner programme.',
                     source_ids=['S1', 'S2'], evidence={'S1': claim_text, 'S2': claim_text},
                     date_evidence=date_evidence, discussion_question='How can we join the programme?')
    uncertain = Claim(text=candidate_text, relevance='Check the schedule.',
                      source_ids=['S3'], evidence={'S3': candidate_text},
                      discussion_question='When will the new office open?')
    synthesis = Synthesis(questions=['When will the new office open?', 'Who is leading it?', 'What is its capacity?'])

    report = compose_briefing(
        request,
        generated_at=now,
        window=(now - timedelta(days=30), now),
        synthesis=synthesis,
        accepted=[accepted],
        uncertain=[uncertain],
        sources=sources,
        warnings=[],
        gaps=['office opening date'],
        research_rounds=2,
        metrics=Metrics(),
    )

    assert report.summary_source_ids == ['S2']
    assert '[S2]' in report.summary and candidate_text not in report.summary
    assert report.claims[0].evidence == {'S2': claim_text}
    assert report.uncertain_claims[0].source_ids == ['S3']
    assert report.questions[0] == 'How can we join the programme?'
    assert 'When will the new office open?' not in report.questions
    assert 'Research gap: office opening date' in report.open_questions
    assert accepted.source_ids == ['S1', 'S2']
    assert set(accepted.evidence) == {'S1', 'S2'}
