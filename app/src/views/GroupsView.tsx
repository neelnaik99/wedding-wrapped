import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Pencil, Trash2, X } from "lucide-react"
import { api, type Group, type GroupPreset, type GroupSuggestion } from "@/api"
import { useStore } from "@/store"
import { buildHash, type Route } from "@/router"
import { cn } from "@/lib/utils"
import FaceContextMenu from "@/components/FaceContextMenu"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

const FIXED = [15, 50] // Neel & Preethi are in every group automatically
const CHIP_CAP = 16 // collapse the member wall beyond this many (#4)

/** The server augments each group with a per-member `together` map (photos shared with the rest
 *  of the group) — see label_server `_groups_with_together`. It is optional so drafts still type. */
interface GroupT extends Group {
  together?: Record<string, number>
}

interface Draft {
  name: string
  members: number[]
}

function firstName(n: string): string {
  return n.split(" ")[0]
}

/** Plain-language co-member line for a suggestion, top two by shared-photo count (#7). */
function sharesText(why: { together: number; name: string }[]): string {
  const w = [...why].sort((a, b) => b.together - a.together).slice(0, 2)
  if (w.length === 0) return "shares photos with current members"
  const parts = w.map((x, i) =>
    i === 0 ? `${x.together} photos with ${firstName(x.name)}` : `${x.together} with ${firstName(x.name)}`
  )
  return "shares " + parts.join(", ")
}

