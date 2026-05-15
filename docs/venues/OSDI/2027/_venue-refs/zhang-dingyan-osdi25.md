# BlitzScale: Fast and Live Large Model Autoscaling with O(1) Host Caching (OSDI '25)

**Authors**: Dingyan Zhang, Haotian Wang, Yang Liu, Xingda Wei, Yizhou Shan, Rong Chen, Haibo Chen (SJTU IPADS).
**Topic**: Model autoscaling for serverless model-as-a-service; loads parameters through GPU compute network instead of host cache.
**Source**: [USENIX page](https://www.usenix.org/conference/osdi25/presentation/zhang-dingyan) · [arXiv 2412.17246](https://arxiv.org/abs/2412.17246) · [GitHub](https://github.com/SJTU-IPADS/BlitzScale)

## Section structure observed

1. Introduction
2. Background: MaaS and Autoscaling
   2.1 System setup
   2.2 Dynamic hardware demands
   2.3 Model autoscaling
3. Characterizing Scaling Requirements and Compute Network
4. System Overview of BlitzScale
5. Detailed Design and Implementation
   5.1 Online network-based scale plan generation
   5.2 Efficient live autoscaling with ZigZag scheduling
   5.3 Global parameter pool and scaling policy
   5.4 Specializations for LLM
6. Evaluation
   6.1 Autoscaling performance under real-world traces
   6.2 Performance and resource usage
   6.3 Detailed performance analysis
   6.4 Performance under LLM PD colocation
7. Related Work
8. Conclusion and Future Work
9. Appendix

## Voice + style

- Heavy first-person "we": "we show", "we design", "we built". Section openings frequently lead with "we".
- **Uses em-dashes liberally** for parentheticals and clarifications.
- Mixed sentence length: short technical claims interleaved with multi-clause constructions.
- Numbers-heavy: 94% tail-latency reduction, 49% GPU time saving, 500 ms scaling-time target, 7.4% bandwidth-utilisation baseline.
- Three-axis framing in §3 (Characterization): builds the wedge before §4 overview.

## Figure / table use

- About **26 figures**, **1 main table** (plus appendix tables). Very figure-heavy.
- Figures are mostly data plots (line charts, bar charts, scaling curves) and small architecture diagrams.
- Uses booktabs (\toprule / \midrule / \bottomrule) for the main table.

## Citation density / style

- USENIX numeric style: `[n]` markers.
- Citations sit after the introduced concept, not as nouns: "ServerlessLLM~\cite{...}" not "as shown in [12]".
- Roughly 60-80 references for a ~12-page body.

## What we'd borrow for Weightlet

1. **Numbers in the abstract and §1**: BlitzScale leads with the 94% number; we should land our headline gap (3.77×) in §1 once §5 results stabilize.
2. **§3 as a "characterization" beat**: a section that establishes the wedge with measurement before the system overview. We already do this in §2; consider whether §1 needs a parallel one-paragraph version.
3. **Subsection naming as mechanism statements**: "5.1 Online network-based scale plan generation" reads as a description of *what the section delivers*, not a label. Apply to §3 of Weightlet (Design).
4. **Caveat**: BlitzScale's em-dash use is heavier than Weightlet's chosen style. Do not borrow.
