import { useEffect, useRef, type ReactNode } from "react"
import { cn } from "@/lib/utils"

interface CardProps {
  children: ReactNode
  className?: string
  /** free = not snap-locked, natural height (used by the long gallery) */
  free?: boolean
  /** top = align content to the top instead of vertically centering (phone only) */
  top?: boolean
  /** extra classes for the inner content column */
  innerClassName?: string
  id?: string
}

/** One full-height "wrapped" card. Fades up once when it enters the viewport. */
export default function Card({ children, className, free, top, innerClassName, id }: CardProps) {
  const ref = useRef<HTMLElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    // Visible by default. Only when motion is fine do we hide-then-reveal, and even then a
    // 1500ms fallback reveals regardless of IntersectionObserver (hidden tabs, odd browsers).
    const motionOK = window.matchMedia("(prefers-reduced-motion: no-preference)").matches
    if (!motionOK || !("IntersectionObserver" in window)) {
      el.classList.add("in")
      return
    }
    el.classList.add("reveal--pending")
    const reveal = () => {
      el.classList.remove("reveal--pending")
      el.classList.add("in")
    }
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            reveal()
            io.disconnect()
          }
        }
      },
      // threshold 0 so very tall cards (the gallery) still trigger; the negative
      // bottom margin means "reveal once ~10% of the viewport has been crossed".
      { threshold: 0, rootMargin: "0px 0px -10% 0px" }
    )
    io.observe(el)
    const t = window.setTimeout(() => {
      reveal()
      io.disconnect()
    }, 1500)
    return () => {
      io.disconnect()
      window.clearTimeout(t)
    }
  }, [])

  return (
    <section
      id={id}
      ref={ref}
      className={cn("card reveal", free && "card--free", top && "card--top", className)}
    >
      <div className={cn("inner", innerClassName)}>{children}</div>
    </section>
  )
}
