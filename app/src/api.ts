/** Typed client for the label server (http://localhost:8792, same origin at runtime). */

export type LabelStatus = "labeled" | "not_guest" | "merged"

export interface Label {
  status?: LabelStatus
  name?: string
  first?: string
  last?: string
  email?: string
  party?: string
  guest_id?: number | null
  merge_into?: number
  provisional?: boolean
}

export interface PersonRow {
  cid: number
  photos: number
  events: Record<string, number>
  face: string
  label: Label
}

export interface Guest {
  id: number
  first: string
  last: string
  name: string
  email: string
  party: string
  envelope: string
  events: Record<string, boolean>
}

export interface PeopleResponse {
  rows: PersonRow[]
  guests: Guest[]
}

export interface ClusterFace {
  crop: string
  photo: string
  box: number[]
  gallery: string
}
export interface ClusterContext {
  url: string
  box: number[]
  gallery: string
}
export interface ClusterCostar {
  cid: number
  n: number
  name: string | null
  face: string
}
export interface ClusterSimilar {
  cid: number
  sim: number
  name: string | null
  photos: number
  face: string
}
export interface ClusterPayload {
  cid: number
  photos: number
  events: Record<string, number>
  faces: ClusterFace[]
  context: ClusterContext[]
  costars: ClusterCostar[]
  similar: ClusterSimilar[]
  label: Label | null
}

export interface GraphNode {
  id: number
  name: string
  photos: number
  x: number
  y: number
  r: number
  comm: number
  col: string
  side: number
  scol: string
  img: string
  labeled: boolean
}
export interface GraphEdge {
  s: number
  t: number
  w: number
  top: 0 | 1
  sw: number
}
export interface GraphCommunity {
  community: number
  people: number
  photos: number
  members: string
}
export interface GraphResponse {
  nodes: GraphNode[]
  edges: GraphEdge[]
  communities: GraphCommunity[]
  W: number
  H: number
  PAL: string[]
  DIV: string[]
  min_photos: number
  min_together: number
  topk: number
}

export interface SharedFace {
  cid: number
  name: string | null
  box: number[]
}
export interface SharedPhoto {
  photo_id: string
  url: string
  gallery: string
  taken_at: string
  w: number
  h: number
  faces: SharedFace[]
}
export interface SharedResponse {
  count: number
  by_event: Record<string, number>
  photos: SharedPhoto[]
}

export interface WrappedEntry {
  slug: string
  name: string
  cluster: number
  n_photos: number
  n_events: number
  n_scenes: number
  hero: string
}

export interface PhotoFace {
  cid: number
  name: string | null
  status: string | null
  photos: number
  box: number[]
  det: number
}
export interface PhotoInfo {
  photo_id: string
  w: number
  h: number
  gallery: string
  url: string
  faces: PhotoFace[]
}

export interface Group {
  id: string
  name: string
  members: number[]
}
export interface GroupPreset {
  name: string
  size: number
  members: number[]
  preview: { cid: number; name: string; face: string }[]
  tag?: string
}
export interface GroupSuggestion {
  cid: number
  name: string
  face: string
  score: number
  why: { together: number; name: string }[]
}
export type GroupOp =
  | { op: "create"; name: string }
  | { op: "rename"; id: string; name: string }
  | { op: "delete"; id: string }
  | { op: "add"; id: string; cids: number[] }
  | { op: "remove"; id: string; cids: number[] }

export interface StateResponse {
  queue: number[]
  guests: Guest[]
  labels: Record<string, Label>
  min: number
  photos: Record<string, number>
}

export interface HistoryRow {
  ts: string
  cid: number
  before: Label | null
  after: Label | null
  who: string
}

async function getJSON<T>(url: string): Promise<T> {
  const r = await fetch(url, { cache: "no-store" })
  if (!r.ok) throw new Error(`${r.status} ${r.statusText} — ${url}`)
  return (await r.json()) as T
}
async function postJSON<T>(url: string, body: unknown): Promise<T> {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error(`${r.status} ${r.statusText} — ${url}`)
  return (await r.json()) as T
}

