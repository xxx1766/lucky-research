# Verify workflow detail (`/paper verify [section]`)

> **Source:** Adapted from the *academic-reviser* discipline in
> [joshua-zyy/academic-paper-writer](https://github.com/joshua-zyy/academic-paper-writer)
> (no explicit LICENSE; public sharing intended). The three-pass ordering and
> the debt-ledger verdict are reproduced in spirit, re-expressed for this
> plugin's LaTeX-native, experiment-bound flow.

`/paper verify` is the **source-level evidence-closure** check. It is distinct
from `/paper review` (Stage 8.6), which simulates a reviewer reading the
rendered PDF. Verify reads the `.tex` source plus the bound experiment outputs
and produces a typed `VerificationReport` with a **debt ledger** and a
**claim → evidence map**.

Load this file when running `/paper verify`. The high-level trigger lives in
`SKILL.md` Stage 8.7.

## The iron rule: three passes, in order, no skipping

```
Pass 1  Evidence    → Pass 2  Argument    → Pass 3  Style
(facts first)         (reasoning next)      (prose last)
```

**You may not polish prose before the facts are checked.** If Pass 1 opens a
hard debt, you still run Pass 2 (it may open more debts), but Pass 3 is
*reporting only* until the hard debts close in a later round — never spend a
round making unsupported prose read better.

## Debt classes (shared vocabulary)

| class | pass | hard? | open when |
|---|---|---|---|
| `citation` | 1 | hard | a `\cite{}` doesn't resolve to `refs.bib`, or a claim that needs a cite has `[REF_NEEDED]` |
| `evidence` | 1 | hard | a reported number/result has no backing experiment version (or is a `[DATA_NEEDED]`) |
| `consistency` | 2 | hard | intro/abstract promises a contribution the results don't deliver; table numbers ≠ prose numbers; method ≠ what was run |
| `prose` | 3 | hard | structure/clarity defects that block comprehension (not mere style taste) |
| `figure` | 1 | **soft** | a referenced figure isn't rendered (`[FIGURE_NEEDED]` / missing `figures/<slug>.pdf`) — a pre-publication debt, does not block `passed` |

`citation` / `evidence` / `figure` are also computed *live* by
`papers.debt_summary` from the source; in the ledger you confirm their
open/closed status. `consistency` / `prose` exist only here.

## Pass 1 — Evidence (fact-check)

Walk the section line by line against this checklist. For each claim, add a row
to the **claim → evidence map** (`ClaimEvidence(claim, evidence, verified)`):

1. Every quantitative claim (number, %, "X× faster", "SOTA") maps to a concrete
   source: `exp:<slug>@<vN.M>` (a registered experiment version) or a cited
   prior result `cite:<slug>`. No source → `evidence` open + leave `[DATA_NEEDED]`.
2. Numbers in prose match the numbers in the bound experiment's
   `analysis_tex` / mirrored `results/` files. A mismatch → `evidence` open.
3. Every `\cite{slug}` resolves to a `refs.bib` entry
   (`refs.unresolved_cite_keys` returns `[]`). Any remainder → `citation` open.
4. No naked claims: every assertion is either cited, experiment-backed, or
   explicitly hedged ("we hypothesize"). A naked claim → record it with
   `verified=False, evidence=""` (it shows as `✗ NAKED`).
5. No fabricated specifics: dataset sizes, hyperparameters, hardware,
   wall-clock — each traces to `design.md` / a version snapshot or becomes
   `[DATA_NEEDED]`.
6. Code ↔ method consistency: the method described matches what the bound repo
   at the recorded SHA actually does (spot-check, not a full audit).

Set `citation` / `evidence` / `figure` debt status from this pass.

## Pass 2 — Argument (peer-review risk)

Read the section as a skeptical reviewer. Open `consistency` debt if any of
these fail; capture the reason in the debt note:

1. Does the intro/abstract promise exactly what the results deliver — no more?
2. Is every contribution claimed in the intro actually validated somewhere?
3. Are baselines fair (same data, aligned versions, tuned comparably)?
4. Do ablations cover the key design decisions, or is a load-bearing choice
   unjustified?
5. Is there a confound or alternative explanation the section doesn't address?
6. Are limitations stated honestly, or buried/omitted?
7. Does any sentence overclaim relative to its evidence (see the
   claim-strength audit below)?

### Claim-strength audit (adapted from APW's *academic-polishing*)

Run `research_assistant.papers.scan_strength_words(direction_dir)` — a
deterministic scan that flags high-risk strength words. A flag is **not**
automatically a debt; for each hit, check whether the *required evidence* is
present. If it is (e.g. "significantly (p<0.01)"), leave it. If not, it is an
overclaim → open `consistency` debt and recommend the downgrade.

| word | requires | downgrade if absent |
|---|---|---|
| significant(ly) | a significance test (p<0.05) or effect size | state the concrete numerical difference |
| robust / robustness | multiple seeds / cross-val / external test set | "consistent within the observed setting" |
| demonstrate(s) | a fully reproduced result, no protocol gaps | "suggests" / "aligns with" |
| generalize / generalization | an independent or multi-dataset test set | restrict to the evaluated dataset |
| state-of-the-art / SOTA | full baseline comparison on an independent test set | "within the compared scope" |
| prove(s) | a formal proof or exhaustive evidence | "show" / "provide evidence that" |

**Evidence-strength tiers** (match verb to evidence, never above it):
- **Strong** — local reproduction, no protocol gaps → "show", "demonstrate".
- **Medium** — internal validation only → "suggest", "indicate".
- **Weak** — user claim, unverifiable → "may", "could", or `[CLAIM_UNVERIFIED]`.

This pass does **not** rewrite — it judges. Defects become `consistency`
debt + notes the user (or a later `/paper write` round) must resolve. The
mechanical downgrades themselves are a job for `/paper humanize`, not verify.

## Pass 3 — Style (only after 1 & 2)

Only now look at prose. Open `prose` debt for *comprehension-blocking* defects
(undefined terms, broken logical flow, an unreadable paragraph) — **not** for
taste (that's `/paper humanize`'s job). Most sections should close Pass 3 with
`prose` = closed. The rule from APW: *"don't mask content gaps with polished
language"* — a long, fluent draft is not evidence of a sound one.

## Verdict + iteration cap (computed, not judged)

After the three passes, build the `VerificationReport`
(`section`, `date`, `round`, `score` 1–10, `debts`, `claims`, `notes`) and call
`papers.write_verification_report(direction_dir, report)`. It runs
`finalize_verdict` for you — the verdict is derived from the ledger, not your
opinion:

- **passed** — no open *hard* debt (`citation`/`evidence`/`consistency`/`prose`).
  A `figure` debt may remain (soft, pre-publication).
- **failed** — an open hard debt and `round < 3`. The user fixes (`/cite`,
  `/experiment`, `/paper write <section>`) and re-runs `/paper verify <section>`
  — increment `round`.
- **blocked** — an open hard debt at `round == 3` → `unresolvable=True`. Stop
  looping; surface the frozen debts to the user. Don't retry automatically.

Score rubric (store the model's judgment): 9–10 all debts closed + rich;
7–8 hard debts closed, soft remain; 5–6 a hard debt open but fixable; ≤4
structural problems.

## After writing the report

1. Print the verdict line + score + the open-debt list to the user.
2. If there are naked claims, print them (`papers.naked_claims(direction_dir)`)
   — these are the most dangerous gaps.
3. Print the footer with the debt roll-up:
   `render_progress_footer(venue, direction, stage_status(direction_dir), debt_summary(direction_dir))`.
   `consistency` / `prose` from this report now show up in the board's `debts:`
   line alongside the live citation/figure/evidence counts.
