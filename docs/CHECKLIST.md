# 交付前自检清单

> **这份文件解决什么问题**：把《Deep Ocean 学术风 PPT · 风格规范与制作教程》第 09 节的交付前自检清单原文保留下来，并逐条标注**哪条规则码会自动检查、哪一条必须人工确认**。规则码就是 `deepocean check` 报告里打印的码（定义在 `src/deepocean/check.py` 的 `RULE_CODES`）。结尾给出把自检挂进 CI 的做法。
>
> **谁该读它**：准备把 deck 拿出去讲的人（答辩 / 组会 / 开题前最后一道关），以及要配 CI 的仓库维护者。

## 目录

| 章节 | 内容 |
|---|---|
| [1](#1-交付前自检清单规范原文--规则码) | 规范原文逐条 + 对应规则码 |
| [2](#2-规则码总表) | 31 条规则的准确含义 |
| [3](#3-两类检查静态检查与产物检查) | `check_deck` / `check_pptx` 各查什么 |
| [4](#4-机器能查什么不能查什么) | 自动 vs 人工的边界 |
| [5](#5-在-ci-里用-deepocean-check---strict) | CI / hook 接入 |
| [6](#6-交付前-30-秒快查) | 四步门禁 |

## 怎么用这份清单

```bash
deepocean check deck.yaml            # 静态检查：结构、节奏、占位文字（不需要 PowerPoint）
deepocean check out.pptx             # 产物检查：几何、排版、色彩（按 1280×720 px 实测每个形状）
deepocean check deck.yaml --json     # 机器可读
deepocean check deck.yaml --strict   # 存在任何告警即非零退出（交付门禁）
```

报告里每条问题都带一个**规则码**（如 `T002`）。第 2 节是这个码的准确含义。

- **自动检查**：`deepocean check` 能判定，`--strict` 下会拦住交付。
- **人工确认**：机器判不了（审美、语义、数据可追溯性），清单里保留成勾选项。

> **两个层次的检查不重叠**：`deck.yaml` 只能静态检查结构与节奏；涉及坐标、字号、颜色的规则必须检查**渲染产物**（`.pptx`）。想一次过完，先 `deepocean build` 或 `deepocean preview`，再检查 pptx。

---

## 1 交付前自检清单（规范原文 + 规则码）

### 母版与一致性

- [ ] 顶条 / 标题位置 / 页脚 / 页码 全篇一致（封面与结尾可例外） —— **自动检查** `M001` `M002`
  （`M001` 查左右 40 px 安全边距；`M002` 查内容有没有压到 y60–72 的顶条预留区。位置一致性来自 `tokens.BANDS` 是唯一坐标来源）
- [ ] 刊名角标（如 `ISR · 2025`）位置全篇固定 —— **人工确认**
  （版式代码统一从 `BANDS["top_bar"]` 推导，但"角标是否出现在每一页"是内容决定）
- [ ] 左右安全边距 40 px 未被突破 —— **自动检查** `M001`
  （判定条件：`x < 40` 或右边界 `> 1240`）
- [ ] 元素不超出 1280×720 画布 —— **自动检查** `M004`（信息级提示）

### 视觉与信息密度

- [ ] 每页主视觉 ≥ 内容区 30% —— **人工确认**（面积占比的语义判断）
- [ ] Hero 页有 ≥ 48 px 锚点数字或 ≥ 40% 主视觉 —— **自动检查** `A001`
  （机器阈值是 `RHYTHM_RULES["min_anchor_px"] = 44`；48 px 是规范对 Hero 页的**更高**人工要求）
- [ ] 内容页卡片撑满，无大面积空白带；卡片填充率 ≥ 80% —— **自动检查** `M003`
  （判定条件：至少一个元素抵达 `y ≥ 600`）
- [ ] 每页 ≥ 1 个视觉锚点（≥ 44 px 元素 或 ≥ 40% 面积图） —— **自动检查** `A001`
- [ ] 相邻两页视觉重量有差异（最大元素面积比 > 1.5:1 或版式结构不同） —— **自动检查** `R004`
  （版式结构不同的部分由 `R004`「相邻两页不得使用相同版式」覆盖；面积比 1.5:1 需 **人工确认**）

### 色彩

- [ ] 红色用量 ≤ 6%，金色 = 0 —— **自动检查** `C003` `C002`
  （`C003` 只查砖红墨色 `#C0392B` 的单页占比 ≤ 6%；`C002` 直接禁用金色）
- [ ] 无紫粉玫红、无橙绿大色块、无纯黑大底 —— **自动检查** `C002`
  （判定依据 `tokens.FORBIDDEN` 的色相 / 饱和度规则）
- [ ] 无彩虹渐变 —— **人工确认**（机器只报告调色板外颜色，见 `C001`）
- [ ] 内容区未使用深色实底或高饱和彩色实底 —— **自动检查** `C005`
  （判定条件：`navy` 深色实底单页占比 > 40%。注意这是"提示级"上限，不是绝对禁止）
- [ ] 强调色只出现在焦点元素上 —— **人工确认**
- [ ] 只在色板内用色 —— **自动检查** `C001`
- [ ] 浅青 / 浅红强调底色单页 ≤ 20%（浅灰卡底不计入，实装上限 35%）—— **自动检查** `C004`

### 文字

- [ ] 正文 ≥ 13 px（11.5–12 px 仅限 caption / footer / kpi 标签）—— **自动检查** `T002`
- [ ] 卡片内小字不低于 11 px / 全文任意文字 ≥ 11 px —— **自动检查** `T001`
- [ ] 文字未溢出卡片、无断词异常 —— **自动检查** `T005`
  （判定条件：文字预估高度超过文本框高度 15%。估算用 `primitives.wrap_lines()` / `text_height()`，对 CJK 按字断行）
- [ ] 深底白字 / 浅底深字，对比度 ≥ 4.5:1 —— **自动检查** `K001`
  （`color.contrast_ratio()`；**≥ 32 px 的大字放宽到 3.0**）
- [ ] 全篇只用 2 套字体家族 —— **自动检查** `T003`（单页上限 2 套）
- [ ] 全篇只用 2 级字重 —— **自动检查** `T004`（单页上限 2 级）
- [ ] 正文行高 1.5–1.6 —— **人工确认**
  （行高由 `TYPE_SCALE` 的 `line_height` 统一给出，机器不单独判定；改动 token 时注意这条）

### 数据与图表

- [ ] 每个数据页含：主图 + 洞察文字 + ≥ 1 个关键数字（"数据 + 判断"两段式） —— 锚点部分 **自动检查** `A001`；"两段式是否写了判断" **人工确认**
- [ ] 图表有数据标签 —— **自动检查** `H001`
- [ ] 图表有显式高度（否则渲染为 0） —— **自动检查** `H002`
- [ ] 轴 / 图例色为中性灰，不抢戏 —— **自动检查** `C001` + `H001`
  （轴用 `CHART["axis_color"] = "grayblue"`、图例 `legend_color = "t2"`，都在色板内，`C001` 会兜住跑出色板的写法）
- [ ] 全篇至少 1 页证据页（图表页） —— **自动检查** `R006`
- [ ] 所有数值可追溯到论文 Table / Figure，页脚标注来源 —— **人工确认** `D002` 附近
  （机器只能确认 `meta.title` 非空；可追溯性必须人查。建议在 `meta.source_note` 写全 DOI）
- [ ] 无杜撰公式、虚构数据、编造引用 —— **人工确认**

### 结构

- [ ] 多卡页有"双重锚定"：一种物理连接（箭头 / 共享外框）+ 一种共享锚点（标题条 / 底部强调条） —— **人工确认**
- [ ] 无 3D / 卡通 / 营销插画 —— **人工确认**（色彩层面由 `C002` 兜底）
- [ ] 占位文字已清零（`lorem` / `TODO` / `待填` 等） —— **自动检查** `X001`
- [ ] 内容页没有空字段 —— **自动检查** `X002`
- [ ] deck 结构与字段合法：layout 名存在、必填字段齐全、内容页有标题、至少一页 —— **自动检查** `D001` `L001` `L002` `L003`
- [ ] `meta.title` 非空 —— **自动检查** `D002`

### 节奏（规范第 06 节的排布规则，纳入交付门禁）

- [ ] Hero 页 = 4/12，peak–valley 交替 —— **自动检查** `R002`
  （判定条件：Hero 占比在 **25%–45%** 之间。13 页示例 deck 的 `hero_count = 4`，占 30.8%，通过）
- [ ] 无连续 3 页 valley —— **自动检查** `R003`
- [ ] 相邻两页版式不相同 —— **自动检查** `R004`
- [ ] 等宽 N 卡片横排全篇 ≤ 2 页；Hero 页 0 页 —— **自动检查** `R005`
- [ ] 全篇页数落在建议区间 —— **自动检查** `R001`（建议 6–24 页，参考节奏按 12 页标定）
- [ ] 非对称版式 ≥ 83% —— **人工确认**
  （`RHYTHM_RULES["asymmetry_ratio"] = 0.83` 写在 token 里，但当前 linter 未单独设码；靠 `R004` 与版式选择间接保证）
- [ ] 「左大图 + 右侧文字」+「非对称双栏」合计 ≤ 全篇 40% —— **人工确认**
  （`RHYTHM_RULES["chart_pages_max_share"] = 0.40` 写在 token 里，未单独设码）

---

## 2 规则码总表

以下描述**逐字来自实现**（`src/deepocean/check.py` 的 `RULE_CODES`），是报告里那串码的权威含义。

> 这张表可以自证不漂移——`check.rule_table()` 直接由规则注册表生成，最新的版本随时可打印：
>
> ```bash
> deepocean check --help        # 看 check 的参数
> python -c "from deepocean import check; print(check.rule_table())"
> ```
>
> `rule_table()` 输出的就是 `code | level | rule | guide section` 四列，本节的四张分组表是它的重排。

### 结构 / 文档（`D`）

| 码 | 级别 | 检查什么 | 规范出处 | 违反时怎么办 |
|---|---|---|---|---|
| `D001` | error | 文档必须至少包含一页。 | 09 · 结构 | 往 `pages:` 里加页 |
| `D002` | error | 文档 `meta.title` 不能为空。 | 09 · 结构 | 补 `meta.title` |

### 结构 / 版式（`L`）

| 码 | 级别 | 检查什么 | 规范出处 | 违反时怎么办 |
|---|---|---|---|---|
| `L001` | error | 页面 `layout` 必须是 `schema.LAYOUTS` 或 `schema.ALIASES` 中的名字。 | `schema.LAYOUTS` | `deepocean layouts` 查合法名；`two-col` / `chart` / `matrix` 这类别名也接受 |
| `L002` | error | 页面必须提供该 layout 的必填字段。 | `schema.fields_of()` | `deepocean layouts <name>` 看 `required=yes` 的字段 |
| `L003` | warn | 内容页（非 Hero 版式）必须有标题。 | 04 · MASTER B 区 | 补 `title:`；`cover` / `closing` 不受此限 |

### 节奏（`R`）

| 码 | 级别 | 检查什么 | 规范出处 | 违反时怎么办 |
|---|---|---|---|---|
| `R001` | warn | 全篇页数建议 6–24 页（参考节奏按 12 页标定）。 | 00 · 页面节奏 | 合并或拆分页面 |
| `R002` | warn | Hero 页占比应在 25%–45%（参考 4/12）。 | 00 · 页面节奏 | 增删 `hero: true`，或换版式（`cover` / `key_findings` / `closing` 默认是 Hero） |
| `R003` | warn | 不允许连续 3 页非 Hero 版式（谷底）。 | 00 · 页面节奏 | 把其中一页换成有锚点的版式 |
| `R004` | warn | 相邻两页不得使用相同版式。 | 08 · 版式排布规则① | 换一个版式（参考 deck 第 06、10 页同为 `chart_insight`，中间隔了 3 页，不冲突） |
| `R005` | warn | 全篇等宽多卡横排不超过 2 页，Hero 页为 0。 | 08 · 版式排布规则③④ | 打散卡片或换非对称版式 |
| `R006` | warn | 全篇至少要有 1 页证据页（`chart_insight` 等图表页）。 | 09 · 数据与图表 | 至少放一页真实图表 |

### 内容卫生（`X`）

| 码 | 级别 | 检查什么 | 规范出处 | 违反时怎么办 |
|---|---|---|---|---|
| `X001` | error | 正文中不得残留占位文字（`lorem` / `TODO` / `待填` 等）。 | 09 · 结构 | 替换成真实内容 |
| `X002` | warn | 内容页不应提交空字段。 | 09 · 视觉与信息密度 | 删掉空字段或补内容 |

### 几何与母版（`M`）

| 码 | 级别 | 检查什么 | 规范出处 | 违反时怎么办 |
|---|---|---|---|---|
| `M001` | error | 元素不得突破左右 40 px 安全边距（`x < 40` 或右边界 `> 1240`）。 | 09 · 母版与一致性 | 把坐标拉回 `x ∈ [40, 1240]`，宽度用 `tokens.SAFE_MARGIN_PX` 推导 |
| `M002` | error | 内容不得压到 y60–72 的顶条预留区。 | 04 · MASTER A 区 | 内容从 `BANDS["title"]["y"] = 72` 或 `BANDS["content"]["y"] = 200` 起 |
| `M003` | warn | 内容页必须撑满：至少一个元素抵达 `y ≥ 600`。 | 09 · 视觉与信息密度 | 加卡或加内容（对应规范"填充率 ≥ 80%"） |
| `M004` | info | 元素不应超出 1280×720 画布。 | 01 · CANVAS | 检查是否有元素被推到画布外 |

### 排版（`T`）

| 码 | 级别 | 检查什么 | 规范出处 | 违反时怎么办 |
|---|---|---|---|---|
| `T001` | error | 任何文字不得小于 11 px。 | 09 · 文字 | 连脚注也不能再小 |
| `T002` | error | 正文不得小于 13 px（11–13 px 仅限 caption / footer / kpi 标签）。 | 09 · 文字 | **减字数**，不要减字号 |
| `T003` | warn | 单页最多 2 套字体家族。 | 03 · 排版铁律③ | 去掉第三种家族 |
| `T004` | warn | 单页最多 2 级字重。 | 03 · 排版铁律③ | 只用 Bold + Regular |
| `T005` | warn | 文字预估高度不得超过文本框高度 15%。 | 09 · 文字 | 缩短文案，或用 `primitives.fit_size()` 降一档字号 |

### 色彩（`C`）

| 码 | 级别 | 检查什么 | 规范出处 | 违反时怎么办 |
|---|---|---|---|---|
| `C001` | error | 颜色必须来自 Deep Ocean 调色板。 | 02 · 色彩系统 | 换成 token 名或角色名；报告会给出最近的色板色 |
| `C002` | error | 禁用紫粉玫红、金色、纯黑等违规颜色。 | 02 · 禁用清单 | 见 `color.forbidden_reason()` 给出的理由 |
| `C003` | warn | 砖红警示色（#C0392B 文字 / 描边）单页占比不得超过 6%。 | 02 · 配色配比 | 降饱和或改灰；只标"下降 / 替代" |
| `C004` | warn | 浅青 / 浅红强调底色单页占比不得超过 20%（实装 35%，浅灰卡底不计入）。 | 02 · 配色配比 | 减强调卡数量 |
| `C005` | info | 深色实底（`navy`）单页占比超过 40%。 | 09 · 色彩 | 深蓝实色卡单页 ≤ 1 张、全篇 ≤ 3 张 |

### 对比度（`K`）

| 码 | 级别 | 检查什么 | 规范出处 | 违反时怎么办 |
|---|---|---|---|---|
| `K001` | warn | 文字与底色对比度不得低于 4.5:1（**≥ 32 px 大字可放宽到 3.0**）。 | 09 · 文字 | 正文换 `t1` / `t2`；深底用白字。注意 `teal` / `grayblue` / `t3` 在白底上天然不足，见 [`docs/STYLE.md` §2.3](STYLE.md#23-中性色要不要用红先把对比度算出来) |

### 锚点（`A`）

| 码 | 级别 | 检查什么 | 规范出处 | 违反时怎么办 |
|---|---|---|---|---|
| `A001` | info | 内容页需要视觉锚点（≥ 44 px 文字或 ≥ 40% 面积图形）。 | 09 · 视觉与信息密度 | 加一个 KPI 巨数字或放大主图 |

### 图表（`H`）

| 码 | 级别 | 检查什么 | 规范出处 | 违反时怎么办 |
|---|---|---|---|---|
| `H001` | warn | 图表必须开启数据标签。 | 09 · 数据与图表 | 打开数据标签 |
| `H002` | error | 图表必须有显式高度（不得为 0 或缺失）。 | 09 · 数据与图表 | 给 `chart.height`，取值 230–400 |

**级别含义**：`error` 必须修；`warn` 需要判断（可能是设计取舍）；`info` 是提示。`--strict` 对**三者任一非空**都会返回非零。

**关于 `cover` / `closing` 的豁免**：`cover` 与 `closing` 属于全幅版式（`check.FULL_BLEED_LAYOUTS`），本来可以突破四区母版——加高顶条、左竖条、底部色带都是规范允许的。几何规则（`M001` `M002`）与锚点规则（`A001`）的豁免依赖"知道这一页是哪个版式"，而版式名来自 deck 文档。因此：

- 用 `deepocean check deck.yaml`，或让 linter 同时拿到 deck（`check.check_pptx(path, deck)`）时，版式豁免生效；
- 只把一个裸 `.pptx` 交给 `deepocean check` 时，linter 无法判断版式，会把 `cover` / `closing` 自绘的顶条与竖条当成越界内容报出来（`M001` `M002`）。

要拿到最准确的产物报告，请显式把 deck 一起传进去：

```python
from deepocean import check, spec

deck = spec.Deck.load("examples/demo-deck.yaml")
report = check.check_pptx("out/deep-ocean-demo.pptx", deck)   # 传 deck 才启用版式豁免
print(report.to_text(color=True))
print(report.counts())        # 13 页参考 deck（v1.0.0 实测）：0 error / 0 warn / 59 info
```

**已知取舍（校准后的口径）**

规则与规范原文有几处**刻意收敛**，都在 `check.py` 里写明，并记录在 [`docs/STYLE.md` §9](STYLE.md#9-规范与代码的已知差异)：

1. **顶条青绿方块**（`x=32, y=26`）：`M001` 已加入"顶条内 ≤40px 见方装饰"的豁免，不再误报。
2. **12px 辅助文字**：`T002` 只判**正文**——要求「内容区、够长、在本框内换行到 ≥2 行」三者同时成立；`caption`(11.5) / `footer`(12) / `kpi_label`(12) 这类辅助文字不报。
3. **`K001` 对比度**：`teal` / `grayblue` / `t3` 在浅底上的低对比属于色板固有性质，且规范 §05 明确"深蓝卡 + 青绿小标"，因此这些组合降级为 `info` 并注明出处，其余仍按 `warn`。
4. **`C003` / `C004` 面积口径**：`C003` 只统计砖红**墨色**（`#C0392B` 文字/描边，≤6%）；`#FCE5E2` 浅红底与 `#E6F3F5` 浅青底按**强调底色**算，上限抬到 35%（一张"撑满"的强调卡本身就有 ~30% 画面）；`#F4F7FB` 是卡片底色，不计入。
5. **`R003` 连续谷底**：降为 `info`——规范的参考 deck 自己就是 4 页连续谷底（Hero 在 01/06/11/12），做不到"无连续 3 页 valley"，因此只作节奏提示。

因此：**`deepocean check`（默认）与 `deepocean check --strict` 在参考 deck 上都是 0 error / 0 warn 通过**（剩下 59 条 `info` 是"色板固有对比度""缺少 44px 锚点""等宽柱提示"这类说明性提示），可以直接当合并门禁。

---

## 3 两类检查：静态检查与产物检查

| | `check_deck`（检查 `deck.yaml` / `.json`） | `check_pptx`（检查 `out.pptx`） |
|---|---|---|
| 输入 | `spec.Deck` 文档 | 渲染产物，或一个活的 `pptx.Presentation` |
| 能查的码 | `D001` `D002` `L001`–`L003` `R001`–`R006` `X001` `X002` | `M001`–`M004` `T001`–`T005` `C001`–`C005` `K001` `A001` `H001` `H002` |
| 要不要 PowerPoint | 不需要（纯文本解析） | 读 pptx 包，逐个形状实测 |
| 坐标基准 | — | 全部换算回 **1280×720 设计 px**，与规范数字对齐 |
| 上游依赖 | `tokens` `schema` `spec` | 再加上 `color` `units` `primitives` |

`check_pptx` 刻意**不依赖** `layouts` / `components` / `build`：它必须能审查版式代码自己产出的文件，否则就成了"自己检查自己"。每个形状探测都包在 `try` / `except` 里（组合形状、无几何的连接线、表格、图表、图片都不会中断整轮审计）。

### 报告怎么读

```bash
deepocean check out.pptx            # 人读，带颜色
deepocean check out.pptx --json     # 机器读
```

报告对象提供 `ok()` / `errors()` / `warnings()` / `infos()` / `by_code()` / `counts()`，`--strict` 就是"`ok()` 为假，或 `warnings()` 非空，即非零退出"。

用 Python 时：

```python
from deepocean import check, spec

report = check.check_deck(spec.Deck.load("examples/demo-deck.yaml"))
print(report.to_text(color=True))
print(report.counts())                 # {'T002': 2, ...}
if not report.ok():
    raise SystemExit(1)
```

---

## 4 机器能查什么、不能查什么

**能自动判定（`--strict` 下拦交付）**

结构与字段（`D001` `D002` `L001`–`L003`）、节奏（`R001`–`R006`）、占位文字与空字段（`X001` `X002`）、边距与撑满（`M001`–`M004`）、字号与家族字重与溢出（`T001`–`T005`）、色板与禁用色与配比（`C001`–`C005`）、对比度（`K001`）、锚点（`A001`）、图表规范（`H001` `H002`）。

**只能人工确认**

- 数值是否可追溯到论文 Table / Figure、有无杜撰
- 是否出现彩虹渐变 / 3D / 卡通 / 营销插画
- 「每页主视觉 ≥ 内容区 30%」「强调色只出现在焦点元素上」
- 「双重锚定」是否符合结构意图
- 「数据 + 判断」两段式是否真的写了判断句
- 非对称版式是否 ≥ 83%；「图表页 + 双栏页」是否 ≤ 40%（阈值在 token 里，但未单独设码）

一句话：**机器负责"像不像这套规范"，人负责"说的是不是真话"。**

---

## 5 在 CI 里用 `deepocean check --strict`

`--strict` 的语义是**存在任何告警即以非零状态退出**，所以它可以直接当交付门禁。仓库已有一份 CI（`.github/workflows/ci.yml`），核心步骤是：

```yaml
      - name: Install
        run: pip install -e ".[dev]"
      - name: Unit tests
        run: python -m pytest -q
      - name: Design tokens are self-consistent
        run: python -m deepocean tokens --md > tokens.md
      - name: Build the reference deck
        run: python -m deepocean demo -o out
      - name: Lint the reference deck (strict)
        run: python -m deepocean check out/deep-ocean-demo.pptx --strict
```

它同时验证了三件事：测试全绿、令牌能自洽导出、**渲染产物在严格模式下被扫过一遍**。其中最后一条是关键——只检查 `deck.yaml` 会漏掉全部几何与色彩规则。

> `--strict` 的语义是"存在任何 `error` 或 `warn` 即非零退出"（`info` 不拦交付）。参考 deck 的静态检查与产物检查在 `--strict` 下**都通过**，可以直接当门禁。把 `--strict` 当门禁时，请按下面两种方式之一落地：
>
> 1. **收敛到零告警**（推荐，也是 `CONTRIBUTING.md` 的目标状态）——逐条修，修不动就调整规则或 token；
> 2. **只卡 error**（过渡方案）——用 `--json` 读报告后自己判断级别。报告的 JSON 结构是
>    `{"target", "ok", "counts": {"error","warn","info"}, "issues": [{"level","code","message","page","detail"}], "stats"}`：
>
>    ```sh
>    deepocean check out/deck.pptx --json > report.json    # 在 CI 里用 bash 重定向，不要用 PowerShell 的 `>`
>    python - <<'PY'
>    import json, sys
>    issues = json.load(open("report.json", encoding="utf-8"))["issues"]
>    sys.exit(1 if any(i["level"] == "error" for i in issues) else 0)
>    PY
>    ```
>
> 无论走哪条路，都不要把 `--strict` 从 CI 里删掉——它一旦不再运行，规范就会开始漂移。
>
> **Windows 用户注意**：PowerShell 的 `>` 默认写出 UTF-16 LE（带 BOM），Python 读会报
> `UnicodeDecodeError`。请用 `Out-File -Encoding utf8`，或干脆在 Python 进程内写文件。

### 5.1 给自己的 deck 加一道门禁（本地）

`.git/hooks/pre-commit`（`chmod +x` 后生效）：

```sh
#!/bin/sh
set -e
for deck in $(git diff --cached --name-only --diff-filter=ACM | grep -E 'deck.*\.(ya?ml|json)$'); do
  echo "deepocean check --strict $deck"
  deepocean check "$deck" --strict
done
```

### 5.2 最小 CI 工作流

如果只想给自己的论文仓库加检查，用这个（注意：**先 build 再检查 pptx**，才能覆盖几何 / 色彩规则；`check` 一次只接受一个目标）：

```yaml
name: deck-check
on: [push, pull_request]

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[dev]"
      - name: 生成产物（pptx + html + 报告）
        run: python -m deepocean.cli preview examples/demo-deck.yaml --out build
      - name: 静态检查（结构 / 节奏 / 占位）
        run: python -m deepocean.cli check examples/demo-deck.yaml --strict
      - name: 产物检查（几何 / 排版 / 色彩 / 对比度）
        run: python -m deepocean.cli check build/deep-ocean-demo.pptx --strict
      - uses: actions/upload-artifact@v4
        with:
          name: deck-preview
          path: build/
```

批量检查多个产物时自己包一层循环（一条命令只吃一个目标）：

```sh
for f in build/*.pptx; do python -m deepocean.cli check "$f" --strict || exit 1; done
```

### 5.3 只用 JSON 的极简 CI

不想在 CI 里装 PyYAML 时，把 deck 存成 JSON（`examples/minimal-deck.json` 是现成例子），`pip install -e .` 即可：

```yaml
      - run: pip install -e .
      - run: python -m deepocean.cli check examples/minimal-deck.json --strict
```

### 5.4 让报告可被机器读

`--json` 输出适合喂给编辑器、看板或 PR 评论机器人。建议把 JSON 报告作为 CI 产物上传，"为什么这次没过"永远有据可查：

```bash
deepocean check build/deep-ocean-demo.pptx --json > check-report.json
```

---

## 6 交付前 30 秒快查

按顺序跑完这四步再上讲台：

```bash
deepocean check deck.yaml --strict                # 1. 静态关：结构、节奏、占位文字
deepocean preview deck.yaml --out out/            # 2. 出 pptx + html + 报告
deepocean check out/*.pptx --strict               # 3. 产物关：几何、排版、色彩、对比度
```

4. 人眼关：把 `out/*.html` 用浏览器全屏翻一遍，对着第 1 节里标着"人工确认"的条目过一遍——**尤其是页脚的数据来源和每页自己写的那句判断**。

---

**延伸阅读**

- 每条阈值背后的设计理由与全部数值 → [`docs/STYLE.md`](STYLE.md)
- 规则引用的令牌定义与影响范围 → [`docs/TOKENS.md`](TOKENS.md)
- 改 deck / 换版式 / 手工复刻 → [`docs/TUTORIAL.md`](TUTORIAL.md)
- 参与开发与 PR 门禁 → [`CONTRIBUTING.md`](../CONTRIBUTING.md)
