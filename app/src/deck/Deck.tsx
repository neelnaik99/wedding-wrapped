import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import type { Household, PoolEntry, PoolFile, Shot, Wrapped } from "@/types"
import { rewriteWrappedUrls } from "@/api"
import { cleanSel, mergePools, readHash, toggle, viewFor, writeHash } from "@/lib/selection"
import MemberPicker, { type PickerMember } from "./MemberPicker"
import Cover from "./Cover"
import TheNumber from "./TheNumber"
import YourPeople from "./YourPeople"
import FeaturedGrid from "./FeaturedGrid"
import PhotoWall from "./PhotoWall"
import AllPhotos from "./AllPhotos"
import GroupMap, { firstMap } from "./GroupMap"
import DownloadBar from "./DownloadBar"
import Lightbox, { type LightboxState } from "./Lightbox"
import { DeckExtrasProvider, type DeckExtras } from "./DeckContext"
import { SelectionProvider, type OpenFn, type PoolPhoto } from "./Selection"
import { restorePeopleScroll } from "./scroll"
import { initBeacon, setSurface, track } from "./beacon"

type View = "deck" | "all" | "map"

type State =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: Wrapped; household: Household | null }

/** Guest accent + the ink that reads on it. Never computed at runtime — read from the
 *  build-time tokens, falling back to haldi / dark ink when a deck predates the palette pass. */
const DEFAULT_ACCENT = "#f2c14e" // haldi
const DEFAULT_ACCENT_INK = "#221b18" // night-canvas — dark ink reads on the light haldi gold

interface DeckProps {
  /**
   * Where to load wrapped.json from. Default "./wrapped.json" (standalone: the bundle sits
   * next to the JSON). In the unified app pass "/site/<slug>/wrapped.json" and rewrite=true so
   * the "../img/…" urls inside become "/site/img/…".
   */
  src?: string
  rewrite?: boolean
  /** true when rendered under the unified app's fixed nav bar */
  embedded?: boolean
  /** admin-only extras (face context menus, live names) — only ever passed when embedded */
  extras?: DeckExtras | null
}

/** "With Preethi & Neel" (guest deck) / "Together" (couple's own deck) → the couple beat. */
const isCoupleSection = (name: string) => /^with\b/i.test(name) || /^together$/i.test(name)
/** "You in focus" → the guest's highlights. */
const isFocusSection = (name: string) => /in focus/i.test(name)

const dedupe = (urls: string[]) => Array.from(new Set(urls))
function dedupeShots(shots: Shot[]): Shot[] {
  const seen = new Set<string>()
  return shots.filter((s) => (seen.has(s.url) ? false : (seen.add(s.url), true)))
}

/** Split the flat wrapped.json into the spine's photo beats (4, 5, 6) + the download pool. */
function derive(data: Wrapped) {
  const accent = data.guest_accent || DEFAULT_ACCENT
  const accentInk = data.accent_ink || DEFAULT_ACCENT_INK
  const hero = data.hero
  const gallery = data.gallery ?? []

  const coupleShots = gallery.filter((g) => isCoupleSection(g.name)).flatMap((g) => g.shots)
  const focusShots = gallery.filter((g) => isFocusSection(g.name)).flatMap((g) => g.shots)
  const restShots = gallery
    .filter((g) => !isCoupleSection(g.name) && !isFocusSection(g.name))
    .flatMap((g) => g.shots)

  // Beat 4 — Your highlights: the guest's "in focus" bucket, or (legacy/couple decks) the
  // curated picks. Always excludes the cover photo (dedupe rule).
  let highlightUrls: string[]
  let highlightsUsePicks = false
  if (focusShots.length) {
    highlightUrls = focusShots.map((s) => s.url)
  } else {
    highlightUrls = data.picks ?? []
    highlightsUsePicks = highlightUrls.length > 0
  }
  highlightUrls = dedupe(highlightUrls.filter((u) => u && u !== hero))

  // Beat 5 — You & the couple.
  const coupleUrls = dedupe(coupleShots.map((s) => s.url).filter((u) => u && u !== hero))

  // Beat 6 — Everything else: the remaining good photos, one flat pool, never sub-sectioned.
  const featured = new Set<string>([hero, ...highlightUrls, ...coupleUrls])
  const wallShots = dedupeShots(restShots.filter((s) => s.url && !featured.has(s.url)))

  // Download pool = exactly what the page shows: hero + every gallery shot (+ picks when they
  // stand in as highlights), each carrying its courtesy flag. "Download all" drops courtesy.
  const poolMap = new Map<string, boolean>()
  const addPool = (url: string, courtesy = false) => {
    if (url) poolMap.set(url, (poolMap.get(url) ?? false) || courtesy)
  }
  addPool(hero)
  for (const g of gallery) for (const s of g.shots) addPool(s.url, !!s.courtesy)
  if (highlightsUsePicks) for (const u of highlightUrls) addPool(u)
  const pool: PoolPhoto[] = Array.from(poolMap, ([url, courtesy]) => ({ url, courtesy }))

  return { accent, accentInk, highlightUrls, coupleUrls, wallShots, pool }
}

