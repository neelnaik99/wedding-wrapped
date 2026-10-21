# Sending links to guests

## Token scheme

Each guest's deck lives at `https://<project>.pages.dev/<token>/` where the token is a
**10-character random string** from a 32-letter alphabet (base32 minus the ambiguous
`0/1/l/o`), minted with `secrets.choice` in `build_guests.py`. That's 32^10 ≈ 1.1×10^15
possibilities — unguessable and un-enumerable in practice.

**Stability:** tokens are keyed by guest identity (`gid:<guest_id>`, falling back to
`cluster:<cid>`) in `data/tokens.json`, which `build_guests.py` reads before minting anything.
As long as that file survives, rebuilds and redeploys keep every guest's URL identical — links
in already-sent emails never break. Two sharp edges:

- `data/tokens.json` is gitignored (it maps people to their private URLs). **Back it up**
  outside the repo once sending starts; losing it silently mints all-new tokens on the next
  build, orphaning every link you've sent.
- The file is written only at the **end** of a `build_guests.py` run. An interrupted first
  build leaves token folders in `site_guest/` with no record; the next run mints fresh tokens.

## Household Deck — one link per Household

Most guests share an email with the person they came with, and reviewers routinely open on
behalf of a spouse or a parent. So there is **one Link per Household** (docs/adr/0002,
GLOSSARY.md): `https://<project>.pages.dev/h/<token>/`, a single Deck with a member picker that
drives every section. One-person Households get one too — every guest has exactly one Link.
(72 Households today: 27 of one, 38 of two, 4 of three, 3 of four.)

- Membership is the `party` column. `household.hh_key` is the single definition of "same
  household" and `make_emails.py` imports it, so the email's recipient list and the Deck's
  member list cannot drift apart.
- **Light guests** (set in the admin Review view; any guest can be marked light) appear in the
  picker like everyone else but carry only the Cover, the couple's picks and their own gallery.
  A light guest alone in their Household gets the light Deck.
- **The rule (the photo rule):** a photo may appear in a Household's Deck only if it includes at
  least one member of that Household, or contains only the couple. `build_guests.py` enforces it
  while building (`photo_rule.strip_wrapped`) and fails the build on any violation.
- **The deploy check:** `deploy_site.sh` re-runs the rule from what is on disk
  (`python photo_rule.py --check site_guest`: `data/photo_people.parquet` plus
  `data/household_guard.json`, which the build writes), so a failed build that left violators
  behind cannot ship. The same check fails if any `h/*/household.json` contains a per-person
  deck token — `household.json` is publicly fetchable, so another guest's personal link must
  never be in it. A missing input is a failure, never a pass.
- Household tokens live in `data/tokens.json` under `hh:<party>` and are stable across rebuilds
  exactly like guest tokens — same back-up warning applies.
- `/h/` is a **reserved prefix**: personal deck tokens sit at the site root, so Household Decks
  can never collide with them, and a future auth layer can own that one path.
- Decks contain **no email addresses and no guest ids** — first names, photos, counts only.
  `deploy_site.sh` greps every data file and page under `h/` for addresses before every deploy.
- A Household that loses its guests has its page removed on the next build, so a URL already
  sent stops resolving rather than showing a stale page.
- The per-person deck folders still exist as build inputs but are no longer linked from anywhere.

## Login — how a Card becomes a Link

The thank-you Card is identical for every Household and prints only the site's root URL.
The root page **is** Login (`/login` 301s to it): a guest types their email and gets a Login
email with one button — their Household Deck (one link per Household, one-person Households included).
Login does not sign anyone in; it mails the existing Link (docs/adr/0001).

- **The map:** `make_emails.py` writes `functions/_lib/login-map.json` (email → Link + greeting)
  from the same rows as the Send, so Login and the Send can't disagree. It's gitignored PII,
  bundled into the Pages Function at deploy, never served. `deploy_site.sh` refuses to deploy
  without it, or if a copy sits inside `site_guest/`.
- **The function:** `functions/api/login.js` → logic in `functions/_lib/login.js`. Every
  well-formed request gets the same answer at the same speed; the send runs in `waitUntil`.
  One Login email per address per 10 minutes (KV `LOGIN_KV`, keys are SHA-256 of the address).
