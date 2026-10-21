"""
Per-household email drafts from send_manifest.json + the guest CSV. NOTHING IS SENT —
outputs are artifacts for review and manual sending (Gmail mail-merge or connector).

  python make_emails.py [--base-url https://<project>.pages.dev] [--subject "..."] [--guests ~/Downloads/guest-list.csv]

Writes (all gitignored):
  data/emails.csv / data/emails.json     one row per household: to, subject, html_body, text_body
  data/no_email_households.csv           deck-holding households with no email (phones included)
"""
import argparse, csv, json, os
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

from household import envelope_names, hh_key
from login_map import build_login_map, login_target

D = Path(__file__).parent / "data"

def abs_url(base, u):
    """Absolute URL for a manifest `url`/`hub_url`, whichever form the build produced.

    build_guests.py writes an ALREADY-absolute url when it is run with --base-url (which
    docs/DEPLOY.md instructs) and a root-relative "/<token>/" when it is not. Blindly
    prefixing `base` produced "https://host.devhttps://host.dev/<token>/" in every email --
    unopenable links for every guest. Normalise here so there is one place to get it right.
    """
    if not u:
        return ""
    if u.startswith(("http://", "https://")):
        return u
    return base + ("" if u.startswith("/") else "/") + u


def photo_url(base, hero):
    """Absolute URL for a guest's best photo (hero is a page-relative '../img/l/<id>' path)."""
    return base + "/" + quote(hero.replace("../", "").lstrip("/"))

def household_rows(manifest, rows, base, subject):
    """(emails, no_email): one row per Household. The only page link a row carries is the
    Household Link (hub_url / login_url); per-person deck URLs never reach the operator's files."""
    # household grouping is household.hh_key -- the same function build_guests.py uses to decide
    # who shares a hub, so the email's recipient list and the hub's member list cannot drift.
    hh_emails, hh_phones, hh_names = defaultdict(set), defaultdict(set), envelope_names(rows)
    for r in rows:
        k = hh_key(r.get("party", ""), f'{r["first name"]} {r["last name"]}')
        if r.get("email", "").strip(): hh_emails[k].add(r["email"].strip())
        if r.get("phone number", "").strip(): hh_phones[k].add(r["phone number"].strip())

    by_hh = defaultdict(list)
    for m in manifest:
        by_hh[hh_key(m.get("party", ""), m["name"])].append(m)

    emails, no_email = [], []
    for k, members in sorted(by_hh.items(), key=lambda kv: -max(x["n_photos"] for x in kv[1])):
        members.sort(key=lambda m: -m["n_photos"])
        to = sorted(hh_emails.get(k, set()) | {m["email"] for m in members if m.get("email")})
        # glimpse guests (tier=glimpse / link=False) have no standalone deck — DESIGN.md's send rule
        # moves the generosity into the email: one great photo of them inline + a direct download link.
        deck_members = [m for m in members if m.get("link", True)]
        glimpse_members = [m for m in members if not m.get("link", True)]
        # One Link per Household: the Household Deck. No per-person list.
        hub = next((m.get("hub_url") for m in deck_members if m.get("hub_url")), "")
        hub_html = (f'<p style="margin:14px 0 10px"><a href="{abs_url(base, hub)}" '
                    f'style="color:#b8862b;font-weight:bold">Open your Wrapped &rarr;</a></p>' if hub else "")
        glimpse_html = "".join(
            f'<p style="margin:14px 0 6px"><b>{m["first"]}</b> — one of our favorites of you:</p>'
            f'<p style="margin:0"><a href="{photo_url(base, m["hero"])}" style="color:#b8862b">'
            f'<img src="{photo_url(base, m["hero"])}" alt="Photo of {m["first"]}" '
            f'style="max-width:100%;border-radius:12px;display:block"></a></p>'
            f'<p style="margin:6px 0"><a href="{photo_url(base, m["hero"])}" download style="color:#b8862b">Download this photo</a></p>'
            for m in glimpse_members)
        links_text = (f'Your Wrapped: {abs_url(base, hub)}' if hub else "")
        links_text += ("\n" if links_text and glimpse_members else "") + "\n".join(
            f'{m["first"]} (photo): {photo_url(base, m["hero"])}' for m in glimpse_members)
        greeting = hh_names.get(k) or " & ".join(m["first"] for m in members[:3])
        recap = ("<p>Thank you for celebrating with us in April — it meant the world. We went through every "
                 "photo and put together the photos of your family from the weekend:</p>" + hub_html) if deck_members else \
                ("<p>Thank you for celebrating with us in April — it meant the world. We went through every "
                 "photo from the weekend and pulled our favorites of you:</p>")
        html = f"""<div style="font-family:Georgia,serif;max-width:520px">
<p>Dear {greeting},</p>
{recap}
{glimpse_html}
<p>{"This link is yours; feel free to share it with family." if deck_members else "These are yours to keep."}</p>
<p>All photos &amp; hi-res downloads: <a href="__PHOTOG_URL__" style="color:#b8862b">the full gallery</a>.</p>
<p>With love,<br>Preethi &amp; Neel</p></div>"""
        row = dict(household=k, greeting=greeting, to="; ".join(to), n_members=len(members),
                   hub_url=abs_url(base, hub),
                   login_url=login_target(base, hub, deck_members),
                   n_glimpse=len(glimpse_members),
                   members=", ".join(m["first"] for m in members),
                   subject=subject,
                   text_body=f"Dear {greeting},\n\nWe put together the photos of your family from the weekend:\n{links_text}\n\nWith love,\nPreethi & Neel",
                   html_body=html)
        if to: emails.append(row)
        else: no_email.append(dict(row, phones="; ".join(sorted(hh_phones.get(k, set())))))

    return emails, no_email


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=""); ap.add_argument("--subject", default="Your Wedding Wrapped is ready 💛")
    ap.add_argument("--guests", default="~/Downloads/guest-list.csv")
    ap.add_argument("--everyone-email", default="",
                    help="test address whose Login email opens the everyone Hub (every Deck); '' to disable")
    a = ap.parse_args()
    manifest = json.loads((D / "send_manifest.json").read_text())
    base = a.base_url.rstrip("/")
    rows = list(csv.DictReader(open(os.path.expanduser(a.guests))))
    emails, no_email = household_rows(manifest, rows, base, a.subject)
    with open(D / "emails.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(emails[0].keys())); w.writeheader(); w.writerows(emails)
    (D / "emails.json").write_text(json.dumps(emails, indent=1, ensure_ascii=False))
    if no_email:
        with open(D / "no_email_households.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(no_email[0].keys())); w.writeheader(); w.writerows(no_email)
    # Login's email -> Link lookup, bundled into the Pages Function (never served; it is PII).
    ev = D / "everyone_hub.json"
    extra = ({a.everyone_email: {"url": abs_url(base, json.loads(ev.read_text())["url"]), "greeting": "Everyone"}}
             if a.everyone_email and ev.exists() else {})
    login = build_login_map(emails, extra=extra)
    lm = Path(__file__).parent / "functions" / "_lib" / "login-map.json"
    lm.parent.mkdir(parents=True, exist_ok=True)
    lm.write_text(json.dumps(login, indent=1, ensure_ascii=False))
    print(f"{len(login)} Login addresses → {lm.relative_to(Path(__file__).parent)}")
    print(f"{len(emails)} household emails → data/emails.csv | {len(no_email)} households need phone/text → data/no_email_households.csv")
    print(f"covering {sum(e['n_members'] for e in emails)} guests by email + {sum(n['n_members'] for n in no_email)} by phone")

if __name__ == "__main__":
    main()
