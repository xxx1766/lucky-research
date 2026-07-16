---
name: academic-story-packaging
description: Use when analyzing an engineering-heavy, incremental, systems, or applied research project and turning it into an evidence-grounded paper story, contribution structure, challenge framing, architecture narrative, experiment plan, introduction, or critical packaging review. Triggered by `/idea-check 2paper` on the active idea; output lands at outputs/idea-checks/<slug>/story.md and AgentDB ideas/<slug>/story.
---

# Academic Story Packaging

## 核心原则

把“包装”限定为发现真实价值、选择正确抽象、组织论证与证据。不得夸大贡献、虚构挑战、隐藏限制、制造不公平比较，或用新名称替代新知识。

始终按以下顺序工作：

`客观工作 → 可复现的失败模式 → 根因与约束 → insight → 机制 → 证据 → 结论边界`

不要先写宏大背景或强行凑贡献数量。

## 输入与输出约定

接受论文 PDF、论文草稿、项目说明、代码、实验结果或研究笔记。先判断任务属于哪一种：

- **分析现有论文**：还原工作本体、作者故事、证据强度与可能的过度表述。
- **组织待投稿工作**：从真实技术动作反推问题、机制、架构和实验。
- **审阅现有叙事**：检查问题—挑战—模块—实验—结论是否闭环。
- **跨论文归纳**：先逐篇建立证据账本，再总结稳定模式；每个共性结论至少由两个案例支持。

若用户未指定格式，输出“分析判断 + 可填写模板 + 证据缺口”。不要把模板当成已经成立的结论。

## 工作流

### 1. 建立事实与证据账本

完整检查输入材料后，记录：

| 声明 | 类型 | 证据位置 | 证据强度 | 限定条件 |
|---|---|---|---|---|
| 做了什么 | 客观事实 | 页码、章节、图表、代码或日志 | 强/中/弱 | 适用场景 |
| 为什么重要 | 作者论证或研究假设 | 引言、数据或引用 | 强/中/弱 | 依赖前提 |
| 为什么有效 | 因果解释 | 消融、诊断或对照 | 强/中/弱 | 替代解释 |
| 能推广到哪里 | 分析判断 | 跨场景实验或理论 | 强/中/弱 | 外推边界 |

引用 PDF 时优先标注物理页码，并在印刷页码不同的情况下明确说明。无法确认的元数据或事实写“未确认”或“证据不足”，不要猜测。

强制区分四类陈述：

1. **客观事实**：材料直接展示的实现、数据或现象。
2. **作者论证**：作者用证据连接事实与结论的方式。
3. **作者价值判断**：关于重要性、普遍性或优越性的主张。
4. **分析判断**：当前分析基于证据作出的评价与推断。

### 2. 写“去包装版摘要”

用工程师口吻回答：

- 改了什么系统、模块、算法、流程或数据结构？
- 最核心的技术动作是什么？
- 实现了哪些具体功能？
- 哪些是真正的新机制？
- 哪些是整合、优化、迁移、参数选择或流程改造？

控制在 150–250 字。避免使用“novel”“holistic”“fundamental”等价值词。若这一步写不清，暂停故事构造并补事实。

### 3. 从动作反推研究问题

依次执行：

1. 列出最朴素的技术动作。
2. 为每个动作找到它修复的可观察失败模式。
3. 将失败模式归入容量、粒度、耦合、状态、边界、异构性或反馈等更高层约束。
4. 寻找多个失败模式的共同根因。
5. 将共同根因定义为候选研究问题。
6. 检查问题是否独立于当前实现：换系统、负载或算法后是否仍可能存在？
7. 用 baseline 失败、真实数据、生产案例或受控实验证明问题确实存在。

若“研究问题”只能由当前实现的细节定义，就把它降级为工程问题，不要升格为领域性问题。

### 4. 提炼挑战，不强求三个

挑战数量由证据决定，通常取 2–4 个。只有在三个挑战彼此区分、共同覆盖问题、分别对应机制且可独立验证时，才采用“三个挑战”。

对每个挑战填写：

