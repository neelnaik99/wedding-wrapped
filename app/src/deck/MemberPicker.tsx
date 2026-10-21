import { useState } from "react"

export interface PickerMember {
  cid: number
  first: string
  /** small face crop, e.g. "../../img/face_124.jpg"; a missing file falls back to the initial */
  face: string
}

interface MemberPickerProps {
  members: PickerMember[]
  selected: number[]
  onToggle: (cid: number) => void
  accent: string
  accentInk: string
}

/**
 * Household Deck member picker: one chip per member, toggled to choose whose Wrapped the
 * deck shows. Never empty — unticking the last selected member is refused with a note.
 * The caller hides it for a one-member Household.
 */
export default function MemberPicker({ members, selected, onToggle, accent, accentInk }: MemberPickerProps) {
  const [refused, setRefused] = useState(false)
  return (
    <div className="member-picker px-4 pb-3 pt-[max(14px,env(safe-area-inset-top))] lg:px-14">
      <p className="eyebrow" id="member-picker-heading">
        Select whose Wrapped you want to look at
      </p>
      <div className="mt-2 flex flex-wrap gap-2" role="group" aria-labelledby="member-picker-heading">
        {members.map((m) => {
          const on = selected.includes(m.cid)
          return (
            <button
              key={m.cid}
              type="button"
              aria-pressed={on}
              aria-label={m.first}
              className="inline-flex min-h-[44px] items-center gap-2 rounded-full border py-1 pl-1 pr-3 text-[14px] transition-colors"
              style={
                on
                  ? { background: accent, color: accentInk, borderColor: accent }
                  : { background: "transparent", color: "rgba(243,236,225,0.75)", borderColor: "rgba(243,236,225,0.25)" }
              }
              onClick={() => {
                const last = on && selected.length === 1
                setRefused(last)
                if (!last) onToggle(m.cid)
              }}
            >
              <Face face={m.face} first={m.first} dim={!on} />
              <span className={on ? "font-semibold" : undefined}>{m.first}</span>
            </button>
          )
        })}
      </div>
      <p className="mt-1 min-h-[18px] text-[12px] text-muted" aria-live="polite">
        {refused ? "Keep at least one person selected." : ""}
      </p>
    </div>
  )
}

function Face({ face, first, dim }: { face: string; first: string; dim: boolean }) {
  const [broken, setBroken] = useState(false)
  const cls = "h-8 w-8 shrink-0 rounded-full object-cover"
  if (broken || !face) {
    return (
      <span aria-hidden="true" className={`${cls} inline-flex items-center justify-center bg-black/30 text-[13px]`}>
        {first.slice(0, 1)}
      </span>
    )
  }
  return (
    <img
      src={face}
      alt=""
      aria-hidden="true"
      className={cls}
      style={dim ? { opacity: 0.55, filter: "grayscale(0.6)" } : undefined}
      onError={() => setBroken(true)}
    />
  )
}
