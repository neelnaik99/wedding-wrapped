---
version: alpha
name: Wedding-Wrapped-design-system
description: "A confident ivory-and-ink editorial frame interrupted by oversized color blocks whose colors are extracted from the wedding photos themselves. The chrome is rigorously monochrome — serif display type, warm paper surfaces, near-black ink, pill-shaped CTAs, mono eyebrows — while each event section drops the page into that event's own extracted palette: marigold for Haldi, indigo for Sangeet, midnight plum for Reception. Guest decks additionally carry a per-guest accent derived from that guest's own photos, so every deck shares one skeleton but no two look alike. Structure is systematic; color is personal; the guest is the anchor of every layout."

colors:
  ink: "#1c1917"
  canvas: "#faf7f2"
  surface-soft: "#f1ece3"
  hairline: "#e7e0d4"
  hairline-soft: "#f0ebe1"
  primary: "#1c1917"
  on-primary: "#faf7f2"
  inverse-ink: "#f6f1e7"
  inverse-muted: "#c9bfae"
  night-canvas: "#221b18"
  night-card: "#2c231f"
  night-ink: "#f3ece1"
  night-muted: "#b3a08f"
  night-hairline: "#3a2f28"
  night-tile: "#382d26"
  night-ring: "#9c8568"
  night-edge: "#8a7561"
  accent-marigold: "#c98a1e"
  accent-marigold-text: "#8f6512"
  semantic-ok: "#12724a"
  semantic-warn: "#c8462f"
  overlay-scrim: "#141210"
  block-morning: "#efe3cd"
  block-haldi: "#e8b45a"
  block-grehshanti: "#c8283c"
  block-sangeet: "#26365c"
  block-wedding: "#f0dfc2"
  block-garden: "#7d915c"
  block-reception: "#241631"
  guest-accent: "derived — see Colors § Derived tokens; default #e8b45a"
  guest-support: "derived — see Colors § Derived tokens; default #c8283c"

typography:
  display-xl:
    fontFamily: weddingSerif
    fontSize: 76px
    fontWeight: 420
    lineHeight: 1.02
    letterSpacing: -1.1px
  display-lg:
    fontFamily: weddingSerif
    fontSize: 48px
    fontWeight: 420
    lineHeight: 1.08
    letterSpacing: -0.5px
  stat-numeral:
    fontFamily: weddingSerif
    fontSize: 96px
    fontWeight: 520
    lineHeight: 1.00
    letterSpacing: -1.4px
  headline:
    fontFamily: weddingSerif
    fontSize: 28px
    fontWeight: 480
    lineHeight: 1.25
    letterSpacing: -0.2px
  body-lg:
    fontFamily: weddingSans
    fontSize: 18px
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: -0.1px
  body:
    fontFamily: weddingSans
    fontSize: 15px
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: 0
  body-sm:
    fontFamily: weddingSans
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: 0
  button:
    fontFamily: weddingSans
    fontSize: 15px
    fontWeight: 560
    lineHeight: 1.4
    letterSpacing: 0
  eyebrow:
    fontFamily: weddingMono
    fontSize: 12px
    fontWeight: 450
    lineHeight: 1.3
    letterSpacing: 1.6px
  caption:
    fontFamily: weddingMono
    fontSize: 11px
    fontWeight: 450
    lineHeight: 1.2
    letterSpacing: 0.8px

rounded:
  sm: 6px
  md: 10px
  lg: 24px
  pill: 50px
  full: 9999px

spacing:
  hair: 1px
  xxs: 4px
  xs: 8px
  sm: 12px
  md: 16px
  lg: 24px
  xl: 32px
  xxl: 48px
  section: 96px
  admin-row: 8px

