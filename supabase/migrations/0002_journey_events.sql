-- Journey-map gaps found pre-prod (session journey audit, 2026-08-30):
--   deck_open           -> the funnel denominator J1 lacked (a visit with zero interaction was invisible)
--   show_blurry_expand  -> the below-bar fold is the threshold-calibration instrument; opening it must be observable
--   lightbox_nav        -> arrow-through views are attention on photos that never got a lightbox_open
--   session             -> random per-page-load nonce (no storage, no fingerprint) so two people on one
--                          forwarded link stop merging into one indecisive guest

alter table events drop constraint events_action_check;
alter table events add constraint events_action_check check (action in (
  'deck_open', 'view_all_open', 'lightbox_open', 'lightbox_nav', 'select_on', 'select_off',
  'download_one', 'download_selected', 'download_all', 'show_all_expand', 'show_blurry_expand'));

alter table events add column session text check (char_length(session) <= 36);
