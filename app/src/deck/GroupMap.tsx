import { useCallback, useLayoutEffect, useMemo, useRef, useState } from "react"
import Card from "./Card"
import FaceImg, { initialOf } from "./FaceImg"
import { track } from "./beacon"
import type { GroupMap as GroupMapData, MapPhoto } from "@/types"
import type { OpenFn } from "./Selection"

/** Below this the ring wraps onto an upper-270° arc so 3/9 o'clock labels stay on-canvas. */
const NARROW = 560
/** The arc the narrow projection spreads members across. */
const SPAN = Math.PI * 1.5

const NIGHT_EDGE = "#8a7561" // DESIGN § Guest ego graph — neutral edge, ≥3:1 on night surfaces
const NIGHT_RING = "#9c8568" // unselected selectable outline
const HALDI = "#f2c14e"

type Pos = Record<number, [number, number]>

/**
 * Beat 3's mind map (`#/map`) — the guest's ego graph plus the combination photo finder,
 * one surface. Formerly a standalone page at `/x<token>/`; folding it in-deck makes the
 * wrapped link the only URL a guest ever receives.
 *
 * The viewer is always the centre node. Tapping a member toggles them into the combination
 * and the grid below filters live to photos containing the viewer + everyone selected —
 * same input, same picture (DESIGN.md § Guest ego graph). Geometry, node radii and edge
 * stroke widths are all baked at build time by `group_explorer.member_map_payload`; this
 * component only reprojects the rings for the current width.
 *
 * Privacy: `map.photos` is guaranteed viewer-inclusive at build time. There is no filtering
 * to do here and nothing to leak — pairings without the viewer never reach the client.
 */
