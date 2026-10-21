import { useEffect, useMemo, useState } from "react"
import { api, type WrappedEntry } from "@/api"
import { buildHash } from "@/router"

export default function WrappedIndex({ go }: { go: (h: string) => void }) {
  const [list, setList] = useState<WrappedEntry[] | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [q, setQ] = useState("")

  useEffect(() => {
    api.wrapped().then(setList).catch((e) => setErr(e instanceof Error ? e.message : String(e)))
  }, [])

  const shown = useMemo(() => {
    const ql = q.trim().toLowerCase()
    return (list ?? []).filter((w) => !ql || w.name.toLowerCase().includes(ql) || w.slug.includes(ql))
  }, [list, q])

  return (
    <div className="ws-page">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[20px] font-semibold tracking-tight">Wrapped — every guest’s recap</h1>
          <p className="mt-0.5 text-[13px] text-ws-muted">{list ? `${list.length} built` : "Loading…"} · click to open</p>
        </div>
        <input className="ws-input w-[240px]" placeholder="Search a name" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      {err && <div className="ws-panel p-3 text-[13px] text-ws-warn">Couldn’t load /api/wrapped: {err}</div>}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
        {shown.map((w) => (
          <a
            key={w.slug}
            href={buildHash("wrapped", w.slug)}
            onClick={(e) => {
              e.preventDefault()
              go(buildHash("wrapped", w.slug))
            }}
            className="ws-panel group overflow-hidden hover:border-ws-accent"
          >
            <div className="aspect-[4/5] overflow-hidden bg-ws-soft">
              <img src={w.hero} alt={w.name} loading="lazy" className="h-full w-full object-cover transition-transform group-hover:scale-[1.02]" />
            </div>
            <div className="p-2.5">
              <div className="truncate text-[14px] font-semibold">{w.name}</div>
              <div className="text-[12px] text-ws-muted">
                {w.n_photos.toLocaleString()} photos · {w.n_events} events · {w.n_scenes} moments
              </div>
              <div className="mt-0.5 text-[11px] text-ws-muted/70">#{w.cluster} · /{w.slug}</div>
            </div>
          </a>
        ))}
      </div>
    </div>
  )
}
