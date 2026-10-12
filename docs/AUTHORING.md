# 离线写作手册 · 手写一份 Deep Ocean deck

> **这份文件解决什么问题**：不联网、不用任何 API key，直接手写（或让 AI agent 写）
> 一份能被 `deepocean build` 编译、并且 `deepocean check --strict` 通过的中文汇报 deck。
>
> **谁该读它**：用 AI agent（Claude Code / Codex / DSH）做汇报的人、想自己精修 `deck.yaml` 的人、
> 以及想把"读论文 → 出稿"这段做成离线流程的人。
>
> 与 `docs/STYLE.md`（设计规范）的关系：STYLE 讲**为什么**这样排，本文讲**怎么写**才能过编译与自检。

---

## 0 三条铁律（不合规的稿子一眼能看出来）

1. **每页一个判断**：页面标题必须是结论（"推荐塌陷，搜索只补回两成"），不是话题（"主效应分析"）。
2. **撑满**：内容页卡片要落到 `y ≥ 600`（内容区 200–640）；不要把所有内容堆在中间。
3. **数字带出处**：任何数字都要能在页脚/注释里指回原文页码。

另外四条硬约束（linter 会拦）：只用调色板里的颜色、正文 ≥ 13px（辅助文字 ≥ 11px）、
红色墨色单页 ≤ 6%、配图页全篇 ≤ 2 页。

---

## 1 最小骨架

```yaml
meta:
  title: 推荐如何影响顾客搜索
  subtitle: How Recommendation Affects Customer Search   # 英文副标（可选，用于核对出处）
  kicker: 组会文献汇报                                     # 页眉眉标
  journal: ISR · 2025                                     # 右上角刊名角标
  authors: [汇报人]
  source_note: 组会文献汇报 · ISR 2025, 36(1): 84-106      # 页脚来源
  footer_note: 组会文献汇报 · 推荐与搜索                     # 页脚左（不写则自动拼）

pages:
  - layout: cover
    title: 推荐如何影响顾客搜索
    data:
      english_title: How Recommendation Affects Customer Search
      authors: 汇报人 · 你的名字
      affiliation: 单位 · 方向 · 2026-10
      series: ISR · 2025
      note: 样本 555,800 名顾客 · 26 个品类 · 一个常规日
```

一页 = 一个 `layout` + `title`（内容页必填）+ `data`（该版式的字段）。
**字段名必须精确**：先查 `deepocean layouts <layout>`，再写。

---

## 2 十三个版式的最小示例（可直接复制）

### cover · 封面

```yaml
- layout: cover
  title: 从人类智能视角解构生成式 AI
  data:
    english_title: Unraveling Generative AI from A Human Intelligence Perspective
    authors: 汇报人 · 你
    affiliation: 管理科学与工程 · 组会 · 2026-10
    series: SSRN · 2025
    note: 17 项行为实验 · 327 个任务 · 50 次重复
```

### two_column · 非对称双栏（背景/综述最常用）

```yaml
- layout: two_column
  kicker: 01 · BACKGROUND
  title: 推荐与搜索是平台帮顾客找货的两条通道
  data:
    left:
      title: 摘要要点
      body: 推荐由平台发起、顾客被动；搜索由顾客发起、主动而明确。
      items: [推荐=平台主动，搜索=顾客主动, 两者关系是替代还是互补尚无定论]
      footer: 原文页码：p2
    right:
      - {chip: GAP, chip_en: 研究缺口, title: 既有研究未分离两渠道, body: 观测数据无法给出因果。}
      - {title: 本文做法, body: 用大型平台随机实验分离推荐的影响。}
```

### big_number · 巨型数字 + 洞察

```yaml
- layout: big_number
  kicker: 02 · QUESTIONS
  title: 三个问题决定这篇论文的边界
  data:
    mode: hero
    items:
      - {number: "01", title: 主效应有多大, body: 推荐下降后搜索能补回多少？}
      - {number: "02", title: 补偿是否因品类而异, body: 哪些品类互补、哪些替代？}
      - {number: "03", title: 机制是什么, body: 需求状态如何驱动渠道关系？}
```

### experiment_design · 上流程 + 下对比

```yaml
- layout: experiment_design
  kicker: 03 · DESIGN
  title: 随机田野实验：只改推荐相关性
  data:
    steps:
      - {label: STEP 1, text: 锁定一个无大促的常规日}
      - {label: STEP 2, text: 随机分流：保留 / 禁用个人数据}
      - {label: STEP 3, text: 观测两条渠道的行为变化}
    groups:
      left:  {title: 对照组, body: 输入个人数据，个性化推荐。}
      right: {title: 处理组, body: 禁用个人数据，推荐退化为大众爆款。}
    vs: VS
    verdict: 唯一差异是个人数据是否进入推荐算法
```

### roadmap · 左标题栏 + 右步骤