- **One-time setup (needs `npx wrangler login`):**
  `npx wrangler kv namespace create LOGIN_KV` → paste the id into `wrangler.toml`;
  `npx wrangler pages secret put RESEND_API_KEY --project-name wedding-wrapped`.
  That sets **production** only — add the same key for the **Preview** environment too
  (Cloudflare dashboard → wedding-wrapped → Settings → Variables and Secrets), or a preview deploy
  answers normally but every send fails with a 401 in the function logs.
- **Sender:** `MAIL_FROM` in `wrangler.toml`. Until the custom domain is verified in Resend it is
  `onboarding@resend.dev`, which only delivers to the Resend account owner — fine for testing,
  not for guests. When the domain lands: verify it in Resend, set `MAIL_FROM`, rebuild with
  `--base-url https://<domain>`, rerun `make_emails.py`, deploy.
- **Preview first:** `./deploy_site.sh wedding-wrapped preview`, then try your own address.
- **Send gate:** custom domain + `MAIL_FROM`, and #50 (see docs/OPEN-ISSUES.md)
- **Launch blocker:** #50 — 6 attending Households have no email anywhere.

## make_emails.py — draft, never send

```bash
.venv/bin/python make_emails.py --base-url https://wedding-wrapped.pages.dev \
    [--subject "Your Wedding Wrapped is ready 💛"] [--guests ~/Downloads/guest-list.csv]
```

Joins `data/send_manifest.json` (from a **full** `build_guests.py` run — an `--only` run
truncates it, see docs/DEPLOY.md) with the guest CSV, groups guests into **households** by the
`party` column (solo key per person without a party), and writes — all gitignored:

- `data/emails.csv` / `data/emails.json` — one row per household: `to` (all household emails,
  `;`-separated), greeting (envelope name if present), subject, `html_body` and `text_body`
  with the household's single Deck link.
- `data/no_email_households.csv` — households holding decks but with **no email address**,
  including their phone numbers: the text/WhatsApp list.

**Nothing is sent by this script, ever.** Before sending, replace the `__PHOTOG_URL__`
placeholder in the HTML bodies with the real Pixieset gallery link.

## Sending options

1. **Gmail mail merge** — import `data/emails.csv` into a mail-merge tool (Google Sheets + the
   built-in Gmail mail merge, or YAMM). Columns are already `to` / `subject` / bodies.
   Watch Gmail's ~500 recipients/day limit — batch over days if needed.
2. **Claude Gmail connector** — have Claude draft each email from `emails.json` into Gmail
   drafts for manual review-and-send, or send household-by-household with per-message
   confirmation. Keeps a human on the trigger, which is the point.
3. **Phone-only households** — work through `no_email_households.csv` by text/WhatsApp;
   the `text_body` column is ready to paste.

Send to yourselves (Neel + Preethi rows) first as the live smoke test.

## Token rotation (revoking a link)

If a link leaks or a guest wants a new one:

1. Delete that guest's entry (`"gid:<guest_id>": "<token>"`) from `data/tokens.json`.
2. Remove the old folder: `rm -rf site_guest/<old-token>`.
3. Rebuild + redeploy: `.venv/bin/python build_guests.py --base-url ... --check && ./deploy_site.sh`
   — a fresh token is minted; the old URL now 404s on the new deployment.
4. Re-run `make_emails.py` (or hand-edit) and resend that household's email.

Note step 2 matters: `build_guests.py` never deletes old folders, so skipping it leaves the
leaked URL alive.

## What guests can and can't see

- **No index anywhere.** The site root is a neutral landing page ("check your email for your
  link") with zero outbound links; there is no directory listing, sitemap, or cross-links
  between decks. A guest sees exactly one deck: their own (plus the shared "our picks" couple
  photos baked into it).
- **No search engines.** `robots.txt` disallows everything, `_headers` sets
  `X-Robots-Tag: noindex` on every response, and each page carries `Referrer-Policy:
  no-referrer` so clicking out (e.g. to Pixieset) doesn't leak the token in the Referer header.
- **No PII beyond their own page.** `wrapped.json` contains first names only (co-stars are
  shown only if labeled — never "Guest #123"), no emails, no guest ids —
  `deploy_site.sh` greps for exactly this before every deploy.

**The honest caveat:** links are **bearer tokens**. Anyone who has a guest's URL sees that
guest's page — there is no login, and the emails explicitly say "feel free to share it with
family". That's the intended trade-off (zero-friction for a 70-year-old aunty) — acceptable
because the content is celebratory photos the household already appeared in, not secrets. If a
specific link travels further than intended, rotate it (above).
