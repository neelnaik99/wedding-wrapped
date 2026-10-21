# Visibility & quality model

Who can see which photo, on which surface, is decided by three orthogonal layers.

## 1. Capability layer (who can open a page)
Bearer URLs, resolved at build time. A guest's personal token unlocks their deck; each
(group, member) pair gets its own explorer page containing only that member's view.
No logins; revocation = rotate token in `data/tokens.json` → rebuild → redeploy.

## 2. Relationship layer (whose photos appear at all)
Groups (`data/groups.json`, many-to-many, couple implicit everywhere). A member A of group
ABCD sees combinations that include A — A solo, AB, AC, AD, ABC, ABD, ACD, ABCD — and
never BC without A. Enforced by *data absence*: A's explorer page embeds only A-inclusive
photos, so nothing to "unhide".

## 3. Quality layer (which of those photos are worth showing)
Every face has a 0–100 `score` (photo_people.parquet) and every person a personal bar
(`data/thresholds.json`, auto-fitted, slider-tunable at /highlights). Grades per (person, photo):

| grade | rule |
|---|---|
| good | score ≥ their bar |
| medium | bar − 15 ≤ score < bar |
| bad | score < bar − 15 |

Policy (curation.courtesy_adjust + build_guests explorer filter):
- **Self rule** — a viewer only receives photos where *they* grade good (deck highlights)
  or ≥ medium (group explorers). Your worst shots are never shown to you or picked for you.
- **Courtesy rule** — photos where *another prominent person* (prom ≥ 0.4, face ≥ 48px)
  grades bad are demoted in ranking (look −0.25) and, in explorers, capped at ≤20% of a
  member's photo pool. So A gets "A good" freely, sees "B bad" only in small doses — and
  symmetrically B is protected from a feed of "A bad".
- Blink and edge-cut faces are excluded from everything, regardless of grades.

The full matrix (A good × B bad, etc.) is therefore resolved per-viewer at build time; the
same photo can appear on A's surfaces and be absent from B's.

## Where each layer is enforced
| Surface | Capability | Relationship | Quality |
|---|---|---|---|
| Personal deck | own token | n/a (own photos) | self-good, courtesy demotion |
| "Your people" card | own token | own groups only | counts only |
| Group explorer | per-member token | member-inclusive combos | self ≥ medium, courtesy cap 20% |
| Admin app / server | localhost only | all | none (operators see everything) |
