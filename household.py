"""
Household hub page — one link that opens everyone in a household.

Most guests share an email address with the person they came with: 46 of 72 households hold
2-4 guests, and the household email already carries a link per member. This turns that list
into a place: `site_guest/h/<token>/` shows every deck in the household, each as a name + best
photo + count, so a recipient who is reviewing on behalf of a spouse or a parent lands
somewhere that shows all of them instead of picking a link out of a paragraph.

Membership is the `party` column, exactly as make_emails.py groups households — `hh_key` lives
here and both import it, so the email and the hub can never disagree about who is in a
household.

Path: `/h/<token>/`, one level deeper than a deck, and a reserved prefix. A deck token sits at
the site root (`/<token>/`), so putting hubs under `/h/` keeps the two namespaces from ever
colliding and leaves a single path a future auth layer can own without touching deck URLs
(ROADMAP "Auth = email magic links"). Being deeper also means image paths need one more `../`
than a deck's — see `_reroot`.

Contains no email addresses and no guest ids: first names, photos, counts and links only. The
page is the same self-contained night chrome as postcard.py — no bundle, no fetch.
"""
import html as _html
import json
from pathlib import Path

# night chrome tokens (DESIGN.md frontmatter) — kept in step with postcard.py
NIGHT_CANVAS, NIGHT_CARD, NIGHT_TILE = "#221b18", "#2c231f", "#382d26"
NIGHT_INK, NIGHT_MUTED, NIGHT_HAIRLINE, NIGHT_RING = "#f3ece1", "#b3a08f", "#3a2f28", "#9c8568"

HUB_DIR = "h"   # reserved path prefix: site_guest/h/<token>/


def hh_key(party, name):
    """Household identity: the party column, or a per-person key when they have no party.

    The single definition of "same household" — make_emails.py imports this so the email's
    recipient grouping and the hub's member list cannot drift apart.
    """
    p = (party or "").strip()
    return p if p else f"solo:{name}"


def households(manifest):
    """Group manifest rows into households, biggest deck first within each.

    Returns {household_key: [manifest rows]}. Every guest appears exactly once; solo guests
    get a one-member household (the caller decides those don't need a hub).
    """
    out = {}
    for m in manifest:
        out.setdefault(hh_key(m.get("party"), m["name"]), []).append(m)
    for members in out.values():
        members.sort(key=lambda m: -m.get("n_photos", 0))
    return out


def envelope_names(rows):
    """{household_key: envelope name} from guest-list CSV rows (csv.DictReader).

    The first non-blank `envelope name` in a household wins. make_emails.py greets with it and
    household_deck.py titles the Deck with it, so the two read it the same way.
    """
    out = {}
    for r in rows:
        k = hh_key(r.get("party", ""), f'{r["first name"]} {r["last name"]}')
        env = (r.get("envelope name") or "").strip()
        if env and k not in out:
            out[k] = env
    return out


def _reroot(url):
    """Rewrite a deck-relative image path for a page one directory deeper.

    Decks live at `/<token>/` and reference `../img/...`; a hub at `/h/<token>/` needs
    `../../img/...`. Anything already absolute is left alone.
    """
    if not url:
        return ""
    if url.startswith(("http://", "https://", "/")):
        return url
    return "../" + url


def render_hub(name, members):
    """One household hub page. `members` are manifest rows, already ordered."""
    cards = []
    for m in members:
        first = _html.escape(m.get("first") or m.get("name") or "")
        hero = _html.escape(_reroot(m.get("hero", "")))
        n = m.get("n_photos") or 0
        count = f"{n} photo{'' if n == 1 else 's'}"
        if m.get("link", True):
            # deck token lives at the site root, and the hub is one level down
            href = _html.escape(f"../../{m['token']}/")
            cards.append(
                f'<a class=card href="{href}">'
                f'<span class=thumb><img loading=lazy src="{hero}" alt=""></span>'
                f'<span class=meta><span class=who>{first}</span>'
                f'<span class=count>{count}</span></span>'
                f'<span class=go>Open {first}&rsquo;s Wrapped &rarr;</span></a>')
        else:
            # glimpse tier has no deck of their own — the photo itself is the gift,
            # mirroring what make_emails.py inlines for them in the email.
            cards.append(
                f'<div class="card card--photo">'
                f'<span class=thumb><img loading=lazy src="{hero}" alt="Photo of {first}"></span>'
                f'<span class=meta><span class=who>{first}</span>'
                f'<span class=count>one of our favorites</span></span>'
                f'<a class=go href="{hero}" download>Download this photo</a></div>')

    n_people = len(members)
    lede = ("Each of you has your own page of photos from the weekend. Select whose Wrapped you want to look at."
            if n_people > 1 else "Your page of photos from the weekend.")
    return render_page(name, lede, "".join(cards))


