import { useMemo, useState } from "react"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Command, CommandInput, CommandItem, CommandList } from "@/components/ui/command"
import { rankGuests } from "@/lib/rank"
import { cn } from "@/lib/utils"
import type { Guest, Label } from "@/api"

interface CommandProps {
  cid: number
  current?: string
  clusterEvents?: Record<string, number>
  guests: Guest[]
  usedBy: Record<number, number[]>
  onPickGuest: (g: Guest) => void
  onCustomName: (name: string) => void
  onClear?: () => void
}

/** The guest-list combobox body (ranked suggestions, custom name, clear) — reused by the table cell and the face menu. */
export function NameCommand({ cid, current, clusterEvents, guests, usedBy, onPickGuest, onCustomName, onClear }: CommandProps) {
  const [q, setQ] = useState("")
  const ranked = useMemo(() => rankGuests(guests, q, clusterEvents, usedBy, 10, cid), [guests, q, clusterEvents, usedBy, cid])
  const qt = q.trim()
  const exact = qt && ranked.some((r) => r.g.name.toLowerCase() === qt.toLowerCase())
  return (
    <Command shouldFilter={false} loop>
      <CommandInput autoFocus value={q} onValueChange={setQ} placeholder="Type a guest name…" className="h-9" />
      <CommandList className="max-h-[320px]">
        {ranked.length === 0 && !qt && <div className="px-3 py-3 text-[12px] text-ws-muted">No guests to suggest.</div>}
        {ranked.map((r) => (
          <CommandItem key={r.g.id} value={`g-${r.g.id}`} onSelect={() => onPickGuest(r.g)} className="flex items-start justify-between gap-2 py-1.5">
            <span className="min-w-0">
              <span className="block truncate text-[13px]">{r.g.name}</span>
              {r.g.email && <span className="block truncate text-[11px] text-ws-muted">{r.g.email}</span>}
            </span>
            <span className="flex shrink-0 flex-col items-end gap-0.5">
              {r.usedBy && <span className="ws-chip bg-red-50 text-ws-warn">already #{r.usedBy.join(", #")}</span>}
              {r.fit > 0 && <span className="ws-chip bg-emerald-50 text-ws-ok">{r.fit} events match</span>}
            </span>
          </CommandItem>
        ))}
        {qt && !exact && (
          <CommandItem value="__custom" onSelect={() => onCustomName(qt)} className="border-t text-[13px]">
            Use “{qt}” as a custom name (not on the guest list)
          </CommandItem>
        )}
        {current && onClear && (
          <CommandItem value="__clear" onSelect={onClear} className="border-t text-[13px] text-ws-warn">
            Clear name
          </CommandItem>
        )}
      </CommandList>
    </Command>
  )
}

interface Props {
  cid: number
  label: Label | null | undefined
  clusterEvents: Record<string, number>
  guests: Guest[]
  usedBy: Record<number, number[]>
  onPickGuest: (g: Guest) => void
  onCustomName: (name: string) => void
  onClear?: () => void
  className?: string
  /** compact = table cell button */
  compact?: boolean
}

/** Inline-editable name cell: button → popover with a guest-list combobox (ranked suggestions). */
export default function NameCombobox({ cid, label, clusterEvents, guests, usedBy, onPickGuest, onCustomName, onClear, className, compact = true }: Props) {
  const [open, setOpen] = useState(false)
  const current = label?.status === "labeled" ? label.name || "" : ""
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className={cn(
            "inline-flex max-w-full items-center gap-1 truncate rounded-md border border-transparent px-1.5 py-0.5 text-left hover:border-ws-line hover:bg-white",
            compact ? "text-[13px]" : "ws-input w-full text-[14px]",
            !current && "italic text-ws-muted",
            className
          )}
          title={current ? `${current} — click to change` : "Click to name this cluster"}
        >
          <span className="truncate">{current || "add name…"}</span>
          {label?.provisional && label.status === "labeled" && <span className="ws-chip bg-amber-100 text-amber-800">?</span>}
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="z-[85] w-[360px] p-0" onOpenAutoFocus={(e) => e.preventDefault()}>
        {open && (
          <NameCommand
            cid={cid}
            current={current}
            clusterEvents={clusterEvents}
            guests={guests}
            usedBy={usedBy}
            onPickGuest={(g) => {
              onPickGuest(g)
              setOpen(false)
            }}
            onCustomName={(n) => {
              onCustomName(n)
              setOpen(false)
            }}
            onClear={
              onClear
                ? () => {
                    onClear()
                    setOpen(false)
                  }
                : undefined
            }
          />
        )}
      </PopoverContent>
    </Popover>
  )
}
