import { useEffect, useRef, useState } from "react"
import { saveOne, useSelection, zipDownload } from "./Selection"
import { track } from "./beacon"

interface DownloadBarProps {
  slug: string
  /** guest accent for the primary button fill (already contrast-clamped at build time) */
  accent: string
  /** ink that reads on the accent (build-time chosen; dark by default) */
  accentInk: string
}

type Job = { kind: "all" | "sel"; done: number; total: number } | null

/**
 * Persistent, bottom-pinned download bar (beat 7). Exactly two actions per DESIGN
 * § Selection & download: "Download all N" (secondary) and "Download N" (primary).
 * The live count element carries aria-live so screen readers hear selection changes.
 */
export default function DownloadBar({ slug, accent, accentInk }: DownloadBarProps) {
  const sel = useSelection()
  const [job, setJob] = useState<Job>(null)
  const [note, setNote] = useState<string | null>(null)
  // Clearing the selection disables the primary button under the caret, so hand focus to the
  // secondary one — a keyboard guest must not be dropped onto <body> (DESIGN § Selection &
  // download). It has to wait for the job to clear: "Download all" is disabled while busy.
  const allRef = useRef<HTMLButtonElement>(null)
  const refocus = useRef(false)
  useEffect(() => {
    if (job || !refocus.current) return
    refocus.current = false
    allRef.current?.focus()
  }, [job])
  if (!sel) return null

  const allN = sel.downloadAll.length
  const selN = sel.count
  const busy = job !== null

  async function run(kind: "all" | "sel") {
    if (!sel || busy) return
    const urls = kind === "all" ? sel.downloadAll : sel.selected
    if (urls.length === 0) return
    setNote(null)
    // #39 — download_all is a session marker (one bulk click, no per-photo opinion);
    // per-photo intent was already captured by the select_on events.
    track(kind === "all" ? "download_all" : urls.length === 1 ? "download_one" : "download_selected",
          urls.length === 1 ? urls[0] : undefined)
    try {
      let failed = 0
      if (kind === "sel" && urls.length === 1) {
        setJob({ kind, done: 0, total: 1 })
        await saveOne(urls[0])
      } else {
        setJob({ kind, done: 0, total: urls.length })
        failed = await zipDownload(
          urls,
          `${slug}-photos${kind === "sel" ? `-${urls.length}` : ""}.zip`,
          (done, total) => setJob({ kind, done, total })
        )
        if (failed)
          setNote(`${failed} photo${failed === 1 ? "" : "s"} couldn’t be fetched and ${failed === 1 ? "was" : "were"} skipped.`)
      }
      // A clean "Download N" consumes the selection: count back to 0, chips off, aria-live
      // announces the reset. Never on a throw or a partial zip — the guest needs the
      // selection to retry. clear() sets state directly, so no select_off beacons fire (#39).
      if (kind === "sel" && failed === 0) {
        sel.clear()
        refocus.current = true
      }
    } catch (e) {
      setNote(`Couldn’t build the download: ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setJob(null)
    }
  }

  const allLabel = job?.kind === "all" ? `${job.done} / ${job.total}…` : `Download all ${allN}`
  const selLabel = job?.kind === "sel" ? `${job.done} / ${job.total}…` : `Download ${selN}`

  return (
    <div className="fixed inset-x-0 bottom-0 z-40 border-t border-hairline bg-card/95 backdrop-blur-sm">
      <div className="mx-auto flex max-w-[1280px] items-center gap-3 px-5 py-3 lg:px-12">
        <p className="min-w-0 flex-1 truncate text-[13px] text-muted" aria-live="polite">
          {selN > 0 ? `${selN} selected` : "Tap photos to select"}
          {note && <span className="ml-2 text-muted/80">· {note}</span>}
        </p>
        <div className="flex shrink-0 items-center gap-2">
          <button
            ref={allRef}
            type="button"
            onClick={() => void run("all")}
            disabled={busy || allN === 0}
            aria-label={`Download all ${allN} photos`}
            className="rounded-full border border-white/25 px-4 py-2.5 text-[14px] font-semibold text-ink hover:border-haldi focus:outline-none focus-visible:ring-2 focus-visible:ring-haldi disabled:opacity-50 lg:px-5"
          >
            {allLabel}
          </button>
          <button
            type="button"
            onClick={() => void run("sel")}
            disabled={busy || selN === 0}
            aria-label={`Download ${selN} selected photo${selN === 1 ? "" : "s"}`}
            className="rounded-full px-4 py-2.5 text-[14px] font-semibold shadow-[0_1px_2px_rgba(0,0,0,0.35)] focus:outline-none focus-visible:ring-2 focus-visible:ring-haldi disabled:opacity-50 lg:px-5"
            style={{ background: accent, color: accentInk }}
          >
            {selLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
