# Demo and live acceptance

## Try the demo

1. Start the application using the [quick start](../README.md#quick-start-no-api-keys-required).
2. Open **Try a demo**, choose a meeting purpose, and select **Create demo briefing**.
3. Open a citation to inspect its excerpt and date evidence. Northstar Labs is fictional, and the source links are placeholders.
4. Export the result as Markdown or select **Save as PDF** to open the browser's print dialog.

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
