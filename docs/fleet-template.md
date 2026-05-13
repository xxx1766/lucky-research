---
as_of: <YYYY-MM-DD>
machines:
  - hostname: gpu-box-3
    gpus:
      - name: NVIDIA A100-SXM4-80GB
        count: 4
        driver: "545.23.06"
    cpu_cores: 64
    ram_gb: 1024
    disk_gb: 4000
    network: "200 GbE"
    available: true                 # flip to false to mark temporarily out-of-pool
    notes: "Shared with X's group; mornings UTC-best."
  - hostname: lab-a100
    gpus:
      - name: NVIDIA A100-PCIE-40GB
        count: 2
    ram_gb: 512
    available: true
    notes: "Exclusive Tue/Thu only."
---

# Fleet — as of {{as_of}}

<!--
This file is the user-curated machine inventory consumed by `/experiment feasibility`.

`/experiment feasibility` merges this with hosts auto-derived from past
`outputs/experiments/*/versions/*.md` frontmatter. When it asks you about a new
machine during a check, your answer is persisted right back here.

Conventions:
- `hostname` should match what your shell `hostname` command returns (or the
  string you've been recording in version frontmatter). Inferred hosts from
  past versions are matched by hostname.
- `gpus[].count` aggregates identical GPUs on the same host. List different
  models as separate entries.
- `available: false` hides the machine from feasibility checks without losing
  the record (handy for vacations / hardware faults).
-->

## Usage notes

<freeform — access tokens, who-to-ask-for-what, shared-quota schedules>
