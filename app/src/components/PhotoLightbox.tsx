import { useEffect, useState } from "react"
import * as DialogPrimitive from "@radix-ui/react-dialog"
import { ChevronLeft, ChevronRight, X } from "lucide-react"
import FaceContextMenu from "@/components/FaceContextMenu"
import { useStore } from "@/store"

export interface BoxedFace {
  cid: number
  name?: string | null
  box: number[]
  /** highlight this box (e.g. the cluster being named) */
  primary?: boolean
}

export interface BoxedPhoto {
  url: string
  /** natural size of the image the boxes refer to; if absent, read from the loaded image */
  w?: number
  h?: number
  faces: BoxedFace[]
  caption?: string
}

interface Props {
  photos: BoxedPhoto[]
  index: number | null
  onClose: () => void
  onIndex: (i: number) => void
  /** cid → wrapped slug; renders an "open Wrapped" chip per boxed person */
  wrappedByCid?: Record<number, string>
  onOpenWrapped?: (slug: string) => void
  /** right-click a box → FaceContextMenu (name / not a guest / open…) */
  withMenu?: boolean
}

/** Full-screen photo viewer that draws named face boxes scaled to the rendered image. */
export default function PhotoLightbox({ photos, index, onClose, onIndex, wrappedByCid, onOpenWrapped, withMenu = true }: Props) {
  const { names } = useStore()
  const open = index != null && index >= 0 && index < photos.length
  const photo = open ? photos[index as number] : null
  const [nat, setNat] = useState<{ w: number; h: number } | null>(null)

  useEffect(() => {
    setNat(null)
  }, [photo?.url])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") {
        e.preventDefault()
        if ((index as number) < photos.length - 1) onIndex((index as number) + 1)
      } else if (e.key === "ArrowLeft") {
        e.preventDefault()
        if ((index as number) > 0) onIndex((index as number) - 1)
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [open, index, photos.length, onIndex])

  const W = photo?.w ?? nat?.w
  const H = photo?.h ?? nat?.h
  const hasPrev = open && (index as number) > 0
  const hasNext = open && (index as number) < photos.length - 1
  const navBtn =
    "fixed top-1/2 z-[95] flex h-11 w-11 -translate-y-1/2 items-center justify-center rounded-full bg-black/55 text-white ring-1 ring-white/20 backdrop-blur-sm hover:bg-black/75 focus:outline-none disabled:opacity-25"

  return (
    <DialogPrimitive.Root open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-[90] bg-black/90 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=closed]:animate-out data-[state=closed]:fade-out-0" />
        <DialogPrimitive.Content
          className="fixed inset-0 z-[91] flex flex-col items-center justify-center p-3 outline-none lg:p-8"
          onClick={onClose}
        >
          <DialogPrimitive.Title className="sr-only">Photo</DialogPrimitive.Title>
          <DialogPrimitive.Description className="sr-only">
            Full photo with recognised faces boxed. Esc closes; ← → move between photos.
          </DialogPrimitive.Description>

          {photo && (
            <div
              className="relative inline-block max-h-[calc(100dvh-24px)] max-w-full lg:max-h-[88vh] lg:max-w-[92vw]"
              onClick={(e) => e.stopPropagation()}
            >
              <img
                key={photo.url}
                src={photo.url}
                alt=""
                className="block max-h-[calc(100dvh-24px)] max-w-full rounded-md object-contain shadow-2xl lg:max-h-[88vh] lg:max-w-[92vw]"
                onLoad={(e) => {
                  const im = e.currentTarget
                  setNat({ w: im.naturalWidth, h: im.naturalHeight })
                }}
              />
              {W && H
                ? photo.faces.map((f, i) => {
                    const [x1, y1, x2, y2] = f.box
                    const l = (x1 / W) * 100
                    const t = (y1 / H) * 100
                    const w = ((x2 - x1) / W) * 100
                    const h = ((y2 - y1) / H) * 100
                    const slug = wrappedByCid?.[f.cid]
                    const nm = names[f.cid] ?? f.name
                    const box = (
                      <div
                        key={`${f.cid}-${i}`}
                        className="face-box"
                        style={{
                          left: `${l}%`,
                          top: `${t}%`,
                          width: `${w}%`,
                          height: `${h}%`,
                          borderColor: f.primary ? "#d9556a" : undefined,
                          pointerEvents: withMenu ? "auto" : "none",
                          cursor: withMenu ? "context-menu" : undefined,
                        }}
                        title={withMenu ? `${nm || `#${f.cid}`} — right-click to name` : undefined}
                      >
                        <span
                          className="face-tag"
                          style={{ left: -2, top: -2, pointerEvents: slug || withMenu ? "auto" : "none" }}
                        >
                          {nm || `#${f.cid}`}
                          {slug && onOpenWrapped && (
                            <button
                              type="button"
                              className="ml-1.5 text-haldi underline decoration-haldi/50 underline-offset-2"
                              onClick={(e) => {
                                e.stopPropagation()
                                onOpenWrapped(slug)
                              }}
                              title={`Open ${f.name}'s Wrapped`}
                            >
                              Wrapped →
                            </button>
                          )}
                        </span>
                      </div>
                    )
                    return withMenu ? (
                      <FaceContextMenu key={`${f.cid}-${i}`} cid={f.cid} name={nm} asChild>
                        {box}
                      </FaceContextMenu>
                    ) : (
                      box
                    )
                  })
                : null}
            </div>
          )}

          {photo?.caption && (
            <div className="pointer-events-none fixed bottom-4 left-1/2 z-[95] -translate-x-1/2 rounded-full bg-black/55 px-3 py-1 text-[12px] text-white/90 backdrop-blur-sm">
              {photo.caption}
              {photos.length > 1 ? ` · ${(index as number) + 1} / ${photos.length}` : ""}
            </div>
          )}

          {photos.length > 1 && (
            <>
              <button
                type="button"
                aria-label="Previous photo"
                disabled={!hasPrev}
                className={`${navBtn} left-3`}
                onClick={(e) => {
                  e.stopPropagation()
                  if (hasPrev) onIndex((index as number) - 1)
                }}
              >
                <ChevronLeft className="h-6 w-6" />
              </button>
              <button
                type="button"
                aria-label="Next photo"
                disabled={!hasNext}
                className={`${navBtn} right-3`}
                onClick={(e) => {
                  e.stopPropagation()
                  if (hasNext) onIndex((index as number) + 1)
                }}
              >
                <ChevronRight className="h-6 w-6" />
              </button>
            </>
          )}

          <DialogPrimitive.Close
            aria-label="Close"
            className="fixed right-4 top-4 z-[95] flex h-11 w-11 items-center justify-center rounded-full bg-black/55 text-white ring-1 ring-white/20 backdrop-blur-sm hover:bg-black/75 focus:outline-none"
          >
            <X className="h-5 w-5" />
          </DialogPrimitive.Close>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}