```yaml
- layout: roadmap
  kicker: 04 · METHOD
  title: 四步证据链
  data:
    aside:
      title: 识别策略
      body: 以处理分配为工具变量，剥离推荐渠道的内生性。
      items: [ITT + IV 弹性, 26 品类分组, NLP 查询特征]
      footer: N = 555,800
    steps:
      - {no: "01", title: 主效应, body: 对比两组在两条渠道的 PV/点击/订单/GMV。, meta: Table 1}
      - {no: "02", title: 渠道弹性, body: 估计推荐 → 搜索的替代弹性。, meta: IV}
```

### chart_insight · 左图 + 右洞察（数据页主力）

```yaml
- layout: chart_insight
  kicker: 05 · RESULTS
  title: 搜索补偿集中在感兴趣品类
  hero: true
  data:
    chart:
      type: bar                       # bar | line | doughnut
      title: 推荐相关性下降后的搜索变化（%）
      categories: [特定需求, 通用查询, 特定品类, 不感兴趣品类]
      series:
        - {name: 搜索变化, values: [10, 19, 10, 0]}
      unit: "%"
      height: 320
      note: 数据来自原文 p25
    kpis:
      - {value: "19%", label: 通用查询增加, note: p25, tone: up}
      - {value: "10%", label: 特定需求增加, note: p25, tone: flat}
    cards:
      - {title: 替代效应, body: 推荐相关性下降、搜索向搜索补偿。}
    takeaway: {label: 一句话, text: 补偿集中在感兴趣品类，整体呈部分替代}
```

> `values` 必须是**纯数字**（写 `19`，不要写 `"19%"`）；长度必须与 `categories` 一致。
> 写错了不用怕：`deepocean normalize` 会离线修好并告诉你改了什么。

### image_evidence · 图片证据页（论文配图）

```yaml
- layout: image_evidence
  kicker: 06 · EVIDENCE
  title: 概念框架：需求状态驱动渠道关系
  data:
    side_ratio: 0.62
    image:
      path: figures/p32-fig01.png      # 相对 deck 文件，或绝对路径
      caption: Figure 2 Conceptual Framework
      source: 来源：论文 p32
      fit: contain
    cards:
      - {title: 需求未满足, body: 推荐作为补偿，顾客转而搜索。}
      - {title: 需求形成时, body: 推荐带动搜索，形成互补。}
    takeaway: {label: 解读, text: 两种机制共同解释渠道关系}
```

### split_cards · 双栏对比卡（互补 vs 替代）

```yaml
- layout: split_cards
  kicker: 07 · HETEROGENEITY
  title: 替代与互补并存，取决于需求状态
  data:
    left:  {chip: SUBSTITUTION, chip_en: 替代, title: 需求未满足时搜索补偿, items: [推荐下降 → 搜索回升], tone: danger}
    right: {chip: COMPLEMENTARY, chip_en: 互补, title: 需求形成时搜索增加, items: [推荐 PV 增加 → 搜索增加], tone: accent}
```

### concept_flow · 左 → 中 ⇄ → 右

```yaml
- layout: concept_flow
  kicker: 08 · FRAMEWORK
  title: 概念框架：两种机制驱动渠道关系
  data:
    left:   {title: 需求形成, body: 推荐帮助顾客发现新需求。}
    center: {label: "⇄", note: update}
    right:  {title: 需求满足, body: 搜索满足明确购买意图。}
    takeaway: 推荐与搜索的关系由需求状态决定
```

### matrix2x2 · 2×2 机制矩阵

```yaml
- layout: matrix2x2
  kicker: 09 · MECHANISM
  title: 需求状态 × 渠道关系构成四象限
  data:
    aside:
      title: 两个维度
      body: 横轴是需求是否已明确，纵轴是渠道关系。
      items: [横轴：需求 未明确 → 明确, 纵轴：关系 替代 → 互补]
      axes: {x: 需求 未明确 → 明确, y: 替代 → 互补}
    quadrants:
      - {no: LT, title: 替代 · 低兴趣, condition: "推荐 −91%", result: "搜索 0%（n.s.）", tone: danger}
      - {no: RT, title: 替代 · 高兴趣, condition: "推荐 −92%", result: "搜索 +10%", tone: alert}
      - {no: LB, title: 互补 · 低兴趣, condition: "推荐 +369%", result: "搜索 +30%", tone: accent}
      - {no: RB, title: 互补 · 高兴趣, condition: "推荐 +48%", result: "搜索 +12%", tone: tint}
```

### data_table · 数据表

```yaml
- layout: data_table
  kicker: APPENDIX · A1
  title: 关键数字：替代效应与异质性
  data:
    columns: [项目, 变化, 出处]
    rows:
      - ["特定需求搜索", "+10%", "p25"]
      - ["通用查询搜索", "+19%", "p25"]
    caption: 来源：论文 p25（自动/手工提取，务必回页核对）
```

### key_findings · 结论横幅 + 启示

```yaml
- layout: key_findings
  kicker: FINDINGS
  title: 推荐相关性下降，搜索增加
  data:
    banner:
      heading: 需要记住的数字
      figures:
        - {value: "555,800", label: 实验样本, tone: flat}
        - {value: "10%", label: 特定需求增加, tone: up}
        - {value: "19%", label: 通用查询增加, tone: up}
    cards:
      - {title: 部分替代, body: 搜索补偿只覆盖部分损失。}
      - {title: 品类异质性, body: 补偿集中在感兴趣品类。}
    cards_ratio: 0.36
```

