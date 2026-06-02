# Architecture-diagram prompt — flat-vector style for structural figures

> **Source:** Adapted from
> [Leey21/awesome-ai-research-writing](https://github.com/Leey21/awesome-ai-research-writing)
> (no explicit LICENSE; public awesome-list intended for sharing).
> The Visual Constraints block below is reproduced verbatim from that README's
> "论文架构图" entry. The Role / Task / Input wrappers are dropped — they're
> redundant with the existing `/figure new` (kind=structural) flow.

## How `/figure new` (kind=structural) uses this

When Step 6 (`render` step, structural branch) constructs the SVG-generation
prompt, it appends the **Architecture diagram conventions** block below to
the existing prompt-construction list (after the Inkscape conventions, palette,
project rules, and hard rules).

The block carries the visual-style guidance from the source repo's
"论文架构图" entry — flat vector, DeepMind/OpenAI aesthetic, soft palette, no
cartoon / painting feel. It complements (does not replace) the existing
`latex-conventions.md` `tables-and-figures` section rules.

These rules apply **only** when generating the SVG. They do not affect the
note.md or the LaTeX include snippet — those keep the existing format from
`SKILL.md`.

## Visual Constraints (reproduce in the structural SVG prompt)

```markdown
1. 风格基调：
   - 必须具备顶会论文风格：专业、干净、现代、极简主义。
   - 核心美学：采用扁平化矢量插画风格，线条简洁，参考 DeepMind 或 OpenAI 论文中的图表美学。
   - 拒绝卡通感、油画感或过度艺术化，保持严谨的学术图表美学。
   - 背景必须是纯白色，无任何纹理或阴影。

2. 色彩体系：
   - 严格使用淡色系或柔和色调。
   - 严禁使用过于鲜艳饱和的颜色（如大红大绿）或过于暗淡沉重的颜色。利用颜色的深浅变化来区分不同的模块类型。
   - 调色板由 /figure 当前 step 5 选定的 palette 决定 —— 不要自行引入未在 palette 中的颜色。

3. 内容与布局：
   - 将理解到的方法论转化为清晰的模块和数据流箭头。
   - 适当使用现代、简洁的矢量图标嵌入到模块中，以增强直观性。
   - 整体箭头流向遵循 latex-conventions.md `tables-and-figures` 的"一致方向"（左→右 或 上→下），不要做回环或交叉箭头簇。

4. 文字规范：
   - 图中所有文字必须使用英文。
   - 你必须为方法论中提到的关键模块或方程式添加清晰易读的文本标签。
   - 严禁在图中出现长句子、描述性段落或复杂的公式。文字是用来说明模块身份的，不是用来解释原理的。

5. 禁止事项：
   - 不允许使用逼真照片感。
   - 不允许杂乱的草图线条。
   - 不允许难以辨认的文本。
   - 不允许廉价的 3D 阴影瑕疵。
```

## Notes for the skill body

- The block above is **Chinese-language** by design; the source prompt is
  Chinese and re-translating it to English risks losing nuance. The model
  reads both fine. Only the **text inside the generated SVG** must be
  English (item 4).
- This block does NOT override the `tables-and-figures` rules in
  `latex-conventions.md`. When the two overlap (e.g. arrow direction,
  palette ≤6 colors), `latex-conventions.md` wins because it is project-wide.
  This file fills in style guidance that `latex-conventions.md` deliberately
  leaves open.
- D2-scaffolded structural figures still apply this block — D2 produces the
  layout, the SVG-touch-up pass applies the aesthetic constraints.
