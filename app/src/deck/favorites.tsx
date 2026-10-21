import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react"

/** "…/img/l/WEDDING/NP-123.jpg" → "WEDDING/NP-123.jpg" (gallery + basename, decoded). */
export function filenameOf(url: string): string {
  const clean = decodeURIComponent(url.split("?")[0])
  const parts = clean.split("/").filter(Boolean)
  return parts.slice(-2).join("/")
}

/** Any of our image urls → the large copy (…/img/s/… → …/img/l/…). */
export function largeUrl(url: string): string {
  return url.replace(/\/img\/s\//, "/img/l/")
}

export const COUPLE_EMAIL = "couple@example.com"

interface Favorites {
  slug: string
  name: string
  hearts: string[]
  has: (id: string) => boolean
  toggle: (id: string) => void
}

const Ctx = createContext<Favorites | null>(null)

const keyFor = (slug: string) => `wrapped-hearts-${slug}`

function load(slug: string): string[] {
  try {
    const raw = localStorage.getItem(keyFor(slug))
    const v = raw ? (JSON.parse(raw) as unknown) : []
    return Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : []
  } catch {
    return []
  }
}

export function FavoritesProvider({ slug, name, children }: { slug: string; name: string; children: ReactNode }) {
  const [hearts, setHearts] = useState<string[]>(() => load(slug))

  useEffect(() => {
    setHearts(load(slug))
  }, [slug])

  const toggle = useCallback(
    (id: string) => {
      setHearts((h) => {
        const next = h.includes(id) ? h.filter((x) => x !== id) : [...h, id]
        try {
          localStorage.setItem(keyFor(slug), JSON.stringify(next))
        } catch {
          /* private mode etc. — keep in-memory state */
        }
        return next
      })
    },
    [slug]
  )

  const value = useMemo<Favorites>(
    () => ({ slug, name, hearts, has: (id) => hearts.includes(id), toggle }),
    [slug, name, hearts, toggle]
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useFavorites(): Favorites | null {
  return useContext(Ctx)
}

/** mailto: href listing the hearted photos, body kept under ~1800 chars. */
export function favoritesMailto(name: string, hearts: string[]): string {
  const files = hearts.map(filenameOf)
  const head = "These are the ones I love:\n\n"
  const tail = `\n\n— ${name}`
  let body = head + files.join("\n") + tail
  if (body.length > 1800) {
    const kept: string[] = []
    let used = head.length + tail.length + 20 // room for the "+N more" line
    for (const f of files) {
      if (used + f.length + 1 > 1800) break
      kept.push(f)
      used += f.length + 1
    }
    body = head + kept.join("\n") + `\n+${files.length - kept.length} more` + tail
  }
  return `mailto:${COUPLE_EMAIL}?subject=${encodeURIComponent(`${name}'s favorites`)}&body=${encodeURIComponent(body)}`
}

/** mailto: for a one-photo note. */
export function commentMailto(name: string, src: string): string {
  return `mailto:${COUPLE_EMAIL}?subject=${encodeURIComponent(`${name} on ${filenameOf(src)}`)}`
}

/** Same-origin fetch → blob anchor download. */
export async function saveBlob(blob: Blob, filename: string) {
  const u = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = u
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(u), 4000)
}

export async function savePhoto(src: string): Promise<void> {
  const r = await fetch(largeUrl(src))
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  const blob = await r.blob()
  await saveBlob(blob, filenameOf(src).split("/").pop() || "photo.jpg")
}
