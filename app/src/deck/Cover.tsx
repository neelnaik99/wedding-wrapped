import type { Wrapped } from "@/types"

/**
 * Cover card.
 * Phone: hero full-bleed with a dark gradient from the bottom, text bottom-left.
 * Wide (>=1024): split slide — hero fills the left 55%, text on the right,
 * with a soft blurred copy of the hero behind everything so a portrait hero
 * never looks stretched or boxed.
 */
export default function Cover({ data }: { data: Wrapped }) {
  return (
    <section
      className="card relative overflow-hidden !p-0 lg:grid lg:grid-cols-[55%_45%]"
      style={{ justifyContent: "flex-end" }}
    >
      {/* Wide: blurred backdrop */}
      <img
        src={data.hero}
        alt=""
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 hidden h-full w-full object-cover opacity-40 lg:block"
        style={{ filter: "blur(48px) saturate(1.1)", transform: "scale(1.15)" }}
      />
      <div className="absolute inset-0 hidden bg-bg/55 lg:block" />

      {/* Hero: absolute full-bleed on phone; left column on wide */}
      <div className="lg:relative lg:z-10 lg:h-full lg:min-h-[100dvh]">
        <img
          src={data.hero}
          alt={data.name}
          className="absolute inset-0 h-full w-full object-cover lg:absolute"
          style={data.hero_fx != null ? { objectPosition: `${data.hero_fx}% ${data.hero_fy}%` } : undefined}
          fetchPriority="high"
        />
        {/* phone gradient */}
        <div
          className="absolute inset-0 lg:hidden"
          style={{
            background:
              "linear-gradient(to top, rgba(34,27,24,0.97) 0%, rgba(34,27,24,0.75) 32%, rgba(34,27,24,0.15) 62%, rgba(34,27,24,0.35) 100%)",
          }}
        />
        {/* wide: soft edge fading the photo into the text panel */}
        <div
          className="absolute inset-y-0 right-0 hidden w-40 lg:block"
          style={{
            background: "linear-gradient(to right, rgba(34,27,24,0) 0%, rgba(34,27,24,0.55) 100%)",
          }}
        />
      </div>

      {/* Text block */}
      <div className="relative z-10 flex flex-col justify-end px-6 pb-14 pt-24 lg:justify-center lg:px-14 lg:pb-16 lg:pt-24 xl:px-20">
        <p className="eyebrow mb-3 lg:mb-5">
          {data.couple}&rsquo;s wedding · {data.dates}
        </p>
        <h1
          className="h-serif text-ink"
          style={{ fontSize: "clamp(44px, 4.6vw, 84px)", lineHeight: 1.04 }}
        >
          {data.name}&rsquo;s
          <br />
          Wedding Wrapped
        </h1>
        <p className="body mt-4 max-w-[30ch] text-muted lg:mt-6">
          We went through every photo. Here&rsquo;s you.
        </p>
      </div>

      <div className="absolute inset-x-0 bottom-4 z-10 flex justify-center lg:bottom-6">
        <span className="text-[11px] uppercase tracking-[0.18em] text-muted/80 lg:hidden">
          swipe up ↑
        </span>
        <span className="hidden text-[12px] uppercase tracking-[0.18em] text-muted/80 lg:inline">
          scroll ↓ &nbsp;·&nbsp; or press ↓
        </span>
      </div>
    </section>
  )
}
