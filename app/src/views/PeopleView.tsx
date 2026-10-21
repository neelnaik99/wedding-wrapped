import { useEffect, useMemo, useState } from "react"
import { Network, Images } from "lucide-react"
import { api, type GraphResponse } from "@/api"
import { buildHash, type Route } from "@/router"
import { cn } from "@/lib/utils"
import GraphView from "./GraphView"
import SharedView from "./SharedView"

type Tab = "insights" | "photos"

/**
 * Merged "People" view: one selection (?sel=15,50), two ways of looking at it —
 *  - Insights: the co-photography map (GraphView)
 *  - Photos together: every frame the whole selection shares (SharedView)
 * Legacy #/graph… and #/shared?cids=… hashes are folded into #/people by the router.
 */
export default function PeopleView({ route, go }: { route: Route; go: (h: string, replace?: boolean) => void }) {
  const tab: Tab = route.params.get("tab") === "photos" ? "photos" : "insights"

  // a legacy hash (#/graph…, #/shared?cids=…) landed here — normalise the URL in place
  useEffect(() => {
    if (route.canonical) go(route.canonical, true)
  }, [route.canonical, go])

  const switchTab = (t: Tab) => {
    if (t === tab) return
    const p: Record<string, string | null> = {}
    route.params.forEach((v, k) => {
      p[k] = v
    })
    p.tab = t === "photos" ? "photos" : null
    go(buildHash("people", null, p))
  }

  // facts strip: totals + strongest pairs, from the widest graph (min=15)
  const [facts, setFacts] = useState<GraphResponse | null>(null)
  useEffect(() => {
    let cancelled = false
    api
      .graph(15)
      .then((d) => !cancelled && setFacts(d))
      .catch(() => !cancelled && setFacts(null))
    return () => {
      cancelled = true
    }
  }, [])

  const topPairs = useMemo(() => {
    if (!facts) return []
    const byId = new Map(facts.nodes.map((n) => [n.id, n]))
    return [...facts.edges]
      .sort((a, b) => b.w - a.w)
      .slice(0, 5)
      .map((e) => ({
        s: e.s,
        t: e.t,
        w: e.w,
        a: byId.get(e.s)?.name ?? `#${e.s}`,
        b: byId.get(e.t)?.name ?? `#${e.t}`,
      }))
  }, [facts])
  const totalPhotos = useMemo(() => (facts ? facts.nodes.reduce((s, n) => s + n.photos, 0) : 0), [facts])

  const showPair = (s: number, t: number) => {
    const p: Record<string, string | null> = {}
    route.params.forEach((v, k) => {
      p[k] = v
    })
    p.sel = `${s},${t}`
    go(buildHash("people", null, p))
  }

  return (
    <div className="ws-page">
      {/* segmented control — one selection, two lenses */}
      <div className="mb-3 inline-flex rounded-lg border border-ws-line bg-white p-1" role="tablist" aria-label="People view">
        {(
          [
            { key: "insights" as Tab, label: "Insights", Icon: Network },
            { key: "photos" as Tab, label: "Photos together", Icon: Images },
          ]
        ).map(({ key, label, Icon }) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={tab === key}
            onClick={() => switchTab(key)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md px-3 py-1 text-[13px] font-medium",
              tab === key ? "bg-ws-ink text-white" : "text-ws-muted hover:bg-ws-soft hover:text-ws-ink"
            )}
          >
            <Icon className="h-3.5 w-3.5" /> {label}
          </button>
        ))}
      </div>

      {/* compact facts strip */}
      {tab === "insights" && facts && (
        <div className="ws-panel mb-3 flex flex-wrap items-center gap-x-3 gap-y-1.5 px-3 py-2 text-[13px]">
          <span>
            <b className="font-semibold">{facts.nodes.length}</b> people in ≥15 photos
          </span>
          <span className="text-ws-line">·</span>
          <span>
            <b className="font-semibold">{totalPhotos.toLocaleString()}</b> photo appearances
          </span>
          {topPairs.length > 0 && (
            <>
              <span className="text-ws-line">|</span>
              <span className="text-ws-muted">most photographed together:</span>
              {topPairs.map((p) => (
                <button
                  key={`${p.s}-${p.t}`}
                  type="button"
                  className="ws-chip bg-white ring-1 ring-ws-line hover:ring-ws-accent"
                  title={`Select ${p.a} + ${p.b} on the map`}
                  onClick={() => showPair(p.s, p.t)}
                >
                  {p.a.split(" ")[0]} + {p.b.split(" ")[0]} <span className="tabular-nums text-ws-muted">{p.w}</span>
                </button>
              ))}
            </>
          )}
        </div>
      )}

      {tab === "insights" ? <GraphView route={route} go={go} embedded /> : <SharedView route={route} go={go} embedded />}
    </div>
  )
}
