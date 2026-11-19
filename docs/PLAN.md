# MeetingIntel AI — implementation plan

Status legend: TODO / IN PROGRESS / DONE. A stage is complete only when its acceptance checks pass.

Official target is **Tavily Problem Statement 05 — Build a Pre-Meeting Briefing Agent**. The initial numbering in the supplied project brief was incorrect. [Official PDF](https://hackcultureplatform.blob.core.windows.net/event-assets/hackathons/6ac5c8240037f69fb28e23ec/problem_explanation_a1nx56ua55u.pdf).

The next development direction is specified in [technology-decisions.md](technology-decisions.md). Context contracts, user identity confirmation, date provenance, selected-page Tavily Extract, strict structured output and one bounded gap-research round have now been implemented and tested with controlled providers. Live provider acceptance and human assessment of briefing usefulness remain pending keys.

## 1. Foundations — DONE
- Monorepo: Next.js frontend and independent FastAPI backend.
- Typed request, source, claim, report and job contracts.
- Environment configuration; secrets excluded; local SQLite persistence.
- Acceptance: API starts, /health responds, input validation rejects invalid dates and fields.

## 2. Research — IMPLEMENTED; LIVE ACCEPTANCE PENDING KEYS
- Build three purpose-aware general/news queries; live mode requires a confirmed identity hint. Add at most two follow-up queries in one gap round.
- Tavily HTTP adapter with bounded results, timeout and one transient retry.
- Exact research window, capped at generation time; date provenance and URL deduplication.
- Keep undated background separate; exclude old/future articles.
- Fictional, explicitly labeled demo fixtures without paid APIs.
- Acceptance: fixture and HTTP-mocked tests cover empty results, duplicates, boundaries, missing dates and provider errors.

## 3. Synthesis and evidence — IMPLEMENTED; LIVE ACCEPTANCE PENDING KEYS
- LangGraph plan → research → synthesize → verify workflow.
- One configurable OpenAI-compatible LLM; schema validation and one JSON repair attempt.
- Claims require source IDs and exact evidence quotations; no model-generated URLs.
- Native JSON Schema output with explicit JSON-object compatibility mode; priority and finding-linked discussion questions.
- Estimated-date candidates remain separate from explicit-timing findings and the extractive cited summary.
- Exclude unsupported claims; label evidence matching as distinct from factual truth.
- Length limits, useful questions, unknowns and honest usage metrics.
- Acceptance: dangling citations and fabricated quotes cannot appear as supported facts.

## 4. Interface and exports — DONE FOR DEMO
- Responsive English interface: form, actual workflow status, briefing and source panel.
- Explicit choice of fictional demo or live research; disable live until keys configured.
- SQLite-backed status polling and SSE endpoint; reload-safe task access.
- Copy and Markdown export; compact print stylesheet for browser Save as PDF.
- Acceptance: frontend production build and component tests; complete API-driven demo.

## 5. Reliability and packaging — LOCAL AND DOCKER CHECKS DONE; REMOTE CI PENDING
- Integration tests with injected providers; no paid calls in CI.
- Task access tokens, bounded active jobs, overall deadline and restart recovery.
- Docker Compose and GitHub Actions; tested local setup instructions.
- Acceptance: backend tests, frontend tests, typecheck and production build pass.

## 6. Submission preparation — DOCUMENTATION READY; LIVE DEMO AND FINAL SUBMISSION PENDING
- README, architecture, demo script and six-slide pitch content.
- Record observed validation results and known limits; do not invent impact metrics.
- Before submission: acquire keys, run live company + person research, inspect citations manually.
- Confirm Tavily challenge document, actual deadline/timezone and required slide/video formats.
- Human deliverables: screenshots, demo recording, final PDF/PPT and submission form.
- Acceptance: fresh-checkout launch, live smoke tests and required submission assets verified.

## Scope and decisions
- Local-first prototype, one API process; SQLite is not a distributed task queue.
- No login, calendar integrations, agent teams or automated contradiction claims in MVP.
- No secrets required for clearly labeled fictional demo. Live failures never silently switch to demo.
- Export is a short briefing with linked references; full source excerpts stay in the evidence panel.
- Local dev proxy keeps API access tokens out of URLs; SSE uses Authorization via fetch.

## Implementation checkpoint — 14 November 2026

- 36 backend tests passed on Python 3.10.11.
- 3 frontend tests passed; production build and TypeScript check passed on Node 24.13.0.
- Browser integration test passed in installed Microsoft Edge against the actual API and production Next.js server.
- Browser test covers report generation, evidence panel, Markdown download, reload, mobile overflow and exactly one A4 page for the fictional demo PDF.
- Desktop/mobile screenshots captured in docs/screenshots; editable six-slide pitch content in docs/pitch.md.
- npm installation audit reported zero vulnerabilities after Next.js/Vitest upgrades.
- No keys were supplied, so no paid live research was run. Workflow file has not run on GitHub.
- Docker Desktop Linux build and Compose startup now passed; both API and web are healthy.
- 36 backend tests passed inside the Python 3.12 Linux container; the browser scenario also passed against the Docker stack.
- Fixed missing platform entries in npm lockfile, added frontend health check, external-stack browser testing and a verified Windows Docker startup script.

## Contextual research implementation checkpoint

- Role, offering and desired outcome guide query planning and model synthesis; live identity hints require user confirmation.
- Search uses official/general and news branches; Extract preserves source origin, exact snapshot digests, snippet fallback and explicit date evidence.
- LangGraph permits at most one extra research round, with partial-failure handling and bounded HTTP calls.
- Structured outputs include finding priority, evidence arrays, discussion questions and coverage gaps. The report composes a cited extractive summary only after verification.
- Additive SQLite tables retain evidence and stage timestamps; existing job records remain readable.
- 63 backend tests and 4 component tests now cover the expanded implementation. Final Docker/browser outcomes are maintained in validation.md.
- Remaining: real provider access and model/schema compatibility, human evaluation, automatic identity candidate resolution, semantic support grading and remote CI. No automated truth or source-independence guarantee is claimed.
