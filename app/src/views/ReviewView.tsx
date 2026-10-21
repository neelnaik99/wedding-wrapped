import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Check, Palette, RefreshCw, SlidersHorizontal } from "lucide-react"
import { useStore } from "@/store"
import type { Route } from "@/router"
import { cn } from "@/lib/utils"

/**
 * Pre-send review queue (issue #33). One row per FLAGGED guest — a tier misfire (photo count
 * within +-15 of a 15 / 50 / 150 boundary) or a fallback-derived accent — so the couple can
 * eyeball the risky decks in minutes before sending. Three actions, all persisted to the files
 * build_guests.py consumes: Approve (review_state), Override tier (data/tier_override.json),
 * Swap accent (data/palette_override.json). Keyboard, naming-drawer style: A approve, O override,
 * S swap, J/K (or arrows) move. Server route: /api/review_queue (GET), /api/review (POST).
 */

interface ReviewRow {
  cid: number
  name: string
  n_photos: number
  tier: string
  boundary_distance: number
  flags: string[]
  accent_fallback: boolean
  accent: string
  support: string
  accent_ink: string
  cover: string
  best_shot: string
  email: string
  reviewed: boolean
}
interface ReviewQueue {
  rows: ReviewRow[]
  total: number
  reviewed: number
  boundaries: number[]
  tiers: string[]
}
type ReviewOp =
  | { op: "approve" | "unapprove"; cid: number }
  | { op: "override_tier"; cid: number; tier: string }
  | { op: "swap_accent"; cid: number; accent: string; support: string }

const TIERS = ["inner", "group", "cameo", "glimpse", "light"]
const TIER_HINT: Record<string, string> = {
  inner: "150+ · full deck",
  group: "50–149 · full deck",
  cameo: "15–49 · postcard",
  glimpse: "<15 · no own link",
  light: "set by hand · light Deck (solo) / ordinary member (family)",
}
// On-brand accent/support pairs, each accent verified to clear 4.5:1 on one of the fixed inks
// (the server re-checks and rejects anything that doesn't). First is guest_palette's own fallback.
const ACCENT_PRESETS: { name: string; accent: string; support: string }[] = [
  { name: "Marigold", accent: "#c98a1e", support: "#26365c" },
  { name: "Haldi", accent: "#e8b04b", support: "#26365c" },
  { name: "Rose", accent: "#d98a8a", support: "#7a5a86" },
  { name: "Sage", accent: "#8bab8b", support: "#cf7a52" },
  { name: "Teal", accent: "#4fa3a3", support: "#e08a6a" },
  { name: "Gold", accent: "#d4a63c", support: "#26365c" },
]

