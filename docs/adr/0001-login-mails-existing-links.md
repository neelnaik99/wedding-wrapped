# Login mails the existing Link; it is not authentication

The Card sends guests to a Login page where they type their email. We look the email up and mail that Household's existing Hub or Deck Link (via Resend), instead of building real auth with sessions and gated pages. Links stay bearer capabilities exactly as before, so nothing already sent breaks, no page needs a gate, and the flow ships in a weekend; real accounts stay on the roadmap (ROADMAP "Auth = email magic links") for when hearts and comments need identity.

## Considered Options

- **Session auth (magic link → cookie → gated pages)**: rejected for now. Puts a gate in front of 133 static pages and converts every Link into a non-capability for no gain at this scale.
- **Per-household QR code on the Card**: rejected. It needs a custom print per Card; the Card must be identical for every Household.
- **SMS fallback for guests with no email**: rejected. 6 Households; collected by hand instead (#50).

## Consequences

- Login always answers the same way whether or not the email is known, so it doesn't reveal who is on the guest list.
- The email→Link map ships inside the server function, never as a public file.
- Anyone who gets a forwarded Link can still open it, same as today.
