import type { ReactNode } from "react"
import { Undo2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { useStore } from "@/store"
import { dismissUndoToast, useUndoToast } from "@/hooks/use-toast"
import type { View } from "@/router"

// `review` (#/review, issue #33) lands in a later wave — the nav link is harmless
// until the route exists, so it's typed alongside the real views here.
const NAV: { view: View | "review"; label: string; hash: string }[] = [
  { view: "admin", label: "Admin", hash: "#/admin" },
  { view: "people", label: "People", hash: "#/people" },
  { view: "groups", label: "Groups", hash: "#/groups-admin" },
  { view: "review", label: "Review", hash: "#/review" },
  { view: "wrapped", label: "Wrapped", hash: "#/wrapped" },
]

/** Fixed top nav for the unified app. `dark` = rendered over the Wrapped deck. */
export default function Shell({
  view,
  dark,
  children,
}: {
  view: View
  dark: boolean
  children: ReactNode
}) {
  const { status, undo, toastMsg } = useStore()
  const undoToast = useUndoToast()
  return (
    <>
      <header
        className={cn(
          "fixed inset-x-0 top-0 z-[80] flex h-[var(--nav-h)] items-center gap-1 border-b px-3 text-[13px] backdrop-blur-sm",
          dark
            ? "border-white/10 bg-[#1a0f12]/85 text-ink"
            : "border-ws-line bg-white/90 text-ws-ink"
        )}
      >
        <a
          href="#/admin"
          className={cn(
            "mr-3 h-serif text-[16px] leading-none tracking-tight",
            dark ? "text-haldi" : "text-ws-accentText"
          )}
          title="Wedding Wrapped"
        >
          Wedding Wrapped
        </a>
        <nav className="flex items-center gap-0.5">
          {NAV.map((n) => {
            const active = n.view === view
            return (
              <a
                key={n.view}
                href={n.hash}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "rounded-md px-2.5 py-1 font-medium transition-colors",
                  active
                    ? dark
                      ? "bg-white/10 text-ink"
                      : "bg-ws-soft text-ws-ink"
                    : dark
                      ? "text-muted hover:text-ink"
                      : "text-ws-muted hover:text-ws-ink"
                )}
              >
                {n.label}
              </a>
            )
          })}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <span
            className={cn(
              "text-[12px]",
              status === "saving" && (dark ? "text-muted" : "text-ws-muted"),
              status === "saved" && "text-ws-ok",
              status === "error" && "text-ws-warn",
              status === "idle" && "opacity-0"
            )}
            aria-live="polite"
          >
            {status === "saving" ? "saving…" : status === "saved" ? "saved ✓" : status === "error" ? "save failed" : "saved ✓"}
          </span>
          <button
            type="button"
            onClick={() => void undo()}
            className={cn(
              "inline-flex items-center gap-1 rounded-md border px-2 py-1 text-[12px] font-medium",
              dark
                ? "border-white/15 text-ink hover:bg-white/10"
                : "border-ws-line bg-white text-ws-ink hover:border-ws-accent"
            )}
            title="Undo the last label change (server-side)"
          >
            <Undo2 className="h-3.5 w-3.5" /> Undo
          </button>
        </div>
      </header>

      {children}

      <div
        aria-live="polite"
        className="pointer-events-none fixed inset-x-0 bottom-6 z-[90] flex flex-col items-center gap-2 px-6"
      >
        {/* Undo toast (issue #15) — dark pill, ivory text, inline Undo (DESIGN.md toast-undo). */}
        {undoToast && (
          <div className="pointer-events-auto flex items-center gap-3 rounded-lg bg-[#1c1917] px-4 py-2.5 text-[13px] font-medium text-[#f6f1e7] shadow-lg">
            <span>{undoToast.message}</span>
            <button
              type="button"
              onClick={() => {
                undoToast.onAction()
                dismissUndoToast()
              }}
              className="inline-flex items-center gap-1 rounded-md border border-white/25 px-2 py-0.5 text-[12px] font-semibold text-[#f6f1e7] hover:bg-white/10"
            >
              <Undo2 className="h-3.5 w-3.5" /> {undoToast.actionLabel}
            </button>
          </div>
        )}
        {toastMsg && (
          <div
            className={cn(
              "rounded-full px-4 py-2 text-[13px] font-medium shadow-lg",
              dark ? "bg-ink text-bg" : "bg-ws-ink text-white"
            )}
          >
            {toastMsg}
          </div>
        )}
      </div>
    </>
  )
}
