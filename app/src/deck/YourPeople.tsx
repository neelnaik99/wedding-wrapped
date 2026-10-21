import Card from "./Card"
import FaceImg from "./FaceImg"
import { useDeckExtras } from "./DeckContext"
import { firstMap } from "./GroupMap"
import { cn } from "@/lib/utils"
import type { CoStar, Wrapped } from "@/types"

const fmt = (n: number) => n.toLocaleString("en-US")
const MAX_CHIPS = 8

/**
 * Beat 3 — "Photos with people". Leads with the guest's most-photographed-with person as a
 * stat, then the remaining ties as face chips, then one CTA into their mind map. Gates on
 * having partners or groups; degrades to a chips-only row when no map exists (DESIGN
 * connection gating).
 */
export default function YourPeople({
  data,
  accent,
  accentInk,
}: {
  data: Wrapped
  accent: string
  accentInk: string
}) {
  const costars = data.costars ?? []
  const groups = (data.groups ?? []).filter((g) => (g.members?.length ?? 0) > 0)
  const hasMap = !!firstMap(data.groups)
  if (costars.length === 0 && groups.length === 0) return null

  // The headline stat is the top *guest* tie. costars is already sorted by shared-photo count
  // desc at build time, but it includes the couple — and the couple are in nearly everyone's
  // photos, so they'd win this stat for almost every guest and say nothing. Beat 5 is already
  // theirs; here we want the person the guest's own weekend revolved around.
  const top = costars.find((c) => c.labeled && !c.couple) ?? null
  const rest = costars.filter((c) => c !== top)

  const shown = rest.slice(0, MAX_CHIPS)
  const more = rest.length - shown.length

  return (
    <Card top id="people">
      <p className="eyebrow mb-2">Photos with people</p>
      <h2 className="h-serif title">Who you were photographed with</h2>

      {top && <TopTie c={top} accent={accent} />}

      {shown.length > 0 && (
        <ul className="mt-6 flex flex-wrap gap-2">
          {shown.map((c) => (
            <Chip key={c.cid} c={c} />
          ))}
          {more > 0 && (
            <li className="flex items-center rounded-full border border-dashed border-[#9c8568] px-3.5 py-1.5 text-[13px] text-muted">
              +{more} more
            </li>
          )}
        </ul>
      )}

      {hasMap && (
        <div className="mt-7">
          <a
            href="#/map"
            className="inline-flex min-h-[44px] items-center rounded-full px-6 text-[15px] font-semibold shadow-[0_1px_2px_rgba(0,0,0,0.35)] focus:outline-none focus-visible:ring-2 focus-visible:ring-haldi"
            style={{ background: accent, color: accentInk }}
          >
            Find your photos with anyone →
          </a>
        </div>
      )}
    </Card>
  )
}

/**
 * The "most photographed with" stat — DESIGN's stat-tile idiom (mono eyebrow, serif numeral
 * tinted with the guest accent), anchored by the other person's face.
 */
function TopTie({ c, accent }: { c: CoStar; accent: string }) {
  return (
    <div className="mt-6 flex items-center gap-4 rounded-2xl bg-card p-4 ring-1 ring-white/10">
      <FaceImg
        src={c.img}
        name={c.name}
        className="h-16 w-16 shrink-0 rounded-full object-cover text-[24px] ring-2 ring-[#9c8568] lg:h-20 lg:w-20"
      />
      <div className="min-w-0">
        <p className="eyebrow">Most photographed with</p>
        <p className="h-serif mt-1 text-[22px] leading-tight text-ink lg:text-[26px]">
          You and {c.name.split(" ")[0]} were in{" "}
          <span style={{ color: accent }}>{fmt(c.n)}</span> photos together
        </p>
      </div>
    </div>
  )
}

/** A face + name + count chip. Non-interactive display; wrapped in the admin FaceMenu when present. */
function Chip({ c }: { c: CoStar }) {
  const extras = useDeckExtras()
  const named = !!extras?.names[c.cid] || c.labeled
  const name = extras?.names[c.cid] ?? (c.labeled ? c.name : "a friend")
  const inner = (
    <span className="flex items-center gap-2 rounded-full bg-tile py-1 pl-1 pr-3 ring-1 ring-white/10">
      <FaceImg src={c.img} name={name} className="h-8 w-8 shrink-0 rounded-full object-cover text-[13px]" />
      <span className={cn("text-[14px] leading-tight", named ? "text-ink" : "italic text-muted")}>
        {name} <span className="not-italic text-muted">· {fmt(c.n)}</span>
      </span>
    </span>
  )
  return (
    <li>
      {extras ? (
        <extras.FaceMenu cid={c.cid} name={c.labeled ? c.name : null} asChild>
          {inner}
        </extras.FaceMenu>
      ) : (
        inner
      )}
    </li>
  )
}