export const api = {
  people: () => getJSON<PeopleResponse>("/api/people"),
  cluster: (cid: number) => getJSON<ClusterPayload>(`/api/cluster?cid=${cid}`),
  state: () => getJSON<StateResponse>("/api/state"),
  names: () => getJSON<Record<string, string>>("/api/names"),
  graph: (min: number) => getJSON<GraphResponse>(`/api/graph?min=${min}`),
  shared: (cids: number[], event?: string | null, limit = 400) =>
    getJSON<SharedResponse>(
      `/api/shared?cids=${cids.join(",")}${event ? `&event=${encodeURIComponent(event)}` : ""}&limit=${limit}`
    ),
  wrapped: () => getJSON<WrappedEntry[]>("/api/wrapped"),
  history: () => getJSON<HistoryRow[]>("/api/history"),
  /** All detected faces in a photo; accepts a photo id or any of our image urls. */
  photo: (idOrUrl: string) => getJSON<PhotoInfo>(`/api/photo?photo_id=${encodeURIComponent(idOrUrl)}`),
  groups: () => getJSON<{ groups: Group[] }>("/api/groups"),
  groupOp: (body: GroupOp) => postJSON<{ groups: Group[] }>("/api/groups", body),
  groupPresets: () => getJSON<{ presets: GroupPreset[] }>("/api/group_presets"),
  groupSuggest: (q: { id: string } | { cids: number[] }) =>
    getJSON<{ suggestions: GroupSuggestion[] }>(
      "id" in q ? `/api/group_suggest?id=${encodeURIComponent(q.id)}` : `/api/group_suggest?cids=${q.cids.join(",")}`
    ),
  label: (body: Record<string, unknown> & { cid: number }) =>
    postJSON<{ ok: boolean }>("/api/label", body),
  undo: () => postJSON<{ ok: boolean; cid?: number; restored?: Label | null; msg?: string }>("/api/undo", {}),
  importCsv: (csv: string) => postJSON<{ ok: boolean; n: number }>("/api/import", { csv }),
}

/** Build the POST /api/label body for assigning a guest-list entry. */
export function guestLabel(g: Guest): Label {
  return {
    status: "labeled",
    name: g.name,
    first: g.first,
    last: g.last,
    email: g.email,
    party: g.party,
    guest_id: g.id,
  }
}

/** Human names for the photo galleries. */
export const EVN: Record<string, string> = {
  "GREH SHANTI": "Greh Shanti",
  HALDI: "Haldi",
  SANGEET: "Sangeet",
  WEDDING: "Wedding",
  "RECEPTION PARTY": "Reception",
  "RECEPTION COUPLE": "Reception (couple)",
  "BRIDE MORNING": "Bride morning",
  "GROOM MORNING": "Groom morning",
  "COUPLE SHOOT": "Couple shoot",
}
/** Gallery → guest-list RSVP event key. */
export const RSVP: Record<string, string> = {
  "GREH SHANTI": "GREH SHANTI",
  HALDI: "HALDI",
  SANGEET: "SANGEET",
  WEDDING: "WEDDING",
  "RECEPTION PARTY": "RECEPTION PARTY",
  "RECEPTION COUPLE": "RECEPTION PARTY",
  "BRIDE MORNING": "WEDDING",
  "GROOM MORNING": "WEDDING",
  "COUPLE SHOOT": "WEDDING",
}
/** One-letter event abbreviations for the compact table column. */
export const EV_ABBR: Record<string, string> = {
  "GREH SHANTI": "G",
  HALDI: "H",
  SANGEET: "S",
  WEDDING: "W",
  "RECEPTION PARTY": "R",
  "RECEPTION COUPLE": "Rc",
  "BRIDE MORNING": "Bm",
  "GROOM MORNING": "Gm",
  "COUPLE SHOOT": "Cs",
}
export const EVENT_ORDER = [
  "GREH SHANTI",
  "HALDI",
  "SANGEET",
  "BRIDE MORNING",
  "GROOM MORNING",
  "COUPLE SHOOT",
  "WEDDING",
  "RECEPTION COUPLE",
  "RECEPTION PARTY",
]

export type RowStatus = "named" | "provisional" | "unlabeled" | "not_guest" | "merged"
export function rowStatus(l: Label | null | undefined): RowStatus {
  if (!l || !l.status) return "unlabeled"
  if (l.status === "not_guest") return "not_guest"
  if (l.status === "merged") return "merged"
  return l.provisional ? "provisional" : "named"
}
export const STATUS_TEXT: Record<RowStatus, string> = {
  named: "named",
  provisional: "provisional",
  unlabeled: "unlabeled",
  not_guest: "not a guest",
  merged: "merged",
}

/** Rewrite the relative image urls inside a wrapped.json ("../img/…") to the server path. */
export function rewriteWrappedUrls<T>(obj: T, prefix = "/site/"): T {
  const fix = (v: unknown): unknown => {
    if (typeof v === "string") return v.startsWith("../") ? prefix + v.slice(3) : v
    if (Array.isArray(v)) return v.map(fix)
    if (v && typeof v === "object") {
      const o: Record<string, unknown> = {}
      for (const [k, val] of Object.entries(v as Record<string, unknown>)) o[k] = fix(val)
      return o
    }
    return v
  }
  return fix(obj) as T
}
