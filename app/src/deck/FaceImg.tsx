import { cn } from "@/lib/utils"

/** The person's initial ("Pat Q" → "P"); "?" when there is no name. */
export const initialOf = (name: string | undefined) => (name ?? "").trim().slice(0, 1).toUpperCase() || "?"

/**
 * A round face chip. `src` is null on a Household Deck when no photo of this person includes a
 * member of the Household (household_deck._localize_faces) — then the chip shows their initial.
 */
export default function FaceImg({
  src,
  name,
  className,
}: {
  src: string | null | undefined
  name: string
  className: string
}) {
  if (!src) {
    return (
      <span
        aria-hidden="true"
        className={cn(className, "inline-flex items-center justify-center bg-black/30 font-semibold text-ink")}
      >
        {initialOf(name)}
      </span>
    )
  }
  return <img src={src} alt="" loading="lazy" className={className} />
}
