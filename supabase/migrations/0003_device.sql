-- Coarse device class per event (user request, 2026-08-30). Client-derived
-- (touch + viewport width), deliberately just an enum — no UA strings, no
-- fingerprinting. CF headers are unavailable: the beacon goes browser->Supabase
-- directly, never through Cloudflare (no-server-compute contract, docs/DEPLOY.md).

alter table events add column device text check (device in ('mobile', 'tablet', 'desktop'));
