# Validation record — 14 November 2026

## Executed locally

| Check | Observed result |
|---|---|
| Backend, `python -m pytest -q` | 63 passed |
| Frontend, `npm run test` | 4 passed |
| Production frontend, `npm run build` | Passed, Next.js 16.4.6 |
| TypeScript, `npm run typecheck` | Passed |
| Browser, `npm run test:e2e` | 2 passed in installed Microsoft Edge |
| npm install audit after dependency updates | 0 vulnerabilities reported |
| Docker Compose build and startup | Passed; API and web both healthy |
| Backend tests in Linux container, Python 3.12 | 63 passed |
| Browser tests against running Docker services | 2 passed, including contextual demo generation and two one-page PDF fixtures |
| API, frontend proxy and frontend HTTP checks | All returned 200 |
| Windows `scripts/start-docker.ps1` | Passed; waits for both services to be healthy |

Environment: Windows, Python 3.10.11, Node.js 24.13.0, npm 11.6.2. Two non-failing dependency deprecation warnings occur in Python (Starlette/AnyIO and LangGraph serialization defaults).

The browser test used the real production frontend, FastAPI, SQLite and LangGraph. It generated a fictional briefing, opened evidence, downloaded Markdown, restored the job after reload, checked mobile width and produced exactly one A4 PDF page for that demo. No browser runtime errors were observed. Screenshots are under `docs/screenshots/`; generated demo PDF is under `apps/web/test-results/` (ignored runtime output).

Windows sandbox process cleanup required stopping the two test-owned server processes after the assertions completed; the test command then returned success. CI uses Linux, but remote execution is not yet verified.

## Initial Docker validation follow-up (earlier checkpoint)

Docker Desktop is now installed and its Linux engine is available. Both images built successfully from their locked dependencies. The frontend npm lockfile needed missing platform-related entries repaired in a clean Linux container; `npm ci` then succeeded. Docker Desktop's credential helper directory was added to the invoking process PATH, without changing global settings. The Windows startup script applies this automatically.

Both services passed their health checks. `http://localhost:8000/health`, `http://localhost:3000/backend/health` and `http://localhost:3000` returned 200. Live readiness remains false because keys are not configured.

The same browser scenario ran against the actual Docker stack with `E2E_EXTERNAL=1`: 1 passed in 2.5 seconds. The Linux API test suite returned 36 passed in 1.56 seconds. Besides the two dependency deprecation warnings, pytest reported its optional cache directory was not writable under the non-root container user; test assertions passed. Containers remain running for local review.

## Contextual research implementation — latest checkpoint

The expanded backend returned **63 passed** locally and **63 passed in 2.00 seconds** inside the Python 3.12 Linux container. Container tests use `-p no:cacheprovider` because the image runs as a non-root user. The remaining two warnings are dependency deprecations. Four Vitest component/API tests passed; TypeScript and the production Docker frontend build passed.

The browser suite against the real Docker stack returned **2 passed in 2.9 seconds**. It checks role/offering/outcome input, context-sensitive demo suggestions, source provenance, evidence interaction, reload, Markdown download, mobile overflow and a one-page A4 demo. A second synthetic fixture checks a long mixed-certainty report with four findings, long references/questions and a separate uncertain section; it also prints on exactly one A4 page. That fixture checks layout, not research truth. Earlier failures exposed reference/spacing overflow and a blank second page; compact linked-domain references, omission of uncertain implications in print, and 8mm A4 margins resolved them.

New backend cases cover typed general/news query planning, date-estimate separation, explicit publication labels, old-event rejection, wrong-entity screening, partial/out-of-order extraction, private-address URL rejection, native provider schema requests, model refusal, missing usage, the single gap-round limit, uncertain findings excluded from the summary, additive database compatibility and persisted source/stage records. No paid APIs were used. Automated tests do not replace live quality review.

Both final containers are healthy and remain available at http://localhost:3000. Full-page screenshots were refreshed from the contextual fictional demo. The existing Docker volume was preserved throughout rebuilds.

## Not yet verified

- Live Tavily and LLM calls: keys unavailable. HTTP-mocked provider tests and injected company/person workflow tests are not substitutes for live validation.
- Actual model output quality, identity accuracy, publication-date coverage, real latency and paid usage.
- One-page layout for maximum-length live results. Demo PDF page count is checked, not all possible reports.
- GitHub Actions execution: configuration exists, not remotely executed. Local Linux image builds and container tests have passed.
- Official Tavily challenge numbering, submission timezone and required deliverable formats.
- Pitch PDF/PPT, final live recording and hackathon submission.

Use `docs/demo.md` as the remaining acceptance checklist. Do not present fictional fixtures or mocked-provider results as live research benchmarks.