components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.button}"
    rounded: "{rounded.pill}"
    padding: 10px 20px
  button-secondary:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.button}"
    rounded: "{rounded.pill}"
    padding: 9px 18px
    border: "1px {colors.hairline}"
  button-accent:
    backgroundColor: "{colors.guest-accent}"
    textColor: "{colors.ink}"
    typography: "{typography.button}"
    rounded: "{rounded.pill}"
    padding: 10px 20px
  face-chip:
    backgroundColor: "{colors.surface-soft}"
    textColor: "{colors.ink}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.pill}"
    padding: 4px 12px 4px 4px
  face-chip-small:
    backgroundColor: "{colors.surface-soft}"
    textColor: "{colors.ink}"
    typography: "{typography.caption}"
    rounded: "{rounded.pill}"
    padding: 2px 10px 2px 2px
  constellation-node-you:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    ring: "3px {colors.guest-accent}"
    rounded: "{rounded.full}"
    size: 88px
  constellation-node-member:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    ring: "2px {colors.hairline}"
    rounded: "{rounded.full}"
    size: 52px
  stat-tile:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.stat-numeral}"
    rounded: "{rounded.lg}"
    padding: 32px
  share-card:
    backgroundColor: "{colors.guest-accent}"
    textColor: "{colors.ink}"
    typography: "{typography.display-lg}"
    rounded: "{rounded.lg}"
    aspectRatio: "4 / 5"
    padding: 48px
  color-block-event:
    backgroundColor: "{colors.block-haldi}"
    textColor: "{colors.ink}"
    typography: "{typography.headline}"
    rounded: "{rounded.lg}"
    padding: 48px
  gallery-figure:
    backgroundColor: "{colors.surface-soft}"
    textColor: "{colors.ink}"
    typography: "{typography.caption}"
    rounded: "{rounded.md}"
  admin-table-row:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.sm}"
    height: 44px
  filter-chip:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.pill}"
    padding: 5px 12px
    border: "1px {colors.hairline}"
  filter-chip-selected:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.pill}"
    padding: 5px 12px
  drawer:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.lg} 0 0 {rounded.lg}"
    padding: 24px
  toast-undo:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.inverse-ink}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.md}"
    padding: 12px 16px
  gallery-figure-selected:
    backgroundColor: "{colors.surface-soft}"
    textColor: "{colors.ink}"
    ring: "checkmark chip 24px, {colors.ink} fill, top-right"
    rounded: "{rounded.md}"
  download-bar:
    backgroundColor: "#ffffff"
    textColor: "{colors.ink}"
    typography: "{typography.button}"
    border: "1px {colors.hairline} top"
    padding: 12px 20px
  postcard-hero:
    backgroundColor: "{colors.surface-soft}"
    textColor: "{colors.ink}"
    typography: "{typography.display-lg}"
    rounded: "{rounded.lg}"
---

## Overview

Wedding Wrapped borrows Figma's marketing grammar — a monochrome editorial frame
punctuated by oversized color-block sections — and replaces the invented pastels with
colors **extracted from the wedding photos themselves**. Nobody on the team dictates a
palette; the day already had one. Marigold garlands, sangeet uplighting, a red mandap:
median-cut extraction over the galleries produced the `{colors.block-*}` tokens, and the
same extractor run per guest produces `{colors.guest-accent}` / `{colors.guest-support}`.

Two consequences define the system:

1. **One deck flow, no per-event sections.** Every Wrapped is a single story:
   cover → the number → photos with people → your highlights → you & the couple →
   everything else. The deck is never broken down by event; event palettes exist
   only as color *sources* (block tokens for explorer/admin surfaces, derived accents
   for guests), and events appear in guest copy only as names in captions.
2. **Every guest's deck shares one skeleton but no two look alike.** Layout, type, and
   chrome are identical across every deck; `{colors.guest-accent}` (their outfit, their
   photos) tints their numerals, constellation, and share card. Personalization lives in
   derived tokens, never in per-guest layout forks.

**Key characteristics:**
- **Two chromes, one grammar.** Guest surfaces are **dark**: `{colors.night-ink}` on
  `{colors.night-canvas}` — a soft warm espresso, never pure black, chosen so photos pop
  while long reading stays easy on the eyes. Admin surfaces are **light**:
  `{colors.ink}` on `{colors.canvas}` warm paper. Same type, same pills, same spacing.
  Color only ever arrives via a block or a derived accent.
