import { useCallback, useEffect, useState } from "react"
import * as DialogPrimitive from "@radix-ui/react-dialog"
import { ChevronLeft, ChevronRight, X } from "lucide-react"
import { useDeckExtras } from "./DeckContext"
import { CheckChip, useSelection } from "./Selection"
import type { PhotoInfo } from "@/api"

export interface LightboxState {
  src: string
  /** Optional list the src belongs to (e.g. all best-shots of the current event) for ← → navigation. */
  list?: string[]
}

interface LightboxProps {
  state: LightboxState | null
  onClose: () => void
  onChange: (src: string) => void
  /** guest accent for the selection chip (same tokens the tiles use) */
  accent: string
  accentInk: string
}

/** Full-screen image viewer built on the shadcn/Radix Dialog primitive. */
export default function Lightbox({ state, onClose, onChange, accent, accentInk }: LightboxProps) {
  const open = !!state
  const list = state?.list ?? []
  const idx = state ? list.indexOf(state.src) : -1
  const canNav = list.length > 1 && idx >= 0
  const hasPrev = canNav && idx > 0
  const hasNext = canNav && idx < list.length - 1

  // #42 — the lightbox selects too, so a photo reached full-screen is never a dead end.
  // Same gesture, same chip as the tiles: DESIGN § Selection & download, "one habit, everywhere".
  const sel = useSelection()
  const selected = state ? (sel?.has(state.src) ?? false) : false

  // Admin-only: face boxes with names + right-click menu (never in the standalone guest deck)
  const extras = useDeckExtras()
  const [faces, setFaces] = useState<PhotoInfo | null>(null)
  const [showFaces, setShowFaces] = useState(true)
  useEffect(() => {
    setFaces(null)
    if (!extras || !state?.src) return
    let cancelled = false
    extras.fetchFaces(state.src).then((p) => !cancelled && setFaces(p)).catch(() => !cancelled && setFaces(null))
    return () => {
      cancelled = true
    }
  }, [extras, state?.src])

  const go = useCallback(
    (delta: number) => {
      if (!canNav) return
      const next = idx + delta
      if (next < 0 || next >= list.length) return
      onChange(list[next])
    },
    [canNav, idx, list, onChange]
  )

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") {
        e.preventDefault()
        go(1)
      } else if (e.key === "ArrowLeft") {
        e.preventDefault()
        go(-1)
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [open, go])

  const navBtn =
    "hidden lg:flex fixed top-1/2 z-[60] h-12 w-12 -translate-y-1/2 items-center justify-center rounded-full bg-black/50 text-ink ring-1 ring-white/15 backdrop-blur-sm hover:bg-black/70 focus:outline-none focus:ring-2 focus:ring-haldi disabled:opacity-25 disabled:hover:bg-black/50"

  return (
    <DialogPrimitive.Root open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-bg/95 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=closed]:animate-out data-[state=closed]:fade-out-0" />
        <DialogPrimitive.Content
          className="fixed inset-0 z-50 flex items-center justify-center p-3 outline-none data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 lg:p-8"
          onClick={onClose}
        >
          <DialogPrimitive.Title className="sr-only">Photo</DialogPrimitive.Title>
          <DialogPrimitive.Description className="sr-only">
            Full-size photo. Tap anywhere or press Escape to close
            {canNav ? "; use the left and right arrow keys to move between photos" : ""}.
          </DialogPrimitive.Description>
          {state && (
            <div className="relative inline-block max-h-[calc(100dvh-24px)] max-w-full lg:max-h-[92vh] lg:max-w-[92vw]" onClick={(e) => e.stopPropagation()}>
              <img
                key={state.src}
                src={state.src}
                alt=""
                className="block max-h-[calc(100dvh-24px)] max-w-full rounded-md object-contain shadow-2xl lg:max-h-[92vh] lg:max-w-[92vw]"
              />
              {extras && showFaces && faces && faces.w > 0 && faces.h > 0 &&
                faces.faces.map((f, i) => {
                  const [x1, y1, x2, y2] = f.box
                  const tiny = (x2 - x1) / faces.w < 0.012 || f.det < 0.5
                  const nm = extras.names[f.cid] ?? f.name
                  return (
                    <extras.FaceMenu key={`${f.cid}-${i}`} cid={f.cid} name={nm} asChild>
                      <div
                        className="face-box"
                        style={{
                          left: `${(x1 / faces.w) * 100}%`,
                          top: `${(y1 / faces.h) * 100}%`,
                          width: `${((x2 - x1) / faces.w) * 100}%`,
                          height: `${((y2 - y1) / faces.h) * 100}%`,
                          pointerEvents: "auto",
                          cursor: "context-menu",
                          opacity: tiny ? 0.45 : 1,
                          borderStyle: tiny ? "dashed" : "solid",
                        }}
                        title={`${nm || `#${f.cid}`} — right-click to name`}
                      >
                        {!tiny && (
                          <span className={"face-tag" + (nm ? "" : " italic")} style={{ left: -2, top: -2 }}>
                            {nm || `#${f.cid}`}
                          </span>
                        )}
                      </div>
                    </extras.FaceMenu>
                  )
                })}
            </div>
          )}
          {extras && state && (
            <label
              className="fixed left-4 z-[60] flex h-9 cursor-pointer items-center gap-2 rounded-full bg-black/50 px-3 text-[12px] text-ink ring-1 ring-white/15 backdrop-blur-sm"
              style={{ top: "calc(max(16px, env(safe-area-inset-top)) + 52px)" }}
              onClick={(e) => e.stopPropagation()}
            >
              <input type="checkbox" className="accent-haldi" checked={showFaces} onChange={(e) => setShowFaces(e.target.checked)} />
              show faces{faces ? ` (${faces.faces.length})` : ""}
              <span className="text-muted">· right-click a face to name</span>
            </label>
          )}

          {state && sel && (
            <button
              type="button"
              aria-pressed={selected}
              aria-label={`${selected ? "Deselect" : "Select"} this photo`}
              onClick={(e) => {
                e.stopPropagation()
                sel.toggle(state.src)
              }}
              className="fixed left-4 z-[60] flex h-11 items-center gap-2 rounded-full bg-black/50 pl-2 pr-4 text-[13px] font-semibold text-ink ring-1 ring-white/15 backdrop-blur-sm hover:bg-black/70 focus:outline-none focus-visible:ring-2 focus-visible:ring-haldi"
              style={{ top: "max(16px, env(safe-area-inset-top))" }}
            >
              <CheckChip selected={selected} accent={accent} accentInk={accentInk} />
              {selected ? "Selected" : "Select"}
            </button>
          )}

          {canNav && (
            <span className="pointer-events-none fixed bottom-4 left-1/2 z-[60] -translate-x-1/2 rounded-full bg-black/50 px-3 py-1 text-[12px] text-ink/85 backdrop-blur-sm">
              {idx + 1} / {list.length}
            </span>
          )}

          {canNav && (
            <>
              <button
                type="button"
                aria-label="Previous photo"
                disabled={!hasPrev}
                className={`${navBtn} left-4`}
                onClick={(e) => {
                  e.stopPropagation()
                  go(-1)
                }}
              >
                <ChevronLeft className="h-6 w-6" />
              </button>
              <button
                type="button"
                aria-label="Next photo"
                disabled={!hasNext}
                className={`${navBtn} right-4`}
                onClick={(e) => {
                  e.stopPropagation()
                  go(1)
                }}
              >
                <ChevronRight className="h-6 w-6" />
              </button>
            </>
          )}

          <DialogPrimitive.Close
            aria-label="Close"
            className="fixed right-4 top-4 z-[60] flex h-11 w-11 items-center justify-center rounded-full bg-black/50 text-ink ring-1 ring-white/15 backdrop-blur-sm hover:bg-black/70 focus:outline-none focus:ring-2 focus:ring-haldi"
            style={{ top: "max(16px, env(safe-area-inset-top))" }}
          >
            <X className="h-5 w-5" />
          </DialogPrimitive.Close>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}
