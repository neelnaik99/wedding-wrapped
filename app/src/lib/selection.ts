// Selection view: Household + selected members -> one Wrapped.
// Pure TS, erasable syntax only, type-only imports — runs under node's type stripping.
import type { CoStar, GalleryEvent, GroupMember, GuestGroup, Household, PoolEntry, Shot, Wrapped } from "../types"

/** Toggle a member in the selection. Removing the last member is a no-op (never empty). */
export function toggle(selected: number[], cid: number): number[] {
  if (!selected.includes(cid)) return [...selected, cid]
  if (selected.length === 1) return selected
  return selected.filter((c) => c !== cid)
}

function minutes(t: string): number {
  const m = /^(\d{1,2}):(\d{2})\s*(AM|PM)?/i.exec(t.trim())
  if (!m) return 0
  let h = Number(m[1]) % 12
  if (m[3]?.toUpperCase() === "PM") h += 12
  else if (!m[3]) h = Number(m[1])
  return h * 60 + Number(m[2])
}

const MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]

/** "Fri Apr 24" -> a sortable day ordinal (0 if unparseable). */
function dayOrd(day: string | undefined): number {
  const m = /([A-Za-z]{3})\w*\s+(\d{1,2})\s*$/.exec(day ?? "")
  if (!m) return 0
  const mo = MONTHS.indexOf(m[1].toLowerCase())
  return mo < 0 ? 0 : (mo + 1) * 32 + Number(m[2])
}

function overlap(who: number[] | undefined, sel: Set<number>): number {
  let n = 0
  for (const c of who ?? []) if (sel.has(c)) n++
  return n
}

function stripLinks(m: GroupMember): GroupMember {
  const { url: _url, slug: _slug, ...rest } = m
  return rest
}

export function viewFor(h: Household, selected: number[]): Wrapped {
  const sel = new Set(selected)
  // selected members, biggest deck first
  const picked = h.members.filter((m) => sel.has(m.cid)).sort((a, b) => b.wrapped.n_photos - a.wrapped.n_photos)
  const lead = picked[0] ?? h.members[0]
  const base = lead.wrapped

  const allSelected = h.members.every((m) => sel.has(m.cid))
  const name = allSelected ? h.title : h.members.filter((m) => sel.has(m.cid)).map((m) => m.first).join(" & ")

  const key = [...selected].sort((a, b) => a - b).join(",")
  const sum = h.summary[key]
  const events = sum ? sum.events : base.events
  const peak = events.length ? events.reduce((a, b) => (b.n > a.n ? b : a)) : base.peak

  // gallery: per event name, union of selected members' shots, deduped by url
  const byEvent = new Map<string, { n_all: number; shots: Map<string, Shot> }>()
  for (const m of picked) {
    for (const ev of m.wrapped.gallery) {
      let slot = byEvent.get(ev.name)
      if (!slot) byEvent.set(ev.name, (slot = { n_all: 0, shots: new Map() }))
      slot.n_all = Math.max(slot.n_all, ev.n_all)
      for (const s of ev.shots) {
        if (overlap(s.who, sel) > 0 && !slot.shots.has(s.url)) slot.shots.set(s.url, s)
      }
    }
  }
  // A shot's `time` is time-of-day only and a bucket spans both wedding days, so the
  // chronological key is the day of the shot's event (from the members' EventStats) + time.
  const evDay = new Map<string, number>()
  for (const m of picked) for (const e of m.wrapped.events) if (!evDay.has(e.name)) evDay.set(e.name, dayOrd(e.day))
  const when = (s: Shot) => (evDay.get(s.event ?? "") ?? 0) * 1440 + minutes(s.time)
  const gallery: GalleryEvent[] = []
  for (const [evName, slot] of byEvent) {
    const order = new Map([...slot.shots.keys()].map((u, i) => [u, i]))
    const shots = [...slot.shots.values()].sort(
      (a, b) =>
        overlap(b.who, sel) - overlap(a.who, sel) || when(a) - when(b) || order.get(a.url)! - order.get(b.url)!,
    )
    if (shots.length) gallery.push({ name: evName, n_all: slot.n_all, shots })
  }

  // costars: union by cid (max n), excluding every household member
  const household = new Set(h.members.map((m) => m.cid))
  const co = new Map<number, CoStar>()
  for (const m of picked) {
    for (const c of m.wrapped.costars) {
      if (household.has(c.cid)) continue
      const prev = co.get(c.cid)
      if (!prev || c.n > prev.n) co.set(c.cid, c)
    }
  }
  const costars = [...co.values()].sort((a, b) => b.n - a.n)

  // groups: union by id; map from the biggest selected member who has one; links to other decks stripped
  const groups = new Map<string, GuestGroup>()
  for (const m of picked) {
    for (const g of m.wrapped.groups ?? []) {
      let out = groups.get(g.id)
      if (!out) groups.set(g.id, (out = { id: g.id, name: g.name, members: [], map: null }))
      for (const gm of g.members) if (!out.members.some((x) => x.cid === gm.cid)) out.members.push(stripLinks(gm))
      if (!out.map && g.map) {
        out.map = { ...g.map, photos: g.map.photos.filter((p) => overlap(p.who, sel) > 0) }
      }
    }
  }

  // Personal fields of the lead member that must not leak into a Selection view:
  // slug (identifies one guest's deck) and n_pool (Task 5 computes the All-photos union).
  // Deliberately carried over from the lead since no subset data exists:
  // n_scenes, n_hidden, n_ties, graph_tier, hero_event.
  const { slug: _slug, n_pool: _nPool, ...rest } = base
  return {
    ...rest,
    n_pool: undefined,
    name,
    n_photos: sum ? sum.n_photos : base.n_photos,
    n_events: sum ? sum.n_events : base.n_events,
    peak,
    events,
    costars,
    gallery,
    picks: base.picks,
    groups: [...groups.values()],
  } as Wrapped
}