export default function GroupsView({ route, go }: { route: Route; go: (h: string) => void }) {
  const { rows, runSaving, toast } = useStore()
  const [groups, setGroups] = useState<GroupT[]>([])
  const [presets, setPresets] = useState<GroupPreset[] | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [draft, setDraft] = useState<Draft | null>(null)
  const [newName, setNewName] = useState("")
  const curId = route.params.get("g")
  const sgOpen = route.params.get("sg") === "1" // suggested-groups rail expanded (#8, hash-persisted)
  const cur = draft ? null : (groups.find((g) => g.id === curId) ?? null)

  const setCur = useCallback(
    (id: string | null) => go(buildHash("groups", null, { g: id, sg: sgOpen ? "1" : null })),
    [go, sgOpen]
  )
  const toggleSg = useCallback(
    () => go(buildHash("groups", null, { g: curId, sg: sgOpen ? null : "1" })),
    [go, curId, sgOpen]
  )

  useEffect(() => {
    api
      .groups()
      .then((r) => setGroups(r.groups))
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)))
    api
      .groupPresets()
      .then((r) => setPresets(r.presets))
      .catch(() => setPresets([]))
  }, [])

  // labeled people only, for chips + combobox
  const people = useMemo(
    () =>
      rows
        .filter((r) => r.label?.status === "labeled")
        .map((r) => ({ cid: r.cid, name: r.label.name || `#${r.cid}`, face: r.face, photos: r.photos })),
    [rows]
  )
  const pinfo = useCallback(
    (cid: number) => people.find((p) => p.cid === cid) ?? { cid, name: `#${cid}`, face: "", photos: 0 },
    [people]
  )

  const mutate = useCallback(
    async (op: Parameters<typeof api.groupOp>[0]) => {
      const r = await runSaving(api.groupOp(op))
      setGroups(r.groups)
      return r
    },
    [runSaving]
  )

  async function createEmpty() {
    const name = newName.trim()
    if (!name) return
    const r = await mutate({ op: "create", name })
    setNewName("")
    setDraft(null)
    setCur(r.groups[r.groups.length - 1].id)
    toast(`Created “${name}”`)
  }

  async function createFromDraft() {
    if (!draft) return
    const name = draft.name.trim() || "New group"
    const r = await mutate({ op: "create", name })
    const g = r.groups[r.groups.length - 1]
    if (draft.members.length) await mutate({ op: "add", id: g.id, cids: draft.members })
    toast(`Created “${name}” with ${draft.members.length} people`)
    setDraft(null)
    setCur(g.id)
    api.groupPresets().then((rr) => setPresets(rr.presets)).catch(() => {})
  }

  return (
    <div className="ws-page">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[20px] font-semibold tracking-tight">Groups</h1>
          <p className="mt-0.5 text-[13px] text-ws-muted">
            Many-to-many · Preethi &amp; Neel are in every group automatically · groups drive each guest’s “Your people”
            card. <span className="text-ws-accentText">Changes affect guest decks after the next rebuild.</span>
          </p>
        </div>
      </div>

      {err && <div className="ws-panel mb-3 p-3 text-[13px] text-ws-warn">Couldn’t load /api/groups: {err}</div>}

      <div className="grid gap-3 lg:grid-cols-[300px_minmax(0,1fr)]">
        {/* left rail */}
        <div className="flex flex-col gap-3">
          <div className="ws-panel p-3">
            <input
              className="ws-input w-full"
              placeholder="new group name… (Enter)"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void createEmpty()
              }}
            />
            <div className="mt-2.5 flex flex-col gap-1.5">
              {groups.map((g) => {
                const on = !draft && cur?.id === g.id
                return (
                  <button
                    key={g.id}
                    type="button"
                    onClick={() => {
                      setDraft(null)
                      setCur(g.id)
                    }}
                    className={cn(
                      "flex items-baseline justify-between gap-2 rounded-lg border px-3 py-2 text-left text-[13px]",
                      on ? "border-ws-ink bg-ws-ink text-white" : "border-ws-line bg-white hover:border-ws-accent"
                    )}
                  >
                    <span className="min-w-0 truncate">{g.name}</span>
                    <span className={cn("tabular-nums", on ? "text-white/70" : "text-ws-muted")}>{g.members.length}</span>
                  </button>
                )
              })}
              {groups.length === 0 && <p className="px-1 text-[12px] text-ws-muted">No groups yet.</p>}
            </div>
          </div>

          {/* suggested groups — collapsed by default, lighter than saved groups (#8) */}
          <div className="ws-panel p-3">
            <button
              type="button"
              onClick={toggleSg}
              aria-expanded={sgOpen}
              className={cn(
                "flex w-full items-center gap-2 rounded-lg border border-dashed border-ws-line px-3 py-2 text-left text-ws-muted hover:border-ws-accent",
                sgOpen && "mb-2"
              )}
            >
              <span className="font-mono text-[10px] uppercase tracking-[0.08em]">
                {presets == null
                  ? "suggested groups"
                  : `${presets.length} suggested group${presets.length === 1 ? "" : "s"}`}
              </span>
              <span className="ml-auto text-[12px]">{sgOpen ? "▾" : "▸"}</span>
            </button>

            {sgOpen && (
              <>
                {presets == null && <p className="text-[12px] text-ws-muted">detecting…</p>}
                {presets != null && presets.length === 0 && (
                  <p className="text-[12px] text-ws-muted">none left — most people are grouped</p>
                )}
                <div className="flex flex-col gap-2">
                  {(presets ?? []).map((p, i) => (
                    <div key={`${i}-${p.name}`} className="rounded-lg border border-dashed border-ws-line bg-ws-soft/50 p-2.5">
                      <div className="flex items-baseline justify-between gap-2">
                        <b className="text-[13px]">{p.name}</b>
                        <span className="text-[11px] text-ws-muted">{p.size} people</span>
                      </div>
                      {p.tag && <div className="mt-0.5 text-[11px] text-ws-muted">{p.tag}</div>}
                      <div className="mt-1.5 flex flex-wrap gap-1">
                        {p.preview.slice(0, 12).map((f) => (
                          <img key={f.cid} src={f.face} alt={f.name} title={f.name} className="h-7 w-7 rounded-full object-cover ring-1 ring-ws-line" />
                        ))}
                        {p.size > 12 && <span className="self-center text-[11px] text-ws-muted">+{p.size - 12}</span>}
                      </div>
                      <button
                        type="button"
                        className="ws-btn ws-btn--primary ws-btn--sm mt-2"
                        onClick={() => {
                          setDraft({ name: p.name, members: [...p.members] })
                          setCur(null)
                        }}
                      >
                        Review &amp; create →
                      </button>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>

        {/* main panel */}
        <div className="ws-panel min-h-[320px] p-4">
          {!cur && !draft && (
            <p className="text-[13px] text-ws-muted">Select a group on the left, or review a suggested one.</p>
          )}
          {(cur || draft) && (
            <GroupPanel
              key={draft ? "draft" : cur!.id}
              group={cur}
              draft={draft}
              groups={groups}
              people={people}
              pinfo={pinfo}
              onDraftChange={setDraft}
              onCreateDraft={() => void createFromDraft()}
              onDiscardDraft={() => setDraft(null)}
              onRename={(name) => void mutate({ op: "rename", id: cur!.id, name }).then(() => toast("Renamed"))}
              onDelete={() =>
                void mutate({ op: "delete", id: cur!.id }).then(() => {
                  setCur(null)
                  toast("Deleted")
                })
              }
              onAdd={(cid) =>
                draft
                  ? setDraft((d) => (d && !d.members.includes(cid) ? { ...d, members: [...d.members, cid] } : d))
                  : void mutate({ op: "add", id: cur!.id, cids: [cid] })
              }
              onRemove={(cid) =>
                draft
                  ? setDraft((d) => (d ? { ...d, members: d.members.filter((x) => x !== cid) } : d))
                  : void mutate({ op: "remove", id: cur!.id, cids: [cid] })
              }
            />
          )}
        </div>
      </div>
    </div>
  )
}

interface PanelProps {
  group: GroupT | null
  draft: Draft | null
  groups: Group[]
  people: { cid: number; name: string; face: string; photos: number }[]
  pinfo: (cid: number) => { cid: number; name: string; face: string; photos: number }
  onDraftChange: (d: Draft | null) => void
  onCreateDraft: () => void
  onDiscardDraft: () => void
  onRename: (name: string) => void
  onDelete: () => void
  onAdd: (cid: number) => void
  onRemove: (cid: number) => void
}

function GroupPanel({ group, draft, groups, people, pinfo, onDraftChange, onCreateDraft, onDiscardDraft, onRename, onDelete, onAdd, onRemove }: PanelProps) {
  const members = draft ? draft.members : (group?.members ?? [])
  const together = group?.together
  const [name, setName] = useState(draft ? draft.name : (group?.name ?? ""))
  const [q, setQ] = useState("")
  const [sugs, setSugs] = useState<GroupSuggestion[] | null>(null)
  const [showAll, setShowAll] = useState(false)
  const [confirmDel, setConfirmDel] = useState(false)
  const savedRef = useRef(draft ? "" : (group?.name ?? "")) // last committed name — dedupes blur + pencil commits

  // suggestions for the current membership
  useEffect(() => {
    let cancelled = false
    setSugs(null)
    if (members.length === 0) {
      setSugs([])
      return
    }
    const p = draft ? api.groupSuggest({ cids: members }) : api.groupSuggest({ id: group!.id })
    p.then((r) => !cancelled && setSugs(r.suggestions ?? [])).catch(() => !cancelled && setSugs([]))
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [members.join(","), draft ? "d" : group?.id])

  // member chips sorted by photos-together-with-the-group desc, tie-break name asc (#4)
  const ordered = useMemo(() => {
    const t = (cid: number) => together?.[String(cid)] ?? 0
    return [...members].sort((a, b) => {
      const d = t(b) - t(a)
      return d !== 0 ? d : pinfo(a).name.localeCompare(pinfo(b).name)
    })
  }, [members, together, pinfo])
  const visible = showAll ? ordered : ordered.slice(0, CHIP_CAP)
  const hidden = ordered.length - visible.length
  const chipLabel = together
    ? `${members.length} member${members.length === 1 ? "" : "s"} · sorted by photos together`
    : `${members.length} member${members.length === 1 ? "" : "s"}`

  const have = useMemo(() => new Set([...members, ...FIXED]), [members])
  const matches = useMemo(() => {
    const ql = q.trim().toLowerCase()
    if (!ql) return []
    return people.filter((p) => !have.has(p.cid) && p.name.toLowerCase().includes(ql)).slice(0, 10)
  }, [q, people, have])
  const otherGroups = (cid: number) => groups.filter((g) => g.members.includes(cid) && g.id !== group?.id).map((g) => g.name)

  const commitName = () => {
    const n = name.trim()
    if (draft || !group || !n) return
    if (n === group.name || n === savedRef.current) return
    savedRef.current = n
    onRename(n)
  }

  return (
    <div>
      {draft && (
        <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[13px] text-amber-900">
          Reviewing a suggested group — <b>nothing is saved until you press Create</b>.
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <input
          className="ws-input w-[300px] text-[14px]"
          value={name}
          onChange={(e) => {
            setName(e.target.value)
            if (draft) onDraftChange({ ...draft, name: e.target.value })
          }}
          onBlur={commitName}
          onKeyDown={(e) => {
            if (e.key === "Enter") (e.target as HTMLInputElement).blur()
          }}
          aria-label="Group name"
        />
        {draft ? (
          <>
            <button type="button" className="ws-btn ws-btn--primary" onClick={onCreateDraft}>
              Create group ({members.length})
            </button>
            <button type="button" className="ws-btn" onClick={onDiscardDraft}>
              Discard
            </button>
          </>
        ) : (
          <>
            <button type="button" className="ws-btn" aria-label="Rename group" title="Rename group" onClick={commitName}>
              <Pencil className="h-3.5 w-3.5" />
            </button>
            <button type="button" className="ws-btn text-ws-warn" onClick={() => setConfirmDel(true)}>
              <Trash2 className="h-3.5 w-3.5" /> Delete…
            </button>
          </>
        )}
      </div>

      {/* Always included — pinned couple in their own accent row (#4) */}
      <div className="mt-4 flex flex-col gap-1.5">
        <div className="font-mono text-[10px] uppercase tracking-[0.08em] text-ws-muted">Always included</div>
        <div className="flex flex-wrap gap-2">
          {FIXED.map((cid) => {
            const p = pinfo(cid)
            return (
              <span
                key={cid}
                className="flex items-center gap-1.5 rounded-full border-2 border-ws-accent bg-ws-soft py-0.5 pl-0.5 pr-3 text-[13px]"
              >
                {p.face && <img src={p.face} alt={p.name} className="h-7 w-7 rounded-full object-cover" />}
                <b className="font-semibold">{p.name.split(" ")[0]}</b>
              </span>
            )
          })}
        </div>
      </div>

      {/* member wall — ordered by photos-together, collapses past CHIP_CAP (#4) */}
      <div className="mt-4 flex flex-col gap-1.5">
        <div className="font-mono text-[10px] uppercase tracking-[0.08em] text-ws-muted">{chipLabel}</div>
        <div className="flex flex-wrap gap-2">
          {visible.map((cid) => {
            const p = pinfo(cid)
            const t = together?.[String(cid)]
            return (
              <FaceContextMenu key={cid} cid={cid} name={p.name}>
                <span className="flex items-center gap-1.5 rounded-full border border-ws-line bg-ws-soft py-1 pl-1 pr-1.5 text-[13px]">
                  {p.face && <img src={p.face} alt={p.name} className="h-7 w-7 rounded-full object-cover" />}
                  <span>
                    {p.name}
                    {together && t != null ? <span className="text-ws-muted"> · {t}</span> : null}
                  </span>
                  <button
                    type="button"
                    aria-label={`Remove ${p.name}`}
                    className="rounded-full p-0.5 text-ws-muted hover:text-ws-warn"
                    onClick={() => onRemove(cid)}
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </span>
              </FaceContextMenu>
            )
          })}
          {hidden > 0 && (
            <button
              type="button"
              onClick={() => setShowAll(true)}
              className="flex items-center rounded-full border border-dashed border-ws-line px-3.5 py-1.5 text-[13px] text-ws-muted hover:border-ws-accent"
            >
              + {hidden} more
            </button>
          )}
          {members.length === 0 && <span className="self-center text-[12px] text-ws-muted">no members yet — add someone below</span>}
        </div>
      </div>

      {/* add person */}
      <div className="relative mt-3 max-w-[420px]">
        <input
          className="ws-input w-full"
          placeholder="add person… type a name"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && matches[0]) {
              onAdd(matches[0].cid)
              setQ("")
            }
            if (e.key === "Escape") setQ("")
          }}
        />
        {matches.length > 0 && (
          <ul className="absolute left-0 top-full z-[60] mt-1 w-full overflow-hidden rounded-lg border border-ws-line bg-white shadow-lg">
            {matches.map((p) => (
              <li key={p.cid}>
                <button
                  type="button"
                  className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left text-[13px] hover:bg-ws-soft"
                  onClick={() => {
                    onAdd(p.cid)
                    setQ("")
                  }}
                >
                  <img src={p.face} alt="" className="h-7 w-7 rounded-full object-cover" />
                  <span className="min-w-0 flex-1 truncate">{p.name}</span>
                  <span className="text-[11px] text-ws-muted">
                    {p.photos} photos
                    {otherGroups(p.cid).length ? ` · in: ${otherGroups(p.cid).join(", ")}` : ""}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* suggestions (#7) */}
      <h4 className="mb-1.5 mt-5 font-mono text-[10px] font-semibold uppercase tracking-[0.08em] text-ws-muted">
        Suggested next
      </h4>
      <ul className="flex flex-col gap-1.5">
        {members.length === 0 && <li className="text-[12px] text-ws-muted">add a first person to seed suggestions</li>}
        {members.length > 0 && sugs == null && <li className="text-[12px] text-ws-muted">…</li>}
        {sugs != null && members.length > 0 && sugs.length === 0 && (
          <li className="text-[12px] text-ws-muted">no strong signals left</li>
        )}
        {(sugs ?? []).map((sg) => (
          <li
            key={sg.cid}
            title={`${sg.score}% fit`}
            className="flex items-center gap-3 rounded-lg border border-ws-line/70 px-3 py-2"
          >
            <img src={sg.face} alt="" className="h-8 w-8 rounded-full object-cover" />
            <div className="min-w-0">
              <div className="text-[14px]">{sg.name}</div>
              <div className="text-[12px] text-ws-muted">{sharesText(sg.why)}</div>
            </div>
            <button type="button" className="ml-auto ws-btn" onClick={() => onAdd(sg.cid)}>
              + Add
            </button>
          </li>
        ))}
      </ul>

      {/* delete confirm — names the blast radius (#16) */}
      {!draft && group && (
        <Dialog open={confirmDel} onOpenChange={setConfirmDel}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>Delete “{group.name}”?</DialogTitle>
              <DialogDescription>
                Removes the group card and mind maps for {members.length}{" "}
                {members.length === 1 ? "person" : "people"} at the next rebuild.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <button type="button" className="ws-btn" onClick={() => setConfirmDel(false)}>
                Keep group
              </button>
              <button
                type="button"
                className="ws-btn text-ws-warn"
                onClick={() => {
                  setConfirmDel(false)
                  onDelete()
                }}
              >
                Delete group
              </button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  )
}
