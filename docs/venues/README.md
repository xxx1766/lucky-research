# `docs/venues/` — shared venue-template library

A year-versioned collection of reusable per-venue assets so a new paper for
`<CONF> <YEAR>` doesn't start from blank. Tracked in git and shared across
the group.

## Layout

```
docs/venues/<CONF>/<YEAR>/
  _venue.md              # venue facts: deadlines, page limits, scoring rubric, recent trends
  _template/             # official LaTeX class / style / template files from the venue
  _venue-refs/           # distilled per-paper analyses of accepted papers at this venue
```

- `<CONF>` — uppercase, no spaces (`OSDI`, `NEURIPS`, `CVPR`, `ATC`, `VLDB`…).
- `<YEAR>` — 4-digit calendar year of the submission deadline (`2027`, `2028`…).
- Multiple years coexist per venue: each `<CONF>/<YEAR>/` is a self-contained
  snapshot. The newest year is the canonical starting point; older years stay
  for diffing trends across cycles.

## What each piece is for

### `_venue.md`

The user-curated facts file for a specific submission cycle: abstract /
full-paper / rebuttal / camera-ready deadlines, page limit, anonymization
rules, scoring rubric, recent-trend summary. `paper-architect`'s Stage 1
generates this from the CFP; once curated, it's worth promoting up to
`docs/venues/<CONF>/<YEAR>/` so the next cycle inherits the structure.

### `_template/`

Official LaTeX assets distributed by the venue — `.sty`, `.cls`, `.bst`,
sample `.tex`. These rarely change across years; even when they do, an
older copy is a useful starting point.

### `_venue-refs/`

Distilled per-paper analyses of accepted papers, produced by
`/paper venue refs distill` (Sub-stage 1b of `/paper venue`). Each
`<author>-<conf><yy>.md` file captures section structure, claim density,
citation style, voice, and any venue-specific writing conventions visible
from one published paper. Aggregated into the "## Writing conventions"
block of `_venue.md`. Year suffix on the filename refers to the paper's
publication year, **not** the year directory it lives in — a CVPR-2026
direction can still consult `_venue-refs/li-cvpr23.md` if it's a useful
reference style.

## How to use this library

### Starting a new paper at an already-cataloged venue

```bash
# Example: targeting OSDI 2028 with the 2027 snapshot as the seed
mkdir -p outputs/papers/OSDI-2028
cp -r docs/venues/OSDI/2027/* outputs/papers/OSDI-2028/
# Then edit _venue.md to refresh deadlines and the recent-trend block.
```

After the deadlines settle for the new cycle, promote the refreshed
`_venue.md` back up to `docs/venues/OSDI/2028/_venue.md` for the next
person to inherit.

### Starting a paper at a brand-new venue

1. Create `docs/venues/<NEW-CONF>/<YEAR>/`.
2. Drop the venue's official LaTeX template into `_template/`.
3. Generate `_venue.md` via `/paper venue` once and edit to taste.
4. Optionally run `/paper venue refs distill` to seed `_venue-refs/` from
   2–3 recent accepted papers.

The library grows organically as the group works on more venues.

## What does *not* belong here

- Specific paper-directions in progress — those live under
  `outputs/papers/<CONF>/<YEAR>/<direction>/` (gitignored, per-user).
- One-off CFP scrapes that won't be revisited — drop them in
  `inputs/papers/` or just paste into a paper-direction's `_venue.md`.
- Per-machine bibliography files (`refs.bib`) — those belong with the paper
  direction, not the venue template.

## Currently cataloged

| Venue | Years |
|---|---|
| `OSDI` | `2027` (seeded from `outputs/papers/OSDI-2027/`) |
