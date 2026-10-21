import { useEffect, useMemo, useState } from "react"
import { X } from "lucide-react"
import { api, EVN, type SharedResponse, type WrappedEntry } from "@/api"
import { useStore } from "@/store"
import { buildHash, type Route } from "@/router"
import { cn } from "@/lib/utils"
import PhotoLightbox, { type BoxedPhoto } from "@/components/PhotoLightbox"
import FaceContextMenu from "@/components/FaceContextMenu"

export default function SharedView({ route, go, embedded = false }: { route: Route; go: (h: string) => void; embedded?: boolean }) {
  const { rows, names } = useStore()
  const cids = useMemo(
    () => (route.params.get("sel") || route.params.get("cids") || "").split(",").filter(Boolean).map(Number).filter((n) => !Number.isNaN(n)),
    [route.params]
  )
  const event = route.params.get("event") || null
  const [data, setData] = useState<SharedResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [q, setQ] = useState("")
  const [lb, setLb] = useState<number | null>(null)
  const [wrapped, setWrapped] = useState<WrappedEntry[]>([])
  const [hoverTile, setHoverTile] = useState<number | null>(null)
  const [limit, setLimit] = useState(400)

  useEffect(() => {
    api.wrapped().then(setWrapped).catch(() => setWrapped([]))
  }, [])
  const wrappedByCid = useMemo(() => Object.fromEntries(wrapped.map((w) => [w.cluster, w.slug])) as Record<number, string>, [wrapped])

  const setHash = (patch: Record<string, string | null>) =>
    go(
      buildHash("people", null, {
        tab: "photos",
        sel: cids.join(",") || null,
        event,
        // keep the Insights tab's graph settings alive across tab switches
        min: route.params.get("min"),
        c: route.params.get("c"),
        n: route.params.get("n"),
        ...patch,
      })
    )

  useEffect(() => {
    setLimit(400)
  }, [cids, event])

  useEffect(() => {
    if (cids.length === 0) {
      setData(null)
      return
    }
    let cancelled = false
    setLoading(true)
    setErr(null)
    api
      .shared(cids, event, limit)
      .then((d) => {
        if (cancelled) return
        setData(d)
        setLb(null)
      })
      .catch((e) => !cancelled && setErr(e instanceof Error ? e.message : String(e)))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [cids, event, limit])

  const byCid = useMemo(() => new Map(rows.map((r) => [r.cid, r])), [rows])
  const nameOf = (cid: number) => names[cid] || byCid.get(cid)?.label?.name || `#${cid}`

  const picks = useMemo(() => {
    const ql = q.trim().toLowerCase()
    if (!ql) return []
    return rows
      .filter((r) => !cids.includes(r.cid))
      .filter((r) => {
        const n = (names[r.cid] || r.label?.name || "").toLowerCase()
        return n.includes(ql) || String(r.cid) === ql.replace("#", "")
      })
      .slice(0, 8)
  }, [q, rows, names, cids])

  // frequent co-stars in the current result (not already selected)
  const suggestions = useMemo(() => {
    if (!data) return []
    const c = new Map<number, number>()
    for (const p of data.photos) for (const f of p.faces) if (!cids.includes(f.cid)) c.set(f.cid, (c.get(f.cid) ?? 0) + 1)
    return [...c.entries()]
      .filter(([cid]) => byCid.has(cid))
      .sort((a, b) => b[1] - a[1])
      .slice(0, 6)
  }, [data, cids, byCid])

  const lbPhotos: BoxedPhoto[] = useMemo(
    () =>
      (data?.photos ?? []).map((p) => ({
        url: p.url,
        w: p.w,
        h: p.h,
        faces: p.faces.map((f) => ({ cid: f.cid, name: f.name || nameOf(f.cid), box: f.box, primary: cids.includes(f.cid) })),
        caption: `${EVN[p.gallery] ?? p.gallery} · ${fmtTime(p.taken_at)} · ${p.photo_id.split("/").pop()}`,
      })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [data, cids, names]
  )

  const evKeys = Object.keys(data?.by_event ?? {}).sort((a, b) => (data!.by_event[b] ?? 0) - (data!.by_event[a] ?? 0))

  return (
    <div className={embedded ? "" : "ws-page"}>
      <div className="mb-3">
        <h1 className="text-[20px] font-semibold tracking-tight">Shared photos — everyone in the same frame</h1>
        <p className="mt-0.5 text-[13px] text-ws-muted">Pick two or more people; we show every photo where all of them appear.</p>
      </div>

      {/* picker */}
      <div className="ws-panel mb-3 p-3">
        <div className="flex flex-wrap items-center gap-2">
          {cids.map((c) => {
            const r = byCid.get(c)
            return (
              <span key={c} className="inline-flex items-center gap-1.5 rounded-full border border-ws-line bg-white py-0.5 pl-0.5 pr-2 text-[13px]">
                {r ? <img src={r.face} alt="" className="h-6 w-6 rounded-full object-cover" /> : <span className="h-6 w-6 rounded-full bg-ws-soft" />}
                {nameOf(c)}
                <button type="button" aria-label={`remove ${nameOf(c)}`} className="ml-0.5 rounded-full p-0.5 text-ws-muted hover:text-ws-warn" onClick={() => setHash({ sel: cids.filter((x) => x !== c).join(",") || null })}>
                  <X className="h-3.5 w-3.5" />
                </button>
              </span>
            )
          })}
          <div className="relative">
            <input
              className="ws-input w-[260px]"
              placeholder={cids.length ? "Add another person…" : "Type a name to add someone…"}
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && picks[0]) {
                  setHash({ sel: [...cids, picks[0].cid].join(",") })
                  setQ("")
                }
                if (e.key === "Escape") setQ("")
              }}
            />
            {picks.length > 0 && (
              <ul className="absolute left-0 top-full z-[60] mt-1 w-[320px] overflow-hidden rounded-lg border border-ws-line bg-white shadow-lg">
                {picks.map((r) => (
                  <li key={r.cid}>
                    <button
                      type="button"
                      className="flex w-full items-center gap-2 px-2 py-1.5 text-left text-[13px] hover:bg-ws-soft"
                      onClick={() => {
                        setHash({ sel: [...cids, r.cid].join(",") })
                        setQ("")
                      }}
                    >
                      <img src={r.face} alt="" className="h-7 w-7 rounded-full object-cover" />
                      <span className="min-w-0 flex-1 truncate">{nameOf(r.cid)}</span>
                      <span className="text-[11px] text-ws-muted">#{r.cid} · {r.photos} photos</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
          {cids.length > 0 && (
            <button type="button" className="ws-btn ws-btn--sm ml-auto" onClick={() => setHash({ sel: null, event: null })}>
              clear
            </button>
          )}
        </div>
        {suggestions.length > 0 && (
          <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[12px] text-ws-muted">
            often with them:
            {suggestions.map(([cid, n]) => (
              <button
                key={cid}
                type="button"
                className="inline-flex items-center gap-1 rounded-full border border-ws-line bg-white py-0.5 pl-0.5 pr-2 text-[12px] text-ws-ink hover:border-ws-accent"
                onClick={() => setHash({ sel: [...cids, cid].join(",") })}
              >
                <img src={byCid.get(cid)!.face} alt="" className="h-5 w-5 rounded-full object-cover" />
                {nameOf(cid)} <span className="text-ws-muted">+{n}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {cids.length === 0 && <div className="ws-panel p-6 text-center text-[13px] text-ws-muted">Add at least one person to see photos.</div>}
      {err && <div className="ws-panel p-3 text-[13px] text-ws-warn">Couldn’t load /api/shared: {err}</div>}

      {data && cids.length > 0 && (
        <>
          <div className="mb-3 flex flex-wrap items-center gap-2 text-[13px]">
            <span className="font-semibold">
              {data.count.toLocaleString()} photo{data.count === 1 ? "" : "s"}
            </span>
            <span className="text-ws-muted">with {cids.map(nameOf).join(" + ")}</span>
            <span className="mx-1 text-ws-line">|</span>
            <button type="button" className={cn("ws-chip", !event ? "bg-ws-ink text-white" : "bg-white ring-1 ring-ws-line hover:ring-ws-accent")} onClick={() => setHash({ event: null })}>
              All {data.count}
            </button>
            {evKeys.map((e) => (
              <button
                key={e}
                type="button"
                className={cn("ws-chip", event === e ? "bg-ws-ink text-white" : "bg-white ring-1 ring-ws-line hover:ring-ws-accent")}
                onClick={() => setHash({ event: event === e ? null : e })}
              >
                {EVN[e] ?? e} {data.by_event[e]}
              </button>
            ))}
            {loading && <span className="text-ws-muted">loading…</span>}
            {data.photos.length < (event ? data.by_event[event] ?? 0 : data.count) && (
              <span className="text-ws-muted">
                showing first {data.photos.length} ·{" "}
                <button type="button" className="underline hover:text-ws-ink" onClick={() => setLimit(event ? data.by_event[event] ?? data.count : data.count)}>
                  show all
                </button>
              </span>
            )}
          </div>

          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
            {data.photos.map((p, i) => (
              <button
                key={p.photo_id}
                type="button"
                className="group relative aspect-[4/3] overflow-hidden rounded-lg bg-ws-soft ring-1 ring-ws-line hover:ring-ws-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-ws-accent"
                onClick={() => setLb(i)}
                onMouseEnter={() => setHoverTile(i)}
                onMouseLeave={() => setHoverTile(null)}
                onFocus={() => setHoverTile(i)}
                onBlur={() => setHoverTile(null)}
                aria-label={`${EVN[p.gallery] ?? p.gallery} · ${fmtTime(p.taken_at)} — ${p.faces.map((f) => f.name || nameOf(f.cid)).join(", ")}`}
              >
                <img src={p.url} alt="" loading="lazy" decoding="async" className="h-full w-full object-cover" />
                <span className="pointer-events-none absolute left-1.5 top-1.5 rounded bg-black/45 px-1.5 py-0.5 text-[10px] text-white/90">
                  {EVN[p.gallery] ?? p.gallery} · {fmtTime(p.taken_at)}
                </span>
                {hoverTile === i && (
                  <span className="absolute inset-x-0 bottom-0 flex flex-wrap gap-1 bg-gradient-to-t from-black/70 to-transparent p-1.5 pt-5" onClick={(e) => e.stopPropagation()}>
                    {p.faces.map((f, k) => (
                      <FaceContextMenu key={k} cid={f.cid} name={f.name}>
                        <span
                          className={cn("cursor-context-menu rounded px-1.5 py-0.5 text-[10px] text-white", cids.includes(f.cid) ? "bg-rose/90" : "bg-black/55")}
                          title="right-click to name"
                        >
                          {names[f.cid] || f.name || nameOf(f.cid)}
                        </span>
                      </FaceContextMenu>
                    ))}
                  </span>
                )}
              </button>
            ))}
          </div>
        </>
      )}

      <PhotoLightbox photos={lbPhotos} index={lb} onClose={() => setLb(null)} onIndex={setLb} wrappedByCid={wrappedByCid} onOpenWrapped={(slug) => go(buildHash("wrapped", slug))} />
    </div>
  )
}

function fmtTime(t: string): string {
  // "2026:04:24 08:38:06" → "Apr 24, 8:38 AM"
  const m = t.match(/^(\d{4}):(\d{2}):(\d{2}) (\d{2}):(\d{2})/)
  if (!m) return t
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
  const h = Number(m[4])
  const hh = h % 12 === 0 ? 12 : h % 12
  return `${months[Number(m[2]) - 1]} ${Number(m[3])}, ${hh}:${m[5]} ${h < 12 ? "AM" : "PM"}`
}
