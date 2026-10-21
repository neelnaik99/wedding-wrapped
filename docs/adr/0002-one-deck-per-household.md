# One Deck per Household, viewed through a Selection

Supersedes the per-person Deck + Hub shape that ADR 0001's Login points at. Each Household gets
one Deck at its Link (`/h/<token>/`); the reader picks any non-empty Selection of members and the
page shows photos with any selected member, photos with more of them first. Per-person Links are
no longer sent anywhere. We chose this because families open these together — one link, one page —
and because measured overlap is real but partial (median 51% of a person's photos include a family
member; only 25% of curated picks are shared), so the Selection keeps each person's solo photos
reachable without making the family open separate pages.

The governing rule: **every photo shown includes at least one member of the viewer's Household.**
The only exemption is a photo of Preethi and Neel alone. The build fails if any page breaks it.

## Considered Options

- **Hub + per-person Decks (status quo):** rejected — a family must pick a person and open several pages to see everything.
- **One merged page, no per-person view:** rejected — half of each person's photos are solo and would be buried.
- **Re-curate every member combination:** rejected — 2ⁿ−1 combinations; a Selection's highlights are the selected members' existing picks merged instead.

## Consequences

- Light guests (marked in the admin app) are ordinary selectable members inside a family; alone, they get a highlights page of the couple's photos plus their own.
- "Our picks" now passes the rule only through the couple exemption, so any couple shot that also shows a non-household guest is dropped.
- About 170 existing Group-map / All-photos references that show no household member are removed by the build check.
