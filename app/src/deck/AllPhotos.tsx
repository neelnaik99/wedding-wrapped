import { useState } from "react"
import Card from "./Card"
import { Tile } from "./PhotoWall"
import { track } from "./beacon"
import type { PoolEntry } from "@/types"

const FOLD = 30 // first screensful; the rest hides behind "Show all"

interface AllPhotosProps {
  entries: PoolEntry[]
  personName: string
  accent: string
  accentInk: string
}

/**
 * The all-photos view (issue #39) — every photo the guest appears in, reached via #/all.
 * shown + skipped render as one flat grid; below_bar sits behind a second fold. Courtesy
 * exclusion happened at build time, so everything here is safe to show and download.
 * Selections made here are the ranker's report card: a pick from the skipped or below_bar
 * zone is a correction signal the deck alone could never produce.
 */
export default function AllPhotos({ entries, personName, accent, accentInk }: AllPhotosProps) {
  const [expanded, setExpanded] = useState(false)
  const [showBlurry, setShowBlurry] = useState(false)

  const main = entries.filter((p) => p.zone !== "below_bar")
  const blurry = entries.filter((p) => p.zone === "below_bar")
  const shownMain = expanded ? main : main.slice(0, FOLD)
  const hidden = main.length - shownMain.length

  return (
    <Card free top>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <p className="eyebrow">All your photos</p>
        <p className="text-[13px] text-muted">
          every photo you&rsquo;re in — tap to select, download below
        </p>
        <a href="#" className="ml-auto text-[13px] text-muted underline underline-offset-2 hover:text-ink">
          ← your Wrapped
        </a>
      </div>

      <div className="mt-4 grid grid-cols-3 gap-2 sm:grid-cols-4 lg:grid-cols-5 lg:gap-3">
        {shownMain.map((p, i) => (
          <Tile key={`${i}-${p.url}`} shot={{ url: p.url }} personName={personName} accent={accent} accentInk={accentInk} />
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
            <span className="pill pill--action">Show all {main.length}</span>
          </button>
        </div>
      )}

      {blurry.length > 0 && (
        <div className="mt-8">
          {!showBlurry ? (
            <div className="flex justify-center">
              <button
                type="button"
                className="hit"
                onClick={() => {
                  setShowBlurry(true)
                  track("show_blurry_expand")
                }}
              >
                <span className="pill pill--action">Show everything — even the blurry ones ({blurry.length})</span>
              </button>
            </div>
          ) : (
            <>
              <p className="text-[13px] text-muted">The ones our filters weren&rsquo;t sure about — sometimes those are the keepers.</p>
              <div className="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-4 lg:grid-cols-5 lg:gap-3">
                {blurry.map((p, i) => (
                  <Tile key={`b-${i}-${p.url}`} shot={{ url: p.url }} personName={personName} accent={accent} accentInk={accentInk} />
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </Card>
  )
}
