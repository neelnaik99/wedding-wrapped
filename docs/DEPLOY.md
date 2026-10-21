# Deploy

Target: **Cloudflare Pages**, project `wedding-wrapped`, site root `site_guest/`.
Live at `https://photos.preethiandneel.com` (custom domain on the Pages project; `https://wedding-wrapped.pages.dev` still works). Build with `--base-url https://photos.preethiandneel.com`.

## The normal path

```bash
cd ~/Downloads/wedding-wrapped

# 1. Build every guest deck + guardrails
.venv/bin/python build_guests.py --base-url https://wedding-wrapped.pages.dev --check

# 2. Deploy (re-runs its own sanity checks first)
./deploy_site.sh                     # optional arg = project name, default wedding-wrapped
```

One-time setup: `npx wrangler login` (browser OAuth; wrangler comes via npx, no global install).

### What `--check` verifies (build_guests.py)

- total file count < 20,000 and no single file > 20 MB;
- every image referenced by every `wrapped.json` (hero, picks, gallery shots, co-star faces)
  actually exists in `site_guest/` — asserts, so a broken build fails loudly.

It also prints **THIN DECKS** (guests with <10 picks) — fix those via the `/highlights`
threshold page before shipping.

### What `deploy_site.sh` verifies

- `site_guest/index.html` exists **and is the neutral landing page** (guards against the admin
  bundle ending up at the root);
- no deck still has `"draft": true`;
- no `wrapped.json` / `pool.json` contains `guest_id` / `@gmail` / `@yahoo` (PII leak check);
- < 20k files, none over 20 MB — then `npx wrangler pages deploy site_guest --project-name
  wedding-wrapped --commit-dirty=true`.

## Limits vs current numbers

| Limit (Cloudflare Pages) | Current |
|---|---|
| 20,000 files per deployment | ~8,400 files (130 decks + full photo pools, issue #39) |
| 25 MiB per file (scripts check at 20 MB) | largest files are ~1400px JPEGs, well under |
| total size — no hard limit, upload time only | ~1.2 GB, ~10 min initial; incrementals stay quick |

## Telemetry + staging (issue #39)

There is still **no server-side compute on Pages** — telemetry is a client→Supabase POST,
nothing runs on Cloudflare. The endpoint config lives in `data/telemetry.json`
(`{"url": "https://<ref>.supabase.co", "anon_key": "…"}`, read-if-exists); absent, the beacon
is a no-op and decks work exactly as before. The anon key is public-by-design; the service key
(for analysis reads) never leaves your machine. Schema is in `supabase/migrations/0001_events.sql`
— apply with `npx supabase link --project-ref <ref> && npx supabase db push`.

Staging: build with the env stamp, deploy to a branch alias, verify, then ship prod —

```bash
.venv/bin/python build_guests.py --base-url https://stage.wedding-wrapped.pages.dev --env stage --check
npx wrangler pages deploy site_guest --project-name wedding-wrapped --branch stage --commit-dirty=true
# click through one stage deck (open #/all, toggle a few, download), then verify rows landed:
#   select action, surface, env, count(*) from events group by 1,2,3;   (env='stage' only)
```

One Supabase project serves both — isolation is the `env` column, and analysis filters
`env='prod'`. Rebuild with `--env prod` (the default) before the production deploy.

Headroom: file count scales at roughly 2 files per guest (index.html + wrapped.json) plus
shared images in `site_guest/img/` — the image pool is shared across decks (each photo emitted
once per size), so even 233 guests stays far below 20k files.

## Rollback

Every deploy is immutable on Cloudflare:

```bash
npx wrangler pages deployment list --project-name wedding-wrapped
npx wrangler pages deployment rollback <deployment-id> --project-name wedding-wrapped
```

(or use the Pages dashboard → Deployments → Rollback). Since `site_guest/` is fully
regenerable, rolling forward — fix, rebuild, redeploy — is usually just as fast.

## Rebuilding ONE guest

```bash
.venv/bin/python build_guests.py --base-url https://wedding-wrapped.pages.dev --only <CID>
./deploy_site.sh
```

`--only CID` rebuilds just that cluster's deck in place (token is reused from
`data/tokens.json`, so the URL doesn't change), and the deploy uploads only changed files —
Pages diffs against the previous deployment, so an incremental deploy is quick.

**Two caveats with `--only`:**

1. `data/send_manifest.json` is rewritten with **only the guests built in that run** — after an
   `--only` run the manifest holds a single entry. Run a full `build_guests.py` (fast: images
   are cached, only wrapped.json + bundle copies are rewritten) before `make_emails.py`.
2. It doesn't remove anything: if a guest was deleted/re-labeled, their old token folder stays
   in `site_guest/` until you prune it manually or rebuild from an empty `site_guest/`.

Also note tokens are written to `data/tokens.json` only at the **end** of a run — don't kill a
first-ever build halfway or the minted tokens are lost (see docs/SEND.md on rotation).

## If Pages ever doesn't fit: R2 fallback (sketch)

Not needed at current scale, but if the site outgrew Pages limits (e.g. full-res images):

1. Create an R2 bucket, put the images there
   (`npx wrangler r2 object put ...` or `rclone` for bulk), keep only HTML + JSON on Pages.
2. Serve the bucket via a custom domain or an R2 public bucket URL; point the `img/` paths in
   `build_wrapped.emit()` at that base URL instead of `../img/`.
3. Keep `_headers` semantics by setting `X-Robots-Tag: noindex` on the bucket's custom-domain
   responses (a tiny Worker or Transform Rule).

The deck bundle is a static file reading a relative `wrapped.json`, so nothing else changes.

## Where everything lives (hosting map, 2026-08)

| What | Where | Cost |
|---|---|---|
| Guest site (decks, group explorers, images) | Cloudflare Pages, project `wedding-wrapped` → https://wedding-wrapped.pages.dev — free tier, unlimited bandwidth, zero egress fees | $0/mo |
| Deploy management / rollbacks | Cloudflare dashboard → Workers & Pages → wedding-wrapped (`npx wrangler pages deployment list`) | — |
| Code + docs | GitHub (private): github.com/neelnaik99/wedding-recap | $0 |
| Admin stack (label server :8792, /explore, /groups, /highlights) + photos/cache + ML data (parquet/JSON) | Local Mac only — never deployed; PII never leaves the machine | $0 |
| Hi-res originals | Pixieset (photographer's hosting) — intentionally not re-hosted | — |

There is **no server-side compute in production** — the guest site is pure static files
behind Cloudflare's CDN, which is why hosting is $0 and why the first backend
(Supabase auth + server-side hearts, see ROADMAP.md "Next") will be the first moving part.
Deploys are content-addressed direct uploads via `./deploy_site.sh` (initial ~5 min,
incremental redeploys seconds-to-a-minute).
