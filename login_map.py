"""
Login map: every Household email -> the one Link its Login email should carry.

Built from make_emails.py's rows — the same grouping the Send uses — so a Household's Login
email and its Send email can never point at different pages. Written into functions/_lib/,
where the Pages Function bundles it at deploy time; it is never a public file (it is PII).
See docs/adr/0001-login-mails-existing-links.md.
"""


def normalise(email):
    """The single form both this map and the Login lookup use for an address."""
    return email.strip().lower()


def login_target(base, hub, deck_members):
    """The one Link a Household's Login email carries: its Household Deck URL (the manifest's
    hub_url, set for every member including one-person Households), nothing when the Household
    has no Deck or no URL. Always absolute — an email can't use a site-relative href."""
    if not hub or not deck_members:
        return ""
    return hub if hub.startswith(("http://", "https://")) else base.rstrip("/") + "/" + hub.lstrip("/")


def build_login_map(rows, extra=None):
    """Send rows -> {email: {"url", "greeting"}}. Rows with no login_url (no Deck) are skipped.
    `extra` adds non-guest addresses (the test address -> everyone Hub); it may not shadow a guest."""
    out = {}
    for r in rows:
        if not r.get("login_url"):
            continue
        for addr in (a for a in r["to"].split(";") if a.strip()):
            key = normalise(addr)
            if key in out and out[key]["url"] != r["login_url"]:
                raise ValueError(f"{key} belongs to two Households")
            out[key] = {"url": r["login_url"], "greeting": r["greeting"]}
    for addr, entry in (extra or {}).items():
        key = normalise(addr)
        if key in out:
            raise ValueError(f"{key} is a guest address; it can't also be an extra Login entry")
        out[key] = entry
    return out
