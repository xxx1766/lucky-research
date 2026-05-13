---
version: "v<major>.<minor>"
description: "<one-line label for this attempt>"
kind: minor                        # major | minor (informational)
status: completed                  # planned | running | completed | failed | abandoned
commit_sha: null                   # bound-repo HEAD at run time (40-char)
config_snapshot: null              # path inside experiment folder
result_file: null                  # path inside the bound repo
mirrored_to: null                  # path inside this experiment folder
started_at: null
finished_at: null
host: null
gpu: []
cuda: null
python: null
libraries: {}
libraries_lockfile: null           # configs/v<N.M>.requirements.txt
seeds: []
metrics: {}
artifacts: []
notes: ""
---

# v<major>.<minor> — {{description}}

## Setup

<exact commands / deviations from the config snapshot>

## Observations

<what worked, what surprised — the kind of thing future-you needs to remember>

## Diff vs prior version

<for v1.1+ — what changed, why; cross-link the prior version's slug>
