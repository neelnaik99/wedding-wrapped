import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { ChevronLeft, ChevronRight, X } from "lucide-react"
import { useStore } from "@/store"
import { api, EVN, RSVP, guestLabel, rowStatus, type ClusterPayload, type Label } from "@/api"
import { cn } from "@/lib/utils"
import PhotoLightbox, { type BoxedPhoto } from "@/components/PhotoLightbox"
import FaceContextMenu from "@/components/FaceContextMenu"
import { buildHash } from "@/router"

const MOD = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform) ? "⌘" : "Ctrl+"

interface Props {
  cid: number
  onClose: () => void
  onNavigate: (cid: number) => void
  go: (hash: string) => void
}

export default function NamerDrawer({ cid, onClose, onNavigate, go }: Props) {
  const { rows, guests, usedBy, saveLabel, toast, names } = useStore()
  const [cur, setCur] = useState<ClusterPayload | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [q, setQ] = useState("")
  const [sel, setSel] = useState(0)
  const [lb, setLb] = useState<number | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const idx = rows.findIndex((r) => r.cid === cid)
  const row = idx >= 0 ? rows[idx] : null
  const label: Label | null = row ? row.label : cur?.label ?? null
  const st = rowStatus(label)

  // load cluster payload
  useEffect(() => {
    let cancelled = false
    setCur(null)
    setErr(null)
    setLb(null)
    api
      .cluster(cid)
      .then((d) => {
        if (cancelled) return
        setCur(d)
        setQ(d.label && d.label.name && d.label.status !== "not_guest" ? d.label.name : "")
        setSel(0)
        setTimeout(() => inputRef.current?.focus(), 30)
      })
      .catch((e) => !cancelled && setErr(e instanceof Error ? e.message : String(e)))
    return () => {
      cancelled = true
    }
  }, [cid])

  // Section membership (#14) is decided by RSVP-event overlap with the cluster and is
  // computed once per cluster — NOT per keystroke — so an entry never jumps across the
  // divider while the user types. Likely matches sort by overlap; everyone else is
  // alphabetical. Order within a section is fixed; typing only filters, never re-sorts.
  const sections = useMemo(() => {
    const evs = new Set(Object.keys(cur?.events ?? {}).map((e) => RSVP[e] ?? e))
    const withMeta = guests.map((g) => {
      let fit = 0
      for (const e of evs) if (g.events[e]) fit += 1
      const used = usedBy[g.id]?.filter((c) => c !== cid)
      return { g, fit, usedBy: used && used.length ? used : undefined }
    })
    const likely = withMeta
      .filter((x) => x.fit > 0)
      .sort((a, b) => b.fit - a.fit || a.g.name.localeCompare(b.g.name))
    const others = withMeta
      .filter((x) => x.fit === 0)
      .sort((a, b) => a.g.name.localeCompare(b.g.name))
    return { likely, others }
  }, [guests, cur?.events, usedBy, cid])

  const ql = q.trim().toLowerCase()
  const hitsQ = (g: { name: string; email: string }) =>
    !ql || g.name.toLowerCase().includes(ql) || (g.email?.toLowerCase().includes(ql) ?? false)
  const likelyView = useMemo(() => sections.likely.filter((x) => hitsQ(x.g)).slice(0, 8), [sections, ql])
  const elseView = useMemo(() => sections.others.filter((x) => hitsQ(x.g)).slice(0, 8), [sections, ql])
  // flat list backing keyboard selection (Likely first, then Everyone else)
  const sugs = useMemo(() => [...likelyView, ...elseView], [likelyView, elseView])
  useEffect(() => setSel((s) => Math.min(s, Math.max(0, sugs.length - 1))), [sugs.length])

  const renderSug = (x: (typeof sugs)[number], k: number) => (
    <li
      key={x.g.id}
      onMouseEnter={() => setSel(k)}
      onClick={() => {
        setSel(k)
        void saveLabel(cid, guestLabel(x.g)).then(() => skip())
      }}
      className={cn(
        "flex cursor-pointer items-center justify-between gap-2 px-2.5 py-1.5 text-[13px]",
        k === sel ? "bg-amber-50" : "hover:bg-ws-soft"
      )}
    >
      <span className="min-w-0 truncate">
        {x.g.name}
        {x.g.email && <span className="ml-1.5 text-[11px] text-ws-muted">{x.g.email}</span>}
      </span>
      <span className="flex shrink-0 gap-1">
        {x.usedBy && <span className="ws-chip bg-red-50 text-ws-warn">already #{x.usedBy.join(", #")}</span>}
        {x.fit > 0 && <span className="ws-chip bg-emerald-50 text-ws-ok">{x.fit} events match</span>}
      </span>
    </li>
  )

  const goPrev = useCallback(() => idx > 0 && onNavigate(rows[idx - 1].cid), [idx, rows, onNavigate])
  const goNext = useCallback(() => idx >= 0 && idx < rows.length - 1 && onNavigate(rows[idx + 1].cid), [idx, rows, onNavigate])
  /** next unlabeled after this one, else just the next */
  const skip = useCallback(() => {
    const n = rows.findIndex((r, k) => k > idx && rowStatus(r.label) === "unlabeled")
    const t = n >= 0 ? n : Math.min(idx + 1, rows.length - 1)
    if (t !== idx && t >= 0) onNavigate(rows[t].cid)
  }, [rows, idx, onNavigate])

  const assign = useCallback(async () => {
    const x = sugs[sel]
    if (x) {
      await saveLabel(cid, guestLabel(x.g))
      skip()
    } else if (q.trim()) {
      await saveLabel(cid, { status: "labeled", name: q.trim() })
      skip()
    }
  }, [sugs, sel, saveLabel, cid, q, skip])
  const notGuest = useCallback(async () => {
    await saveLabel(cid, { status: "not_guest" })
    skip()
  }, [saveLabel, cid, skip])
  const clear = useCallback(() => void saveLabel(cid, null), [saveLabel, cid])
  const merge = useCallback(
    async (into: number) => {
      const tgt = rows.find((r) => r.cid === into)?.label
      const l: Label = tgt && tgt.status === "labeled" ? { ...tgt } : { status: "merged", merge_into: into }
      await saveLabel(cid, l)
      toast(`#${cid} merged into #${into}${tgt?.name ? ` (${tgt.name})` : ""}`)
      skip()
    },
    [rows, saveLabel, cid, toast, skip]
  )
  const confirmProvisional = useCallback(() => {
    if (!label) return
    const { provisional: _p, ...rest } = label
    void saveLabel(cid, rest)
  }, [label, saveLabel, cid])

  // keyboard: Enter = assign · ↑/↓ = pick · ⌘/Ctrl+→ next/skip · ⌘/Ctrl+← prev · ⌘/Ctrl+. not a guest
  // · ⌘/Ctrl+/ merge into first similar · ⌘/Ctrl+Backspace clear · Esc close.
  // Plain letters always go to the search box (never bound as shortcuts).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (lb != null) return // lightbox handles its own keys
      if (document.querySelector('[role="dialog"]')) return
      const inQ = document.activeElement === inputRef.current
      const mod = e.metaKey || e.ctrlKey
      if (e.key === "Escape") {
        e.preventDefault()
        onClose()
        return
      }
      if (mod && !e.altKey && !e.shiftKey) {
        if (e.key === "ArrowRight") {
          e.preventDefault()
          skip()
        } else if (e.key === "ArrowLeft") {
          e.preventDefault()
          goPrev()
        } else if (e.key === ".") {
          e.preventDefault()
          void notGuest()
        } else if (e.key === "/") {
          e.preventDefault()
          if (cur?.similar[0]) void merge(cur.similar[0].cid)
        } else if (e.key === "Backspace") {
          e.preventDefault()
          clear()
        }
        return
      }
      if (mod) return
      if (e.key === "Enter") {
        e.preventDefault()
        void assign()
      } else if (e.key === "ArrowDown") {
        e.preventDefault()
        setSel((s) => Math.min(s + 1, sugs.length - 1))
      } else if (e.key === "ArrowUp") {
        e.preventDefault()
        setSel((s) => Math.max(s - 1, 0))
      } else if (!inQ && e.key.length === 1 && !e.altKey) {
        // any printable character → search box
        inputRef.current?.focus()
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [lb, sugs.length, assign, goPrev, skip, notGuest, merge, clear, cur, onClose])

  const lbPhotos: BoxedPhoto[] = useMemo(
    () =>
      (cur?.faces ?? []).map((f) => ({
        url: f.photo,
        faces: [{ cid, name: label?.name || `#${cid}`, box: f.box, primary: true }],
        caption: `${EVN[f.gallery] ?? f.gallery} · ${decodeURIComponent(f.photo.split("/").pop() ?? "")}`,
      })),
    [cur, cid, label?.name]
  )
  const ctxOffset = cur?.faces.length ?? 0
  const lbAll: BoxedPhoto[] = useMemo(
    () => [
      ...lbPhotos,
      ...(cur?.context ?? []).map((c) => ({
        url: c.url,
        faces: [{ cid, name: label?.name || `#${cid}`, box: c.box, primary: true }],
        caption: `${EVN[c.gallery] ?? c.gallery} · ${decodeURIComponent(c.url.split("/").pop() ?? "")}`,
      })),
    ],
    [lbPhotos, cur, cid, label?.name]
  )

  const statusLine =
    st === "unlabeled"
      ? "Unlabeled"
      : st === "not_guest"
        ? "Marked: not a guest (vendor / staff / priest)"
        : st === "merged"
          ? `Merged into #${label?.merge_into}`
          : `Labeled: ${label?.name}${label?.email ? ` · ${label.email}` : ""}${label?.provisional ? " (provisional — Enter to confirm)" : ""}`

  return (
    <>
      {/* backdrop only behind the mobile full-screen sheet (#3 Responsive: <768px) */}
      <div className="fixed inset-0 z-[60] bg-black/20 md:hidden" onClick={onClose} />
      {/* Full-screen sheet below 768px; an in-flow ~400px sibling column at/above it so
          the table reflows to the remaining width instead of being covered. */}
      <aside
        className="fixed inset-x-0 bottom-0 top-[var(--nav-h)] z-[70] flex w-full flex-col border-l border-ws-line bg-white shadow-2xl md:static md:z-auto md:min-h-0 md:w-[400px] md:shrink-0 md:self-stretch md:shadow-none"
        aria-label={`Cluster #${cid}`}
      >
        {/* header */}
        <div className="flex items-center gap-3 border-b border-ws-line px-4 py-2.5">
          {row && <img src={row.face} alt="" className="h-10 w-10 rounded-md object-cover ring-1 ring-ws-line" />}
          <div className="min-w-0 flex-1">
            <div className="flex items-baseline gap-2">
              <span className="text-[16px] font-semibold">#{cid}</span>
              <span className="text-[12px] text-ws-muted">
                {(cur?.photos ?? row?.photos ?? 0).toLocaleString()} photos · {idx + 1} of {rows.length}
              </span>
            </div>
            <div
              className={cn(
                "truncate text-[12px]",
                st === "unlabeled" ? "text-ws-muted" : st === "not_guest" ? "text-ws-warn" : "text-ws-ok"
              )}
            >
              {statusLine}
            </div>
          </div>
          <button type="button" className="ws-btn ws-btn--sm" onClick={goPrev} disabled={idx <= 0} title={`Previous (${MOD}←)`}>
            <ChevronLeft className="h-4 w-4" />
          </button>
          <button type="button" className="ws-btn ws-btn--sm" onClick={goNext} disabled={idx < 0 || idx >= rows.length - 1} title={`Next (${MOD}→)`}>
            <ChevronRight className="h-4 w-4" />
          </button>
          <button type="button" className="ws-btn ws-btn--sm" onClick={onClose} title="Close (Esc)">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
          {err && <div className="mb-3 text-[13px] text-ws-warn">Couldn’t load cluster: {err}</div>}

          {/* search + suggestions */}
          <div className="mb-3">
            <input
              ref={inputRef}
              className="ws-input w-full text-[14px]"
              placeholder="Type a name — Enter assigns the highlighted guest"
              value={q}
              onChange={(e) => {
                setQ(e.target.value)
                setSel(0)
              }}
            />
            <ul className="mt-1.5 divide-y divide-ws-line/60 overflow-hidden rounded-lg border border-ws-line">
              {likelyView.length > 0 && (
                <li className="border-none bg-white px-2.5 pb-1 pt-2 font-mono text-[10px] uppercase tracking-[0.08em] text-ws-muted">
                  Likely matches
                </li>
              )}
              {likelyView.map((x, k) => renderSug(x, k))}
              {elseView.length > 0 && (
                <li className="bg-white px-2.5 pb-1 pt-2 font-mono text-[10px] uppercase tracking-[0.08em] text-ws-muted">
                  Everyone else
                </li>
              )}
              {elseView.map((x, k) => renderSug(x, likelyView.length + k))}
              {sugs.length === 0 && (
                <li className="border-none px-2.5 py-2 text-[12px] text-ws-muted">
                  {q.trim() ? `No guest matches — Enter saves “${q.trim()}” as a custom name.` : "Type to search the guest list."}
                </li>
              )}
            </ul>
            <div className="mt-2 flex flex-wrap gap-1.5">
              <button type="button" className="ws-btn ws-btn--primary" onClick={() => void assign()} disabled={!sugs[sel] && !q.trim()}>
                Assign <kbd className="ml-1 rounded bg-white/20 px-1 text-[10px]">Enter</kbd>
              </button>
              {st === "provisional" && (
                <button type="button" className="ws-btn border-ws-ok text-ws-ok" onClick={confirmProvisional}>
                  Confirm “{label?.name}”
                </button>
              )}
              <button type="button" className="ws-btn" onClick={skip}>
                Skip <kbd className="ml-1 rounded bg-ws-soft px-1 text-[10px]">{MOD}→</kbd>
              </button>
              <button type="button" className="ws-btn" onClick={() => void notGuest()}>
                Not a guest <kbd className="ml-1 rounded bg-ws-soft px-1 text-[10px]">{MOD}.</kbd>
              </button>
              {cur?.similar[0] && (
                <button type="button" className="ws-btn" onClick={() => void merge(cur.similar[0].cid)} title={`Merge into #${cur.similar[0].cid}`}>
                  Merge → #{cur.similar[0].cid} <kbd className="ml-1 rounded bg-ws-soft px-1 text-[10px]">{MOD}/</kbd>
                </button>
              )}
              {st !== "unlabeled" && (
                <button type="button" className="ws-btn text-ws-warn" onClick={clear}>
                  Clear <kbd className="ml-1 rounded bg-ws-soft px-1 text-[10px]">{MOD}⌫</kbd>
                </button>
              )}
            </div>
          </div>

          {/* events */}
          {cur && (
            <div className="mb-3 flex flex-wrap gap-1">
              {Object.entries(cur.events).map(([e, n]) => (
                <span key={e} className="ws-chip bg-ws-soft text-ws-ink">
                  {EVN[e] ?? e} · {n}
                </span>
              ))}
            </div>
          )}

          {/* faces */}
          <Section title="Faces" hint="click to see the full photo">
            {cur ? (
              <div className="grid grid-cols-6 gap-1.5">
                {cur.faces.map((f, k) => (
                  <FaceContextMenu key={f.crop + k} cid={cid} name={label?.name} className="block">
                    <button
                      type="button"
                      className="block aspect-square w-full overflow-hidden rounded-md ring-1 ring-ws-line hover:ring-ws-accent"
                      onClick={() => setLb(k)}
                      title={`${EVN[f.gallery] ?? f.gallery} — click for the photo, right-click to name`}
                    >
                      <img src={f.crop} alt="" loading="lazy" className="h-full w-full object-cover" />
                    </button>
                  </FaceContextMenu>
                ))}
              </div>
            ) : (
              <Skel h={160} />
            )}
          </Section>

          {/* context */}
          <Section title="In context">
            {cur ? (
              <div className="grid grid-cols-2 gap-2">
                {cur.context.map((c, k) => (
                  <FaceContextMenu key={c.url + k} cid={cid} name={label?.name} className="block">
                    <BoxedThumb url={c.url} box={c.box} caption={EVN[c.gallery] ?? c.gallery} onClick={() => setLb(ctxOffset + k)} />
                  </FaceContextMenu>
                ))}
              </div>
            ) : (
              <Skel h={180} />
            )}
          </Section>

          {/* co-stars */}
          <Section title="Photographed with">
            {cur ? (
              <div className="flex flex-wrap gap-1.5">
                {cur.costars.map((c) => (
                  <FaceContextMenu key={c.cid} cid={c.cid} name={c.name}>
                    <button
                      type="button"
                      className="flex items-center gap-1.5 rounded-full border border-ws-line bg-white py-0.5 pl-0.5 pr-2 text-[12px] hover:border-ws-accent"
                      onClick={() => onNavigate(c.cid)}
                      title={`Open #${c.cid} — right-click to name`}
                    >
                      <img src={c.face} alt="" className="h-6 w-6 rounded-full object-cover" />
                      <span className={cn(!(names[c.cid] || c.name) && "text-ws-muted")}>{names[c.cid] || c.name || `#${c.cid}`}</span>
                      <span className="text-ws-muted">{c.n}</span>
                    </button>
                  </FaceContextMenu>
                ))}
                {cur.costars.length === 0 && <span className="text-[12px] text-ws-muted">—</span>}
              </div>
            ) : (
              <Skel h={32} />
            )}
          </Section>

          {/* similar */}
          <Section title="Looks similar" hint="click to merge this cluster into it">
            {cur ? (
              <div className="flex flex-wrap gap-1.5">
                {cur.similar.map((s) => (
                  <FaceContextMenu key={s.cid} cid={s.cid} name={s.name}>
                    <button
                      type="button"
                      className="flex items-center gap-1.5 rounded-full border border-ws-line bg-white py-0.5 pl-0.5 pr-2 text-[12px] hover:border-ws-accent"
                      onClick={() => void merge(s.cid)}
                      title={`Merge #${cid} into #${s.cid} — right-click to name #${s.cid}`}
                    >
                      <img src={s.face} alt="" className="h-6 w-6 rounded-full object-cover" />
                      <span className={cn(!(names[s.cid] || s.name) && "text-ws-muted")}>{names[s.cid] || s.name || `#${s.cid}`}</span>
                      <span className="text-ws-muted">
                        {s.photos} · sim {s.sim}
                      </span>
                    </button>
                  </FaceContextMenu>
                ))}
                {cur.similar.length === 0 && <span className="text-[12px] text-ws-muted">none above 0.35</span>}
              </div>
            ) : (
              <Skel h={32} />
            )}
          </Section>

          <div className="mt-4 flex flex-wrap gap-2 border-t border-ws-line pt-3 text-[12px]">
            <button type="button" className="ws-btn ws-btn--sm" onClick={() => go(buildHash("people", null, { tab: "photos", sel: String(cid) }))}>
              Shared photos with #{cid} →
            </button>
            <span className="self-center text-ws-muted">
              Keys: Enter assign · ↑↓ pick · {MOD}→ skip/next · {MOD}← prev · {MOD}. not a guest · {MOD}/ merge · {MOD}⌫ clear · Esc close
            </span>
          </div>
        </div>
      </aside>

      <PhotoLightbox photos={lbAll} index={lb} onClose={() => setLb(null)} onIndex={setLb} />
    </>
  )
}

function Section({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="mb-3">
      <div className="mb-1.5 flex items-baseline gap-2">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.06em] text-ws-muted">{title}</h3>
        {hint && <span className="text-[11px] text-ws-muted/70">{hint}</span>}
      </div>
      {children}
    </div>
  )
}

