import { readHash } from "@/lib/selection"

/**
 * Beat-3 anchor restore. The mind map used to be its own page, so returning from it needed a
 * sessionStorage scroll handshake (#35); now that it's the in-deck `#/map` view, the view
 * switch in Deck.tsx parks and restores the offset itself. What's left is the plain `#people`
 * fragment — a deep link into beat 3 — which still needs help, because the deck renders after
 * the browser has already tried (and failed) to find the anchor.
 */

/** True when the deck was loaded pointing at beat 3 (`#people`, or `#people?sel=…` on a Household deck). */
export function isPeopleReturn(): boolean {
  return /^#\/?people$/i.test(readHash(location.hash).route)
}

/**
 * Scroll beat 3 into view on a `#people` load, once the data is ready and the element exists.
 * Two frames so layout (async images/fonts) has settled before we measure. No-op otherwise.
 */
export function restorePeopleScroll(): void {
  if (!isPeopleReturn()) return
  requestAnimationFrame(() =>
    requestAnimationFrame(() => {
      document.getElementById("people")?.scrollIntoView({ block: "start" })
    })
  )
}