export default function GroupMap({
  map,
  onOpen,
}: {
  map: GroupMapData
  onOpen: OpenFn
}) {
  const [sel, setSel] = useState<number[]>([])
  const [width, setWidth] = useState(0)
  const boxRef = useRef<HTMLDivElement>(null)

  const by = useMemo(
    () => Object.fromEntries(map.members.map((m) => [m.cid, m])),
    [map.members]
  )
  const me = by[map.me]

  // Track the rendered width so the projection can switch between wide and the narrow arc.
  // Measure the wrapping div, never the <svg>: an svg root is replaced content, and
  // ResizeObserver silently never fires for it (not even the initial callback), which
  // would pin the map to the wide projection forever on a phone.
  useLayoutEffect(() => {
    const el = boxRef.current
    if (!el) return
    const measure = () => setWidth(el.clientWidth || 0)
    measure()
    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", measure)
      return () => window.removeEventListener("resize", measure)
    }
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  // Deterministic reprojection of the build-time rings. Wide keeps the canonical full circle;
  // narrow fans members across the upper 270° so their labels stay inside the canvas at 390px.
  const { pos, W, H } = useMemo((): { pos: Pos; W: number; H: number } => {
    const narrow = width > 0 && width < NARROW
    const Rmax = map.ringR.length ? map.ringR[map.ringR.length - 1] : 155
    const p: Pos = {}
    let w: number, h: number, cx: number, cy: number

    if (!narrow) {
      w = map.W
      h = map.H
      cx = w / 2
      cy = h / 2
      map.rings.forEach((ring, ri) => {
        const R = map.ringR[ri]
        const n = ring.length || 1
        const rot = ri === 1 ? Math.PI / n : 0 // offset the outer ring between inner nodes
        ring.forEach((c, i) => {
          const th = (2 * Math.PI * i) / n + rot // clockwise from 12 o'clock
          p[c] = [cx + R * Math.sin(th), cy - R * Math.cos(th)]
        })
      })
    } else {
      w = 2 * (Rmax + map.viewR + 44)
      h = 2 * (Rmax + map.viewR + 70)
      cx = w / 2
      cy = h / 2 - 6
      map.rings.forEach((ring, ri) => {
        const R = map.ringR[ri]
        const n = ring.length || 1
        ring.forEach((c, i) => {
          let th: number
          if (n === 1) {
            th = 0
          } else {
            const half = Math.ceil((n - 1) / 2) || 1
            const step = SPAN / 2 / half
            const k = Math.ceil(i / 2)
            th = i === 0 ? 0 : (i % 2 ? 1 : -1) * k * step
          }
          p[c] = [cx + R * Math.sin(th), cy - R * Math.cos(th)]
        })
      })
    }
    p[map.me] = [cx, cy]
    return { pos: p, W: w, H: h }
  }, [map, width])

  // The current combination: photos containing the viewer AND everyone selected, plus the
  // per-member co-occurrence counts within that result (the numbers under each face).
  const { hits, counts } = useMemo(() => {
    const h = map.photos.filter((p) => sel.every((c) => p.mem.includes(c)))
    const n: Record<number, number> = {}
    for (const p of h) for (const c of p.mem) n[c] = (n[c] ?? 0) + 1
    return { hits: h, counts: n }
  }, [map.photos, sel])

  const toggle = useCallback((cid: number) => {
    setSel((s) => {
      const next = s.includes(cid) ? s.filter((x) => x !== cid) : s.concat([cid])
      track(next.length > s.length ? "map_node_select" : "map_node_deselect")
      return next
    })
  }, [])

  const lightboxList = useMemo(() => hits.map((p) => p.l || p.s), [hits])
  const captionOf = useCallback(
    (p: MapPhoto) =>
      p.mem
        .filter((c) => by[c])
        .map((c) => (c === map.me ? "You" : by[c].first))
        .join(", "),
    [by, map.me]
  )

  // A member is on the map when they're you, selected, or still reachable from the current
  // combination — so the graph narrows as the combination tightens, never showing dead ends.
  const visible = useCallback(
    (c: number) => c === map.me || sel.includes(c) || (counts[c] ?? 0) > 0,
    [map.me, sel, counts]
  )
  const active = useMemo(() => new Set([map.me, ...sel]), [map.me, sel])

  return (
    <Card free top>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <p className="eyebrow">{map.name}</p>
        <p className="text-[13px] text-muted">
          every photo here includes you — tap faces to build a combination
        </p>
        <a
          href="#people"
          className="ml-auto text-[13px] text-muted underline underline-offset-2 hover:text-ink"
        >
          ← your Wrapped
        </a>
      </div>

      <div ref={boxRef} className="mt-4">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="group"
        aria-label={`${map.name} — tap or press Enter on a face to filter photos`}
        className="block h-auto w-full touch-manipulation"
      >
        {map.edges.map(([a, b, , sw]) => {
          const pa = pos[a]
          const pb = pos[b]
          if (!pa || !pb) return null
          if (!(visible(a) && visible(b))) return null
          if (!(active.has(a) || active.has(b))) return null // only edges touching you or your selection
          const hot = active.has(a) && active.has(b)
          return (
            <line
              key={`${a}-${b}`}
              x1={pa[0]}
              y1={pa[1]}
              x2={pb[0]}
              y2={pb[1]}
              stroke={hot ? HALDI : NIGHT_EDGE}
              strokeOpacity={0.85}
              strokeLinecap="round"
              strokeWidth={hot ? sw + 1.5 : sw}
            />
          )
        })}

        {map.members.map((m) => {
          if (!visible(m.cid)) return null
          const p = pos[m.cid]
          if (!p) return null
          const isMe = m.cid === map.me
          const [x, y] = p
          const r = isMe ? map.viewR : m.r || 28
          const picked = sel.includes(m.cid)
          const n = counts[m.cid] ?? 0
          return (
            <g
              key={m.cid}
              className={isMe ? undefined : "cursor-pointer focus:outline-none"}
              role={isMe ? undefined : "button"}
              tabIndex={isMe ? undefined : 0}
              aria-pressed={isMe ? undefined : picked}
              aria-label={
                isMe ? undefined : `${m.first} — ${n} photos with you — toggle into combination`
              }
              onClick={isMe ? undefined : () => toggle(m.cid)}
              onKeyDown={
                isMe
                  ? undefined
                  : (e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault()
                        toggle(m.cid)
                      }
                    }
              }
            >
              <clipPath id={`gm-clip-${m.cid}`}>
                <circle cx={x} cy={y} r={r} />
              </clipPath>
              <circle cx={x} cy={y} r={r + 2} fill="#2c231f" />
              {m.face ? (
                <image
                  href={m.face}
                  x={x - r}
                  y={y - r}
                  width={2 * r}
                  height={2 * r}
                  clipPath={`url(#gm-clip-${m.cid})`}
                  preserveAspectRatio="xMidYMid slice"
                />
              ) : (
                // no photo of this person includes a member of the Household: their initial
                <text
                  x={x}
                  y={y}
                  textAnchor="middle"
                  dominantBaseline="central"
                  fontSize={Math.max(12, r * 0.9)}
                  fontWeight={600}
                  fill="#f3ece1"
                  aria-hidden="true"
                >
                  {initialOf(m.first || m.name)}
                </text>
              )}
              <circle
                cx={x}
                cy={y}
                r={r + 1}
                fill="none"
                stroke={isMe || picked ? HALDI : NIGHT_RING}
                strokeWidth={isMe ? 4.5 : picked ? 5 : 2.5}
              />
              <text
                x={x}
                y={y + r + 15}
                textAnchor="middle"
                fontSize={12}
                fill={isMe ? HALDI : "#f3ece1"}
                paintOrder="stroke"
                stroke="#221b18"
                strokeWidth={3}
              >
                {isMe ? "You" : m.first}
              </text>
              {!isMe && n > 0 && (
                <text x={x} y={y + r + 29} textAnchor="middle" fontSize={11} fill="#b3a08f">
                  {n}
                  {sel.length ? " together" : " with you"}
                </text>
              )}
            </g>
          )
        })}
      </svg>
      </div>

      <div className="mt-2 flex min-h-[44px] flex-wrap items-center gap-2">
        <span className="flex items-center gap-1.5 rounded-full border border-[#9c8568] bg-card py-1 pl-1 pr-2.5 text-[13px]">
          <FaceImg src={me?.face} name={me?.first ?? ""} className="h-7 w-7 rounded-full object-cover text-[12px]" />
          <b>You</b>
        </span>
        {sel.map((c) => (
          <span
            key={c}
            className="flex items-center gap-1.5 rounded-full border border-hairline bg-card py-1 pl-1 pr-1 text-[13px]"
          >
            <FaceImg src={by[c]?.face} name={by[c]?.first ?? ""} className="h-7 w-7 rounded-full object-cover text-[12px]" />
            <b>{by[c]?.first}</b>
            <button
              type="button"
              onClick={() => toggle(c)}
              aria-label={`Remove ${by[c]?.first} from combination`}
              className="inline-flex h-7 w-7 items-center justify-center rounded-full text-[16px] font-bold leading-none text-haldi focus:outline-none focus-visible:ring-2 focus-visible:ring-haldi"
            >
              ×
            </button>
          </span>
        ))}
        {sel.length > 0 && (
          <button
            type="button"
            onClick={() => setSel([])}
            className="min-h-[28px] min-w-[44px] rounded-lg border border-hairline px-3 py-1.5 text-[13px] text-muted focus:outline-none focus-visible:ring-2 focus-visible:ring-haldi"
          >
            clear
          </button>
        )}
      </div>

      <p aria-live="polite" className="my-2 text-[13px] text-muted">
        {sel.length
          ? `${hits.length} photo${hits.length === 1 ? "" : "s"} of you with ${sel
              .map((c) => by[c]?.first)
              .join(" + ")}`
          : `all ${hits.length} photos of you with this group (including a few of just you)`}
      </p>

      <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-3 lg:grid-cols-4">
        {hits.map((p) => {
          const cap = captionOf(p)
          const src = p.l || p.s
          return (
            <figure
              key={p.id}
              tabIndex={0}
              role="button"
              aria-label={`Photo with ${cap} — open larger`}
              onClick={() => onOpen(src, lightboxList)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault()
                  onOpen(src, lightboxList)
                }
              }}
              className="group relative m-0 aspect-square cursor-zoom-in overflow-hidden rounded-lg bg-tile focus:outline-none focus-visible:ring-2 focus-visible:ring-haldi"
            >
              <img src={p.s} alt="" loading="lazy" className="h-full w-full object-cover" />
              <figcaption className="pointer-events-none absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/75 to-transparent px-2 pb-1.5 pt-3.5 text-[11px] text-white opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">
                {cap}
              </figcaption>
            </figure>
          )
        })}
      </div>
    </Card>
  )
}

/** Pick the map the guest reaches from beat 3 — the first group that has one. */
export function firstMap(groups: { map?: GroupMapData | null }[] | undefined): GroupMapData | null {
  return groups?.find((g) => g.map)?.map ?? null
}
