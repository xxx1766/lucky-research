# Decouple and Decompose: Scaling Resource Allocation with DeDe (OSDI '25)

**Authors**: Zhiying Xu, Minlan Yu, Francis Y. Yan (Harvard, UIUC).
**Topic**: Scalable optimization framework for large-scale resource allocation; decomposes the global problem into per-resource and per-demand subproblems via ADMM.
**Source**: [USENIX page](https://www.usenix.org/conference/osdi25/presentation/xu) · [arXiv 2412.11447](https://arxiv.org/abs/2412.11447) · [GitHub illinois-nsai/dede](https://github.com/illinois-nsai/dede)

## Section structure observed

1. Introduction
2. Real-World Resource Allocation Problems
3. DeDe: Decouple and Decompose
4. Generality and Limitations
5. Case Studies
6. Implementation of DeDe
7. Evaluation
8. Related Work
9. Conclusion
Appendix A. Cluster scheduling evaluation setup

## Voice + style

- Opens with the problem ("Resource allocation remains a critical and challenging problem today, especially as cloud providers operate multi-tenant systems on an unprecedented scale"). Anchors the work in the cloud-multi-tenancy context before introducing the technique.
- Uses worked examples (job scheduling on GPUs, small throughput numbers) before formal definitions. Pedagogical rather than dense.
- Comparative positioning: consistently names the prior baselines (POP, exact solvers) when introducing each claim.
- Theory-grounded framing: cites ADMM and Lagrange multipliers to establish credibility.
- "Generality" gets its own section (§4). Explicit about scope.

## Figure / table use

- About **8 figures** and **1 main table** (Table 1 cataloguing prior resource-allocation problems). Much lighter than BlitzScale.
- The table is a *taxonomy* table positioning prior work, useful as a §6 Related-Work device.
- Figures 4-8 are experimental result plots; Figures 1-3 are conceptual.

## Citation density / style

- USENIX numeric style.
- Citations placed after the concept they support, common in theory-leaning systems papers.
- Heavy comparison with named prior systems (POP, Pop, Gemel) by name, not just by [n].

## What we'd borrow for Weightlet

1. **§4 "Generality and Limitations"** as a separate section: pre-empts reviewer "what about cases X / Y" questions. Worth considering for Weightlet's §7 (Discussion).
2. **Worked example before formalism**: a small concrete case before introducing the split-spec format will help reviewers. Apply to Weightlet §3.
3. **Taxonomy table in Related Work**: Table 1 of DeDe lists prior systems against a fixed axis. Mirrors outline.md's "Tbl 3 — citation taxonomy (3-axis)".
4. **"Real-world problems" §2**: leads with concrete instances (cluster scheduling, traffic engineering, load balancing) before formalising. Mirrors Weightlet §2's measurement-first structure.
