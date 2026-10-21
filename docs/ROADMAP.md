# Roadmap (updated 2026-08-27)

North star: Preethi & Neel's wedding is the founding case study for a marketable
guest-experience product (photographer channel first — see the Aug product brainstorm).

## NOW — Ship the proof (≤2 weeks, hard-scoped)
1. **Deck polish sprint** — timeboxed 1 weekend, fixed punch list (motion: numeral count-up,
   staggered reveals, cover parallax; typography rhythm; lightbox/filmstrip transitions;
   share-card glow-up; blur-up loading). No open-ended redesign.
2. **Send gate (user decisions)** — Pixieset URL or drop link · email copy approval ·
   phone-list plan · messaging for 43 no-deck households · final rebuild + deploy.
2b. **Login (built 2026-10-19)** — Card → root Login page → Login email → Hub/Deck. Needs
   domain + Resend key + #50 before guests can use it. See docs/SEND.md "Login".
3. **THE SEND** — 65 emails + 7 texts; collect favorites-emails, replies, screenshots
   (this is the market research).
4. **Measurement lite** — Cloudflare Pages analytics (views per token ≈ open rate).

Explicitly deferred from NOW: the database. Nothing about the send needs it.

## NEXT — Platform spine (Sept, after the send)
5. **Auth = email magic links** (no passwords). Recommend Supabase (Postgres + auth + RLS)
   for solo-builder speed; images stay static on Pages/R2. Existing token URLs remain valid
   bearer capabilities; auth adds identity for writes.
6. **Schema migration** — JSON files → tables 1:1 (people, photos, faces, labels, groups,
   memberships, tokens, thresholds). Parquet stays the ML source of truth.
7. **First dynamic features** — server-side hearts + comments (admin-visible, moderated),
   "most-loved photos"; dynamic group lookups where auth exists, static fallback preserved.
8. **Onboarding guide** — written "run this for your wedding" guide extending docs/
   (interactive wizard deferred to LATER).

Dependency: 5 → 7. 6 ∥ 5.

## LATER — Make it a business (Oct+, gated)
9.  Onboarding wizard (create event → import → cluster → name → thresholds → send).
    GATE: a committed design partner #2 (friend's wedding or photographer pilot).
10. Multi-tenancy + billing (tiered per-event pricing; photographer wholesale). After 9.
11. Compliance package (consent flow, BIPA posture, deletion, ToS) + product naming /
    trademark (retire "Wrapped"). HARD GATE before first paying customer.
12. Video chapters (mix-fingerprint + Whisper plan from the original brainstorm). Independent.

## Risks
- Sequencing: the DB is the fun work; the send is the scary work. Do not swap them.
- Solo capacity → one theme at a time (~1 focused weekend/week).
- Polish scope creep → fixed punch list only.
- No design partner #2 yet → start the ask at the send.