```text
挑战名称：
观察到的现象：
直接工程问题：
共同根因：
学术抽象：
表述层级：科学 / 系统 / 算法 / 工程 / 实验
解决机制：
验证实验：
普遍性：强 / 中 / 弱
可能的夸大：强 / 中 / 弱
结论边界：
```

允许以下转换，但必须证明中间推理：

| 直接问题 | 可接受的学术抽象 | 所需证据 |
|---|---|---|
| 性能不够 | 效率—精度或吞吐—延迟权衡 | 目标冲突曲线，而非单点结果 |
| 模块难连接 | 跨层协同或接口失配 | 两层独立优化确实导致全局失败 |
| 参数很多 | 复杂设计空间 | 参数交互、敏感性或搜索成本 |
| 场景不一致 | 异构性或泛化挑战 | 跨场景失败具有稳定规律 |
| 旧系统不支持 | 兼容性或可部署性约束 | 真实接口、成本或迁移限制 |
| corner case | 鲁棒性挑战 | 可分类、可复现且有实际影响 |
| 多条启发式规则 | 决策机制 | 统一状态、目标或不变量 |

命名不能完成抽象。必须给出“现象 → 根因 → 抽象 → 机制 → 实验”的完整链条。

### 5. 从实现形成学术架构

按以下层级提升，每升一级都补证据：

`实现清单 → 功能单元 → 机制 → 模块 → 架构 → 设计原则 → 一般性结论`

使用对应表检查：

| 实际实现 | 学术名称 | 对应挑战 | 中心不变量或接口 | 创新类型 | 证据 |
|---|---|---|---|---|---|

合理架构必须满足：

- 模块边界来自不同职责、状态或时间尺度，而非代码目录。
- 模块共同维护一个中心不变量、目标函数、状态表示或反馈回路。
- 每个关键模块至少对应一个独立实验问题。
- 去掉命名后仍能解释为什么这样分层。
- 通用性由接口、约束或可迁移原则支持，而不是只由图示支持。

若架构只是把若干技巧画进方框，称为“实现组织”，不要称为通用框架。

### 6. 还原或构造论证链

写出一条可逐项证伪的链：

`现实背景 → 重要问题 → 现有方法缺口 → 挑战 → 核心 insight → 总体架构 → 关键机制 → 实验问题 → 实验证据 → 贡献与边界`

逐项检查：

- 缺口是否由证据证明，而非只由措辞制造？
- insight 是否解释多个设计选择，而非改写方案名称？
- 每个挑战是否有机制响应？
- 每个机制是否有消融、诊断或对照验证？
- 结论是否超过实验覆盖范围？
- 是否存在明显的“先有方案、后构造问题”？若有，诚实标记并重写问题。

把最关键的逻辑跳跃标为“故事转折点”，并列出补强它所需的最低证据。

### 7. 让实验回答研究问题

不要按表格顺序总结实验。把实验分为：

- **存在性**：目标失败模式是否真实存在？
- **有效性**：整体方法是否改善目标指标？
- **机制性**：改善是否来自声称的 insight 或模块？
- **代价性**：资源、复杂度、兼容性和负面影响是否可接受？
- **泛化性**：结论能否跨场景、负载、模型、平台或时间成立？
- **边界性**：在什么条件下失效或不值得使用？

建立闭环矩阵：

| 研究缺口 | 挑战 | 设计目标 | 机制 | 核心实验 | 消融/诊断 | 结论边界 |
|---|---|---|---|---|---|---|

检查 baseline 是否同硬件、同预算、同调优强度、同输入和同指标。报告原始指标与派生指标；启发式代理指标不能替代用户价值或端到端结果。

### 8. 组织贡献与命名

先按真实类型分类，再写贡献：

- 新问题或新观察
- 新 insight
- 新算法或机制
- 新系统架构
- 新工程实现
- 新数据或基准
- 新实验发现
- 已有技术的新组合
- 已有技术的新场景迁移

分别评价技术新颖性、问题重要性、系统完整性、实证充分性、可推广知识和叙事强度。不要用高叙事强度替代技术新颖性。

命名遵循“对象 + 动作/约束 + 作用”，例如描述协调、隔离、反馈或自适应的真实机制。避免无证据使用 `universal`、`optimal`、`complete`、`fundamental`、`first`、`all`。

