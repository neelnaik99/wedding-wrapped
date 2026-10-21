import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react"
import { api, type Guest, type Label, type PersonRow, type WrappedEntry } from "@/api"

export type SaveStatus = "idle" | "saving" | "saved" | "error"

interface Store {
  rows: PersonRow[]
  guests: Guest[]
  loading: boolean
  error: string | null
  /** guest_id → cids that use it */
  usedBy: Record<number, number[]>
  /** cid → display name (labeled/merged-with-name) */
  names: Record<number, string>
  /** cluster id → wrapped slug */
  wrappedByCid: Record<number, string>
  refresh: () => Promise<void>
  saveLabel: (cid: number, label: Label | null) => Promise<boolean>
  undo: () => Promise<void>
  /** run any server mutation through the saving…/saved ✓ indicator */
  runSaving: <T,>(p: Promise<T>) => Promise<T>
  status: SaveStatus
  toast: (msg: string) => void
  toastMsg: string | null
}

const Ctx = createContext<Store | null>(null)

export function StoreProvider({ children }: { children: ReactNode }) {
  const [rows, setRows] = useState<PersonRow[]>([])
  const [guests, setGuests] = useState<Guest[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState<SaveStatus>("idle")
  const [toastMsg, setToastMsg] = useState<string | null>(null)
  const [wrapped, setWrapped] = useState<WrappedEntry[]>([])
  const toastTimer = useRef<number | null>(null)
  const statusTimer = useRef<number | null>(null)

  const toast = useCallback((msg: string) => {
    setToastMsg(msg)
    if (toastTimer.current) window.clearTimeout(toastTimer.current)
    toastTimer.current = window.setTimeout(() => setToastMsg(null), 2600)
  }, [])

  const refresh = useCallback(async () => {
    try {
      const d = await api.people()
      setRows(d.rows)
      setGuests(d.guests)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
    api.wrapped().then(setWrapped).catch(() => setWrapped([]))
  }, [refresh])
  const wrappedByCid = useMemo(() => Object.fromEntries(wrapped.map((w) => [w.cluster, w.slug])) as Record<number, string>, [wrapped])

  const markSaved = useCallback((ok: boolean) => {
    setStatus(ok ? "saved" : "error")
    if (statusTimer.current) window.clearTimeout(statusTimer.current)
    statusTimer.current = window.setTimeout(() => setStatus("idle"), 2500)
  }, [])

  const saveLabel = useCallback(
    async (cid: number, label: Label | null) => {
      setStatus("saving")
      // optimistic
      setRows((rs) => rs.map((r) => (r.cid === cid ? { ...r, label: label ?? {} } : r)))
      try {
        const body: Record<string, unknown> & { cid: number } = label
          ? { cid, ...label }
          : { cid, clear: true }
        const res = await api.label(body)
        markSaved(!!res.ok)
        void refresh()
        return !!res.ok
      } catch (e) {
        markSaved(false)
        toast(`Save failed: ${e instanceof Error ? e.message : String(e)}`)
        void refresh()
        return false
      }
    },
    [markSaved, refresh, toast]
  )

  const undo = useCallback(async () => {
    setStatus("saving")
    try {
      const r = await api.undo()
      if (!r.ok) {
        markSaved(true)
        toast(r.msg || "Nothing to undo")
        return
      }
      markSaved(true)
      const what = r.restored
        ? r.restored.status === "labeled"
          ? `back to “${r.restored.name}”`
          : r.restored.status === "not_guest"
            ? "back to “not a guest”"
            : `back to merged into #${r.restored.merge_into}`
        : "cleared"
      toast(`Undid #${r.cid} — ${what}`)
      await refresh()
    } catch (e) {
      markSaved(false)
      toast(`Undo failed: ${e instanceof Error ? e.message : String(e)}`)
    }
  }, [markSaved, refresh, toast])

  const runSaving = useCallback(
    async <T,>(p: Promise<T>): Promise<T> => {
      setStatus("saving")
      try {
        const r = await p
        markSaved(true)
        return r
      } catch (e) {
        markSaved(false)
        throw e
      }
    },
    [markSaved]
  )

  const usedBy = useMemo(() => {
    const m: Record<number, number[]> = {}
    for (const r of rows) {
      const g = r.label?.guest_id
      if (g != null && r.label.status === "labeled") (m[g] = m[g] || []).push(r.cid)
    }
    return m
  }, [rows])

  const names = useMemo(() => {
    const m: Record<number, string> = {}
    for (const r of rows) if (r.label?.name && r.label.status !== "not_guest") m[r.cid] = r.label.name
    return m
  }, [rows])

  const value = useMemo<Store>(
    () => ({ rows, guests, loading, error, usedBy, names, wrappedByCid, refresh, saveLabel, undo, runSaving, status, toast, toastMsg }),
    [rows, guests, loading, error, usedBy, names, wrappedByCid, refresh, saveLabel, undo, runSaving, status, toast, toastMsg]
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useStore(): Store {
  const s = useContext(Ctx)
  if (!s) throw new Error("useStore outside StoreProvider")
  return s
}
