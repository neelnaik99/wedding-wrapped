import { useRef, useState } from "react"
import Card from "./Card"
import type { Wrapped } from "@/types"

const fmt = (n: number) => n.toLocaleString("en-US")

// Dry one-liners cycled on tap; milestone lines land on the 10th / 25th / 50th tap so
// repeated taps pay off (DESIGN § Voice & takeaways — the sanctioned easter egg).
const LINES = [
  "Yes, that many.",
  "We counted twice.",
  "Every single one has you in it.",
  "Someone liked the camera.",
  "The photographer earned their fee.",
  "Still tapping? Same energy.",
]
const MILESTONES: Record<number, string> = {
  10: "Ten taps in — we’re flattered.",
  25: "Twenty-five. Okay, you really like this number.",
  50: "That’s the lot. Now go download some photos. →",
}

export default function TheNumber({ data, accent }: { data: Wrapped; accent: string }) {
  const [taps, setTaps] = useState(0)
  const [line, setLine] = useState<string | null>(null)
  const burstRef = useRef<HTMLSpanElement>(null)

  function tap() {
    const n = taps + 1
    setTaps(n)
    setLine(MILESTONES[n] ?? LINES[(n - 1) % LINES.length])
    confetti(burstRef.current, accent)
  }

  return (
    <Card>
      <div className="flex flex-col items-center text-center">
        <p className="eyebrow mb-4">The number</p>

        <span ref={burstRef} className="relative inline-block">
          <button
            type="button"
            onClick={tap}
            aria-label={`${fmt(data.n_photos)} — tap for a surprise`}
            className="block rounded-2xl focus:outline-none focus-visible:ring-2 focus-visible:ring-haldi"
          >
            <span
              aria-hidden="true"
              className="h-serif block"
              style={{
                color: accent,
                fontSize: "clamp(88px, 26vw, 160px)",
                lineHeight: 0.92,
                letterSpacing: "-0.03em",
              }}
            >
              {fmt(data.n_photos)}
            </span>
          </button>
        </span>

        <p className="h-serif mt-3 text-[26px] text-ink lg:mt-5 lg:text-[32px]">
          photos of you, across {data.n_events} events
        </p>

        <p aria-hidden="true" className="mt-4 min-h-[1.4em] text-[13px] text-muted lg:text-[15px]">
          {line ?? "psst — the number is clickable"}
        </p>
      </div>
    </Card>
  )
}

/** Decorative confetti burst via the Web Animations API — no CSS, no deps, aria-hidden. */
function confetti(host: HTMLElement | null, accent: string) {
  if (!host || typeof host.animate !== "function") return
  if (window.matchMedia && !window.matchMedia("(prefers-reduced-motion: no-preference)").matches) return
  const colors = [accent, "#f2c14e", "#d9556a"]
  for (let i = 0; i < 12; i++) {
    const dot = document.createElement("span")
    dot.setAttribute("aria-hidden", "true")
    const size = 5 + Math.random() * 5
    dot.style.cssText = `position:absolute;left:50%;top:38%;width:${size}px;height:${size}px;border-radius:9999px;background:${colors[i % colors.length]};pointer-events:none;z-index:50;`
    host.appendChild(dot)
    const ang = (i / 12) * 2 * Math.PI + Math.random()
    const dist = 70 + Math.random() * 90
    const anim = dot.animate(
      [
        { transform: "translate(-50%,-50%) scale(1)", opacity: 1 },
        { transform: `translate(calc(-50% + ${Math.cos(ang) * dist}px), calc(-50% + ${Math.sin(ang) * dist}px)) scale(0.4)`, opacity: 0 },
      ],
      { duration: 700 + Math.random() * 300, easing: "cubic-bezier(0.2,0.7,0.3,1)" }
    )
    anim.onfinish = () => dot.remove()
  }
}
