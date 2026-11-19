# Architecture — contextual research prototype

## Boundaries

Next.js renders meeting context, progress, findings and the evidence panel. A same-origin proxy forwards `/backend/*` to FastAPI. Provider keys remain on the backend. Pydantic validates requests and model output. LangGraph controls the bounded workflow; HTTPX adapters own Tavily and LLM transport details.

FastAPI persists jobs in SQLite, requires per-job bearer tokens for read/export/SSE, and runs at most three active jobs in one process. Startup marks interrupted jobs failed. Existing job JSON is retained; schema-v2 reports use new optional fields. The UI labels unrecorded legacy date provenance rather than inventing it.

## Workflow

1. **Context and identity:** accept company/person, meeting instant/timezone, purpose, role, offering and desired outcome. Live mode requires a user-confirmed website or organization/role hint. Lexical screening excludes obvious mismatches; it does not resolve every ambiguous entity.
2. **Plan and search:** three typed queries cover official/general sources, external news and meeting-specific relevance. Only the official branch is domain-restricted. Canonicalize URLs, deduplicate and retain up to twelve sources.
3. **Extract:** read up to five selected public pages per round through Tavily. Reconcile partial successes by URL. Preserve original snippets, extracted content, SHA-256 digests, source origin and retrieval time. No direct arbitrary URL scraping occurs on our server.
4. **Synthesize:** native strict JSON Schema by default; explicit JSON-object compatibility mode is available. Evidence uses fixed-shape arrays. Validate again with Pydantic; handle refusal, truncation and one repair attempt. Model output includes priority, suggested relevance, finding-linked questions and up to two research gaps.
5. **Verify:** match exact evidence and factual excerpt wording, existing IDs and identity screening. Distinguish explicit timing from estimated provider dates. Reject unquoted or out-of-window event dates. Deduplicate repeated factual excerpts.
6. **Conditional follow-up:** if material gaps remain, run at most one additional round with up to two queries. A failed follow-up retains existing evidence and communicates the remaining gap. No unbounded agent loop or executable source instructions.
7. **Compose:** up to four findings total, split between explicit-timing evidence and date-unconfirmed candidates. The executive summary quotes at most two accepted findings with citations; uncertain or rejected output is excluded. Use supported finding-linked questions first and neutral questions when rejected/uncertain output could have influenced suggestions.

## Time and provenance

Window: `[meeting − 30 days, min(meeting, generation)]`. Input meeting instants require an offset and a valid IANA display timezone. Day-only publication dates must fit wholly within the UTC window.

Tavily dates are provider estimates that may reflect publication or update. They are stored separately as `provider_date`. A limited parser recognizes explicitly labeled page publication dates and records their literal evidence. Missing or unrecognized dates remain unknown; old explicit dates override recent estimates by excluding the page. An explicitly quoted event date is checked separately. These are checks of retrieved text, not proof of a publisher's accuracy or of semantic interpretation.

`content_origin` distinguishes fixture, search snippet and extracted page. `date_origin` distinguishes fixture, provider estimate, explicit page date and unknown. Evidence snapshots and job-stage timestamps are persisted through additive SQLite tables; per-job token hashes stay in the jobs table.

## Budgets and failure policy

- One worker process; maximum active jobs defaults to 3.
- HTTP connection timeout 8s, request timeout 25s, overall job deadline 120s.
- Three initial + up to two follow-up Search plans; at most two Extract batches.
- Hard HTTP-attempt caps: 10 Search, 4 Extract and 8 LLM calls per job, including retries/repairs.
- At most two LLM synthesis stages; max 2,600 output tokens per attempt. Final summary composition needs no LLM call.
- Further model requests stop once returned cumulative usage reaches 60,000 tokens. This is an observed-usage guard, not a prepaid cap; a final in-flight request can cross it.
- Authentication failures stop immediately. Rate limits, network failures and server errors retry once. Initial research/model failure is terminal; extraction can fall back to labeled snippets; follow-up failure retains earlier evidence.
- Provider bodies, headers and keys do not appear in user errors or logs. Logs identify only job ID and exception type. Stage persistence contains stage names/timestamps, not private prompt contents.

## Verification limits

Verbatim evidence is intentional: no paraphrase is labeled mechanically verified. The system does not independently establish identity, truth, source independence or contradictions. A recent publication can describe an older event whose date is not stated; this still requires review. Automated candidate identity resolution and a separate semantic verifier remain future work. Native schema support must be checked with the exact chosen live model.

## Interface and packaging

The UI uses reconnectable polling; authenticated SSE is also available. Source panels expose text origin and date evidence. Markdown includes uncertainty and references. Browser print CSS targets one A4 page: compact references keep clickable URLs, and uncertain candidates' suggested implications stay in the full app rather than the printout. Test demo and long mixed-certainty fixtures, then inspect live results in print preview.

Compose runs both services as non-root users and binds local ports. SQLite is a local prototype boundary. Public/multi-process use needs authenticated accounts, per-user limits, retention, a durable queue and a suitable database. See technology-decisions.md for the rationale and alternatives; validation.md records executed checks.
