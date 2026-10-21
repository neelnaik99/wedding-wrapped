import { useMemo, useRef, useState } from "react"
import { ArrowDown, ArrowUp, Download, Upload } from "lucide-react"
import { useStore } from "@/store"
import { buildHash, type Route } from "@/router"
import { api, EV_ABBR, EVN, EVENT_ORDER, guestLabel, rowStatus, STATUS_TEXT, type PersonRow, type RowStatus } from "@/api"
import NameCombobox from "@/components/NameCombobox"
import NamerDrawer from "@/views/NamerDrawer"
import { showUndoToast } from "@/hooks/use-toast"
import { cn } from "@/lib/utils"

type Filter = "all" | "unlabeled" | "named" | "provisional" | "duplicates" | "not_guest" | "merged"
type SortKey = "cid" | "photos" | "name" | "status" | "email" | "party"

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "unlabeled", label: "Unlabeled" },
  { key: "named", label: "Named" },
  { key: "provisional", label: "Provisional" },
  { key: "duplicates", label: "Duplicates" },
  { key: "not_guest", label: "Not a guest" },
  { key: "merged", label: "Merged" },
]

const STATUS_CLS: Record<RowStatus, string> = {
  named: "bg-emerald-50 text-ws-ok",
  provisional: "bg-amber-50 text-amber-700",
  unlabeled: "bg-ws-soft text-ws-muted",
  not_guest: "bg-red-50 text-ws-warn",
  merged: "bg-sky-50 text-sky-700",
}

