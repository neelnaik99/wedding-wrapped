import Card from "./Card"
import { Tile } from "./PhotoWall"
import type { OpenFn } from "./Selection"
import { cn } from "@/lib/utils"

interface FeaturedGridProps {
  eyebrow: string
  /** full-res photo urls, in display order */
  urls: string[]
  personName: string
  /** guest accent for the selected ring + check chip */
  accent: string
  accentInk: string
  onOpen: OpenFn
  /** tailwind grid-cols + tile aspect (defaults suit "Your highlights") */
  gridClass?: string
  aspectClass?: string
}

/**
 * The featured beats — 4 "Your highlights" and 5 "You & the couple". `derive()` calls this
 * same set (hero + highlights + couple) `featured`, hence the name.
 *
 * Every tile is selectable, exactly like the wall — DESIGN § Selection & download: "Every
 * photo a guest can see is takeable … one habit, everywhere". These beats were view-only
 * until #42, which had made the guest's own best photos the only ones they couldn't take
 * individually. The corner control on each tile opens the lightbox for a closer look.
 *
 * Differs from PhotoWall (beat 6) in what it is FOR, not just how it looks: a short curated
 * set shown whole, at a beat-specific aspect, with a lightbox door — versus one flat pool of
 * square tiles behind a fold. Captions are event names only, never a clock (DESIGN § no clock
 * on guest surfaces).
 */
export default function FeaturedGrid({
  eyebrow,
  urls,
  personName,
  accent,
  accentInk,
  onOpen,
  gridClass = "grid-cols-2 sm:grid-cols-3 lg:grid-cols-4",
  aspectClass = "aspect-[4/5]",
}: FeaturedGridProps) {
  if (urls.length === 0) return null
  return (
    <Card free top>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <p className="eyebrow">{eyebrow}</p>
        <p className="text-[13px] text-muted">tap to select — take the ones you love</p>
      </div>
      <div className={cn("mt-4 grid gap-2 lg:gap-3", gridClass)}>
        {urls.map((src, i) => (
          <Tile
            key={`${i}-${src}`}
            shot={{ url: src }}
            personName={personName}
            accent={accent}
            accentInk={accentInk}
            aspectClass={aspectClass}
            onExpand={() => onOpen(src, urls)}
          />
        ))}
      </div>
    </Card>
  )
}