def render_page(greeting, lede, cards_html):
    """The night-chrome page shell: escaped greeting, trusted lede + card markup."""
    return _TEMPLATE \
        .replace("__GREETING__", _html.escape(greeting)) \
        .replace("__LEDE__", lede) \
        .replace("__CARDS__", cards_html) \
        .replace("__NIGHT_CANVAS__", NIGHT_CANVAS).replace("__NIGHT_CARD__", NIGHT_CARD) \
        .replace("__NIGHT_TILE__", NIGHT_TILE).replace("__NIGHT_INK__", NIGHT_INK) \
        .replace("__NIGHT_MUTED__", NIGHT_MUTED).replace("__NIGHT_HAIRLINE__", NIGHT_HAIRLINE) \
        .replace("__NIGHT_RING__", NIGHT_RING)


def build_hub(out_dir, name, members):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(render_hub(name, members))


_TEMPLATE = """<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name=robots content="noindex,nofollow"><meta name=theme-color content="#221b18">
<title>Your Wedding Wrapped &middot; Preethi &amp; Neel</title>
<style>
:root{--bg:__NIGHT_CANVAS__;--card:__NIGHT_CARD__;--tile:__NIGHT_TILE__;--ink:__NIGHT_INK__;
--muted:__NIGHT_MUTED__;--hair:__NIGHT_HAIRLINE__;--ring:__NIGHT_RING__}
*,:before,:after{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
padding:clamp(24px,6vw,72px) clamp(20px,5vw,56px)}
.wrap{max-width:820px;margin:0 auto}
.serif{font-family:"Iowan Old Style",Palatino,Georgia,serif}
.eyebrow{font:450 12px/1.3 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:1.6px;
text-transform:uppercase;color:var(--muted)}
h1{margin:10px 0 0;font-weight:450;font-size:clamp(30px,5vw,48px);line-height:1.08;letter-spacing:-.5px}
.lede{margin:12px 0 0;color:var(--muted);max-width:46ch}
.grid{display:grid;gap:14px;margin:clamp(28px,5vw,44px) 0 0}
.card{display:flex;align-items:center;gap:16px;padding:14px;border-radius:16px;background:var(--card);
border:1px solid var(--hair);text-decoration:none;color:inherit;transition:border-color .15s}
a.card:hover,a.card:focus-visible{border-color:var(--ring)}
.card--photo{flex-wrap:wrap}
.thumb{flex:0 0 auto;width:84px;height:84px;border-radius:12px;overflow:hidden;background:var(--tile)}
.thumb img{width:100%;height:100%;object-fit:cover;display:block}
.meta{display:flex;flex-direction:column;gap:2px;min-width:0;flex:1 1 auto}
.who{font-family:"Iowan Old Style",Palatino,Georgia,serif;font-size:22px;line-height:1.2}
.count{font:450 11px/1.2 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.8px;color:var(--muted)}
.go{flex:0 0 auto;font-size:14px;font-weight:560;color:var(--muted)}
a.card:hover .go,a.card:focus-visible .go{color:var(--ink)}
.card--photo .go{border:1px solid var(--ring);border-radius:50px;padding:8px 16px;
text-decoration:none;color:var(--ink)}
.foot{margin:36px 0 0;color:var(--muted);font-size:14px}
@media(max-width:520px){.card{flex-wrap:wrap}.go{width:100%;padding-left:100px}}
</style></head><body><div class=wrap>
  <div class=eyebrow>Preethi &amp; Neel &middot; April 24&ndash;25, 2026</div>
  <h1 class=serif>__GREETING__</h1>
  <p class=lede>__LEDE__</p>
  <div class=grid>__CARDS__</div>
  <p class=foot>These pages are personal to your family &mdash; feel free to share them.</p>
</div></body></html>"""
