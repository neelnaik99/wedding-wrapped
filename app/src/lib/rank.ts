import { RSVP, type Guest } from "@/api"

export interface RankedGuest {
  g: Guest
  score: number
  fit: number
  usedBy: number[] | undefined
}

/**
 * Rank guest-list entries for a cluster: name match first, then RSVP-event overlap with the
 * cluster's events, then unused guests first (same heuristics as the original namer).
 */
export function rankGuests(
  guests: Guest[],
  query: string,
  clusterEvents: Record<string, number> | undefined,
  usedBy: Record<number, number[]>,
  limit = 8,
  excludeCid?: number
): RankedGuest[] {
  const q = query.trim().toLowerCase()
  const evs = new Set(Object.keys(clusterEvents ?? {}).map((e) => RSVP[e] ?? e))
  const out: RankedGuest[] = []
  for (const g of guests) {
    const n = g.name.toLowerCase()
    let s = 0
    if (q) {
      if (n.startsWith(q)) s += 6
      else if (n.split(" ").some((w) => w.startsWith(q))) s += 4
      else if (n.includes(q)) s += 2
      else if (g.email && g.email.toLowerCase().includes(q)) s += 1
      else continue
    }
    let fit = 0
    for (const e of evs) if (g.events[e]) fit += 1
    s += fit
    const used = usedBy[g.id]?.filter((c) => c !== excludeCid)
    const usedList = used && used.length ? used : undefined
    if (!usedList) s += 1.5
    out.push({ g, score: s, fit, usedBy: usedList })
  }
  out.sort((a, b) => b.score - a.score || a.g.name.localeCompare(b.g.name))
  return out.slice(0, limit)
}
