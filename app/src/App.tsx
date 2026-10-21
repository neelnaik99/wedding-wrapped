import { useEffect, useMemo } from "react"
import Deck from "@/deck/Deck"
import type { DeckExtras } from "@/deck/DeckContext"
import FaceContextMenu from "@/components/FaceContextMenu"
import { api } from "@/api"
import { StoreProvider, useStore } from "@/store"
import { useRoute } from "@/router"
import Shell from "@/components/Shell"
import AdminView from "@/views/AdminView"
import PeopleView from "@/views/PeopleView"
import GroupsView from "@/views/GroupsView"
import ReviewView from "@/views/ReviewView"
import WrappedIndex from "@/views/WrappedIndex"

/**
 * Two ways this bundle is used:
 *  - standalone: copied next to a guest's wrapped.json (site/<slug>/index.html) — render the deck
 *    straight from "./wrapped.json" (works from any static host, no server needed);
 *  - unified: served by label_server.py at "/", "/admin", "/wrapped…", "/shared…", "/graph…", "/app…"
 *    — hash-routed SPA over the API.
 */
function isUnifiedMode(): boolean {
  const p = location.pathname
  // the public demo (demo/) is a Deck wherever it is hosted
  if (document.documentElement.hasAttribute("data-demo")) return false
  if (p === "/" || p === "") return true
  return /^\/(admin|wrapped|shared|graph|app)(\/|$)/.test(p)
}

export default function App() {
  if (!isUnifiedMode()) return <Deck />
  return (
    <StoreProvider>
      <Unified />
    </StoreProvider>
  )
}

function Unified() {
  const [route, go] = useRoute()
  const isDeck = route.view === "wrapped" && !!route.slug
  const { names } = useStore()
  // Admin-only deck extras: right-click-to-name on co-stars + face boxes in the lightbox.
  const extras = useMemo<DeckExtras>(
    () => ({
      names,
      FaceMenu: FaceContextMenu,
      fetchFaces: (src) => api.photo(src).catch(() => null),
    }),
    [names]
  )

  // light workspace theme everywhere except inside a Wrapped deck
  useEffect(() => {
    const el = document.documentElement
    if (isDeck) el.classList.remove("ws")
    else el.classList.add("ws")
    return () => el.classList.remove("ws")
  }, [isDeck])

  useEffect(() => {
    if (!isDeck) {
      const t = { admin: "Admin · Wedding Wrapped", people: "People · Wedding Wrapped", groups: "Groups · Wedding Wrapped", review: "Review · Wedding Wrapped", wrapped: "Wrapped · Wedding Wrapped" }[route.view]
      document.title = t
      window.scrollTo(0, 0)
    }
  }, [route.view, route.slug, isDeck])

  return (
    <Shell view={route.view} dark={isDeck}>
      {route.view === "admin" && <AdminView route={route} go={go} />}
      {route.view === "people" && <PeopleView route={route} go={go} />}
      {route.view === "groups" && <GroupsView route={route} go={go} />}
      {route.view === "review" && <ReviewView route={route} go={go} />}
      {route.view === "wrapped" && !route.slug && <WrappedIndex go={go} />}
      {route.view === "wrapped" && route.slug && (
        <Deck key={route.slug} src={`/site/${encodeURIComponent(route.slug)}/wrapped.json`} rewrite embedded extras={extras} />
      )}
    </Shell>
  )
}
