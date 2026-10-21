import { filenameOf } from "./favorites"

/**
 * Telemetry beacon (issue #39) — selection/download events as ranking ground truth.
 * Fire-and-forget POSTs to Supabase REST; ts is stamped server-side. Fail-silent by
 * contract: no config (data/telemetry.json absent at build) → every call is a no-op,
 * and a failed request is swallowed — telemetry must never block or break the deck.
 * Config ships inside wrapped.json (the per-deck runtime-config pattern; the Parcel
 * bundle has no env vars), so the client never learns anything the page doesn't hold.
 */

export type BeaconAction =
  | "deck_open"
  | "view_all_open"
  | "lightbox_open"
  | "lightbox_nav"
  | "select_on"
  | "select_off"
  | "download_one"
  | "download_selected"
  | "download_all"
  | "show_all_expand"
  | "show_blurry_expand"
  | "view_map_open"
  | "map_node_select"
  | "map_node_deselect"

export type Surface = "deck" | "all_photos" | "map"

export interface BeaconCfg {
  url: string
  key: string
  env: string
}

let cfg: BeaconCfg | null = null
let armed = false
let slug = ""
let surface: Surface = "deck"
/** Events tracked before initBeacon (e.g. a direct #/all landing fires view_all_open
 *  before wrapped.json arrives) are buffered and flushed on arm — bounded, then dropped. */
let pending: Array<{ action: BeaconAction; photo?: string; surface: Surface }> = []

/** Per-page-load nonce: separates two people on one forwarded link without any
 *  storage or fingerprinting — a fresh id every load, gone when the tab closes. */
const session: string = (() => {
  try {
    return crypto.randomUUID()
  } catch {
    return ""
  }
})()

/** Coarse device class — an enum, not a fingerprint. Touch + width beats UA sniffing. */
const device: string = (() => {
  try {
    const touch = navigator.maxTouchPoints > 0
    const narrow = window.matchMedia("(max-width: 767px)").matches
    return touch ? (narrow ? "mobile" : "tablet") : "desktop"
  } catch {
    return ""
  }
})()

export function initBeacon(c: BeaconCfg | undefined | null, deckSlug: string): void {
  cfg = c && c.url && c.key ? c : null
  slug = deckSlug
  armed = true
  const queued = pending
  pending = []
  for (const q of queued) send(q.action, q.photo, q.surface)
}

/** The same click means opposite things by surface: select_on from the deck = "ranker was
 *  right", from all_photos = "ranker was wrong". Views set this on mount. */
export function setSurface(s: Surface): void {
  surface = s
}

/** Log one event. `photo` is a deck url; it's sent as "GALLERY/file.jpg" (PII-free,
 *  matches the build pipeline's photo_ids for the offline join). Never awaited. */
export function track(action: BeaconAction, photo?: string): void {
  if (!armed) {
    if (pending.length < 20) pending.push({ action, photo, surface })
    return
  }
  send(action, photo, surface)
}

function send(action: BeaconAction, photo: string | undefined, eventSurface: Surface): void {
  if (!cfg) return
  try {
    void fetch(`${cfg.url}/rest/v1/events`, {
      method: "POST",
      keepalive: true,
      headers: {
        apikey: cfg.key,
        Authorization: `Bearer ${cfg.key}`,
        "Content-Type": "application/json",
        Prefer: "return=minimal",
      },
      body: JSON.stringify({
        slug,
        action,
        surface: eventSurface,
        env: cfg.env,
        ...(session ? { session } : {}),
        ...(device ? { device } : {}),
        ...(photo ? { photo: filenameOf(photo) } : {}),
      }),
    }).catch(() => {})
  } catch {
    /* telemetry must never break the deck */
  }
}