### closing · 总结与展望

```yaml
- layout: closing
  kicker: CONCLUSION
  title: 总结
  data:
    quote: {text: 推荐与搜索的关系由需求状态决定，而不是平台的单方面选择。, source: 论文 p25–p27}
    panels:
      - {title: 局限, body: 单一平台、单一算法、一个常规日。}
      - {title: 展望, body: 跨平台复现与长期效应值得跟进。}
    thanks: 感谢聆听 · 欢迎批评指正
```

---

## 3 从论文到 deck 的离线流程（不需要任何模型 API）

```bash
# ① 提取：只读 PDF，输出摘要包与配图（纯本地）
deepocean from-paper "论文.pdf" --digest "论文.digest.md" --figures "figures" --max-figures 1
#    这会同时给出一份"离线骨架" deck.yaml：结构对、数字带页码，但文字还是原文要点

# ② 写作：打开 论文.digest.md，按下面顺序把骨架改成中文叙事
#    01 摘要/引言 → 第 2 页 two_column（背景与缺口）
#    02 方法     → experiment_design 或 roadmap
#    03 结果数字 → chart_insight（values 用 digest 里的数字，note 写 p 页）
#    04 配图     → image_evidence（最多 2 页）
#    05 表格     → data_table
#    06 结论     → key_findings + closing（金句抄原文结论句）

# ③ 离线修结构（补 0、对齐列宽、修正 tone）
deepocean normalize "论文.deck.yaml"

# ④ 自检：必须 0 error / 0 warn
deepocean check "论文.deck.yaml" --strict

# ⑤ 出片 + 目视验收
deepocean preview "论文.deck.yaml" --out out
python tools/make_preview.py --deck "论文.deck.yaml" --out out/preview.png --pages 1,2,4,5,8
```

**AI agent 用这条**：agent 自己就是"模型"，读 `论文.digest.md` 写出 `deck.yaml`（这一步不需要 API key，
用的就是 agent 本身的推理）。规则只有一条：**只写 digest 里出现过的数字，并保留页码**。

---

## 4 写完自查（规则码 → 怎么改）

| 提示 | 意思 | 怎么改 |
|---|---|---|
| YAML 解析报 `mapping values are not allowed here` | 英文标题/副标里带了 `: `（冒号+空格） | 用引号包起来：`subtitle: "How X: A Field Experiment"`。全角「：」不受影响 |
| `L002` 缺少必填字段 | 该版式少了一个 key | `deepocean layouts <layout>` 看契约 |
| `L002` 缺少 `title`/`number`/`label` | 嵌套项名字写错，卡片会空白 | 卡片统一 `{title, body, items, tone}`；KPI 用 `{value, label, note, tone}` |
| `L002` chart.categories 为空 | 图表没数据 | 补 categories 与等长 values（纯数字） |
| `L002` rows 单元格数不一致 | 表格列宽错位 | `deepocean normalize` 自动修 |
| `L003` 内容页没有标题 | 少了判断句 | 补一句结论式标题 |
| `M001` 突破安全边距 / `M003` 没撑满 | 内容没占满内容区 | 用版式库给的版式，不要手摆坐标 |
| `T001`/`T002` 字号过小 | 正文写小了 | 正文 ≥13px（用 `card_body`），辅助文字 ≥11px |
| `C001`/`C002` 颜色不在调色板 | 手填了 hex | 只用 `navy/teal/grayblue/brick/white/light/mint/pink/line` |
| `K001` 对比度不足 | 浅色字压浅底/深蓝卡用了深字 | 深蓝卡内一律白字；浅底用 `t1/t2` |
| `R002` Hero 占比超 45% | `hero: true` 标多了 | `deepocean normalize` 自动收敛 |
| `X001` 占位文字 | 写了"待填/示例/TODO" | 换成真实内容 |

---

## 5 交付前的四条命令（缺一不可）

```bash
deepocean normalize "deck.yaml"          # 结构体检 + 自动修
deepocean check "deck.yaml" --strict     # 必须 0 error / 0 warn
deepocean preview "deck.yaml" --out out  # 出 pptx + html + 报告
python tools/make_preview.py --deck "deck.yaml" --out out/preview.png   # 逐页看图
```

> 最后一步不能省：自检抓不到"字压到卡片外""横轴标签被截断""图片路径没解析到"这三类问题，
> 只有真的看图才发现。

---

## 6 可选：想让它自己改写叙事（需要联网与付费 API）

```bash
export DEEPSEEK_API_KEY=sk-...           # 或 OPENAI_API_KEY
deepocean from-paper "论文.pdf" --llm --journal "ISR · 2025" --max-figures 1 --build
```

这是**唯一**需要 key 的功能。不用它，上面第 3 节的离线流程完全等价——只是"改写成中文叙事"
这一步由你（或你的 agent）来做，而不是由远端模型做。