把“我们实现了 X”提升为“我们观察到 Y；据此设计 X；实验在条件 Z 下验证 Y”，前提是 Y 与 Z 均有证据。

### 9. 做反事实与诚实性审计

输出两版故事：

- **弱叙事版**：仅按实施顺序描述，指出为何显得零散或局部。
- **强叙事版**：按问题、根因、机制和证据组织，但不新增事实。

然后回答：强版本增加的是可迁移知识，还是只有措辞？

出现以下任一情况时，降低主张强度：

- 挑战只是模块的同义改写。
- 普通实现困难被描述为领域根本问题。
- 只有端到端增益，没有机制证据。
- 单场景结果被外推为普遍规律。
- baseline 比较预算不对称。
- 只展示成功案例，未报告成本或失败条件。
- 架构图中的模块没有独立职责或验证。
- insight 无法预测新现象或解释设计选择。

## 默认交付结构

根据材料规模选择深度，但保持以下顺序：

1. 执行摘要。
2. 材料与元数据。
3. 去包装版工作本体。
4. 正式学术故事及陈述类型区分。
5. 挑战分析。
6. 实现—机制—架构对应表。
7. 论证链与关键转折。
8. 实验叙事与证据强度。
9. 写作、标题、命名与图表作用。
10. 弱/强叙事反事实。
11. 贡献强度与过度表述风险。
12. 可执行的改写或补实验建议。
13. 证据索引。

分析多个材料时，先逐项分析，再横向归纳。仅出现一次的模式标记为“个案”，不要包装成稳定套路。

## 完成标准

提交前确认：

- 每个重要判断均能追溯到证据或明确标为推断。
- 客观贡献与故事表达能力已分开评价。
- 挑战数量由材料决定，没有强行凑数。
- 问题、挑战、机制、实验和结论已形成闭环。
- 工程工作量没有被直接当作学术贡献。
- 负面结果、成本、失败条件和适用边界没有被隐藏。
- 删除具体案例后，方法仍能用于新的研究项目。
- 未保留与当前任务无关的论文编号、作者或项目专名。

## Integration with /idea-check (lucky-research)

Triggered as `/idea-check 2paper [<slug>]`. This is an on-demand lens over an
existing idea, **not** a stage of the 6-stage pipeline — it never advances the
idea's `status`.

1. **Resolve scope** — read the cursor (`mcp__claude-flow__memory_retrieve`
   namespace=`project`, key=`idea-context.current`), or use the explicit
   `<slug>` argument. If neither resolves:
   `Run /idea-check "<your idea>" first.`
2. **Collect evidence** — load whatever exists under
   `outputs/idea-checks/<slug>/` (`idea.md`, `socratic.md`, `scout.md`,
   `evaluate.md`, `knowledge.md`). If the idea has been handed off to
   `/paper`, offer to also pull the direction's drafts under
   `outputs/papers/<venue>/<direction>/` and any bound experiment results
   under `outputs/experiments/<slug>/results/`. The user may hand over extra
   material (PDF, draft, repo notes) — accept it as input.
3. **Pick the task type** per「输入与输出约定」— for an idea that has code /
   experiments behind it, default to 组织待投稿工作; for a bare captured idea
   with no artifacts yet, say so and point at the missing evidence instead of
   fabricating a story.
4. **Run the workflow above** (事实账本 → 去包装摘要 → 反推问题 → 挑战 →
   架构 → 论证链 → 实验闭环 → 贡献 → 诚实性审计), depth scaled to the
   material.
5. **Save** — write the deliverable to `outputs/idea-checks/<slug>/story.md`;
   mirror to AgentDB via `mcp__claude-flow__memory_store` namespace=`ideas`,
   key=`<slug>/story` (statement, task type, evidence-gap list, 转折点,
   over-claim risks).
6. **Next-step hint** — `Next: /paper focus` when the idea is handed off and
   the story holds; `Next: /idea-check evaluate` or a补实验 list when
   evidence gaps dominate.

Re-entry is safe: re-running overwrites `story.md` and the AgentDB key.
