# Open issues / backlog

## Before send (Phase 0 gate)
- [ ] Send gate: custom domain verified in Resend + `MAIL_FROM` set (until then Login mail only reaches the Resend account owner), then rebuild with `--base-url https://<domain>`, rerun `make_emails.py`, deploy.
- [ ] Preview-environment Resend key is still invalid — previews answer the neutral 200 but every send 401s; add a valid `RESEND_API_KEY` under Settings → Variables and Secrets → Preview.
- [ ] Household Deck titles: the guest-list envelope name exists on only 22 of 233 rows, so most Deck titles are first names joined ("Ashley & Rob"). Fill envelope names or accept.
- [ ] #50 — emails for 6 attending Households with none on file (blocks Login).
- [ ] Login one-time setup: KV namespace id, RESEND_API_KEY secret, custom domain + MAIL_FROM (docs/SEND.md "Login").
- [ ] PHOTOG_URL placeholder in build_wrapped.py — needs the real Pixieset guest URL (or drop the link).
- [ ] Email copy review (data/emails.csv) + decide messaging for 43 no-deck households.
- [ ] 5 name-only labels (no guest_id/email) → resolve in Admin or deliver by phone.
- [ ] Duplicate/empty groups from panel-bug era ("Preethi('s) extended family" ×3) — tidy in /groups.
- [ ] Final: full rebuild → local pass → deploy → regenerate emails.csv against live URL.

## Known rough edges
- Rita Taylor: only 8 usable picks (small pool, not threshold) — accept or hand-curate.
- Couples detector can't distinguish couples from tight sibling pairs — human review step.
- Camera-clock timestamps ~1h off; timeline card footnoted rather than corrected.
- Cloudflare Pages SPA fallback serves the landing (200) for wrong tokens instead of 404 — acceptable.
- `build_guests --only` merges into the manifest but never prunes guests deleted from labels.
- Re-clustering renumbers cluster ids → orphans labels/thresholds/groups/COUPLE constant. Never re-cluster casually; see PIPELINE.md.

## Next build (still static)
- [ ] Select-to-download in group explorers (checkbox selection → client-side zip, like deck favorites).
- [ ] Grade cap refinement: courtesy cap currently explorer-only (deck uses demotion only); consider hard cap in decks.
- [ ] Explorer: event filter pills; download-visible-set.
- [ ] Surface "your favorites" (hearts) count back to the couple via the mailto — consider a scheduled reminder.

## v2 (requires backend — Workers/Functions + D1/Postgres)
- [ ] Server-side hearts/comments (live, visible to the couple; moderation view).
- [ ] "Most loved photos" shared card once hearts are server-side.
- [ ] On-demand zips, arbitrary cross-wedding lookups, real revocation/expiry, analytics.
- [ ] Productization: multi-event tenancy, magic-link auth, onboarding flow, photographer channel (see brainstorm 2026-08-26).