async function getQueue(all: boolean): Promise<ReviewQueue> {
  const r = await fetch(all ? "/api/review_queue?all=1" : "/api/review_queue", { cache: "no-store" })
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
  return (await r.json()) as ReviewQueue
}
async function postReview(body: ReviewOp): Promise<{ ok: boolean; row?: ReviewRow; error?: string }> {
  const r = await fetch("/api/review", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  return (await r.json()) as { ok: boolean; row?: ReviewRow; error?: string }
}

function flagLabel(f: string): string {
  return f === "boundary" ? "near tier boundary" : f === "fallback" ? "fallback accent" : f === "light" ? "marked light" : f
}

export default function ReviewView(_props: { route: Route; go: (h: string) => void }) {
  const { toast } = useStore()
  const [data, setData] = useState<ReviewQueue | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [active, setActive] = useState(0)
  const [tierMenu, setTierMenu] = useState<number | null>(null) // cid whose tier picker is open
  const [accentMenu, setAccentMenu] = useState<number | null>(null) // cid whose accent picker is open
  const [showAll, setShowAll] = useState(false) // true → every labeled guest, not just flagged ones
  const [busy, setBusy] = useState<number | null>(null) // cid mid-request
  const rowRefs = useRef<Record<number, HTMLDivElement | null>>({})

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const d = await getQueue(showAll)
      setData(d)
      setErr(null)
      setActive((a) => Math.min(a, Math.max(0, d.rows.length - 1)))
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [showAll])

  useEffect(() => {
    void load()
  }, [load])

  const rows = useMemo(() => data?.rows ?? [], [data])
  const reviewedCount = useMemo(() => rows.filter((r) => r.reviewed).length, [rows])
  const closeMenus = useCallback(() => {
    setTierMenu(null)
    setAccentMenu(null)
  }, [])

  const patchRow = useCallback((row: ReviewRow) => {
    setData((d) => (d ? { ...d, rows: d.rows.map((r) => (r.cid === row.cid ? row : r)) } : d))
  }, [])

  // Move focus to the next not-yet-reviewed row (wraps); called after an approve.
  const advance = useCallback(() => {
    setActive((cur) => {
      const n = rows.length
      if (!n) return 0
      for (let i = 1; i <= n; i++) {
        const j = (cur + i) % n
        if (!rows[j].reviewed) return j
      }
      return cur
    })
  }, [rows])

  const run = useCallback(
    async (body: ReviewOp, after?: () => void): Promise<boolean> => {
      setBusy(body.cid)
      try {
        const res = await postReview(body)
        if (!res.ok || !res.row) {
          toast(res.error ? `Couldn’t save: ${res.error}` : "Save failed")
          return false
        }
        patchRow(res.row)
        after?.()
        return true
      } catch (e) {
        toast(`Save failed: ${e instanceof Error ? e.message : String(e)}`)
        return false
      } finally {
        setBusy(null)
      }
    },
    [patchRow, toast]
  )

  const approve = useCallback(
    async (row: ReviewRow) => {
      const wasReviewed = row.reviewed
      const ok = await run({ op: wasReviewed ? "unapprove" : "approve", cid: row.cid })
      if (ok && !wasReviewed) advance()
    },
    [run, advance]
  )
  const overrideTier = useCallback(
    (cid: number, tier: string) => run({ op: "override_tier", cid, tier }, () => { setTierMenu(null); toast(`Tier set to ${tier}`) }),
    [run, toast]
  )
  const swapAccent = useCallback(
    (cid: number, accent: string, support: string) =>
      run({ op: "swap_accent", cid, accent, support }, () => { setAccentMenu(null); toast(`Accent swapped to ${accent}`) }),
    [run, toast]
  )

  // Keyboard: naming-drawer rapid loop. Ignore while typing or when a picker is open.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = document.activeElement
      if (el && /^(input|textarea|select)$/i.test(el.tagName)) return
      if (e.metaKey || e.ctrlKey || e.altKey) return
      if (tierMenu != null || accentMenu != null) {
        if (e.key === "Escape") closeMenus()
        return
      }
      const row = rows[active]
      const k = e.key.toLowerCase()
      if (k === "a" && row) { e.preventDefault(); void approve(row) }
      else if (k === "o" && row) { e.preventDefault(); setAccentMenu(null); setTierMenu(row.cid) }
      else if (k === "s" && row) { e.preventDefault(); setTierMenu(null); setAccentMenu(row.cid) }
      else if (k === "j" || e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(rows.length - 1, a + 1)) }
      else if (k === "k" || e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(0, a - 1)) }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [rows, active, approve, tierMenu, accentMenu, closeMenus])

  // Keep the active row in view during keyboard navigation.
  useEffect(() => {
    const row = rows[active]
    if (row) rowRefs.current[row.cid]?.scrollIntoView({ block: "nearest" })
  }, [active, rows])

  const pct = data && data.total ? Math.round((reviewedCount / data.total) * 100) : 0

  return (
    <div className="ws-page">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[20px] font-semibold tracking-tight">Review — flagged decks before you send</h1>
          <p className="mt-0.5 text-[13px] text-ws-muted">
            Tier misfires and fallback accents, riskiest first. Keys:{" "}
            <kbd className="rounded bg-ws-soft px-1 text-[10px]">A</kbd> approve ·{" "}
            <kbd className="rounded bg-ws-soft px-1 text-[10px]">O</kbd> tier ·{" "}
            <kbd className="rounded bg-ws-soft px-1 text-[10px]">S</kbd> accent ·{" "}
            <kbd className="rounded bg-ws-soft px-1 text-[10px]">J</kbd>/
            <kbd className="rounded bg-ws-soft px-1 text-[10px]">K</kbd> move
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <div className="text-[13px] font-semibold tabular-nums">
              {reviewedCount} of {data?.total ?? 0} reviewed
            </div>
            <div className="mt-1 h-1.5 w-[160px] overflow-hidden rounded-full bg-ws-soft">
              <div className="h-full rounded-full bg-ws-accent transition-[width]" style={{ width: `${pct}%` }} />
            </div>
          </div>
          <label className="flex items-center gap-1.5 text-[12px]">
            <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} /> Show all guests
          </label>
          <button type="button" className="ws-btn" onClick={() => void load()} disabled={loading}>
            <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} /> Refresh
          </button>
        </div>
      </div>

      {err && <div className="ws-panel mb-3 p-3 text-[13px] text-ws-warn">Couldn’t load /api/review_queue: {err}</div>}

      {loading && !data && (
        <div className="ws-panel p-6 text-center text-[13px] text-ws-muted">
          Deriving each guest’s palette from their photos… (first load takes a few seconds)
        </div>
      )}

      {data && rows.length === 0 && !loading && (
        <div className="ws-panel p-6 text-center text-[13px] text-ws-muted">
          Nothing flagged — every guest is clear of a tier boundary and has a derived accent. 🎉
        </div>
      )}

      <div className="flex flex-col gap-2.5">
        {rows.map((r, i) => {
          const isActive = i === active
          return (
            <div
              key={r.cid}
              ref={(el) => { rowRefs.current[r.cid] = el }}
              onClick={() => setActive(i)}
              className={cn(
                "ws-panel flex flex-wrap items-center gap-4 p-3 transition-shadow",
                isActive && "ring-2 ring-ws-accent",
                r.reviewed && "opacity-70"
              )}
            >
              {/* thumbnails: cover (deck hero) + best shot */}
              <div className="flex gap-1.5">
                {[
                  { src: r.cover, label: "cover" },
                  { src: r.best_shot, label: "best" },
                ].map((t) => (
                  <figure key={t.label} className="m-0">
                    <div className="h-[76px] w-[62px] overflow-hidden rounded-md bg-ws-soft ring-1 ring-ws-line">
                      <img src={t.src} alt={`${r.name} ${t.label}`} loading="lazy" className="h-full w-full object-cover" />
                    </div>
                    <figcaption className="mt-0.5 text-center text-[9px] uppercase tracking-wide text-ws-muted">{t.label}</figcaption>
                  </figure>
                ))}
              </div>

              {/* identity + flags */}
              <div className="min-w-[180px] flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-[15px] font-semibold">{r.name}</span>
                  <span className="text-[11px] text-ws-muted">#{r.cid}</span>
                  {r.reviewed && (
                    <span className="ws-chip bg-emerald-50 text-ws-ok">
                      <Check className="h-3 w-3" /> reviewed
                    </span>
                  )}
                </div>
                <div className="mt-0.5 text-[12px] text-ws-muted">
                  <b className="font-medium text-ws-ink tabular-nums">{r.n_photos.toLocaleString()}</b> photos ·{" "}
                  <span className="tabular-nums">{r.boundary_distance}</span> from nearest boundary
                  {r.email ? <> · {r.email}</> : null}
                </div>
                <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                  {r.flags.map((f) => (
                    <span
                      key={f}
                      className={cn("ws-chip", f === "fallback" ? "bg-amber-50 text-amber-700" : "bg-orange-50 text-orange-700")}
                    >
                      {flagLabel(f)}
                    </span>
                  ))}
                </div>
              </div>

              {/* current tier */}
              <div className="min-w-[92px]">
                <div className="text-[10px] uppercase tracking-wide text-ws-muted">tier</div>
                <div className="text-[14px] font-semibold capitalize">{r.tier}</div>
                <div className="text-[10.5px] text-ws-muted">{TIER_HINT[r.tier]}</div>
              </div>

              {/* accent + support swatches */}
              <div className="flex items-center gap-2">
                {[
                  { hex: r.accent, label: "accent" },
                  { hex: r.support, label: "support" },
                ].map((s) => (
                  <div key={s.label} className="text-center">
                    <div className="h-9 w-9 rounded-md ring-1 ring-ws-line" style={{ background: s.hex }} title={`${s.label} ${s.hex}`} />
                    <div className="mt-0.5 font-mono text-[9.5px] text-ws-muted">{s.hex}</div>
                  </div>
                ))}
              </div>

              {/* actions */}
              <div className="relative ml-auto flex items-center gap-1.5">
                <button
                  type="button"
                  className={cn("ws-btn", !r.reviewed && "ws-btn--primary")}
                  disabled={busy === r.cid}
                  onClick={(e) => { e.stopPropagation(); void approve(r) }}
                >
                  <Check className="h-3.5 w-3.5" /> {r.reviewed ? "Undo" : "Approve"}
                </button>

                <button
                  type="button"
                  className="ws-btn"
                  disabled={busy === r.cid}
                  onClick={(e) => { e.stopPropagation(); setAccentMenu(null); setTierMenu(tierMenu === r.cid ? null : r.cid) }}
                >
                  <SlidersHorizontal className="h-3.5 w-3.5" /> Tier
                </button>
                {tierMenu === r.cid && (
                  <div className="absolute right-0 top-[calc(100%+4px)] z-20 w-[220px] rounded-lg border border-ws-line bg-white p-1 shadow-lg">
                    {(data?.tiers ?? TIERS).map((t) => (
                      <button
                        key={t}
                        type="button"
                        className={cn(
                          "flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-[13px] hover:bg-ws-soft",
                          t === r.tier && "font-semibold text-ws-accentText"
                        )}
                        onClick={(e) => { e.stopPropagation(); void overrideTier(r.cid, t) }}
                      >
                        <span className="capitalize">{t}</span>
                        <span className="text-[10.5px] text-ws-muted">{TIER_HINT[t]}</span>
                      </button>
                    ))}
                  </div>
                )}

                <button
                  type="button"
                  className="ws-btn"
                  disabled={busy === r.cid}
                  onClick={(e) => { e.stopPropagation(); setTierMenu(null); setAccentMenu(accentMenu === r.cid ? null : r.cid) }}
                >
                  <Palette className="h-3.5 w-3.5" /> Accent
                </button>
                {accentMenu === r.cid && (
                  <div className="absolute right-0 top-[calc(100%+4px)] z-20 w-[220px] rounded-lg border border-ws-line bg-white p-2 shadow-lg">
                    <div className="mb-1 text-[11px] text-ws-muted">Swap in a safe pair</div>
                    <div className="grid grid-cols-2 gap-1.5">
                      {ACCENT_PRESETS.map((p) => (
                        <button
                          key={p.accent}
                          type="button"
                          className="flex items-center gap-1.5 rounded-md border border-ws-line px-1.5 py-1 hover:border-ws-accent"
                          onClick={(e) => { e.stopPropagation(); void swapAccent(r.cid, p.accent, p.support) }}
                        >
                          <span className="h-4 w-4 rounded ring-1 ring-black/10" style={{ background: p.accent }} />
                          <span className="h-4 w-4 rounded ring-1 ring-black/10" style={{ background: p.support }} />
                          <span className="text-[11px]">{p.name}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
