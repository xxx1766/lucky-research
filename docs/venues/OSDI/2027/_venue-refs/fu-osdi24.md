# ServerlessLLM: Low-Latency Serverless Inference for Large Language Models (OSDI '24)

**Authors**: Yao Fu, Leyang Xue, Yeqi Huang, Andrei-Octavian Brabete, Dmitrii Ustiugov, Yuvraj Patel, Luo Mai (University of Edinburgh + Microsoft Research).
**Topic**: Distributed system for low-latency serverless inference of LLMs; combines rapid multi-tier checkpoint loading, live migration, and locality-aware scheduling.
**Source**: [USENIX page](https://www.usenix.org/conference/osdi24/presentation/fu) · [arXiv 2401.14351](https://arxiv.org/abs/2401.14351) · cited in this paper as `\cite{serverlessllm-osdi24}`.

## Section structure observed

1. Introduction
2. Background and Motivation
3. ServerlessLLM Design (three subsections, one per contribution: loading-optimized checkpoint format, live migration, locality-aware scheduling)
4. Implementation
5. Evaluation
6. Discussion
7. Related Work
8. Conclusion

## Voice + style

- Opens with the cost gap: "Serving LLMs serverlessly is desirable for elasticity but the cold-start dominates" pattern.
- Three named mechanisms presented in parallel (loading format, migration, scheduling). Each gets one subsection.
- Numbers in the abstract: "reduces latency by 10-200X". Range, not single number, because the gap depends on the workload mix.
- Lead with the system name infrequently. Most paragraphs lead with the mechanism or measurement.

## Figure / table use

- Roughly 10-12 figures, 2-3 tables.
- Figures include CDFs (latency distribution), tables (configuration matrices, evaluation setup), and one architecture diagram.

## Citation density / style

- USENIX numeric style. Roughly 60+ refs.
- Comparative naming: "vs Ray Serve", "vs KServe", "vs prior X" appears in evaluation prose alongside the numeric markers.

## What we'd borrow for Weightlet

1. **Three named mechanisms structure**: ServerlessLLM presents (loading format, migration, scheduling) as three parallel design sections. Weightlet's design has three parts too (split-spec, weight-unit-aware Score, deploy-time assembly). Mirror the structure.
2. **Range-of-improvement headline**: "10-200X across workloads" frames the result honestly (workload-dependent). Weightlet's fleet-decay finding is similarly workload-dependent. Borrow the "range" framing for §1 once §5 numbers stabilise.
3. **Comparative naming in §5 prose**: name the baseline systems (vLLM, Dragonfly, Nydus, ServerlessLLM) directly in the evaluation text, not only via cite markers. Easier for reviewers to skim.
4. **§6 Discussion** before §7 Related Work: this ordering pre-empts limitation questions before walking through prior work. Consider for Weightlet.
