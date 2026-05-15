# Fork in the Road: Reflections and Optimizations for Cold Start Latency in Production Serverless Systems (OSDI '25)

**Authors**: Xiaohu Chai, Tianyu Zhou, Keyang Hu, Jianfeng Tan, Tiwei Bie, Anqi Shen, Dawei Shen, Qi Xing, Shun Song, Tongkai Yang, Le Gao, Feng Yu, Zhengyu He, Dong Du, Yubin Xia, Kang Chen, Yu Chen (Alibaba Cloud + Tsinghua + SJTU).
**Topic**: In-depth measurement and optimisation of cold-start latency in Alibaba's production serverless platform, including a forked process management redesign.
**Source**: [USENIX page](https://www.usenix.org/conference/osdi25/presentation/chai-xiaohu) · [USENIX PDF](https://www.usenix.org/system/files/osdi25-chai-xiaohu.pdf) (no arXiv mirror found; USENIX PDF returned 403 to automated fetch, so structural details below are inferred from the abstract, public talk summaries, and Alibaba's typical OSDI paper conventions).

## Section structure observed (inferred from abstract + conference summary)

1. Introduction (cold-start in serverless, scale of production)
2. Background and characterization of cold-start at Alibaba scale
3. Optimisation: process forking + relevant runtime redesign
4. Implementation in production
5. Evaluation on real production traces
6. Related work
7. Conclusion

Production papers from Alibaba (Nydus, Dragonfly, RAFS) typically follow this shape: very strong characterization section (lots of measurement plots from real traffic), system mechanism in §3-§4, evaluation on either A/B-tested production or replay-from-trace data.

## Voice + style (inferred)

- Production-paper voice. Leads with measurement, not theory.
- Heavy use of "the production system", "we deployed", "in our production cluster" framing.
- Latency numbers (ms, seconds) carry most claims.
- Likely fewer rhetorical flourishes; measurement-table-heavy.

## Figure / table use (inferred)

- Production papers from Alibaba typically run heavier: 10+ figures, 3+ tables.
- Heavy CDF and histogram use for latency distributions.
- A/B comparison tables comparing pre/post-deployment metrics.

## Citation density / style

- USENIX numeric style.
- Will cite prior serverless cold-start work (Slacker, Faasm, Pheromone, Catalyzer, FAST '24 cold-start papers).

## What we'd borrow for Weightlet

1. **Measurement-first §2**: the Alibaba style of characterising the problem with real-trace plots before introducing the mechanism. Weightlet's §2 already does this; reinforces the direction.
2. **Production framing**: language like "in the production system" or "at deployed scale" lends credibility. Weightlet's §1 references HuggingFace's public hub as the production-flavour anchor.
3. **Headline number with deployment context**: if our paper can report a number from a real cluster (not just simulation), the "production-validated" angle becomes much sharper.
4. **Caveat on author count**: 18 co-authors signals a large industry+academia team. Weightlet has fewer authors; do not over-mirror the production-team voice.
