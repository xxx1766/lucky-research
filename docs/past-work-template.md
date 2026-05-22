---
slug: <kebab-case-slug>
title: "<Project / paper title>"
year: <YYYY>
venue: "<NeurIPS | EMNLP | journal | internal | blog>"
status: "<published | unpublished | abandoned | in-progress>"
tags: [<tag1>, <tag2>]
links:
  - "arxiv:<id>"
  - "github:<user>/<repo>"
# Optional GitHub repo binding. Populate via `/past-work bind <slug> <url>`,
# clone via `/past-work clone <slug>`. Leave the whole block out for prose-only
# entries (e.g. abandoned ideas, external projects without code).
#
# repo:
#   url: "git@github.com:user/repo.git"
#   branch: "main"
#   last_known_sha: null
#   clone_status: "tracked"       # tracked | cloned | missing
#   cloned_at: null
---

# {{title}}

## Abstract

<one-paragraph summary of what the project was about>

## What I learned

- <one-line lesson 1>
- <one-line lesson 2>

## Methods used

<datasets, models, tools, training recipe>

## Outcome / impact

<published? cited? abandoned and why? blocked X downstream?>

## Notes for future-me

- <if I revisit, start from commit abc1234>
- <the dataset lives at /shared/...>
- <if a repo is bound, the clone lives at `inputs/past-work/<slug>/repo/`>
