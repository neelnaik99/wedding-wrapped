export interface EventStat {
  key: string
  name: string
  n: number
  first: string
  last: string
  day: string
  pct: number
}

export interface CoStar {
  cid: number
  n: number
  name: string
  /** face crop; null on a Household Deck when no photo of them includes a member (show the initial) */
  img: string | null
  labeled: boolean
  /** one half of the couple — excluded from the "most photographed with" stat (beat 5 is theirs) */
  couple?: boolean
}

export interface Shot {
  url: string
  thumbs: string[]
  n_alt: number
  time: string
  portrait: boolean
  fx?: number
  fy?: number
  /** courtesy-grade third-party photo — excluded from "Download all" by default, still individually selectable */
  courtesy?: boolean
  /** Household members (cids) in this photo — present in household.json */
  who?: number[]
  /** the photo's event (EventStat.name), e.g. "Sangeet" — with that event's `day` it orders shots across days */
  event?: string
}

export interface GalleryEvent {
  name: string
  n_all: number
  shots: Shot[]
}

/** A "moment" is a plain string today; the video pipeline may later attach a clip. */
export type Moment = string | { text: string; clip_url?: string | null }

export function momentText(m: Moment): string {
  return typeof m === "string" ? m : m.text
}
export function momentClip(m: Moment): string | null {
  return typeof m === "string" ? null : m.clip_url || null
}

/** Someone the guest shares a group with (family table, dance crew, …). */
export interface GroupMember {
  cid: number
  name: string
  first: string
  /** relative img url, e.g. "../img/face_123.jpg" or a Household's "faces/123.jpg"; null → initial */
  face: string | null
  /** photos of the two of you together */
  together: number
  /** that member's own deck, e.g. "/k7m3xq9w2p/" — stripped from Household views (never link to another guest's deck) */
  url?: string
  slug?: string
}

/** A node in the viewer's ego graph: a group member, sized by tie strength to the viewer. */
export interface MapNode {
  cid: number
  name: string
  first: string
  /** null on a Household Deck when no photo of them includes a member → the initial */
  face: string | null
  /** node radius baked at build time from this member's tie weight to the viewer */
  r: number
}

/** One photo in the map's finder pool. Always includes the viewer (build-time guarantee). */
export interface MapPhoto {
  id: string
  /** grid thumbnail (~500px) */
  s: string
  /** lightbox image (~1400px) */
  l: string
  /** event name, already title-cased */
  gallery: string
  /** cids in frame, restricted to this group */
  mem: number[]
  /** another member in frame grades poorly for this viewer — rationed at build time (#34) */
  courtesy?: boolean
  /** Household members (cids) in this photo — present in household.json */
  who?: number[]
}

/** `[a, b, weight, strokeWidth]` — the stroke width encodes weight, baked at build time. */
export type MapEdge = [number, number, number, number]

/**
 * The viewer-scoped ego graph + finder pool, rendered in-deck at `#/map`.
 * Every photo in `photos` includes the viewer; pairings that exclude them never ship.
 */
export interface GroupMap {
  name: string
  /** the viewer's cid — always the centre node */
  me: number
  members: MapNode[]
  photos: MapPhoto[]
  edges: MapEdge[]
  /** canonical wide projection size */
  W: number
  H: number
  /** members clockwise from 12 o'clock, strongest first; the client reprojects these */
  rings: number[][]
  /** ring radii, parallel to `rings` */
  ringR: number[]
  /** the viewer node's radius */
  viewR: number
}

export interface GuestGroup {
  id: string
  name: string
  members: GroupMember[]
  /** the viewer's mind map for this group (absent → no map for them) */
  map?: GroupMap | null
}

export interface Wrapped {
  name: string
  slug: string
  cluster: number
  hero: string
  n_photos: number
  n_events: number
  n_scenes: number
  n_hidden: number
  peak: EventStat
  events: EventStat[]
  costars: CoStar[]
  moments: Moment[]
  gallery: GalleryEvent[]
  picks: string[]
  couple: string
  dates: string
  gallery_link: string
  from_us: string | null
  /** show the "DRAFT" pill; defaults to true when missing */
  draft?: boolean
  curated?: boolean
  n_picks?: number | null
  hero_fx?: number
  hero_fy?: number
  /** the guest's groups (family, table, crew) — most guests have none */
  groups?: GuestGroup[]
  /** experience tier from photo count (absent → treat as a full deck) */
  tier?: "inner" | "group" | "cameo" | "glimpse" | "light"
  /** per-guest accent hex derived from their photos at build time (absent → default haldi #f2c14e) */
  guest_accent?: string
  /** per-guest support hex (second derived hue; absent → falls back to accent) */
  guest_support?: string
  /** ink hex for text sitting on the derived accent, chosen by contrast at build time (absent → dark ink) */
  accent_ink?: string
  /** photo count in this deck's pool.json (issue #39); absent → old build, hide the all-photos CTA */
  n_pool?: number
  /** telemetry endpoint baked at build time (issue #39); absent → beacon no-ops */
  telemetry?: { url: string; key: string; env: string }
}

/** One entry in pool.json — the guest's full photo pool for the all-photos view (issue #39).
 *  zone records the ranker's verdict at build time; courtesy-grade photos never ship. */
export interface PoolEntry {
  url: string
  zone: "shown" | "skipped" | "below_bar"
  /** the guest's look_rank percentile at build time (the offline join's prior) */
  rank: number
  /** Household members (cids) in this photo — present in pool-<cid>.json; absent → just that member */
  who?: number[]
}

export interface PoolFile {
  photos: PoolEntry[]
}

/** One person in a Household, carrying their full personal Wrapped (with `who` on every photo). */
export interface HouseholdMember {
  cid: number
  first: string
  light: boolean
  wrapped: Wrapped
}

/** site_guest/h/<token>/household.json — one Deck per Household. */
export interface Household {
  title: string
  /** the couple's cids — their photos are never in `members` */
  couple: number[]
  members: HouseholdMember[]
  /** keyed by sorted comma-joined cids of a member subset */
  summary: Record<string, { n_photos: number; n_events: number; events: EventStat[] }>
  /** "light" (Task 6): a solo light Household — Cover + couple picks + own gallery only */
  mode?: "light"
}
