# Demo and live acceptance

## Three-minute presentation

1. Problem (20s): preparing for a business conversation means checking scattered, potentially stale pages.
2. Input (20s): company/person, identity hint, meeting time and purpose. Explain the 30-day window.
3. Research (40s): generate a live report. Show actual stages; explain Tavily is the retrieval layer.
4. Evidence (40s): click a citation and compare the excerpt with the original source/date. Separate the factual quote from its suggested meeting implication.
5. Action (20s): choose a useful suggested question and export the compact briefing.
6. Reliability (20s): show what happens with missing evidence, plus test results and limits.
7. Impact (20s): one concise prep artifact with inspectable evidence; future calendar refreshes and identity disambiguation.

If external providers fail, switch explicitly to the fictional demo and say so. Do not present Northstar Labs as real web research.

## Live acceptance checklist — requires locally configured keys

- [ ] Obtain keys and restart the backend. Confirm `/health` reports live_ready (this only checks configuration).
- [ ] Generate a company briefing with a known official domain as identity hint.
- [ ] Generate a person briefing with employer/role as hint.
- [ ] Confirm output concerns the correct entity; manually inspect every factual excerpt.
- [ ] Verify dates fall within the exact window; inspect undated background handling.
- [ ] Add your role, offering and desired outcome; confirm that query focus and discussion points change.
- [ ] Confirm identity hint before live research. Check that lexical matching did not confuse two entities with the same name.
- [ ] Inspect an extracted source versus a snippet fallback; ensure provider date estimates are not labeled as confirmed publication dates.
- [ ] Inspect a coverage gap: no more than one follow-up round, with remaining uncertainty reported.
- [ ] Check original links and context. Note conflicting accounts instead of claiming resolved truth.
- [ ] Inspect an entity with sparse recent coverage: no invented recent facts.
- [ ] Inspect source counts, elapsed time, actual calls and configured cost estimate.
- [ ] Export a live report and inspect the A4 print preview.
- [ ] Capture real screenshots and a short recording without secrets.

## Submission checks

- [ ] Match the official Tavily challenge document and number.
- [ ] Confirm closing timezone with organizer; do not assume Polish midnight.
- [ ] Confirm public repository visibility and final branch.
- [ ] Run README instructions in a clean environment.
- [ ] Export pitch in the organizer's requested format and check every slide.
- [ ] Add demo video/link only if required or actually available.
- [ ] Complete the submission form and retain confirmation.
