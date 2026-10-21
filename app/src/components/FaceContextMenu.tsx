import { useRef, useState, type ReactNode } from "react"
import { MoreHorizontal } from "lucide-react"
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuLabel,
  ContextMenuSeparator,
  ContextMenuTrigger,
} from "@/components/ui/context-menu"
import { Popover, PopoverAnchor, PopoverContent } from "@/components/ui/popover"
import { NameCommand } from "@/components/NameCombobox"
import { useStore } from "@/store"
import { guestLabel, rowStatus } from "@/api"
import { buildHash, navigate } from "@/router"
import { cn } from "@/lib/utils"

interface Props {
  cid: number
  /** fallback name when the store doesn't know this cluster */
  name?: string | null
  photos?: number
  children: ReactNode
  /** show a small "…" affordance on hover (for discoverability on non-touch) */
  hint?: boolean
  hintClassName?: string
  /** wrap children with a block/inline-block span (default) or pass through as-is (asChild) */
  asChild?: boolean
  className?: string
}

/**
 * Right-click / long-press (Radix handles touch long-press) any face → name that person.
 * Saves go through store.saveLabel → optimistic update, "saved ✓", Undo.
 */
export default function FaceContextMenu({ cid, name, photos, children, hint, hintClassName, asChild, className }: Props) {
  const { rows, guests, usedBy, names, wrappedByCid, saveLabel } = useStore()
  const [nameOpen, setNameOpen] = useState(false)
  const triggerRef = useRef<HTMLElement | null>(null)
  const row = rows.find((r) => r.cid === cid)
  const label = row?.label
  const st = rowStatus(label)
  const shown = names[cid] || (label?.status === "labeled" ? label.name : undefined) || name || `#${cid}`
  const nPhotos = row?.photos ?? photos
  const slug = wrappedByCid[cid]

  const openHint = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    const el = triggerRef.current
    if (!el) return
    el.dispatchEvent(new MouseEvent("contextmenu", { bubbles: true, cancelable: true, clientX: e.clientX, clientY: e.clientY }))
  }

  const inner = hint ? (
    <span className={cn("group/face relative inline-block", className)}>
      {children}
      <button
        type="button"
        aria-label={`Actions for ${shown}`}
        onClick={openHint}
        onPointerDown={(e) => e.stopPropagation()}
        className={cn(
          "absolute right-0.5 top-0.5 z-[5] flex h-5 w-5 items-center justify-center rounded-full bg-black/55 text-white opacity-0 shadow ring-1 ring-white/30 transition-opacity group-hover/face:opacity-100 focus:opacity-100",
          hintClassName
        )}
      >
        <MoreHorizontal className="h-3 w-3" />
      </button>
    </span>
  ) : (
    children
  )

  return (
    <Popover open={nameOpen} onOpenChange={setNameOpen}>
      <ContextMenu modal={false}>
        <PopoverAnchor asChild>
          <ContextMenuTrigger asChild={asChild || hint || false} ref={triggerRef as React.Ref<HTMLSpanElement>} className={!asChild && !hint ? cn("inline-block", className) : undefined}>
            {inner}
          </ContextMenuTrigger>
        </PopoverAnchor>
        <ContextMenuContent className="z-[96] w-64" onCloseAutoFocus={(e) => e.preventDefault()}>
          <ContextMenuLabel className="flex items-center gap-2 font-normal">
            {row?.face && <img src={row.face} alt="" className="h-8 w-8 rounded-md object-cover ring-1 ring-ws-line" />}
            <span className="min-w-0">
              <span className={cn("block truncate text-[13px] font-semibold", !names[cid] && !label?.name && "italic text-ws-muted")}>
                {shown}
                {label?.provisional && label.status === "labeled" ? " (provisional)" : ""}
              </span>
              <span className="block text-[11px] text-ws-muted">
                #{cid}
                {nPhotos != null ? ` · ${nPhotos.toLocaleString()} photos` : ""}
                {st === "not_guest" ? " · not a guest" : st === "merged" ? ` · merged into #${label?.merge_into}` : ""}
              </span>
            </span>
          </ContextMenuLabel>
          <ContextMenuSeparator />
          <ContextMenuItem onSelect={() => setTimeout(() => setNameOpen(true), 0)}>Name this person…</ContextMenuItem>
          {st === "provisional" && label && (
            <ContextMenuItem
              onSelect={() => {
                const { provisional: _p, ...rest } = label
                void saveLabel(cid, rest)
              }}
            >
              Confirm “{label.name}”
            </ContextMenuItem>
          )}
          {st !== "not_guest" && <ContextMenuItem onSelect={() => void saveLabel(cid, { status: "not_guest" })}>Not a guest</ContextMenuItem>}
          {st !== "unlabeled" && (
            <ContextMenuItem className="text-ws-warn" onSelect={() => void saveLabel(cid, null)}>
              Clear name
            </ContextMenuItem>
          )}
          <ContextMenuSeparator />
          <ContextMenuItem onSelect={() => navigate(buildHash("admin", null, { cid: String(cid) }))}>Open in Admin</ContextMenuItem>
          <ContextMenuItem onSelect={() => navigate(buildHash("people", null, { tab: "photos", sel: String(cid) }))}>Photos with them</ContextMenuItem>
          {slug && <ContextMenuItem onSelect={() => navigate(buildHash("wrapped", slug))}>Wrapped →</ContextMenuItem>}
        </ContextMenuContent>
      </ContextMenu>
      <PopoverContent align="start" className="z-[97] w-[360px] p-0" onOpenAutoFocus={(e) => e.preventDefault()}>
        {nameOpen && (
          <NameCommand
            cid={cid}
            current={label?.status === "labeled" ? label.name : undefined}
            clusterEvents={row?.events}
            guests={guests}
            usedBy={usedBy}
            onPickGuest={(g) => {
              void saveLabel(cid, guestLabel(g))
              setNameOpen(false)
            }}
            onCustomName={(n) => {
              void saveLabel(cid, { status: "labeled", name: n })
              setNameOpen(false)
            }}
            onClear={
              st !== "unlabeled"
                ? () => {
                    void saveLabel(cid, null)
                    setNameOpen(false)
                  }
                : undefined
            }
          />
        )}
      </PopoverContent>
    </Popover>
  )
}
