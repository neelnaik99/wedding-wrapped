# Admin app

## Start

```bash
cd ~/Downloads/wedding-wrapped
.venv/bin/python label_server.py --min 15          # → http://localhost:8792
```

Flags: `--min 15` (only clusters with ≥N photos enter the naming queue), `--port 8792`,
`--guests ~/Downloads/guest-list.csv` (the RSVP export; used for name suggestions and
labels' email/party fields).

The server binds `0.0.0.0`, so any phone/laptop on the same Wi-Fi can use it
(`http://<your-mac-ip>:8792`) — built for handing the namer to family. It is a stdlib
`ThreadingHTTPServer`, single data dir, no auth: LAN use only, never expose it publicly.

`/` serves the React SPA (`app/bundle.html`, gated on the `app/.unified` marker). Legacy
standalone pages still exist: `/namer` (original label UI), `/people` (grid), `/review`
(server-rendered named-cluster list), `/highlights` (threshold slider, see below).

## `#/admin` — naming table + drawer

The main table: one row per queued cluster (photos, status, name, email, party), with filter
chips (All / Unlabeled / Named / Provisional / Duplicates / Not a guest / Merged), search,
sortable columns, CSV export/import buttons, and history/undo.

Click a row → the **namer drawer**: face strip, a few full photos for context, per-event
counts, co-stars, similar clusters (embedding-centroid cosine ≥ 0.35, top 5 — merge
candidates), and a guest-list combobox with suggestions ranked by name match + RSVP-event
overlap + not-yet-used.

Keyboard (in the drawer; plain letters always type into the search box):

| Key | Action |
|---|---|
| `Enter` | assign the selected guest to this cluster |
| `↑` / `↓` | move suggestion selection |
| `⌘→` / `Ctrl+→` | skip to next cluster |
| `⌘←` / `Ctrl+←` | previous cluster |
| `⌘.` | mark **not a guest** (vendor, staff, photographer) |
| `⌘/` | merge into the first similar cluster |
| `⌘⌫` | clear the label |
| `Esc` | close drawer |

Label states written to `data/labels.json`:
`{status:"labeled", name, first, last, email, party, guest_id}` ·
`{status:"not_guest"}` · `{status:"merged", merge_into}` · plus an optional
`provisional: true` flag for seeded/uncertain names (confirm in the drawer).
Merging into an already-labeled cluster copies that label instead of a merge pointer;
builders union merged/same-`guest_id` clusters into one person.

**Right-click naming works everywhere.** `FaceContextMenu` wraps every face in the app —
co-stars, graph nodes, shared-photo boxes, deck lightboxes — right-click (or long-press on
touch) any face to name/rename that person on the spot, without leaving your current view.
Saves are optimistic with a toast + Undo.

## `#/graph` — relationship graph

Interactive who-with-whom SVG (from `relationship_graph.build()` via `/api/graph?min=`).
Discs = people (size ~ photos), lines = photographed together. Controls: min-photos, color by
Louvain **community** or **bride ↔ groom side**, all-names toggle, all-ties toggle, min tie
weight slider. Drag to pan, wheel to zoom.

- **Click** a face → add it to the multi-select (also available from the "Pick people…"
  combobox). With ≥1 selected: jump to **shared photos** for the whole selection.
- **Shift/⌘-click** a face → details panel: their strongest ties, open their Wrapped deck,
  find photos shared with them.

## `#/shared` — photos of a group

`#/shared?cids=15,50,110` shows every photo containing **all** the listed people (usable faces),
chronological, filterable by event, with name boxes drawn on faces in the lightbox — and
right-click naming, so it doubles as a way to sweep up unnamed small clusters seen next to
known people.

## `#/wrapped` — deck previews

Index of every built draft deck in `site/` (name, photos, hero). `#/wrapped/:slug` renders the
actual guest deck inline (same `<Deck>` component guests get), with admin extras: face boxes +
right-click naming inside the photo lightbox. What you preview here is byte-for-byte what
`build_guests.py` ships, minus the extras.

## `/highlights` — threshold curation page

Standalone page (`highlights_ui.html`) for the curation pass, one person at a time:

- Person picker + their **score histogram** with a draggable threshold slider (0–100, the
  per-person bar from `data/thresholds.json`). Moving it re-runs `pick_highlights` live via
  `/api/highlights?cid=&thr=` so you see exactly which ~25 photos survive.
- Save writes `{value, auto:false}` via `POST /api/threshold`; the **auto** button restores the
  fitted value (min(55th pct, keep-best-30)). Manual (`auto:false`) values survive re-runs of
  `add_scene_scores.py`.
- Each pick shows its bucket (With the couple / You in focus / Group), score bar, and the full
  per-face breakdown of everyone in the photo (role, score vs their own threshold, blink/edge
  flags) via `/api/photo_people`.

Start with the **THIN DECKS** list printed by `build_guests.py` — those are the people whose
threshold likely needs lowering.

## Undo, history, backups

- Every label change is appended to `data/labels_history.jsonl`
  (`{ts, cid, before, after, who}`). `POST /api/undo` reverts the last line (repeatable);
  `/api/history` shows the last 200 changes in the UI.
- On every server start, `data/labels.json` is snapshotted to
  `data/backups/labels-<timestamp>.json` (last 30 kept). Restore = copy one back over
  `data/labels.json` and restart.
- Writes are atomic (tmp file + rename) and serialized behind a lock, so concurrent phone +
  laptop labeling is safe.

## Labels CSV round-trip

- **Export:** `GET /api/export.csv` (button in `#/admin`) → columns
  `cluster_id, photos, status, name, first, last, email, party, guest_id, merge_into, provisional`.
- **Import:** upload the same shape via the admin table (POST `/api/import`). Rules per row:
  blank name **and** status = clear the label; `status=not_guest` / `merged` (+`merge_into`)
  pass through; otherwise the row is matched to the guest list by `guest_id` first, then exact
  name (case-insensitive) — matched rows get the guest's email/party, unmatched named rows are
  stored as free-text labels. Every imported row goes through the same history log, so a bad
  import is undoable.

Typical use: export → fix names in a spreadsheet (or hand to a family member) → import.

## Rebuilding the SPA

Only needed after editing `app/src/`:

```bash
cd app && bash <web-artifacts-builder-skill>/scripts/bundle-artifact.sh   # Parcel + html-inline → app/bundle.html
cd .. && ./deploy_bundle.sh    # copy the new bundle over every site/<slug>/index.html
```

`label_server.py` serves `app/bundle.html` directly, so the admin app updates on reload;
`deploy_bundle.sh` only refreshes the **admin draft** decks in `site/`. Guest decks in
`site_guest/` get the new bundle the next time `build_guests.py` runs (it copies
`app/bundle.html` into every token folder).
