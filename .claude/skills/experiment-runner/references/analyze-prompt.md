# Analyze prompt — turn raw experiment results into a LaTeX analysis paragraph

> **Source:** Adapted from
> [Leey21/awesome-ai-research-writing](https://github.com/Leey21/awesome-ai-research-writing)
> (no explicit LICENSE; public awesome-list intended for sharing).
> The prompt body below — Role / Task / Constraints — is reproduced verbatim
> from that README's "实验分析" entry.

## How `/experiment analyze` uses this

1. Read this file as the prompt prelude.
2. Resolve the current experiment cursor; collect the **mirrored result files**
   under `results/<vN.M>/` for the versions to be analyzed (positional list, or
   all when none given).
3. Also read:
   - `designs/<latest>.md` — for metric definitions, RQ, success criteria.
   - `references.md` — for baseline numbers from comparison papers, when
     present (this is what makes the SOTA framing concrete).
4. Stitch result files + design context as the `# Input` block. Format is
   free-form text — paste the raw numbers verbatim, no pre-summarization.
5. The model returns a two-part structured response:
   - `Part 1 [LaTeX]` — one or more `\paragraph{Title Case Conclusion}` blocks
     plus the analysis prose. Bold / italic emphasis is disallowed; emphasis
     comes from sentence structure.
   - `Part 2 [Translation]` — Chinese direct translation for the user to
     spot-check that no number was hallucinated.
6. Write outputs:
   - `results/<vN.M>/analysis.tex` — Part 1 (consumed verbatim by
     `/paper write results`).
   - `results/<vN.M>/analysis.md` — full response (Part 1 + Part 2) for the
     audit log.

   When analyzing multiple versions in one call, the analysis file lives
   under the **latest** version's `results/<vN.M>/` and references the prior
   versions inline. The `.tex` is meant to be self-contained — paste it under
   `\section{Results}` and it compiles.

## Prompt body (reproduce verbatim to the model)

```markdown
# Role
你是一位具有敏锐洞察力的资深数据科学家，擅长处理复杂的实验数据并撰写高质量的学术分析报告。

# Task
请仔细阅读我提供的【实验数据】从中挖掘关键特征、趋势和对比结论，并将其整理为符合顶级会议标准的 LaTeX 分析段落。

# Constraints
1. 数据真实性：
   - 所有结论必须严格基于输入的数据。严禁编造数据、夸大提升幅度或捏造不存在的实验现象。
   - 如果数据中没有明显的优势或趋势，请如实描述，不要强行总结所谓的显著提升。

2. 分析深度：
   - 拒绝简单的报账式描述（例如不要只说 A 是 0.5，B 是 0.6），重点在于比较和趋势分析。
   - 关注点包括：方法的有效性（SOTA 比较）、参数的敏感性、性能与效率的权衡，以及消融实验中的关键模块贡献。

3. 排版与格式规范：
   - 严禁使用加粗或斜体：正文中不要使用 \textbf 或 \emph，依靠文字逻辑来表达重点。
   - 结构强制：必须使用 \paragraph{核心结论} + 分析文本 的形式。
     * \paragraph{} 中填写高度凝练的短语结论（使用 Title Case 格式）。
     * 紧接着在同一段落中展开具体的数值分析和逻辑推演。
   - 不要使用列表环境，保持纯文本段落。

4. 输出格式：
   - Part 1 [LaTeX]：只输出分析后的 LaTeX 代码。
     * 必须对特殊字符进行转义（例如：`%`、`_`、`&`）。
     * 保持数学公式原样（保留 `$` 符号）。
     * 不同的结论点之间请空一行。
   - Part 2 [Translation]：对应的中文直译（用于核对数据结论是否准确）。
   - 除以上两部分外，不要输出任何多余的对话。

# Input
[在此处粘贴你的 Excel 数据或实验结果文本]
```

## Integration with `/paper write results`

When `/paper write results` runs, it reads
`outputs/experiments/<slug>/results/<latest>/analysis.tex` directly and
either pastes it under the section heading or weaves it into the existing
draft. This is the bridge that makes the experiment cursor and the paper
cursor talk to each other.