- **The universal deck spine.** Every Wrapped, every tier, in this exact order:
  1. **Cover** — the guest's name, the wedding name, the dates, their best photo.
  2. **The number** — how many photos, across how many events. Nothing else — no
     "distinct moments" or dedup talk; that's pipeline noise, not a takeaway.
  3. **Photos with people** — leads with the "most photographed with" stat (top tie by
     shared photos, the couple excluded — beat 5 is already theirs), then the remaining
     partners as chips, plus one CTA into the combination finder ("Find your photos with
     anyone →") which opens the mind map inside the deck.
  4. **Your highlights.**
  5. **You & the couple.**
  6. **Everything else** — every remaining good photo, selectable.
  Rich tiers extend each beat; the postcard is the same spine at minimum size.
- **No clock on guest surfaces.** Events are named, never timed — "Sangeet", not
  "Sangeet · 7:41 PM", and never "your best hour was 7 PM". Time-of-day is admin-only
  metadata.
- Serif display (`weddingSerif`) for headlines and big numerals; sans body; `weddingMono`
  uppercase eyebrows/captions for taxonomy — never for reading text.
- Pill is the only button shape. Circles are the only face shape.
- **The featured person is the anchor of every layout** — top-center, largest, named in
  the page title. This is spatial personalization matching the chromatic kind.
- **Position carries meaning.** Sort orders are visible in geometry (tiers, arcs,
  left-to-right rank), never encoded in color alone.

## Colors

### Fixed chrome (never derived)
- **Ink** (`{colors.ink}`): all text on light surfaces. Hierarchy comes from weight and
  size, not gray steps — there is no mid-gray body text role on guest surfaces.
- **Canvas** (`{colors.canvas}`): warm paper page ground. **Surface Soft**
  (`{colors.surface-soft}`) for chips and tiles sitting on canvas; **Hairline** tokens for
  1px borders. **Inverse Ink / Inverse Muted** for text on dark blocks.
- **Accent Marigold** (`{colors.accent-marigold}`): the single-shot brand accent for
  chrome moments that must pop before any derived color is known (landing page CTA,
  admin primary actions). One per viewport, maximum. `#c98a1e` is for **fills, rings,
  and icons only** — it measures 2.75:1 on paper and fails as text. Marigold **text** on
  any light surface uses `{colors.accent-marigold-text}` (`#8f6512`, 4.87:1 on canvas,
  5.20:1 on white). On dark guest surfaces gold-on-dark already passes at ~9:1, so text
  there stays the brighter block-haldi gold.
- **Semantic ok/warn**: admin status badges and destructive actions only.
  `{colors.semantic-ok}` (`#12724a`) is a text/glyph color and reads at 5.95:1 on white;
  the older `#1b8f5a` fell to 4.10:1 at badge sizes and is retired.

### Event blocks (derived once, committed)
Extracted from `cache/<GALLERY>/` via saturation-weighted median-cut (see Derivation).
`{colors.block-morning}` `{colors.block-haldi}` `{colors.block-grehshanti}`
`{colors.block-sangeet}` `{colors.block-wedding}` `{colors.block-garden}`
`{colors.block-reception}`. Light blocks take `{colors.ink}` text; `block-sangeet`,
`block-reception`, and `block-grehshanti` are inverse blocks taking `{colors.inverse-ink}`.

### Derived tokens (computed per guest at build time)
- **`{colors.guest-accent}`**: the most saturated distinctive hue from the guest's
  focus-role photos, clamped to L 55–80 (light-block use) with an auto-generated deep
  variant for inverse use.
- **`{colors.guest-support}`**: second distinct hue (≥60° apart), same clamps.
- **Fallback**: guests whose extraction yields nothing above saturation 0.25 receive
  `{colors.accent-marigold}` / `{colors.block-sangeet}` — never `block-grehshanti`, which
  sits too close to `semantic-warn` to serve as an emotional accent.
- **Ink on a derived-accent surface** (share card, tinted numerals, CTA fills) is chosen
  by measured contrast, never by a fixed lightness threshold: it is whichever of
  `{colors.ink}` (`#1c1917`) / `{colors.night-ink}` (`#f3ece1`) yields the higher contrast
  ratio against the rendered accent, and the build fails if neither reaches 4.5:1. A
  single luminance cutoff misfires on mid-luminance accents (e.g. `block-garden` `#7d915c`,
  L≈0.24, where ivory reads 2.95:1 but ink reads 5.06:1).

### Derivation rules
1. Sample the guest's top ~30 `role=focus` photos (from `photo_people.parquet`).
2. Median-cut quantize; drop colors with saturation < 0.22, value < 0.14 or > 0.97
   (removes grays, shadows, blowouts, most skin tones).
3. Weight remaining colors by `count × (0.5 + saturation)`; bin by hue to merge neighbors.
4. Take the top two hues ≥ 60° apart; clamp lightness into the contrast-safe band.
5. Deterministic: same photos in, same tokens out. Tokens are written into
   `wrapped.json` at build time — the runtime never computes color.

## Typography

- **weddingSerif** — display voice. Stack: `"Fraunces", "Iowan Old Style",
  "Palatino Linotype", Palatino, Georgia, serif`. Fraunces (variable, Google Fonts) when
  a webfont is acceptable; Iowan Old Style is the zero-dependency system fallback the
  static guest decks can ship with alone.
- **weddingSans** — body voice. System stack: `-apple-system, BlinkMacSystemFont,
  "Segoe UI", Roboto, sans-serif` (or Inter when self-hosting).
- **weddingMono** — taxonomy voice. `"Geist Mono", "SF Mono", Menlo, monospace`.
  Always uppercase, always positive tracking, never body copy.

| Token | Use |
|---|---|
| `{typography.display-xl}` | Deck cover ("Neel's Wedding Wrapped") |
| `{typography.display-lg}` | Section openers, share-card name |
| `{typography.stat-numeral}` | The Number, stat tiles — tinted `{colors.guest-accent}` |
| `{typography.headline}` | Card titles inside color blocks, group names |
| `{typography.body-lg}` / `{typography.body}` / `{typography.body-sm}` | Reading text, table cells |
| `{typography.button}` | All pills |
| `{typography.eyebrow}` | "THE NUMBER", "CO-STARS" section markers |
| `{typography.caption}` | Photo timestamps, footer, admin metadata |

Principles: weight carries emphasis at equal size; negative tracking scales with display
size; body stays near zero. Numerals are always serif — stats are emotional content here,
not telemetry. **Size floor:** guest-facing text never renders below 11px;
`{typography.caption}` (11px) is the floor for anything a guest reads, including photo-tile
captions. Admin metadata may drop to 10px, since the admin is an editor tool, not a
gift.

## Layout

- Base unit 8px; `{spacing.section}` (96px) between major deck sections, always returning
  to `{colors.canvas}` between two color blocks so each block reads as deliberate.
- Color blocks span full content width (max 1100px) with `{rounded.lg}` corners and
  `{spacing.xxl}` interior padding; below 768px they bleed full-width, corners removed.
- Admin uses the same grammar at `{spacing.admin-row}` density on the same warm paper —
  the admin is the "editor UI" to the deck's "marketing site."
- Admin tables scroll inside their own container (`height: calc(100vh - chrome)`), never
  the page; action columns pin right.

## Components

### Buttons
- **`button-primary`** — ink pill, the default CTA everywhere. Keep scarce: two in one
  viewport means the section is doing too much.
- **`button-secondary`** — canvas pill with hairline border, the pairing partner.
- **`button-accent`** — guest-accent pill; guest surfaces only, for the emotional CTA
  ("Explore your group", "Share your Wrapped"). One per deck section.

### Face chips (`face-chip`, `face-chip-small`)
Circular face crop + name + count metadata in a pill. Always a real link. Variants:
removable (× on right), pinned/fixed (accent ring, for the couple), suggestion (carries
an explicit "+ Add" `button-secondary`). Chips in any collection are **sorted** —
photos-together descending or alphabetical, never insertion order.

### The two graphs — signature
There are exactly two graph layouts, both deterministic, never force-directed:

**Admin graph — everyone.** The site-wide overview at #/people: all guests at once,
clustered by community (communities ordered by size, members within ordered by photo
count, bride/groom pinned). It answers "who was photographed with whom across the whole
wedding" and exists for setup and exploration — it is never shown to guests.

**Guest ego graph (`constellation-node-you`, `constellation-node-member`).** Reached from the
deck's "Your people" beat via its one CTA, and rendered in-deck at `#/map` — never a separate
page, never a second link:
- Featured person at the **center**, `constellation-node-you` size,
  `{colors.guest-accent}` ring, page titled with their name.
- Members **radiate from the center**, placed clockwise from 12 o'clock in sort order
  `(together desc, name asc)`; strongest tie at 12. With 10+ members, the top ~8 take
  the inner ring and the rest a wider outer ring, detected couples adjacent.
- Edges from the center outward, stroke width `1.5 + 3.5·log1p(w)/log1p(max)`. Neutral
  (unselected) edges use `{colors.night-edge}` (`#8a7561`) on the dark graph surfaces so
  the tie-strength encoding clears the 3:1 non-text floor; an edge on the active
  combination brightens toward `{colors.guest-accent}` (up to 85% opacity). Edges are
  informational, not decorative — never drop them below 3:1. Purely decorative card
  borders stay `{colors.night-hairline}` (exempt from 1.4.11).
- Unselected selectable outlines — node rings and photo-select rings — use
  `{colors.night-ring}` (`#9c8568`, ≥3.8:1 on `{colors.night-tile}`) so the "selectable"
  affordance is actually visible.
- **Tapping a node toggles it into the combination** — the photo grid below filters
  live to photos containing you + every selected person. Graph and photos are one
  surface, not two features. Same input, same picture, always. Every togglable node is a
  real control: `role="button"` with `aria-pressed` reflecting whether it is in the
  combination, kept in sync on every repaint.

### Color-block sections (`color-block-event`)
One event, one block, one `{colors.block-*}` surface. Interior: mono eyebrow → serif
headline → content. Inverse blocks (`sangeet`, `reception`, `grehshanti`) switch text to
`{colors.inverse-ink}` and dim metadata to `{colors.inverse-muted}`.

### Stat tile (`stat-tile`) and share card (`share-card`)
Stat tile: mono eyebrow + serif numeral tinted `{colors.guest-accent}`. Share card: the
forwardable artifact — 4:5 portrait, guest-accent ground, guest's face, their number,
their name in `{typography.display-lg}`, couple wordmark in `{typography.caption}`.
Composed for a phone screenshot: nothing interactive, nothing truncatable.

### Gallery figure (`gallery-figure`)
Square crop, `{rounded.md}`, caption gradient on hover, tap opens lightbox. Captions
carry the event name only. The "Everything else" beat shows a first screenful behind
"Show all" — one flat pool of good photos, never sub-sectioned by event.

### Admin set (`admin-table-row`, `filter-chip`, `filter-chip-selected`, `drawer`, `toast-undo`)
- Filter chips: selected = primary surface, exactly like a pricing-tab pattern.
- Drawer: right-anchored, own scroll region; suggestion list sectioned "Likely matches"
  (with match badges) above "Everyone else".
- Toast-undo: every destructive row action (clear, not-a-guest) answers with an inline
  Undo; bulk-destructive actions confirm first, naming their blast radius.

### Focus
Every interactive element shows a visible focus indicator: a **2px ring at 2px offset**,
applied via `:focus-visible` so pointer users never see it but keyboard users always do.
The ring color is chrome-specific — `{colors.block-haldi}` gold `#e8b45a` on night (guest)
surfaces, `{colors.ink}` `#1c1917` on paper (admin) surfaces — and must read at ≥3:1
against whatever it sits on. Never `outline: none` without a replacement indicator visible
at ≥3:1. The focused node in the ego graph thickens its ring to the focus gold; the
combination finder is fully keyboard-operable (Tab to reach, Enter/Space to toggle).

## Experience tiers (data-adaptive)

The link itself is tiered. Distribution over 154 guests: 7 have 500+ photos, 24 have
150–499, 52 have 50–149 (median 62), 71 have 15–49. Rules are deterministic:

| Tier | Photos | They receive | Number card | Graph |
|---|---|---|---|---|
| Inner circle | 150+ | Full Wrapped | count leads | two rings + explorer |
| Group guest | 50–149 | Full Wrapped | count leads | one ring, linked to photos |
| Cameo | 15–49 | **Postcard page** | best photo leads; count is a caption | "you & the couple" strip; 4+ ties upgrades it |
| Glimpse | under 15 | **No own link** | — | — |

- **The send rule:** a link goes out only when the page behind it feels generous.
  Glimpse guests appear in their household's deck ("Also seen" strip) and the household
  email carries one great photo of them inline — generosity moves into the email.
  A couple-household deck gets a **joint cover** ("Adam & Megan") so the low-photo
  spouse is a co-anchor, never a footnote. A glimpse guest with **no household** gets a
  personal email with their best photo inline and a direct download link.
- **Graph features gate on connections, not photo count — and the connection gate
  overrides the tier table**: combination finder at 4+ real ties (even for a cameo);
  2–3 ties → face row; 1 tie → pair card with the couple; 0 → no graph section.
- **Tiers are deterministic but overridable.** A per-guest `tier_override` in data
  (same veto pattern as colors) protects close family near a boundary from being
  demoted by a photo count. Before sending, an admin **pre-send review queue** lists
  every guest within ±15 photos of a tier boundary plus every accent fallback: cover
  thumbnail, best shot, tier, swatch, approve/override — minutes, not hours.
- **As data shrinks, faces grow.** A sparse page compresses into fewer, larger, warmer
  elements; it never renders emptied-out versions of rich layouts.
- Every guest surface ships web and mobile: same sections, same order — mobile stacks,
  pins the download bar, and puts combination-finder chips in a horizontal scroll row
  above the grid; web spreads into split layouts.

## Selection & download

Every photo a guest can see is takeable. Tap/click toggles
`{components.gallery-figure-selected}` (24px check chip, top-right); a persistent
`{components.download-bar}` (bottom-pinned on mobile) always offers exactly two
actions: **"Download all"** (secondary) and **"Download N"** (primary, N = selected
count). No other download verbs anywhere. Selection is the same gesture in the gallery, the
combination finder, and the postcard grid — one habit, everywhere. Constraints:
- **The hit target is the whole element, not the chip.** For photo selection the
  tap/click target is the **entire tile**; for chip removal it is the **entire right half
  of the chip**. Each target is at minimum 24×24 CSS px (WCAG 2.5.8), and 44px is
  preferred on touch. The 22–24px check circle drawn top-right is **visual state only** —
  it is never the sole hit area.
- **Announce the count.** The download bar's selected-count element carries
  `aria-live="polite"` so toggling a photo announces the new count without moving focus,
  and the "Download N" button's accessible name always includes the current count
  (e.g. "Download 3").
- **A completed "Download N" consumes the selection.** On success the count returns to 0,
  every check chip clears, and the `aria-live` element announces the reset. The selection
  survives a download that threw or that skipped photos — the guest needs it to retry, and
  the "couldn't be fetched" note is useless without it. Because clearing disables the
  primary button, focus moves to "Download all" rather than falling to `<body>`. "Download
  all" never touches the selection; it didn't consume one.
- **Downloadable set = build-time visible set**, exactly (the visibility model in
  docs/VISIBILITY.md). No page may offer a photo through download that its builder
  would not display.
- "Take all" defaults exclude courtesy-grade photos of third parties (still
  individually selectable) so the ≤20% courtesy dose never bulk-exports.
- Confirm the photographer's license before shipping "full quality, no watermark"
  copy; until confirmed, say nothing about quality or watermarks.

## Voice & takeaways

Every screen has exactly one takeaway; every element either serves it or leaves:

- Cover — *"This was made for you, specifically."*
- The Number — *"That's a lot of photos of you"* — and it's fun to poke: tapping it
  is the sanctioned easter egg (confetti tick + a dry one-liner, milestone lines at
  10/25/all taps so repeated taps pay off). It ships on postcards too — delight never
  gates on tier. Never promise a countdown the page won't finish. The numeral is a real
  `<button>` with an `aria-label` naming the count and the affordance (e.g.
  "1,437 — tap for a surprise"); the confetti and one-liner are decorative (`aria-hidden`)
  so repeated taps never spam a screen reader.
- Wedding graph — *"These are your people."*
- Photos together — *"Any combination, instantly."*
- Everything else — *"Take the ones you love."*
- Photos with people — *"These are your people — go find any combination."*
- Postcard — *"We're glad you were there."* Warmth leads; never stats-first on small data.
- Share card — *"Show someone."*
- Admin naming — *"Keep going — N left."* The admin metric is minutes spent, so admin
  copy is progress-oriented and never decorative.
- Groups — *"The next right person is one click away."*

Tone: a warm host, specific and a little dry. Counts are written in plain language
("shares 32 photos with Avery"). Small numbers are framed as favorites ("our 27
favorite photos of you") — selection *toward* love, never away from badness: no "we
kept the good stuff," no "caught you," nothing that reveals the grading. On small-data
pages, prefer naming events over counting photos.

## Do's and Don'ts

### Do
- Let extraction pick colors; let humans veto. Derived tokens may be overridden per guest
  in data, never hardcoded in components.
- Anchor every people-layout on the featured person: top-center, largest, titled.
- Keep sort orders visible in geometry — tiers, arcs, left-to-right rank.
- Return to `{colors.canvas}` between color blocks; one block per viewport.
- Write counts in plain language: "shares 32 photos with Avery."
- Pair every destructive action with undo (row-level) or a consequence-naming confirm.
- Use `{colors.guest-accent}` only against surfaces it has been contrast-clamped for.

### Don't
- Don't introduce colors outside `{colors.block-*}`, derived tokens, and
  `{colors.accent-marigold}`. A new hex in a component is a system bug.
- Don't use force-directed/spring layouts anywhere a guest can see. Physics is not a
  reading order.
- Don't encode identity or grouping in color alone — pair with position, ring weight, or label.
- Don't put mono in body copy, gray steps in guest text, or squares on CTAs and faces.
- Don't show raw metrics ("4.6% fit") on any surface; translate or tooltip them.
- Don't let two guests' decks differ in layout. Personalization is chromatic and
  data-driven, never structural.

## Responsive

| Width | Key changes |
|---|---|
| ≥1100px | Max content width; deck two-column (photo / text) splits active |
| 768px | Color blocks go full-bleed, corners removed; admin drawer becomes full-screen sheet |
| 560px | `display-xl` 76→44px, `stat-numeral` 96→64px; pills full-width; constellation tier-2 collapses to sorted `face-chip-small` rows |

Touch targets ≥44px everywhere (constellation members render at 52px minimum), and never
below the 24×24 CSS px floor (WCAG 2.5.8). The **hit target is the whole element**: the
entire photo tile toggles selection, the entire right half of a chip removes it — the
small check circle or `×` glyph is visual state, not the tap area. Share card is fixed 4:5
and never reflows — it is an image, conceptually.

## Iteration Guide

1. Reference components by token name (`{components.share-card}`) when asking an AI
   session for UI work; this file is the contract.
2. New section? Decide its `{colors.block-*}` surface first — that is the most
   consequential choice.
3. New color need? Extend the extractor, not the palette. If a color can't be derived
   from the photos or the fixed chrome, question the design.
4. Regenerate derived tokens only at build time (`build_guests.py`); commit event-block
   token changes like schema changes — they alter every deck.
5. Add component variants as separate entries (`-selected`, `-pressed`); don't bury
   states in prose.
6. Cross-reference: visibility rules in `docs/VISIBILITY.md`; open UX debt in GitHub
   issues #1–#18 (this file encodes the fixes for #1, #2, #4, #7, #11, #12, #14, #15, #16).
