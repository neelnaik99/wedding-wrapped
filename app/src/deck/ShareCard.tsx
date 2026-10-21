import Card from "./Card"
import type { Wrapped } from "@/types"

interface ShareCardProps {
  data: Wrapped
  onToast: (msg: string) => void
}

const fmt = (n: number) => n.toLocaleString("en-US")

export default function ShareCard({ data, onToast }: ShareCardProps) {
  const top = data.costars?.[0]

  async function share() {
    const url = window.location.href
    const title = `${data.name}'s Wedding Wrapped`
    const text = `${fmt(data.n_photos)} photos of ${data.name} across ${data.n_events} events — ${data.couple}, ${data.dates}.`
    const nav = navigator as Navigator & { share?: (d: ShareData) => Promise<void> }
    if (nav.share) {
      try {
        await nav.share({ title, text, url })
        return
      } catch (err) {
        // User cancelled or share failed — fall through to clipboard.
        if ((err as { name?: string })?.name === "AbortError") return
      }
    }
    try {
      await navigator.clipboard.writeText(url)
      onToast("Link copied")
    } catch {
      onToast("Couldn’t copy — long-press the address bar to share")
    }
  }

  const rows: [string, string][] = [
    ["Photos", fmt(data.n_photos)],
    ["Events", fmt(data.n_events)],
    ["Moments", fmt(data.n_scenes)],
    ["Top co-star", top ? top.name : "—"],
  ]

  return (
    <Card innerClassName="lg:flex lg:flex-col lg:items-center">
      <div className="w-full lg:max-w-[560px]">
      <div
        className="rounded-2xl p-6 text-maroon shadow-[0_20px_60px_rgba(0,0,0,0.35)] lg:p-8"
        style={{
          background:
            "linear-gradient(150deg, #f2c14e 0%, #e0a63a 48%, #d9556a 100%)",
        }}
      >
        <p className="text-[11px] uppercase tracking-[0.16em] text-maroon/75">
          Preethi &amp; Neel · Wedding Wrapped
        </p>
        <p className="h-serif mt-3 text-[40px] leading-none lg:text-[52px]">{data.name}</p>

        <dl className="mt-6">
          {rows.map(([k, v]) => (
            <div
              key={k}
              className="flex items-baseline justify-between border-t border-maroon/15 py-2.5 first:border-t-0"
            >
              <dt className="text-[13px] uppercase tracking-[0.08em] text-maroon/75">{k}</dt>
              <dd className="h-serif text-[24px] leading-none">{v}</dd>
            </div>
          ))}
        </dl>

        <p className="mt-5 text-[12px] text-maroon/70">{data.dates}</p>
      </div>

      <button
        type="button"
        onClick={share}
        className="pill pill--action mt-6 min-h-[44px] px-6 !text-[14px] focus:outline-none focus-visible:ring-2 focus-visible:ring-haldi"
      >
        Share your Wrapped
      </button>
      <p className="mt-3 text-[12px] text-muted/80">
        Made with love (and a lot of face-matching) by Preethi &amp; Neel.
      </p>
      </div>
    </Card>
  )
}
