import { useCallback, useEffect, useState } from "react"

export type View = "admin" | "people" | "groups" | "review" | "wrapped"

export interface Route {
  view: View
  /** wrapped slug (for #/wrapped/:slug) */
  slug: string | null
  params: URLSearchParams
  /** set when a legacy hash (#/graph…, #/shared?cids=…) was parsed — the normalised #/people hash to replace it with */
  canonical?: string | null
}

/** Parse `#/view/segment?query` — hash routing so deep links work under any server path. */
export function parseHash(hash: string): Route {
  let h = hash.replace(/^#/, "")
  if (!h.startsWith("/")) h = "/" + h
  const qi = h.indexOf("?")
  const path = qi >= 0 ? h.slice(0, qi) : h
  const params = new URLSearchParams(qi >= 0 ? h.slice(qi + 1) : "")
  const segs = path.split("/").filter(Boolean)
  const v = (segs[0] || "admin") as string
  const view: View =
    v === "graph" || v === "people" || v === "shared"
      ? "people"
      : v === "groups-admin"
        ? "groups"
        : v === "review"
          ? "review"
          : v === "wrapped"
            ? "wrapped"
            : "admin"
  let canonical: string | null = null
  if (v === "graph" || v === "shared") {
    // legacy routes fold into the merged People view, preserving selection
    if (v === "shared") {
      const sel = params.get("cids") ?? params.get("sel")
      params.delete("cids")
      if (sel) params.set("sel", sel)
      params.set("tab", "photos")
    }
    const s = params.toString().replace(/%2C/gi, ",")
    canonical = `#/people${s ? `?${s}` : ""}`
  }
  const slug = view === "wrapped" && segs[1] ? decodeURIComponent(segs[1]) : null
  return { view, slug, params, canonical }
}

export function buildHash(view: View, slug?: string | null, params?: Record<string, string | null | undefined>): string {
  // "groups" routes to #/groups-admin so it can't collide with the server's standalone /groups page
  let h = `#/${view === "groups" ? "groups-admin" : view}`
  if (slug) h += `/${encodeURIComponent(slug)}`
  if (params) {
    const sp = new URLSearchParams()
    for (const [k, v] of Object.entries(params)) if (v != null && v !== "") sp.set(k, v)
    // keep commas readable in shareable links (#/shared?cids=15,50)
    const s = sp.toString().replace(/%2C/gi, ",")
    if (s) h += `?${s}`
  }
  return h
}

export function navigate(hash: string, replace = false) {
  if (replace) history.replaceState(null, "", hash)
  else location.hash = hash
  // hashchange doesn't fire for replaceState — notify listeners manually
  if (replace) window.dispatchEvent(new HashChangeEvent("hashchange"))
}

export function useRoute(): [Route, (hash: string, replace?: boolean) => void] {
  const [route, setRoute] = useState<Route>(() => parseHash(location.hash))
  useEffect(() => {
    const on = () => setRoute(parseHash(location.hash))
    window.addEventListener("hashchange", on)
    return () => window.removeEventListener("hashchange", on)
  }, [])
  const go = useCallback((hash: string, replace = false) => navigate(hash, replace), [])
  return [route, go]
}