/** Light solo Household (Ruling P2): Cover + the couple's picks + the member's own gallery. */
function deriveLight(data: Wrapped) {
  const base = derive(data)
  const hero = data.hero
  const pickUrls = dedupe((data.picks ?? []).filter((u) => u && u !== hero))
  const seen = new Set<string>([hero, ...pickUrls])
  const wallShots = dedupeShots((data.gallery ?? []).flatMap((g) => g.shots).filter((s) => s.url && !seen.has(s.url)))
  const pool: PoolPhoto[] = [{ url: hero }, ...pickUrls.map((url) => ({ url })), ...wallShots.map((s) => ({ url: s.url, courtesy: !!s.courtesy }))]
  return { ...base, pickUrls, wallShots, pool }
}

/** "../../img/l/X.jpg" → "../../img/face_<cid>.jpg" — same img root as the deck's photos. */
const faceFor = (hero: string, cid: number) => {
  const i = hero.indexOf("img/")
  return i < 0 ? "" : `${hero.slice(0, i)}img/face_${cid}.jpg`
}

/** Telemetry id for a Household deck: "h/<token>" from the path — never a member's slug. */
const householdId = () => {
  const parts = location.pathname.split("/").filter(Boolean)
  const i = parts.lastIndexOf("h")
  return i >= 0 && parts[i + 1] ? `h/${parts[i + 1]}` : "household"
}

/** A household.json that fails to parse or looks wrong is treated as absent (fall back to
 *  wrapped.json) — a static host may answer a missing file with an HTML page and a 200. */
async function fetchHousehold(): Promise<Household | null> {
  try {
    const r = await fetch("./household.json", { cache: "no-cache" })
    if (!r.ok) return null
    const h = (await r.json()) as Household
    return h && Array.isArray(h.members) && h.members.length > 0 ? h : null
  } catch {
    return null
  }
}

/** #/all → all photos (issue #39); #/map → the group mind map; anything else (incl. the bare
 *  #people anchor) → the deck. Note #/map is deliberately NOT "#people": that fragment is the
 *  beat-3 anchor and must keep resolving to the deck. */
const readView = (): View => {
  // the route part only — a Household deck carries its Selection as `?sel=…` after it
  const route = readHash(location.hash).route
  return /^#\/?all$/i.test(route) ? "all" : /^#\/?map$/i.test(route) ? "map" : "deck"
}

