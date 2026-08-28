# Gate workflow — 五关逐步流程

本文件是 `SKILL.md` 中五个关卡的完整步骤。SKILL 里写的是判据，这里写的是操作。

## 通用循环（每一关都一样）

1. **读 ledger** — AgentDB `ideas/<slug>/gates`；缺失时按 `gates.md` 重建，
   再缺就 `GateLedger(slug=<slug>)` 起一个空的。
2. **can_enter 检查** — `ok, blocker = gates.can_enter(ledger, gate)`。
   `ok=False` 时**立刻停下**，输出：
   ```
   ❌ 卡在 `<blocker>`（<GATE_LABELS[blocker]>）。
   那一关缺的是：<该关最近一次 GateRecord.reason 或 "还没评估">
   补法：<该关的 next_action，或对应 service 的建议>
   ```
   不要顺手把后面的关卡内容也讲一遍 —— 那等于绕过门禁。
3. **问那一关的核心问题** — 用 `gates.GATE_QUESTIONS[gate]` 原话问，纯文本，
   一次一个。用户答完若信息不足，再追问一次（**同一关最多 3 轮**，超过就判
   ⚠️ 存疑并给出取证行动）。
4. **需要事实支撑就先跑 service** — 见每关的"取证"小节。不要凭记忆断言。
5. **判定** — 构造 `GateRecord`，`verdict` 三选一：
   - `pass` — 判据满足，有具体证据。
   - `doubt` — 方向对但证据只覆盖一个点/一个数据集，或解释还停在现象层。
   - `fail` — 判据明确不满足。
   `reason` 必填（校验器会拦空值）；`key_question` 写你打算问的下一个问题；
   `next_action` 写一条分钟级可做的事。
6. **落盘** — 见 SKILL 的"每关通过时的落盘块"六步。
7. **输出三段** — 状态 / 最关键的一个追问 / 下一步行动。

## `--force` 的处理

用户带 `--force`，或明确说"我知道风险，先过"：

1. 仍然按第 5 步做出**真实判定**（`verdict` 不要改成 `pass`）。
2. `GateRecord(..., forced=True)`。
3. `registry.update_idea(slug, status=gates.GATE_STATUS[gate],
   forced_gates=sorted(set(old + [gate])))`。
4. 输出里明确写一行：`⚠️ <gate> 是强制放行的 —— 后续实验若失败，先回到这一关。`

不要主动推荐 `--force`。用户问起时才说它存在。

## Gate 1 — failure-case

**问**：`现有方法到底在什么情况下真的会失效？给一个具体、可复现的场景或例子。`

追问梯度（每次只问一个）：
1. 哪个方法、哪个输入、失效表现是什么（数值/输出/行为）？
2. 这个失效能复现吗 —— 你见过一次，还是能稳定触发？
3. 除了这个方法，还有别的方法在同一处失效吗？

**取证**：`/idea-check scout` → `ScoutGaps.where_broken`。把命中条目按
`"<paper title> (<arXiv/URL>) — <他们在哪失效>"` 写进 `evidence`。

**判据**
- `pass` — 有具体可复现场景，且至少有一条外部证据（论文/自己的 run）表明**不止
  一个方法**在同一处失效。
- `doubt` — 场景具体但只在单一方法/单一数据集上出现（可能是 patch 级）。
- `fail` — 说不出具体场景，或说的是"还能继续提升"。

`fail` 时的 `next_action` 二选一：跑 scout 看别人在哪翻车；或去复现一个失败样例。

## Gate 2 — problem-standalone

**问**：`如果没有你这个方法，这个问题本身还值得研究吗？谁会关心？`

操作：
1. 你先把 idea 重写成一个**不含任何方法名词**的 problem statement，展示给用户。
2. 问用户：这句话是否依然成立、是否依然有人关心；哪里需要改。
3. 若用户的辩护里必须提到自己的方法才成立 → 这就是"先有 solution 再凑
   problem"的信号。

