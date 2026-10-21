import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react"
import JSZip from "jszip"
import { filenameOf, largeUrl, saveBlob } from "./favorites"
import { track } from "./beacon"
import { cn } from "@/lib/utils"

/** Open a photo in the lightbox; `list` is the set it belongs to for ← → navigation. */
export type OpenFn = (src: string, list?: string[]) => void

/** "…/img/l/X.jpg" → the small copy; callers fall back to the large url on error. */
export const smallUrl = (url: string) => url.replace(/\/img\/l\//, "/img/s/")

/** One entry in the page's downloadable payload. */
export interface PoolPhoto {
  url: string
  courtesy?: boolean
}

interface Selection {
  /** currently selected photo urls (for "Download N") */
  selected: string[]
  count: number
  has: (url: string) => boolean
  toggle: (url: string) => void
  clear: () => void
  /** the full "Download all" pool — every visible photo minus courtesy-grade ones */
  downloadAll: string[]
}

const Ctx = createContext<Selection | null>(null)

export function SelectionProvider({
  pool,
  resetKey,
  children,
}: {
  pool: PoolPhoto[]
  /** a change empties the selection (a Household deck's new member Selection is a new photo set) */
  resetKey?: string
  children: ReactNode
}) {
  const [selected, setSelected] = useState<string[]>([])
  useEffect(() => setSelected([]), [resetKey])

  const downloadAll = useMemo(() => {
    const seen = new Set<string>()
    const out: string[] = []
    for (const p of pool) {
      if (p.courtesy) continue
      if (seen.has(p.url)) continue
      seen.add(p.url)
      out.push(p.url)
    }
    return out
  }, [pool])

  // ref mirror so the memoized toggle can log outside the updater (StrictMode-safe, #39)
  const selRef = useRef(selected)
  selRef.current = selected
  const toggle = useCallback((url: string) => {
    const on = !selRef.current.includes(url)
    track(on ? "select_on" : "select_off", url)
    setSelected((s) => (on ? [...s, url] : s.filter((x) => x !== url)))
  }, [])
  const clear = useCallback(() => setSelected([]), [])

  const value = useMemo<Selection>(
    () => ({
      selected,
      count: selected.length,
      has: (url) => selected.includes(url),
      toggle,
      clear,
      downloadAll,
    }),
    [selected, toggle, clear, downloadAll]
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useSelection(): Selection | null {
  return useContext(Ctx)
}

/**
 * The 24px selection-state chip (DESIGN `{components.gallery-figure-selected}`) — drawn by
 * every surface that can select: the wall tiles, the highlight tiles, and the lightbox
 * chrome. Visual state ONLY; the hit target is always the control that wraps it
 * (DESIGN § Selection & download / a11y #24). Shared so the three can never drift apart.
 */
export function CheckChip({
  selected,
  accent,
  accentInk,
  className,
}: {
  selected: boolean
  accent: string
  accentInk: string
  className?: string
}) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "flex h-6 w-6 items-center justify-center rounded-full",
        !selected && "border-2 border-[#9c8568] bg-card/85",
        className,
      )}
      style={selected ? { background: accent } : undefined}
    >
      {selected && (
        <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke={accentInk} strokeWidth="2.5">
          <path d="M3 8.5l3.5 3.5L13 4.5" />
        </svg>
      )}
    </span>
  )
}

/**
 * Client-side, store-only zip of the given full-res photos — no server, works from any
 * static host. Reuses the JSZip dependency and blob-save helper the favorites tray shipped
 * with. Returns the number of photos that failed to fetch (skipped).
 */
export async function zipDownload(
  urls: string[],
  filename: string,
  onProgress?: (done: number, total: number) => void
): Promise<number> {
  const bundle = new JSZip()
  let failed = 0
  for (let i = 0; i < urls.length; i++) {
    try {
      const r = await fetch(largeUrl(urls[i]))
      if (!r.ok) throw new Error(String(r.status))
      bundle.file(filenameOf(urls[i]), await r.blob())
    } catch {
      failed += 1
    }
    onProgress?.(i + 1, urls.length)
  }
  const blob = await bundle.generateAsync({ type: "blob" })
  await saveBlob(blob, filename)
  return failed
}

/** Single-photo download via a same-origin fetch → blob anchor (iOS-Safari safe). */
export async function saveOne(url: string): Promise<void> {
  const r = await fetch(largeUrl(url))
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  await saveBlob(await r.blob(), filenameOf(url).split("/").pop() || "photo.jpg")
}
