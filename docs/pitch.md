# MeetingIntel AI — six-slide pitch content

This is editable slide content, not a submitted PDF/PPT. Replace placeholders with observed live results before export.

## 1. Arrive informed
MeetingIntel AI turns recent web research into a compact, source-backed meeting briefing.
Target: professionals preparing for business, recruitment and partnership conversations.
Visual: application home screen and a real generated briefing.

## 2. The preparation gap
Company updates are scattered across news, product announcements and organizational pages.
Generic summaries can hide dates, evidence gaps and ambiguous identities.
The user needs context and useful questions with a way to inspect the underlying evidence.
Do not invent numerical time-saving statistics.

## 3. From search to conversation
Enter entity, identity hint, meeting date and purpose.
Get dated factual excerpts, suggested implications, meeting questions and open issues.
Click any citation to inspect the retrieved text and publication link.
Visual: one development card with its evidence drawer.

## 4. Architecture with boundaries
Next.js → FastAPI → LangGraph → Tavily + LLM → evidence gate → briefing.
Tavily supplies current web evidence; LLM selects excerpts and suggests questions.
Pydantic and deterministic checks reject unsupported output.
One-process SQLite prototype, bounded requests and safe error handling.
Visual: architecture diagram from README.

## 5. Working demo and measured reliability
Show a live company report and inspect a citation.
Show Markdown / print export and a no-evidence case.
Include actual test counts from docs/validation.md and observed live elapsed time/calls.
State that excerpt matching is provenance checking, not proof of truth.
Label fictional fixture screenshots if used.

## 6. Impact and next steps
Value: a concise briefing people can inspect before acting.
Next: calendar-triggered refresh, identity confirmation, full-page extraction and evaluation of claim support.
Include public GitHub URL and a real demo link/video if available.
End with a working artifact, not unsupported impact claims.