export default function Deck({ src = "./wrapped.json", rewrite = false, embedded = false, extras = null }: DeckProps) {
  const [state, setState] = useState<State>({ status: "loading" })
  const [lightbox, setLightbox] = useState<LightboxState | null>(null)
  const [view, setView] = useState<View>(readView)
  const [pool, setPool] = useState<PoolFile | null>(null)
  /** Household deck: the selected member cids (never empty); mirrored into the hash as ?sel= */
  const [selected, setSelected] = useState<number[]>([])
  const selectedRef = useRef<number[]>(selected)
  selectedRef.current = selected
  /** Household deck: pool-<cid>.json per member, fetched once each */
  const [pools, setPools] = useState<Record<number, PoolEntry[]>>({})
  const poolsAsked = useRef<Set<number>>(new Set())
  const deckScroll = useRef(0)
  /** member cids of a multi-member (non-light) Household, for the once-registered hash listener */
  const householdRef = useRef<number[] | null>(null)
  /** mirrors `view` for the hashchange listener, which is registered once and would
   *  otherwise close over the initial value. */
  const viewRef = useRef<View>(view)

  useEffect(() => {
    let cancelled = false
    setState({ status: "loading" })
    // Standalone decks try the Household file first; old per-guest dirs only have wrapped.json.
    // The unified admin app passes its own src and never looks for a Household.
    const standalone = !rewrite && src === "./wrapped.json"
    ;(standalone ? fetchHousehold() : Promise.resolve(null))
      .then((household) => {
        if (cancelled || !household) return household
        const cids = household.members.map((m) => m.cid)
        const multi = cids.length > 1 && household.mode !== "light"
        const sel = multi ? cleanSel(readHash(location.hash).sel, cids) : cids
        householdRef.current = multi ? cids : null
        if (multi) history.replaceState(history.state, "", writeHash(location.hash, sel))
        setSelected(sel)
        document.title = `${household.title}’s Wedding Wrapped · ${household.members[0].wrapped.couple}`
        setState({ status: "ready", data: household.members[0].wrapped, household })
        return household
      })
      .then(async (household) => {
        if (cancelled || household) return null
        const r = await fetch(src, { cache: "no-cache" })
        if (!r.ok) throw new Error(`HTTP ${r.status} loading wrapped.json`)
        return (await r.json()) as Wrapped
      })
      .then((raw) => {
        if (cancelled || raw === null) return
        if (!raw || typeof raw !== "object" || !("name" in raw)) {
          throw new Error("wrapped.json didn’t look like a Wrapped file")
        }
        const data = rewrite ? rewriteWrappedUrls(raw) : raw
        document.title = `${data.name}’s Wedding Wrapped · ${data.couple}`
        setState({ status: "ready", data, household: null })
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setState({ status: "error", message: err instanceof Error ? err.message : String(err) })
      })
    return () => {
      cancelled = true
    }
  }, [src, rewrite])

  // A `#people` deep link lands on beat 3 once the deck has actually rendered it.
  useEffect(() => {
    if (state.status === "ready") restorePeopleScroll()
  }, [state])

  // issue #39 — telemetry: arm the beacon once the deck is ready (no-op without config).
  // deck_open is the funnel denominator: a visit that never interacts is otherwise invisible.
  useEffect(() => {
    if (state.status === "ready") {
      initBeacon(state.data.telemetry, state.household ? householdId() : state.data.slug)
      track("deck_open")
    }
  }, [state])

  // hash sub-routes: #/all and #/map ↔ deck, preserving deck scroll across the round trip.
  useEffect(() => {
    const onHash = () => {
      // Park the deck's offset HERE, before the view swaps. Once the deck unmounts the page
      // collapses to the short view's height and the browser clamps scrollY to 0, so reading
      // it in the effect below (which runs after commit) always returned 0.
      if (viewRef.current === "deck") deckScroll.current = window.scrollY
      setView(readView())
      // Household deck: a `?sel=` in the new hash (back/forward, a pasted link) is adopted; a
      // hash without one (an in-deck link like #/all or #people) gets the current Selection
      // written back so the next back/forward or share keeps it.
      const cur = selectedRef.current
      const cids = householdRef.current
      if (!cids || cids.length < 2) return
      const want = readHash(location.hash).sel
      if (want) {
        const next = cleanSel(want, cids)
        if (next.join(",") !== cur.join(",")) setSelected(next)
      } else {
        history.replaceState(history.state, "", writeHash(location.hash, cur))
      }
    }
    window.addEventListener("hashchange", onHash)
    return () => window.removeEventListener("hashchange", onHash)
  }, [])
  useEffect(() => {
    viewRef.current = view
    if (view === "deck") {
      setSurface("deck")
      // Two frames: on the first the deck has committed but its cards haven't laid out, so the
      // document is still short and scrollTo would clamp to the top. Same reason the old
      // finder-return handshake needed a double rAF.
      requestAnimationFrame(() =>
        requestAnimationFrame(() => window.scrollTo(0, deckScroll.current))
      )
      return
    }
    window.scrollTo(0, 0)
    setSurface(view === "all" ? "all_photos" : "map")
    track(view === "all" ? "view_all_open" : "view_map_open")
  }, [view])
  const household = state.status === "ready" ? state.household : null
  const light = household?.mode === "light"
  useEffect(() => {
    // Household deck: pool-<cid>.json for each selected member, once each. Fetched as soon as
    // the deck is up (not on first #/all open) because the "See all N" CTA needs the union's
    // size; the files are a few KB each.
    if (!household || light) return
    for (const cid of selected) {
      if (poolsAsked.current.has(cid)) continue
      poolsAsked.current.add(cid)
      fetch(`./pool-${cid}.json`, { cache: "no-cache" })
        .then((r) => (r.ok ? (r.json() as Promise<PoolFile>) : null))
        .catch(() => null)
        // a missing/broken pool counts as empty, so one bad file can't stall All photos;
        // the others still pass the who ∩ Selection filter on their own
        .then((p) => setPools((cur) => ({ ...cur, [cid]: p && Array.isArray(p.photos) ? p.photos : [] })))
    }
  }, [household, light, selected])
  useEffect(() => {
    // lazy pool.json fetch, first time the all view is opened; silent failure keeps the CTA harmless
    if (household || view !== "all" || pool || state.status !== "ready") return
    fetch(src.replace(/wrapped\.json$/, "pool.json"), { cache: "no-cache" })
      .then((r) => (r.ok ? (r.json() as Promise<PoolFile>) : null))
      .then((p) => {
        if (!p) return
        if (rewrite) p.photos = p.photos.map((e) => ({ ...e, url: e.url.replace(/^\.\.\//, "/site/") }))
        setPool(p)
      })
      .catch(() => {})
  }, [household, view, pool, state, src, rewrite])

  const openLightbox = useCallback<OpenFn>((s, list) => {
    track("lightbox_open", s)
    setLightbox({ src: s, list })
  }, [])
  const closeLightbox = useCallback(() => setLightbox(null), [])
  const changeLightbox = useCallback((s: string) => {
    track("lightbox_nav", s)
    setLightbox((st) => (st ? { ...st, src: s } : st))
  }, [])

  // What the sections render: a Household's Selection view, or the plain per-guest Wrapped.
  const data = useMemo<Wrapped | null>(() => {
    if (state.status !== "ready") return null
    if (!state.household) return state.data
    const h = state.household
    return viewFor(h, light || selected.length === 0 ? h.members.map((m) => m.cid) : selected)
  }, [state, light, selected])
  const derived = useMemo(
    () => (data ? (light ? deriveLight(data) : { ...derive(data), pickUrls: [] as string[] }) : null),
    [data, light]
  )
  // All photos: the union of the selected members' pools, available once every one has loaded.
  const allEntries = useMemo<PoolEntry[] | null>(() => {
    if (!household) return pool ? pool.photos : null
    if (light || !selected.every((c) => pools[c])) return null
    return mergePools(pools, selected)
  }, [household, light, pool, pools, selected])
  const members = useMemo<PickerMember[]>(
    () => (household ? household.members.map((m) => ({ cid: m.cid, first: m.first, face: faceFor(m.wrapped.hero, m.cid) })) : []),
    [household]
  )
  const onToggle = useCallback((cid: number) => {
    const next = toggle(selectedRef.current, cid)
    if (next === selectedRef.current) return
    setSelected(next)
    history.replaceState(history.state, "", writeHash(location.hash, next))
  }, [])

  // Desktop keyboard nav: ↓ / ↑ / space / PageDown / PageUp jump between cards.
  useEffect(() => {
    if (state.status !== "ready") return
    const mq = window.matchMedia("(min-width: 1024px)")
    const onKey = (e: KeyboardEvent) => {
      if (!mq.matches) return
      if (e.metaKey || e.ctrlKey || e.altKey) return
      if (document.querySelector('[role="dialog"]')) return
      const t = e.target as HTMLElement | null
      if (t && /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) return
      if (t && /^(BUTTON|A)$/.test(t.tagName) && e.key === " ") return
      let dir = 0
      if (e.key === "ArrowDown" || e.key === "PageDown" || (e.key === " " && !e.shiftKey)) dir = 1
      else if (e.key === "ArrowUp" || e.key === "PageUp" || (e.key === " " && e.shiftKey)) dir = -1
      if (!dir) return

      const cards = Array.from(document.querySelectorAll<HTMLElement>("main.deck > section"))
      if (!cards.length) return
      let cur = 0
      cards.forEach((c, i) => {
        if (c.getBoundingClientRect().top <= 8) cur = i
      })
      const curEl = cards[cur]
      const r = curEl.getBoundingClientRect()
      const isFree = curEl.classList.contains("card--free")
      if (isFree) {
        if (dir > 0 && r.bottom > window.innerHeight + 8) return
        if (dir < 0 && r.top < -8) return
      }
      let target: HTMLElement | undefined
      if (dir > 0) target = cards[Math.min(cur + 1, cards.length - 1)]
      else target = r.top < -8 && !isFree ? curEl : cards[Math.max(cur - 1, 0)]
      if (!target || (target === curEl && dir > 0)) return
      e.preventDefault()
      target.scrollIntoView({ behavior: "smooth", block: "start" })
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [state.status])

  // A light Household has no map and no All photos: those routes fall back to the deck.
  const effView: View = light ? "deck" : view
  const picker =
    household && !light && members.length > 1 && derived ? (
      <MemberPicker
        members={members}
        selected={selected}
        onToggle={onToggle}
        accent={derived.accent}
        accentInk={derived.accentInk}
      />
    ) : null

  return (
    <DeckExtrasProvider value={embedded ? extras : null}>
      <div className={embedded ? "deck-root deck-root--embedded" : "deck-root"}>
        {state.status === "ready" && state.data.draft !== false && <DraftBanner embedded={embedded} />}

        {state.status === "loading" && (
          <Centered>
            <p className="h-serif text-[20px] text-muted">Loading your Wrapped…</p>
          </Centered>
        )}

        {state.status === "error" && (
          <Centered>
            <p className="h-serif text-[24px] text-ink">We couldn&rsquo;t load your Wrapped.</p>
            <p className="mt-3 max-w-[36ch] text-[14px] text-muted">
              {state.message}. Try refreshing — and if it keeps happening, tell Preethi &amp; Neel.
            </p>
          </Centered>
        )}

        {state.status === "ready" && data && derived && (
          <SelectionProvider
            // A new member Selection is a new set of visible photos: photo picks made for the
            // old one must not ride along into "Download N".
            resetKey={household ? selected.join(",") : undefined}
            pool={
              effView === "all" && allEntries
                ? allEntries.map((p): PoolPhoto => ({ url: p.url })) // courtesy excluded at build (#40)
                : derived.pool
            }
          >
            {effView === "map" ? (
              <main className="deck">
                {(() => {
                  const map = firstMap(data.groups)
                  return map ? (
                    <GroupMap map={map} onOpen={openLightbox} />
                  ) : (
                    // Reachable only by typing #/map on a deck with no map — never by a CTA.
                    <Centered>
                      <p className="h-serif text-[20px] text-muted">
                        There&rsquo;s no group map on this Wrapped.
                      </p>
                      <p className="mt-3">
                        <a href="#people" className="text-[14px] text-muted underline underline-offset-2">
                          ← your Wrapped
                        </a>
                      </p>
                    </Centered>
                  )
                })()}
              </main>
            ) : effView === "all" ? (
              <main className="deck">
                {picker}
                {allEntries ? (
                  <AllPhotos
                    entries={allEntries}
                    personName={data.name}
                    accent={derived.accent}
                    accentInk={derived.accentInk}
                  />
                ) : (
                  <Centered>
                    <p className="h-serif text-[20px] text-muted">Gathering every photo…</p>
                  </Centered>
                )}
                {/* clearance for the fixed download bar */}
                <div aria-hidden="true" className="h-24 lg:h-28" />
              </main>
            ) : light ? (
              <main className="deck">
                {/* Light solo Household: Cover + the couple's picks + their own gallery only */}
                <Cover data={data} />
                <FeaturedGrid
                  eyebrow={`Picked by ${data.couple}`}
                  urls={derived.pickUrls}
                  personName={data.name}
                  accent={derived.accent}
                  accentInk={derived.accentInk}
                  onOpen={openLightbox}
                />
                <PhotoWall
                  shots={derived.wallShots}
                  personName={data.name}
                  accent={derived.accent}
                  accentInk={derived.accentInk}
                />
                <div aria-hidden="true" className="h-24 lg:h-28" />
              </main>
            ) : (
              <main className="deck">
                {/* 0 · whose Wrapped (multi-member Household only) */}
                {picker}
                {/* 1 · Cover */}
                <Cover data={data} />
                {/* 2 · The Number (easter-egg button) */}
                <TheNumber data={data} accent={derived.accent} />
                {/* 3 · Photos with people */}
                <YourPeople data={data} accent={derived.accent} accentInk={derived.accentInk} />
                {/* 4 · Your highlights */}
                <FeaturedGrid
                  eyebrow="Your highlights"
                  urls={derived.highlightUrls}
                  personName={data.name}
                  accent={derived.accent}
                  accentInk={derived.accentInk}
                  onOpen={openLightbox}
                />
                {/* 5 · You & the couple */}
                <FeaturedGrid
                  eyebrow="You & the couple"
                  urls={derived.coupleUrls}
                  personName={data.name}
                  accent={derived.accent}
                  accentInk={derived.accentInk}
                  onOpen={openLightbox}
                  gridClass="grid-cols-2 sm:grid-cols-3"
                  aspectClass="aspect-[4/3]"
                />
                {/* 6 · Everything else (selectable) */}
                <PhotoWall
                  shots={derived.wallShots}
                  personName={data.name}
                  accent={derived.accent}
                  accentInk={derived.accentInk}
                  nPool={household ? allEntries?.length : data.n_pool}
                />
                {/* clearance for the fixed download bar */}
                <div aria-hidden="true" className="h-24 lg:h-28" />
              </main>
            )}

            {/* 7 · Persistent download bar — deck and all-photos only.
                The map's photos open the lightbox; they are not selectable tiles (selection
                there is the backlog's "select-to-download in group explorers"). Rendering the
                bar over the map would advertise "Tap photos to select" above photos that
                can't be, and offer "Download all N" for the deck's N, not the N on screen. */}
            {effView !== "map" && (
              <DownloadBar slug={data.slug || "wedding-wrapped"} accent={derived.accent} accentInk={derived.accentInk} />
            )}

            {/* Inside the provider on purpose: the lightbox selects too (#42), and
                useSelection() returns null anywhere outside it. */}
            <Lightbox
              state={lightbox}
              onClose={closeLightbox}
              onChange={changeLightbox}
              accent={derived.accent}
              accentInk={derived.accentInk}
            />
          </SelectionProvider>
        )}
      </div>
    </DeckExtrasProvider>
  )
}

/** Small high-contrast pill in the top-right corner (toggle with `draft:false` in wrapped.json). */
function DraftBanner({ embedded }: { embedded: boolean }) {
  return (
    <div
      className="draft-pill"
      role="note"
      title="Faces auto-grouped, names provisional, video clips pending"
      style={{ top: embedded ? "calc(var(--nav-h, 48px) + 10px)" : "max(10px, env(safe-area-inset-top))" }}
    >
      DRAFT
    </div>
  )
}

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <div className="deck flex min-h-[100dvh] flex-col items-center justify-center px-6 text-center">
      {children}
    </div>
  )
}
