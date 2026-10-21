# Findings — what the data taught us (2026-08)

- **Cluster purity is high on Indian-wedding photos**; failure mode is fragmentation
  (haldi paste, profiles, sunglasses), not mis-merges. Fix = merge tooling, not thresholds.
  The groom was split across 4 clusters; the priest formed a clean 185-photo cluster.
- **Quality is not comparable across people.** Global cutoffs starve dimly-lit or
  rarely-shot guests; per-person bars (min(45th pct, keep-best-50)) made every deck's
  "best" genuinely theirs. Bars range 0.5–85 across 347 people.
- **Raw quality scores carry daylight bias** (Haldi outdoor photos dominate) → rank
  within person + bucket quotas, never one global sort.
- **Prominence beats presence.** ~29% of face appearances are background; role
  (focus/group/background) filtering is what makes decks feel curated.
- **Perceptual hash fails for scene grouping** on pro photography (every reframe hashes
  differently). Time gap ≤120s + who's-in-frame Jaccard ≥0.34 works.
- **Relationship structure is recoverable from co-occurrence alone.** Hub-resistant
  affinity min(shared/|A|, shared/|B|) neutralizes the couple; mutual-best pairs find
  married couples (validated: the groom's parents ranked #1); Louvain at res 1.3 finds
  friend circles and family sides. Tags from tightness × event-profile (party vs ceremony)
  read correctly ("friend group — tight, party-heavy").
- **The couple co-occurs with everyone** — exclude them from all group math; include them
  as implicit members of every group.
- **Static + bearer tokens covered every guest-facing feature** requested so far, including
  group-scoped lookup and per-viewer photo pools — because every audience is known at
  build time. First true backend trigger: guest writes (hearts server-side, comments).