const ZONE_ORDER: Record<PoolEntry["zone"], number> = { shown: 0, skipped: 1, below_bar: 2 }

/**
 * All photos for a Selection: union of the selected members' pool-<cid>.json files by url.
 * An entry without `who` belongs to the member whose pool it came from. Only entries whose
 * who ∩ selected ≠ ∅ survive; order is |who ∩ selected| desc, then first-seen (each pool
 * is already in rank order). A url in several pools keeps its best zone and merged `who`.
 */
export function mergePools(pools: Record<number, PoolEntry[] | undefined>, selected: number[]): PoolEntry[] {
  const sel = new Set(selected)
  const byUrl = new Map<string, { e: PoolEntry; i: number }>()
  let i = 0
  for (const cid of selected) {
    for (const e of pools[cid] ?? []) {
      const who = e.who ?? [cid]
      const prev = byUrl.get(e.url)
      if (!prev) {
        byUrl.set(e.url, { e: { ...e, who: [...who] }, i: i++ })
        continue
      }
      const merged = new Set([...(prev.e.who ?? []), ...who])
      const zone = ZONE_ORDER[e.zone] < ZONE_ORDER[prev.e.zone] ? e.zone : prev.e.zone
      prev.e = { ...prev.e, zone, who: [...merged] }
    }
  }
  return [...byUrl.values()]
    .filter((x) => overlap(x.e.who, sel) > 0)
    .sort((a, b) => overlap(b.e.who, sel) - overlap(a.e.who, sel) || a.i - b.i)
    .map((x) => x.e)
}

/** Split a location hash into its route ("#/all", "#people", "") and the `sel` query (cids). */
export function readHash(hash: string): { route: string; sel: number[] | null } {
  const q = hash.indexOf("?")
  const route = q < 0 ? hash : hash.slice(0, q)
  if (q < 0) return { route, sel: null }
  const m = /(?:^|&)sel=([^&]*)/.exec(hash.slice(q + 1))
  if (!m) return { route, sel: null }
  // cids are plain digits: no decoding, so a malformed %-sequence can't throw (it just drops out)
  const sel = m[1]
    .split(",")
    .map((x) => Number(x))
    .filter((n) => Number.isInteger(n) && n >= 0)
  return { route, sel: sel.length ? sel : null }
}

/** The hash with `sel` written into its query, keeping the route: ("#/all", [1,2]) → "#/all?sel=1,2". */
export function writeHash(hash: string, selected: number[]): string {
  const { route } = readHash(hash)
  const base = route === "" || route === "#" ? "#" : route
  return `${base}?sel=${selected.join(",")}`
}

/** A `sel` from the URL, cleaned against the Household: unknown cids dropped, dupes removed;
 *  nothing left → every member (the never-empty rule). */
export function cleanSel(sel: number[] | null, cids: number[]): number[] {
  const ok = cids.filter((c) => sel?.includes(c))
  return ok.length ? ok : [...cids]
}