export default function AdminView({ route, go }: { route: Route; go: (h: string) => void }) {
  const { rows, guests, loading, error, usedBy, saveLabel, undo, toast, refresh } = useStore()
  const [filter, setFilter] = useState<Filter>((route.params.get("f") as Filter) || "all")
  const [q, setQ] = useState(route.params.get("q") || "")
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "photos", dir: -1 })
  const fileRef = useRef<HTMLInputElement>(null)
  const openCid = route.params.get("cid") ? Number(route.params.get("cid")) : null

  const setHash = (patch: Record<string, string | null>) => {
    const p: Record<string, string | null> = { f: filter === "all" ? null : filter, q: q || null, cid: openCid != null ? String(openCid) : null, ...patch }
    go(buildHash("admin", null, p))
  }
  const openCluster = (cid: number | null) => setHash({ cid: cid == null ? null : String(cid) })

  const counts = useMemo(() => {
    const c: Record<RowStatus, number> = { named: 0, provisional: 0, unlabeled: 0, not_guest: 0, merged: 0 }
    for (const r of rows) c[rowStatus(r.label)] += 1
    const dupes = Object.values(usedBy).filter((v) => v.length > 1).length
    return { ...c, dupes, placed: Object.keys(usedBy).length }
  }, [rows, usedBy])

  const visible = useMemo(() => {
    const ql = q.trim().toLowerCase()
    let v = rows.filter((r) => {
      const st = rowStatus(r.label)
      if (filter === "unlabeled" && st !== "unlabeled") return false
      if (filter === "named" && st !== "named") return false
      if (filter === "provisional" && st !== "provisional") return false
      if (filter === "not_guest" && st !== "not_guest") return false
      if (filter === "merged" && st !== "merged") return false
      if (filter === "duplicates") {
        const g = r.label?.guest_id
        if (g == null || !(usedBy[g]?.length > 1)) return false
      }
      if (ql) {
        const hay = `${r.cid} ${r.label?.name ?? ""} ${r.label?.email ?? ""} ${r.label?.party ?? ""}`.toLowerCase()
        if (!hay.includes(ql)) return false
      }
      return true
    })
    const val = (r: PersonRow): string | number => {
      switch (sort.key) {
        case "cid":
          return r.cid
        case "photos":
          return r.photos
        case "name":
          return (r.label?.name ?? "").toLowerCase()
        case "status":
          return rowStatus(r.label)
        case "email":
          return (r.label?.email ?? "").toLowerCase()
        case "party":
          return (r.label?.party ?? "").toLowerCase()
      }
    }
    v = [...v].sort((a, b) => {
      const x = val(a)
      const y = val(b)
      if (x === y) return b.photos - a.photos
      if (typeof x === "number" && typeof y === "number") return (x - y) * sort.dir
      // empty strings last regardless of direction
      if (x === "") return 1
      if (y === "") return -1
      return String(x).localeCompare(String(y)) * sort.dir
    })
    return v
  }, [rows, filter, q, sort, usedBy])

  const toggleSort = (key: SortKey) =>
    setSort((s) => (s.key === key ? { key, dir: s.dir === 1 ? -1 : 1 } : { key, dir: key === "photos" || key === "cid" ? -1 : 1 }))

  const firstUnlabeled = rows.find((r) => rowStatus(r.label) === "unlabeled")

  // Destructive per-row actions answer with an inline Undo toast (#15) wired to the
  // server-side /api/undo (store.undo pops the last label change we just pushed).
  const rowNotGuest = (r: PersonRow) => {
    const who = r.label?.name || `#${r.cid}`
    void saveLabel(r.cid, { status: "not_guest" })
    showUndoToast({ message: `${who} marked not a guest`, onAction: () => void undo() })
  }
  const rowClear = (r: PersonRow) => {
    const who = r.label?.name || `#${r.cid}`
    void saveLabel(r.cid, null)
    showUndoToast({ message: `${who} cleared`, onAction: () => void undo() })
  }

  // Legend for the compact event-code column (#5). Codes come from EV_ABBR (the single
  // source of truth — this is where `Bm` was missing before), long names from EVN, in
  // EVENT_ORDER, so every code that can appear in a row also appears here.
  const eventLegend = EVENT_ORDER.map((e) => `${EV_ABBR[e] ?? e} ${EVN[e] ?? e}`).join(" · ")

  async function onImport(file: File) {
    const csv = await file.text()
    try {
      const r = await api.importCsv(csv)
      toast(`Imported ${r.n} row${r.n === 1 ? "" : "s"}`)
      await refresh()
    } catch (e) {
      toast(`Import failed: ${e instanceof Error ? e.message : String(e)}`)
    }
  }

  const Th = ({ k, children, className }: { k: SortKey; children: React.ReactNode; className?: string }) => (
    <th className={cn("sortable", className)} onClick={() => toggleSort(k)} aria-sort={sort.key === k ? (sort.dir === 1 ? "ascending" : "descending") : "none"}>
      <span className="inline-flex items-center gap-1">
        {children}
        {sort.key === k && (sort.dir === 1 ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />)}
      </span>
    </th>
  )

  return (
    // Full-height app frame under the fixed nav: nothing here scrolls the window (#3) —
    // the table gets its own scroll region and the drawer is an in-flow sibling column.
    <div
      className="flex flex-col overflow-hidden"
      style={{ height: "calc(100vh - var(--nav-h))", marginTop: "var(--nav-h)" }}
    >
      <div className="flex min-h-0 flex-1">
        {/* left column — header, filters, legend, and the table's own scroll container.
            Shrinks to the remaining width when the drawer opens beside it. */}
        <div className="flex min-h-0 min-w-0 flex-1 flex-col px-5 pb-4 pt-4 md:px-7">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[20px] font-semibold tracking-tight">People &amp; names</h1>
          <p className="mt-0.5 text-[13px] text-ws-muted">
            {rows.length} face clusters (≥15 photos) · {guests.length} guests ·{" "}
            <b className="font-medium text-ws-ink">{counts.placed}</b> guests placed
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="ws-btn ws-btn--primary"
            disabled={!firstUnlabeled}
            onClick={() => firstUnlabeled && openCluster(firstUnlabeled.cid)}
          >
            Start naming {firstUnlabeled ? `(#${firstUnlabeled.cid})` : "— all done"}
          </button>
          <a className="ws-btn" href="/api/export.csv" download="labels.csv">
            <Download className="h-3.5 w-3.5" /> Export CSV
          </a>
          <button type="button" className="ws-btn" onClick={() => fileRef.current?.click()}>
            <Upload className="h-3.5 w-3.5" /> Import CSV
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) void onImport(f)
              e.target.value = ""
            }}
          />
        </div>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="flex flex-wrap gap-1 rounded-lg border border-ws-line bg-white p-1">
          {FILTERS.map((f) => {
            const n =
              f.key === "all"
                ? rows.length
                : f.key === "duplicates"
                  ? counts.dupes
                  : counts[f.key as RowStatus]
            return (
              <button
                key={f.key}
                type="button"
                onClick={() => {
                  setFilter(f.key)
                  setHash({ f: f.key === "all" ? null : f.key })
                }}
                className={cn(
                  "rounded-md px-2.5 py-1 text-[12px] font-medium",
                  filter === f.key ? "bg-ws-ink text-white" : "text-ws-muted hover:bg-ws-soft hover:text-ws-ink"
                )}
              >
                {f.label} <span className={cn("ml-0.5 tabular-nums", filter === f.key ? "text-white/70" : "text-ws-muted/70")}>{n}</span>
              </button>
            )
          })}
        </div>
        <input
          className="ws-input w-[240px]"
          placeholder="Search name, email, household, #id"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onBlur={() => setHash({ q: q || null })}
        />
        <span className="text-[12px] text-ws-muted">{visible.length} shown</span>
      </div>

      {/* Event-code legend (#5): mono caption, contrast-safe gold; codes match the Events column. */}
      <div className="mb-3 font-mono text-[10px] leading-relaxed tracking-[0.06em] text-ws-accentText">
        {eventLegend}
      </div>

      {error && <div className="ws-panel mb-3 p-3 text-[13px] text-ws-warn">Couldn’t load /api/people: {error}</div>}

      {/* The table's own scroll container (#3): vertical + horizontal scroll live here, never
          on the window; the sticky <th> pins to the top of THIS box (top:0, not nav height). */}
      <div className="ws-panel min-h-0 flex-1 overflow-auto">
        <table className="ws-table [&_th]:!top-0">
          <thead>
            <tr>
              <th className="w-[52px]">Face</th>
              <Th k="cid" className="w-[64px]">#id</Th>
              <Th k="photos" className="w-[80px] text-right">Photos</Th>
              <th className="min-w-[200px]">Events</th>
              <Th k="status" className="w-[100px]">Status</Th>
              <Th k="name" className="min-w-[200px]">Name</Th>
              <Th k="email" className="min-w-[150px]">Email</Th>
              <Th k="party" className="min-w-[120px]">Household</Th>
              {/* Actions pinned to the right edge of the horizontal scroll (#6) so they're
                  reachable at any width, incl. 1280px with the drawer open. */}
              <th className="sticky right-0 w-[210px] border-l border-ws-line">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={9} className="py-10 text-center text-ws-muted">Loading people…</td>
              </tr>
            )}
            {!loading && visible.length === 0 && (
              <tr>
                <td colSpan={9} className="py-10 text-center text-ws-muted">Nothing matches.</td>
              </tr>
            )}
            {visible.map((r) => {
              const st = rowStatus(r.label)
              const gid = r.label?.guest_id
              const also = gid != null ? (usedBy[gid] ?? []).filter((c) => c !== r.cid) : []
              const activeEvents = EVENT_ORDER.filter((e) => r.events[e])
              return (
                <tr key={r.cid} className={cn(openCid === r.cid && "is-selected")}>
                  <td>
                    <button
                      type="button"
                      onClick={() => openCluster(r.cid)}
                      className="block h-9 w-9 overflow-hidden rounded-md ring-1 ring-ws-line hover:ring-ws-accent"
                      title={`Open #${r.cid}`}
                    >
                      <img src={r.face} alt="" loading="lazy" className="h-full w-full object-cover" />
                    </button>
                  </td>
                  <td className="tabular-nums text-ws-muted">
                    <button type="button" className="hover:text-ws-ink hover:underline" onClick={() => openCluster(r.cid)}>
                      #{r.cid}
                    </button>
                  </td>
                  <td className="text-right tabular-nums">{r.photos.toLocaleString()}</td>
                  <td className="max-w-[300px] text-[11.5px] leading-snug text-ws-muted">
                    {activeEvents.map((e, i) => (
                      <span key={e} title={`${EVN[e] ?? e} — ${r.events[e].toLocaleString()} photos`} className="whitespace-nowrap">
                        {EV_ABBR[e] ?? e} {r.events[e]}
                        {i < activeEvents.length - 1 ? " · " : ""}
                      </span>
                    ))}
                  </td>
                  <td>
                    <span className={cn("ws-chip", STATUS_CLS[st])}>{STATUS_TEXT[st]}</span>
                  </td>
                  <td>
                    {st === "merged" ? (
                      <span className="text-[13px] text-ws-muted">
                        → #{r.label.merge_into}
                        {r.label.merge_into != null && rows.find((x) => x.cid === r.label.merge_into)?.label?.name
                          ? ` (${rows.find((x) => x.cid === r.label.merge_into)?.label?.name})`
                          : ""}
                      </span>
                    ) : st === "not_guest" ? (
                      <span className="text-[13px] text-ws-muted">—</span>
                    ) : (
                      <div className="min-w-0">
                        <NameCombobox
                          cid={r.cid}
                          label={r.label}
                          clusterEvents={r.events}
                          guests={guests}
                          usedBy={usedBy}
                          onPickGuest={(g) => void saveLabel(r.cid, guestLabel(g))}
                          onCustomName={(name) => void saveLabel(r.cid, { status: "labeled", name })}
                          onClear={() => void saveLabel(r.cid, null)}
                        />
                        {also.length > 0 && (
                          <div className="mt-0.5 text-[11px] text-ws-warn">
                            also #{also.join(", #")}
                          </div>
                        )}
                      </div>
                    )}
                  </td>
                  <td className="max-w-[200px] truncate text-[12px] text-ws-muted">{r.label?.email || ""}</td>
                  <td className="max-w-[160px] truncate text-[12px] text-ws-muted" title={r.label?.party || ""}>
                    {householdName(r.label?.party, guests)}
                  </td>
                  <td className="sticky right-0 z-[1] border-l border-ws-line bg-white [.is-selected_&]:!bg-[#fdf6e6] [tr:hover_&]:bg-[#fbfaf7]">
                    <div className="flex flex-nowrap gap-1">
                      {st === "provisional" && (
                        <button
                          type="button"
                          className="ws-btn ws-btn--sm border-ws-ok text-ws-ok"
                          onClick={() => {
                            const { provisional: _p, ...rest } = r.label
                            void saveLabel(r.cid, { ...rest })
                          }}
                        >
                          confirm
                        </button>
                      )}
                      {st !== "not_guest" && (
                        <button type="button" className="ws-btn ws-btn--sm" onClick={() => rowNotGuest(r)}>
                          not a guest
                        </button>
                      )}
                      {st !== "unlabeled" && (
                        <button type="button" className="ws-btn ws-btn--sm" onClick={() => rowClear(r)}>
                          clear
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
        </div>

        {/* Drawer is a right-anchored sibling of the left column (#3): an in-flow ~400px
            column on desktop so the table reflows to the remaining width, and a
            full-screen sheet below 768px. */}
        {openCid != null && (
          <NamerDrawer
            cid={openCid}
            onClose={() => openCluster(null)}
            onNavigate={(cid) => openCluster(cid)}
            go={go}
          />
        )}
      </div>
    </div>
  )
}

/** Party ids look like "<uuid>-First-Last"; show the envelope name if we can find it, else the readable tail. */
function householdName(party: string | undefined, guests: { party: string; envelope: string }[]): string {
  if (!party) return ""
  const g = guests.find((x) => x.party === party && x.envelope)
  if (g) return g.envelope
  const m = party.match(/^[0-9a-f-]{36}-(.+)$/i)
  return m ? m[1].replace(/-/g, " ") : party
}
