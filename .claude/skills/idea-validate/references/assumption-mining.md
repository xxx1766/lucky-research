# Assumption mining — 从论文中挖 idea

`/idea-check assumptions [<paper|slug>]` 的完整流程。

核心信念：**很多新 idea 不是发明新模块，而是发现"大家一直默认成立的一件事，
其实不一定成立"。** 这个模式服务 Gate 3（机制）——一个被推翻的默认假设，往往
就是机制解释的入口。

## 输入解析

参数可以是：

- 一个 arXiv URL / DOI / `inputs/papers/*.pdf` 路径 → 先看 `outputs/summaries/`
  里有没有对应 summary；没有就建议先 `/summarize`（**不要**自动跑，PDF 解析可能
  很慢），或直接读 PDF 前 3 节 + 实验节。
- 一个已索引的 paper slug → 从 AgentDB `papers/<slug>` 取。
- 空参数 → 用当前活跃 idea 的 `scout.md` 里排第一的论文，并说明你选了哪篇。

## 三步提问（一次一个，纯文本）

### 步骤 1 — 这篇论文到底发现了什么问题？

- 用一句话写出问题，不要用作者的摘要措辞。
- 追问：**为什么以前的方法解决不了？** 答案必须落到某个具体机制上，
  "效果不好"不算。

### 步骤 2 — 作者默认了什么？

列出论文中**未经论证**的隐含假设，逐条问：**这在什么条件下不成立？**

挖假设的几个常见位置：

| 位置 | 典型默认 |
|---|---|
| 问题设定 | 输入分布、任务边界、评测指标能代表真实目标 |
| 方法设计 | 某个中间量可加/可分解/单调、误差独立、梯度可用 |
| 实验设置 | baseline 调参充分、数据集有代表性、规模可外推 |
| 结论外推 | "在 X 上成立" → "普遍成立" |

每条假设记为：

```
- A<n>: <假设陈述>
  - 论文哪里用到它: <节号 / 一句引文>
  - 什么条件下不成立: <具体条件>
  - 若不成立会怎样: <对结论的影响>
```

### 步骤 3 — 那个条件本身是不是一个普遍存在的 failure case？

- 若**是** → 这就是一个 idea 的种子。走 spawn 流程（下节），新 idea 从
  Gate 1 起跑，把 `A<n>` 的"不成立条件"作为 Gate 1 的候选 failure case。
- 若**否**（只在一个数据集/一个特殊设定下不成立）→ 明说这是 patch 级，
  不值得单独立项；记进 `assumptions.md` 备查即可。

## 产物

写 `outputs/idea-checks/<slug>/assumptions.md`：

```markdown
# Assumptions — <paper title>

_Source: <URL / path> · mined <date>_

## 论文解决的问题

<一句话> —— 以前解决不了的原因：<机制>

## 隐含假设

- A1: ...
  - 论文哪里用到它: ...
  - 什么条件下不成立: ...
  - 若不成立会怎样: ...

## 判定

| 假设 | 不成立条件是否普遍 | 处理 |
|---|---|---|
| A1 | 是 | spawn `<new-slug>` → Gate 1 |
| A2 | 否 | 记录备查（patch 级） |
```

AgentDB 镜像：namespace=`ideas`, key=`<slug>/assumptions`，payload 带
`{"source": ..., "assumptions": [...], "spawned": [<new-slug>, ...]}`。

**不推进 status** —— 这是 service。

## spawn 流程（某条假设值得单独立项）

1. 把"该假设不成立"写成一句不含方法的 problem statement。
2. `registry.create_variant_idea(parent_slug, suffix="assumption", new_statement=...)`
   —— slug 冲突会自动退到 `-assumption-2` / `-3`。
3. 写新 idea 的 `assumptions.md`（说明它来自哪篇论文的哪条假设），AgentDB 镜像
   `ideas/<new-slug>`。
4. 问用户是否切换 cursor（默认**不切**，留在当前 idea）。
5. 提示：新 idea 需要从 `/idea-check failure-case` 走完五关 —— 它继承的是一个
   线索，不是一个已验证的问题。
