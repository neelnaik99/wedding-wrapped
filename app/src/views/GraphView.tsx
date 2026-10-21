import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Check, ChevronsUpDown, SlidersHorizontal, X } from "lucide-react"
import { api, type GraphEdge, type GraphNode, type GraphResponse } from "@/api"
import { buildHash, type Route } from "@/router"
import { cn } from "@/lib/utils"
import { useStore } from "@/store"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Command, CommandInput, CommandItem, CommandList } from "@/components/ui/command"
import FaceContextMenu from "@/components/FaceContextMenu"

type ColorMode = "community" | "side"

/** communities carry a mono caption + on-canvas anchor from relationship_graph.py (#10) */
type Cluster = GraphResponse["communities"][number] & { label?: string; lx?: number; ly?: number }

interface ViewBox {
  x: number
  y: number
  w: number
  h: number
}

export default function GraphView({ route, go, embedded = false }: { route: Route; go: (h: string) => void; embedded?: boolean }) {
  const [min, setMin] = useState<number>(Number(route.params.get("min") || 50))
  const [data, setData] = useState<GraphResponse | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [allTies, setAllTies] = useState(false)
  const [minW, setMinW] = useState(0)
  const [mode, setMode] = useState<ColorMode>((route.params.get("c") as ColorMode) || "community")
  const [allNames, setAllNames] = useState(false)
  const [hover, setHover] = useState<number | null>(null)
  const [tip, setTip] = useState<{ x: number; y: number } | null>(null)
  const [selected, setSelected] = useState<number | null>(route.params.get("n") ? Number(route.params.get("n")) : null)
  const [vb, setVb] = useState<ViewBox | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const drag = useRef<{ x: number; y: number; vb: ViewBox; moved: boolean } | null>(null)
  const pick = useMemo(() => (route.params.get("sel") || "").split(",").filter(Boolean).map(Number), [route.params])
  const pickSet = useMemo(() => new Set(pick), [pick])
  const { rows: people, wrappedByCid } = useStore()
  const [sharedCount, setSharedCount] = useState<number | null>(null)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [pickerQ, setPickerQ] = useState("")
  const [filtersOpen, setFiltersOpen] = useState(false)

  // "X photos with all of them" for the summary strip
  useEffect(() => {
    if (pick.length === 0) {
      setSharedCount(null)
      return
    }
    let cancelled = false
    setSharedCount(null)
    api
      .shared(pick, null, 1)
      .then((d) => !cancelled && setSharedCount(d.count))
      .catch(() => !cancelled && setSharedCount(null))
    return () => {
      cancelled = true
    }
  }, [pick])

  useEffect(() => {
    let cancelled = false
    setData(null)
    setErr(null)
    api
      .graph(min)
      .then((d) => {
        if (cancelled) return
        setData(d)
        setVb({ x: 0, y: 0, w: d.W, h: d.H })
        setMinW(d.min_together)
      })
      .catch((e) => !cancelled && setErr(e instanceof Error ? e.message : String(e)))
    return () => {
      cancelled = true
    }
  }, [min])

  const setHash = useCallback(
    (patch: Record<string, string | null>) => {
      const p: Record<string, string | null> = {
        min: min === 50 ? null : String(min),
        c: mode === "community" ? null : mode,
        n: selected != null ? String(selected) : null,
        sel: pick.length ? pick.join(",") : null,
        event: route.params.get("event"), // keep the Photos tab's event filter alive
        ...patch,
      }
      go(buildHash("people", null, p))
    },
    [go, min, mode, selected, pick, route.params]
  )

  const nodes = data?.nodes ?? []
  const byId = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes])
  const clusters = (data?.communities ?? []) as Cluster[]
  // events count per person (for "N photos · M events"), from the store's people rows
  const eventsOf = useCallback(
    (cid: number) => Object.values(people.find((r) => r.cid === cid)?.events ?? ({} as Record<string, number>)).filter((v) => v > 0).length,
    [people]
  )
  // an "ego graph" page exists for named clusters via the live admin explorer route (no server change);
  // unnamed clusters have no meaningful ego page -> the pill is hidden
  const egoUrlOf = useCallback((n: GraphNode) => (n.labeled ? `/explore?cid=${n.id}` : null), [])

  const edges = useMemo(() => {
    const es = (data?.edges ?? []).filter(
      (e) => ((allTies || e.top === 1) && e.w >= minW) || pickSet.has(e.s) || pickSet.has(e.t)
    )
    return es
  }, [data, allTies, minW, pickSet])

  const neighbors = useMemo(() => {
    const m = new Map<number, { id: number; w: number }[]>()
    for (const e of data?.edges ?? []) {
      if (!m.has(e.s)) m.set(e.s, [])
      if (!m.has(e.t)) m.set(e.t, [])
      m.get(e.s)!.push({ id: e.t, w: e.w })
      m.get(e.t)!.push({ id: e.s, w: e.w })
    }
    for (const v of m.values()) v.sort((a, b) => b.w - a.w)
    return m
  }, [data])

  const focus = hover ?? selected
  // highlight = neighbours along the *displayed* edges (top ties by default)
  const focusSet = useMemo(() => {
    if (focus == null) return null
    const s = new Set<number>([focus])
    for (const e of edges) {
      if (e.s === focus) s.add(e.t)
      else if (e.t === focus) s.add(e.s)
    }
    return s
  }, [focus, edges])
  // selection neighbourhood: selected people + anyone connected to any of them (any tie)
  const pickHood = useMemo(() => {
    if (pick.length === 0) return null
    const s = new Set<number>(pick)
    for (const e of data?.edges ?? []) {
      if (pickSet.has(e.s)) s.add(e.t)
      if (pickSet.has(e.t)) s.add(e.s)
    }
    return s
  }, [pick, pickSet, data])
  const togglePick = useCallback(
    (id: number) => {
      const next = pickSet.has(id) ? pick.filter((c) => c !== id) : [...pick, id]
      setHash({ sel: next.length ? next.join(",") : null })
    },
    [pick, pickSet, setHash]
  )
  const pickerRows = useMemo(() => {
    const ql = pickerQ.trim().toLowerCase().replace(/^#/, "")
    const list = people
      .filter((r) => r.label?.status !== "not_guest" && r.label?.status !== "merged")
      .map((r) => ({ cid: r.cid, name: r.label?.name || `#${r.cid}`, face: r.face, photos: r.photos, named: !!r.label?.name }))
    const f = ql ? list.filter((r) => r.name.toLowerCase().includes(ql) || String(r.cid).startsWith(ql)) : list
    return f.slice(0, 60)
  }, [people, pickerQ])
  const faceOf = (cid: number) => byId.get(cid)?.img ?? people.find((r) => r.cid === cid)?.face
  const nameOfCid = (cid: number) => byId.get(cid)?.name ?? people.find((r) => r.cid === cid)?.label?.name ?? `#${cid}`

  // pan / zoom
  useEffect(() => {
    const svg = svgRef.current
    if (!svg) return
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      setVb((v) => {
        if (!v) return v
        const f = Math.exp(e.deltaY * 0.0015)
        const nw = Math.min(Math.max(v.w * f, 200), (data?.W ?? 1600) * 3)
        const nh = (nw / v.w) * v.h
        const r = svg.getBoundingClientRect()
        const px = v.x + ((e.clientX - r.left) / r.width) * v.w
        const py = v.y + ((e.clientY - r.top) / r.height) * v.h
        return { x: px - ((px - v.x) * nw) / v.w, y: py - ((py - v.y) * nh) / v.h, w: nw, h: nh }
      })
    }
    svg.addEventListener("wheel", onWheel, { passive: false })
    return () => svg.removeEventListener("wheel", onWheel)
  }, [data])

  const onPointerDown = (e: React.PointerEvent) => {
    if (!vb) return
    drag.current = { x: e.clientX, y: e.clientY, vb, moved: false }
    ;(e.currentTarget as Element).setPointerCapture(e.pointerId)
  }
  const onPointerMove = (e: React.PointerEvent) => {
    if (drag.current && vb) {
      const svg = svgRef.current!
      const r = svg.getBoundingClientRect()
      const dx = ((e.clientX - drag.current.x) / r.width) * drag.current.vb.w
      const dy = ((e.clientY - drag.current.y) / r.height) * drag.current.vb.h
      if (Math.abs(e.clientX - drag.current.x) + Math.abs(e.clientY - drag.current.y) > 3) drag.current.moved = true
      setVb({ ...drag.current.vb, x: drag.current.vb.x - dx, y: drag.current.vb.y - dy })
    }
    if (hover != null) setTip({ x: e.clientX, y: e.clientY })
  }
  const onPointerUp = () => {
    drag.current = null
  }
  const wasDrag = () => drag.current?.moved

  const sel = selected != null ? byId.get(selected) : undefined
  const selNeighbors = selected != null ? (neighbors.get(selected) ?? []).slice(0, 5) : []
  const egoUrl = sel ? egoUrlOf(sel) : null
  const hovNode = hover != null ? byId.get(hover) : undefined
  const hovNeighbors = hover != null ? (neighbors.get(hover) ?? []).slice(0, 5) : []

  const legend =
    mode === "community"
      ? (data?.communities ?? []).map((c) => ({ label: `Community ${c.community + 1}`, col: data!.PAL[c.community % data!.PAL.length] }))
      : [
          { label: "Groom's side", col: data?.DIV[0] ?? "#2a78d6" },
          { label: "Mixed", col: data?.DIV[2] ?? "#9a9a94" },
          { label: "Bride's side", col: data?.DIV[4] ?? "#eb6834" },
        ]

  return (
    <div className={embedded ? "" : "ws-page"}>
      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[20px] font-semibold tracking-tight">People — everyone, at once</h1>
          <p className="mt-0.5 text-[13px] text-ws-muted">
            {nodes.length} people with ≥{min} photos · clustered by community · this admin view is the whole wedding; each guest sees their own ego graph
          </p>
        </div>
        {/* top level keeps exactly two controls: Filters pill + people picker (#17) */}
        <div className="flex flex-wrap items-center gap-2 text-[13px]">
          <Popover open={filtersOpen} onOpenChange={setFiltersOpen}>
            <PopoverTrigger asChild>
              <button type="button" className="ws-btn inline-flex items-center gap-1.5" aria-expanded={filtersOpen}>
                <SlidersHorizontal className="h-3.5 w-3.5 opacity-70" /> Filters
              </button>
            </PopoverTrigger>
            <PopoverContent align="end" className="z-[85] w-[320px] p-3">
              <div className="flex flex-col gap-3.5 text-[13px]">
                <label className="flex flex-col gap-1">
                  <span className="flex items-center justify-between">
                    min photos
                    <select
                      className="ws-input py-1"
                      value={min}
                      onChange={(e) => {
                        const v = Number(e.target.value)
                        setMin(v)
                        setSelected(null)
                        setHash({ min: v === 50 ? null : String(v), n: null })
                      }}
                    >
                      {[15, 30, 50, 100].map((v) => (
                        <option key={v} value={v}>
                          {v}
                        </option>
                      ))}
                    </select>
                  </span>
                  <span className="text-[11px] text-ws-muted">only people with at least this many photos appear as nodes</span>
                </label>

                <label className="flex flex-col gap-1">
                  <span className="flex items-center gap-2">
                    <input type="checkbox" checked={allTies} onChange={(e) => setAllTies(e.target.checked)} /> all ties
                  </span>
                  <span className="text-[11px] text-ws-muted">draw every co-appearance, not just each person’s strongest few</span>
                </label>

                <label className="flex flex-col gap-1">
                  <span className="flex items-center gap-2">
                    min together
                    <input type="range" min={data?.min_together ?? 1} max={60} value={minW} onChange={(e) => setMinW(Number(e.target.value))} className="w-24 accent-ws-accent" />
                    <span className="w-6 tabular-nums">{minW}</span>
                  </span>
                  <span className="text-[11px] text-ws-muted">hide ties with fewer than this many shared photos</span>
                </label>

                <label className="flex flex-col gap-1">
                  <span className="flex items-center gap-2">
                    <input type="checkbox" checked={allNames} onChange={(e) => setAllNames(e.target.checked)} /> all names
                  </span>
                  <span className="text-[11px] text-ws-muted">label every face, not just the most-photographed people</span>
                </label>

                <div className="flex flex-col gap-1">
                  <span className="flex items-center justify-between gap-2">
                    colour by
                    <span className="flex items-center gap-1 rounded-lg border border-ws-line bg-white p-1">
                      {(["community", "side"] as ColorMode[]).map((m) => (
                        <label key={m} className={cn("cursor-pointer rounded-md px-2 py-0.5", mode === m && "bg-ws-ink text-white")}>
                          <input
                            type="radio"
                            name="cmode"
                            className="sr-only"
                            checked={mode === m}
                            onChange={() => {
                              setMode(m)
                              setHash({ c: m === "community" ? null : m })
                            }}
                          />
                          {m === "community" ? "community" : "bride ↔ groom"}
                        </label>
                      ))}
                    </span>
                  </span>
                  <span className="text-[11px] text-ws-muted">community hue, or lean toward the bride’s vs groom’s side</span>
                </div>
              </div>
            </PopoverContent>
          </Popover>

          <Popover open={pickerOpen} onOpenChange={(o) => { setPickerOpen(o); if (o) setPickerQ("") }}>
            <PopoverTrigger asChild>
              <button type="button" className="ws-btn min-w-[200px] justify-between" aria-expanded={pickerOpen}>
                <span className="text-ws-muted">{pick.length ? `${pick.length} selected — add more…` : "Pick people…"}</span>
                <ChevronsUpDown className="h-3.5 w-3.5 opacity-60" />
              </button>
            </PopoverTrigger>
            <PopoverContent align="end" className="z-[85] w-[360px] p-0" onOpenAutoFocus={(e) => e.preventDefault()}>
              <Command shouldFilter={false} loop>
                <CommandInput autoFocus value={pickerQ} onValueChange={setPickerQ} placeholder="Search a name or #id…" className="h-9" />
                <CommandList className="max-h-[360px]">
                  {pickerRows.length === 0 && <div className="px-3 py-3 text-[12px] text-ws-muted">No match.</div>}
                  {pickerRows.map((r) => {
                    const on = pickSet.has(r.cid)
                    return (
                      <CommandItem key={r.cid} value={`p-${r.cid}`} onSelect={() => togglePick(r.cid)} className="flex items-center gap-2 py-1.5">
                        <span className={cn("flex h-4 w-4 items-center justify-center rounded border", on ? "border-ws-accent bg-ws-accent text-white" : "border-ws-line")}>
                          {on && <Check className="h-3 w-3" />}
                        </span>
                        <img src={r.face} alt="" className="h-7 w-7 rounded-full object-cover" />
                        <span className={cn("min-w-0 flex-1 truncate text-[13px]", !r.named && "text-ws-muted")}>{r.name}</span>
                        <span className="text-[11px] tabular-nums text-ws-muted">{r.photos}</span>
                      </CommandItem>
                    )
                  })}
                </CommandList>
              </Command>
            </PopoverContent>
          </Popover>
        </div>
      </div>

      {/* selected people + selection summary (renders only when something is picked) */}
      {pick.length > 0 && (
        <div className="ws-panel mb-3 p-3">
          <div className="flex flex-wrap items-center gap-2">
            {pick.map((c) => (
              <span key={c} className="inline-flex items-center gap-1.5 rounded-full border border-ws-accent/60 bg-white py-0.5 pl-0.5 pr-1.5 text-[13px]">
                {faceOf(c) ? <img src={faceOf(c)} alt="" className="h-6 w-6 rounded-full object-cover" /> : <span className="h-6 w-6 rounded-full bg-ws-soft" />}
                {nameOfCid(c)}
                <button type="button" aria-label={`remove ${nameOfCid(c)}`} className="rounded-full p-0.5 text-ws-muted hover:text-ws-warn" onClick={() => togglePick(c)}>
                  <X className="h-3.5 w-3.5" />
                </button>
              </span>
            ))}
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2 border-t border-ws-line pt-2 text-[13px]">
            <span>
              <b className="font-semibold">{pick.length}</b> {pick.length === 1 ? "person" : "people"} selected ·{" "}
              {sharedCount == null ? <span className="text-ws-muted">counting…</span> : <><b className="font-semibold">{sharedCount.toLocaleString()}</b> photos with {pick.length === 1 ? "them" : "all of them"}</>}
            </span>
            <button type="button" className="ws-btn ws-btn--primary ws-btn--sm" onClick={() => go(buildHash("people", null, { tab: "photos", sel: pick.join(","), event: route.params.get("event") }))}>
              Show photos together →
            </button>
            <button type="button" className="ws-btn ws-btn--sm" onClick={() => setHash({ sel: null })}>
              Clear
            </button>
          </div>
        </div>
      )}

      {err && <div className="ws-panel mb-3 p-3 text-[13px] text-ws-warn">Couldn’t load /api/graph: {err}</div>}

      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="ws-panel relative overflow-hidden" style={{ aspectRatio: `${data?.W ?? 16} / ${data?.H ?? 10}` }}>
          {!data && !err && <div className="absolute inset-0 flex items-center justify-center text-[13px] text-ws-muted">Building the graph…</div>}
          {data && vb && (
            <svg
              ref={svgRef}
              viewBox={`${vb.x} ${vb.y} ${vb.w} ${vb.h}`}
              className="h-full w-full touch-none select-none"
              style={{ cursor: drag.current ? "grabbing" : "grab", background: "#fbfaf7" }}
              onPointerDown={onPointerDown}
              onPointerMove={onPointerMove}
              onPointerUp={onPointerUp}
              onPointerLeave={() => {
                onPointerUp()
                setHover(null)
                setTip(null)
              }}
              onClick={() => {
                if (!wasDrag()) {
                  setSelected(null)
                  setHash({ n: null })
                }
              }}
            >
              <defs>
                {nodes.map((n) => (
                  <clipPath key={n.id} id={`clip-${n.id}`}>
                    <circle cx={n.x} cy={n.y} r={n.r} />
                  </clipPath>
                ))}
              </defs>
              <g>
                {edges.map((e) => {
                  const a = byId.get(e.s)
                  const b = byId.get(e.t)
                  if (!a || !b) return null
                  const lit = focusSet ? focusSet.has(e.s) && focusSet.has(e.t) && (e.s === focus || e.t === focus) : true
                  const both = pickSet.has(e.s) && pickSet.has(e.t)
                  const one = !both && (pickSet.has(e.s) || pickSet.has(e.t))
                  let stroke = "#8a857a"
                  let op = e.top ? 0.35 : 0.18
                  let sw = e.sw
                  if (both) {
                    stroke = "#1a1a19"
                    op = 0.9
                    sw = e.sw + 1.5
                  } else if (one) {
                    stroke = "#9a6f1c"
                    op = 0.55
                  } else if (pickHood) {
                    op = 0.05
                  }
                  if (focusSet) {
                    if (lit) {
                      stroke = both ? "#1a1a19" : "#9a6f1c"
                      op = 0.9
                    } else op = Math.min(op, 0.06)
                  }
                  return (
                    <g key={`${e.s}-${e.t}`}>
                      <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={stroke} strokeWidth={sw} strokeOpacity={op} strokeLinecap="round" />
                      {both && (
                        <text
                          x={(a.x + b.x) / 2}
                          y={(a.y + b.y) / 2}
                          textAnchor="middle"
                          dominantBaseline="middle"
                          fontSize={11}
                          fontWeight={600}
                          fill="#1a1a19"
                          stroke="#fbfaf7"
                          strokeWidth={3}
                          paintOrder="stroke"
                          style={{ pointerEvents: "none" }}
                        >
                          {e.w}
                        </text>
                      )}
                    </g>
                  )
                })}
              </g>
              <g>
                {nodes.map((n) => {
                  const picked = pickSet.has(n.id)
                  const dim = focusSet ? !focusSet.has(n.id) : pickHood ? !pickHood.has(n.id) : false
                  const showLabel = picked || allNames || n.photos >= 100 || (focusSet ? focusSet.has(n.id) : false)
                  const ring = mode === "community" ? n.col : n.scol
                  return (
                    <FaceContextMenu key={n.id} cid={n.id} name={n.name} photos={n.photos} asChild>
                    <g
                      opacity={dim ? 0.15 : 1}
                      style={{ cursor: "pointer", transition: "opacity .15s" }}
                      onPointerEnter={(e) => {
                        setHover(n.id)
                        setTip({ x: e.clientX, y: e.clientY })
                      }}
                      onPointerLeave={() => {
                        setHover(null)
                        setTip(null)
                      }}
                      onClick={(e) => {
                        e.stopPropagation()
                        if (wasDrag()) return
                        if (e.shiftKey || e.metaKey || e.ctrlKey) {
                          setSelected(n.id)
                          setHash({ n: String(n.id) })
                        } else togglePick(n.id)
                      }}
                    >
                      {picked && <circle cx={n.x} cy={n.y} r={n.r + 6} fill="none" stroke="#9a6f1c" strokeWidth={4} />}
                      <circle cx={n.x} cy={n.y} r={n.r + 2.5} fill={ring} />
                      <image
                        href={n.img}
                        x={n.x - n.r}
                        y={n.y - n.r}
                        width={n.r * 2}
                        height={n.r * 2}
                        clipPath={`url(#clip-${n.id})`}
                        preserveAspectRatio="xMidYMid slice"
                      />
                      {selected === n.id && <circle cx={n.x} cy={n.y} r={n.r + 5} fill="none" stroke="#1a1a19" strokeWidth={2} />}
                      {showLabel && (
                        <text
                          x={n.x}
                          y={n.y + n.r + 12}
                          textAnchor="middle"
                          fontSize={Math.max(10, Math.min(14, n.r * 0.7))}
                          fill="#1a1a19"
                          stroke="#fbfaf7"
                          strokeWidth={3}
                          paintOrder="stroke"
                          style={{ fontFamily: "inherit", pointerEvents: "none" }}
                        >
                          {n.name}
                        </text>
                      )}
                    </g>
                    </FaceContextMenu>
                  )
                })}
              </g>
              {/* per-community mono captions — the non-colour encoding (#10) */}
              <g>
                {clusters.map((c) =>
                  c.label && c.lx != null && c.ly != null ? (
                    <text
                      key={c.community}
                      x={c.lx}
                      y={c.ly}
                      textAnchor="middle"
                      fontSize={16}
                      letterSpacing={1.4}
                      fill="#6f695e"
                      stroke="#fbfaf7"
                      strokeWidth={3.5}
                      paintOrder="stroke"
                      style={{ fontFamily: '"Geist Mono", ui-monospace, "SF Mono", Menlo, monospace', pointerEvents: "none" }}
                    >
                      {c.label.toUpperCase()}
                    </text>
                  ) : null
                )}
              </g>
            </svg>
          )}
          {/* legend */}
          {data && (
            <div className="pointer-events-none absolute bottom-2 left-2 flex flex-wrap gap-x-3 gap-y-1 rounded-md bg-white/85 px-2 py-1 text-[11px] backdrop-blur-sm">
              {legend.map((l) => (
                <span key={l.label} className="inline-flex items-center gap-1">
                  <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: l.col }} /> {l.label}
                </span>
              ))}
              <span className="inline-flex items-center gap-1 text-ws-muted">
                <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: data.PAL[7] }} /> couple
              </span>
            </div>
          )}
          {/* tooltip */}
          {hovNode && tip && (
            <div
              className="pointer-events-none fixed z-[85] max-w-[240px] rounded-md bg-ws-ink px-2.5 py-1.5 text-[12px] text-white shadow-lg"
              style={{
                left: Math.min(tip.x + 14, (typeof window !== "undefined" ? window.innerWidth : 9999) - 252),
                top: Math.min(tip.y + 14, (typeof window !== "undefined" ? window.innerHeight : 9999) - 130),
              }}
            >
              <div className="font-semibold">{hovNode.name}</div>
              <div className="text-white/70">{hovNode.photos.toLocaleString()} photos</div>
              {hovNeighbors.length > 0 && (
                <div className="mt-1 border-t border-white/15 pt-1 text-white/85">
                  {hovNeighbors.map((nb) => (
                    <div key={nb.id} className="flex justify-between gap-3">
                      <span className="truncate">{byId.get(nb.id)?.name ?? `#${nb.id}`}</span>
                      <span className="tabular-nums text-white/60">{nb.w}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* selection details -> right-hand panel (#9); no bottom-anchored / clipping card */}
        <div className="flex flex-col gap-3">
          <div className="ws-panel p-4">
            {sel ? (
              <>
                <div className="flex items-center gap-3.5">
                  <img
                    src={sel.img}
                    alt={sel.name}
                    className="h-14 w-14 shrink-0 rounded-full object-cover"
                    style={{ boxShadow: "0 0 0 3px #c98a1e" }}
                  />
                  <div className="min-w-0">
                    <div className="truncate font-serif text-[22px] leading-tight">{sel.name}</div>
                    <div className="text-[12px] text-ws-muted">
                      {sel.photos.toLocaleString()} photos · {eventsOf(sel.id)} {eventsOf(sel.id) === 1 ? "event" : "events"}
                      {!sel.labeled ? " · unnamed" : ""}
                    </div>
                  </div>
                </div>

                <div className="my-3.5 h-px bg-ws-line" />

                {selNeighbors.length > 0 && (
                  <div>
                    <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-ws-muted">Top ties</div>
                    <ul className="flex flex-col gap-2 text-[14px]">
                      {selNeighbors.map((nb) => {
                        const n = byId.get(nb.id)
                        return (
                          <li key={nb.id} className="flex items-center gap-2.5">
                            <button
                              type="button"
                              className="flex min-w-0 flex-1 items-center gap-2.5 text-left hover:underline"
                              onClick={() => { setSelected(nb.id); setHash({ n: String(nb.id) }) }}
                            >
                              {n && <img src={n.img} alt="" className="h-6 w-6 shrink-0 rounded-full object-cover" />}
                              <span className="truncate">{n?.name ?? `#${nb.id}`}</span>
                            </button>
                            <span className="tabular-nums text-[13px] text-ws-muted">{nb.w}</span>
                          </li>
                        )
                      })}
                    </ul>
                  </div>
                )}

                <div className="mt-4 flex flex-col gap-2">
                  {egoUrl && (
                    <a href={egoUrl} className="ws-btn ws-btn--primary justify-center text-center">
                      Open their ego graph
                    </a>
                  )}
                  {wrappedByCid[sel.id] && (
                    <button type="button" className="ws-btn justify-center text-center" onClick={() => go(buildHash("wrapped", wrappedByCid[sel.id]))}>
                      Open Wrapped
                    </button>
                  )}
                </div>
              </>
            ) : (
              <p className="text-[13px] text-ws-muted">
                Click a face to add it to your selection; shift-click (or ⌘/Ctrl-click) a face to open its details here — top ties, its ego graph, and its Wrapped.
              </p>
            )}
          </div>
        </div>
      </div>

      {data && data.communities.length > 0 && (
        <div className="ws-panel mt-3 overflow-x-auto">
          <table className="ws-table">
            <thead>
              <tr>
                <th className="w-[140px]">Community</th>
                <th className="w-[80px] text-right">People</th>
                <th className="w-[90px] text-right">Photos</th>
                <th>Members</th>
              </tr>
            </thead>
            <tbody>
              {clusters.map((c) => (
                <tr key={c.community}>
                  <td>
                    <span className="inline-flex items-center gap-2">
                      <span className="inline-block h-3 w-3 rounded-full" style={{ background: data.PAL[c.community % data.PAL.length] }} />
                      {c.label ?? `Community ${c.community + 1}`}
                    </span>
                  </td>
                  <td className="text-right tabular-nums">{c.people}</td>
                  <td className="text-right tabular-nums">{c.photos.toLocaleString()}</td>
                  <td className="text-[12px] text-ws-muted">{c.members}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export type { GraphEdge, GraphNode }
