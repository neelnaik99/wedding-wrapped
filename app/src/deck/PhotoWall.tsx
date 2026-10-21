import { useState } from "react"
import { Maximize2 } from "lucide-react"
import Card from "./Card"
import { CheckChip, smallUrl, useSelection } from "./Selection"
import { cn } from "@/lib/utils"
import { track } from "./beacon"
import type { Shot } from "@/types"

/** "…/img/l/HALDI/NP-1.jpg" → "Haldi" (event name from the folder, for captions/labels). */
export function eventOf(src: string): string {
  const m = src.match(/\/img\/[ls]\/([^/]+)\//)
  if (!m) return ""
  return decodeURIComponent(m[1]).toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase())
}

const FOLD = 15 // first screenful (3 rows × 5 on wide); the rest hides behind "Show all"

interface PhotoWallProps {
  shots: Shot[]
  personName: string
  accent: string
  accentInk: string
  /** total photos in pool.json — renders the "See all N" CTA to #/all when present (issue #39) */
  nPool?: number
}

/**
 * Beat 6 — "Everything else". One flat pool of the remaining good photos, never
 * sub-sectioned by event. Every tile toggles selection (whole tile is the hit target,
 * per DESIGN § Selection & download / a11y #24); the 24px check chip is visual state only.
 */
export default function PhotoWall({ shots, personName, accent, accentInk, nPool }: PhotoWallProps) {
  const [expanded, setExpanded] = useState(false)
  if (shots.length === 0) return null
  const shown = expanded ? shots : shots.slice(0, FOLD)
  const hidden = shots.length - shown.length

  return (
    <Card free top>
      <div className="flex items-baseline gap-3">
        <p className="eyebrow">Everything else</p>
        <p className="text-[13px] text-muted">tap to select — take the ones you love</p>
      </div>

      <div className="mt-4 grid grid-cols-3 gap-2 sm:grid-cols-4 lg:grid-cols-5 lg:gap-3">
        {shown.map((shot, i) => (
          <Tile key={`${i}-${shot.url}`} shot={shot} personName={personName} accent={accent} accentInk={accentInk} />
        ))}
      </div>

      {hidden > 0 && (
        <div className="mt-4 flex justify-center">
          <button
            type="button"
            className="hit"
            onClick={() => {
              setExpanded(true)
              track("show_all_expand")
            }}
          >
            <span className="pill pill--action">Show all {shots.length}</span>
          </button>
        </div>
      )}

      {/* issue #39 — the door to the full pool (only decks built with pool.json have it) */}
      {nPool != null && nPool > 0 && (
        <div className="mt-5 flex justify-center">
          <a href="#/all" className="hit">
            <span className="pill pill--action">See all {nPool} photos you&rsquo;re in →</span>
          </a>
        </div>
      )}
    </Card>
  )
}

/**
 * The one selectable photo tile, used by every grid that renders photos: the wall (beat 6),
 * the featured beats (4 and 5, via FeaturedGrid) and the all-photos view. Whole tile
 * toggles selection — DESIGN § Selection & download, "one habit, everywhere" (#42).
 *
 * Only reads url/fx/fy, so pool.json entries (issue #39) render through it too.
 *
 * `onExpand` adds a corner door to the lightbox for the beats that want a closer look. It
 * is a SIBLING of the select button, never a child: a <button> inside a <button> is invalid
 * HTML and collapses to a single control for screen readers.
 */
export function Tile({
  shot,
  personName,
  accent,
  accentInk,
  aspectClass = "aspect-square",
  onExpand,
}: {
  shot: Pick<Shot, "url" | "fx" | "fy">
  personName: string
  accent: string
  accentInk: string
  /** tile aspect — square on the wall, taller on the highlight beats */
  aspectClass?: string
  /** when set, a 44px corner control opens the lightbox instead of toggling selection */
  onExpand?: () => void
}) {
  const sel = useSelection()
  const selected = sel?.has(shot.url) ?? false
  const ev = eventOf(shot.url)
  const label = `${personName}${ev ? ` — ${ev}` : ""}`
  return (
    <div className={cn("relative", aspectClass)}>
      <button
        type="button"
        onClick={() => sel?.toggle(shot.url)}
        aria-pressed={selected}
        aria-label={`${selected ? "Deselect" : "Select"} photo${ev ? `: ${label}` : ""}`}
        className="group relative block h-full w-full overflow-hidden rounded-lg bg-tile focus:outline-none focus-visible:ring-2 focus-visible:ring-haldi"
        style={selected ? { boxShadow: `0 0 0 2px ${accent}` } : undefined}
      >
        <img
          src={smallUrl(shot.url)}
          alt=""
          loading="lazy"
          decoding="async"
          className="h-full w-full object-cover"
          style={shot.fx != null ? { objectPosition: `${shot.fx}% ${shot.fy}%` } : undefined}
          onError={(e) => {
            const im = e.currentTarget
            if (im.dataset.fallback) return
            im.dataset.fallback = "1"
            im.src = shot.url
          }}
        />
        {/* 24px check chip, top-right — visual state only (the whole tile is the hit target). */}
        <CheckChip selected={selected} accent={accent} accentInk={accentInk} className="absolute right-2 top-2" />
      </button>

      {onExpand && (
        <button
          type="button"
          onClick={onExpand}
          aria-label={`View photo full screen${ev ? `: ${label}` : ""}`}
          className="absolute bottom-0 right-0 flex h-11 w-11 items-center justify-center rounded-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-haldi"
        >
          <span
            aria-hidden="true"
            className="flex h-7 w-7 items-center justify-center rounded-full bg-black/55 text-ink ring-1 ring-white/20 backdrop-blur-sm transition-colors hover:bg-black/75"
          >
            <Maximize2 className="h-3.5 w-3.5" />
          </span>
        </button>
      )}
    </div>
  )
}
