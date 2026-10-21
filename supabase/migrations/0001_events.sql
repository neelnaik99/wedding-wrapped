-- Telemetry events (issue #39) — selection/download signals as ranking ground truth.
-- Append-only from guests: RLS with a single INSERT policy for anon, no SELECT policy;
-- reads happen locally via the service key. Check constraints double as the payload cap
-- (arch review #40: no per-IP rate limiting by design — private token-URL site).
-- ts is server-side: guest clocks lie.

create table events (
  id      bigint generated always as identity primary key,
  slug    text not null check (char_length(slug) <= 24),
  photo   text check (char_length(photo) <= 200),
  action  text not null check (action in (
            'view_all_open', 'lightbox_open', 'select_on', 'select_off',
            'download_one', 'download_selected', 'download_all', 'show_all_expand')),
  surface text check (surface in ('deck', 'all_photos')),
  env     text not null default 'prod' check (env in ('prod', 'stage')),
  ts      timestamptz not null default now()
);

alter table events enable row level security;

-- Scoped to anon + authenticated so the future hearts sign-in (ROADMAP "Next") doesn't
-- silently stop logged-in guests from logging (arch review #40 dim 3).
create policy events_insert_only on events
  for insert to anon, authenticated with check (true);

-- deliberately NO select/update/delete policies: append-only for the site.
