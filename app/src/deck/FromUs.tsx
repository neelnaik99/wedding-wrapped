import Card from "./Card"
import type { Wrapped } from "@/types"

/** True when there is a real hand-written note — the card is only rendered then. */
export function hasNote(data: Wrapped): boolean {
  return typeof data.from_us === "string" && data.from_us.trim().length > 0
}

export default function FromUs({ data }: { data: Wrapped }) {
  const note = hasNote(data) ? (data.from_us as string) : ""
  return (
    <Card>
      <div className="split split--center">
        <div className="split-head">
          <p className="eyebrow mb-6">From us</p>
          <p className="h-serif title">{data.name},</p>
        </div>
        <div>
          <p
            className="h-serif mt-5 whitespace-pre-line text-[21px] leading-[1.45] text-ink lg:mt-0 lg:text-[30px] lg:leading-[1.4]"
          >
            {note}
          </p>
          <p className="h-serif mt-6 text-[19px] text-ink lg:text-[24px]">— {data.couple}</p>
        </div>
      </div>

      <div className="divider mt-10 pt-5 text-[14px] text-muted lg:mt-14 lg:text-[16px]">
        Full galleries &amp; hi-res downloads:{" "}
        <a
          href={data.gallery_link || "#"}
          target={data.gallery_link && data.gallery_link !== "#" ? "_blank" : undefined}
          rel="noreferrer"
          className="text-gold underline decoration-gold/40 underline-offset-4 hover:decoration-gold"
        >
          photographer&rsquo;s gallery →
        </a>
      </div>
    </Card>
  )
}