function Skel({ h }: { h: number }) {
  return <div className="animate-pulse rounded-md bg-ws-soft" style={{ height: h }} />
}

/** Thumbnail of a full photo with the face box drawn (box in the image's natural pixel space). */
export function BoxedThumb({ url, box, caption, onClick }: { url: string; box: number[]; caption?: string; onClick?: () => void }) {
  const [nat, setNat] = useState<{ w: number; h: number } | null>(null)
  const [x1, y1, x2, y2] = box
  return (
    <button type="button" onClick={onClick} className="block w-full text-left">
      <div className="relative inline-block w-full overflow-hidden rounded-md bg-ws-soft ring-1 ring-ws-line hover:ring-ws-accent">
        <img
          src={url}
          alt=""
          loading="lazy"
          className="block h-auto w-full"
          onLoad={(e) => setNat({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight })}
        />
        {nat && (
          <div
            className="face-box"
            style={{
              left: `${(x1 / nat.w) * 100}%`,
              top: `${(y1 / nat.h) * 100}%`,
              width: `${((x2 - x1) / nat.w) * 100}%`,
              height: `${((y2 - y1) / nat.h) * 100}%`,
            }}
          />
        )}
      </div>
      {caption && <div className="mt-0.5 text-[11px] text-ws-muted">{caption}</div>}
    </button>
  )
}