**取证**：`/idea-check contrarian`（主流默认是什么、反过来会怎样）、`scout` 的
`untried` 桶（问题重要却没人做，是没人想到还是做不动）。

**判据**
- `pass` — 去方法化的 problem statement 独立成立，且能说出具体受益者。
- `doubt` — 成立但受益范围窄（一个团队/一个内部系统）。
- `fail` — 去掉方法后问题消失，或受益者说不出来。

`fail` 的出路：`/idea-check brainstorm`（换角度提炼真问题）或从 contrarian 的
兄弟 idea 重新起跑，而不是把方法再包装一次。

## Gate 3 — mechanism

**问**：`原来的方法到底错在哪里？真正影响结果的因素是什么？(要机制，不要现象)`

追问梯度：
1. 为什么会失效 —— 是数据分布、优化目标、还是某个结构假设？
2. 如果换一个满足同样条件的方法，会不会一样失效？（能推广 = 机制）
3. 你的方法为什么能修 —— 修的是哪一步的什么量？

**取证**：`/idea-check assumptions`（见 `assumption-mining.md`）；`evaluate` 的
`technical_depth` / `theoretical_contribution` 两轴的理由行。

**判据**
- `pass` — 解释能让别人不看代码也预测出同样的失效。
- `doubt` — 有候选机制但缺一个能区分它与竞争解释的判别点。
- `fail` — 只有"加了这个模块就好了"这种现象描述。

通过后同步把机制写回 `socratic` 的 hypothesis tree（`H1` = 机制陈述），
`/experiment design` 会读 `to_experiment_hypothesis_seed(trace)`。

## Gate 4 — predictions

**问**：`如果这个解释成立：什么情况下问题会更严重？什么情况下根本不会发生？`

操作：
1. 让用户给出至少 2 条预测；你负责把每条整理成
   `Prediction(statement=..., kind="worse"|"absent"|"other", cheap_check=...)`。
2. 每条都要有 `cheap_check` —— 一次检索、一个小规模 run、一个已有 benchmark 的
   子集都算；"跑完整训练"不算。
3. `GateRecord(gate="predictions", verdict="pass", ...)` 在 usable 预测 < 2 时
   **会被校验器拒绝**。不要改成 `forced=True` 绕过，除非用户明确要求。

**判据**
- `pass` — ≥2 条带验证方式的预测，且至少有一条是"不会发生"方向（`absent`）：
  只会预测"更糟"的解释往往是同义反复。
- `doubt` — 有 2 条但都缺低成本验证方式。
- `fail` — 预测就是机制的换句话说。

## Gate 5 — minimal-experiment

**问**：`用什么最小实验、多久能验证上面的预测？(分钟级，不是两个月)`

操作：
1. 针对 Gate 4 的每条预测，写出最小验证：数据、方法、要看的量、预期方向。
2. 逐条纯文本问 pre-registration（一次一个）：
   - `用什么 proxy metric 衡量这个 idea？(应能在分钟级，不是小时级跑出来)`
   - `当前 baseline 数值是多少？来自哪里？(论文报告 / prior run / 业内默认)`
   - `多少改进算成功？(自由文本：'+10%' / '+0.5 BLEU' / '≥ 0.80' 都行)`
   - `有什么前提需要注意？(可选；e.g. "只在长上下文场景有意义")`
3. 存 `ev.pre_registration = PreRegistration(...)`，写 `evaluate.md`，AgentDB
   `ideas/<slug>/evaluation` = `ev.model_dump()`。

**判据**
- `pass` — 最小实验能在小时级内给出"预测成立/不成立"的二元答案，且
  pre-registration 四项齐全（notes 可空）。
- `doubt` — 实验设计合理但成本仍是天级。
- `fail` — 唯一的验证方式是大规模训练/完整 benchmark。

通过后提示：`/experiment init` 落地实验，或 `/idea-check handoff` 进 `/paper`。
提醒一句：**先跑最小实验验证预测，再扩大规模。**
