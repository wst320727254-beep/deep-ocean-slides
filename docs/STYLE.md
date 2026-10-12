# Deep Ocean 风格规范（代码化版）

> **这份文件解决什么问题**：把《Deep Ocean 学术风 PPT · 风格规范与制作教程》里散落在 HTML 教程中的数值，整理成一份**可被代码执行、可被人工照抄**的规范。它同时是设计文档和实现契约。
>
> **谁该读它**：要改配色的设计师、要新增版式的贡献者、要拿这套风格去别的工具（PowerPoint / Keynote / Figma）复刻的人，以及任何想知道"为什么代码里是这个数字"的人。
>
> **权威顺序**：本文件的每一个 hex、px、字号都必须与 `src/deepocean/tokens.py` 一致；一旦两者冲突，**以代码为准**，并按 `CONTRIBUTING.md` 提 PR 修正文档。规范原文与代码的已知差异集中列在本文件 [§9](#9-规范与代码的已知差异)。

## 目录

| 章节 | 内容 |
|---|---|
| [0](#0-设计哲学) | 设计哲学、适用与不适用场景、风格 DNA |
| [1](#1-画布与栅格) | 画布规格、单位换算、四区母版、安全边距 |
| [2](#2-色彩系统) | 完整色板、配比预算、对比度实测、禁用清单 |
| [3](#3-字体与字号阶梯) | 字体家族、`TYPE_SCALE` 全表、排版铁律 |
| [4](#4-组件规格) | 卡片 / KPI / 图表 / 流程 / 矩阵 / 表格 |
| [5](#5-页面节奏规则) | peak–valley 节奏、非对称比例、Hero 配额 |
| [6](#6-12-页逐页坐标表) | 12 页版式的逐页坐标 |
| [7](#7-从规范到代码) | 每个数字对应哪个常量，改 token 就改全篇 |
| [8](#8-版式库) | 12 个 layout 的用途、必填字段、新增版式四步法 |
| [9](#9-规范与代码的已知差异) | 规范原文 vs 代码的不一致清单 |

---

## 0 设计哲学

### 0.1 一条总原则：像论文，不像海报

`tokens.TAGLINE_ZH = "像论文，不像海报"`（`tokens.py` 身份区）。判断一张页面是否合格，只问一个问题：**它更像期刊论文的一页，还是更像一张营销海报？**

学术可信的视觉来源是三件事，缺一不可：

1. **证据化配图** —— 图不是装饰，是数据。每张图都要能直接读数。
2. **卡体克制** —— 卡片是分区工具，不是视觉主角。没有阴影、没有渐变、没有立体感。
3. **层次清楚** —— 同一页里，读者视线路径唯一：标题 → 主体 → 关键数字。

### 0.2 适用 / 不适用场景

| 维度 | 取值 |
|---|---|
| 风格 DNA | 学术可信 · 撑满优先 · 证据化配图 · 卡体克制 · 层次清楚 · 色彩受控 |
| 适用场景 | 课题组组会、文献汇报、开题/中期、学术会议、学科评估、教学课件（理工医） |
| 不适用 | 产品发布、营销方案、政务党建、儿童/卡通、需要强情绪煽动的场合 |
| 情绪基调 | 克制、冷静、可信、专业。不做营销感，**不用大留白当风格** |
| 输出规格 | 16:9，12 页为默认篇幅（组会汇报的典型时长为 10–15 分钟） |

### 0.3 风格 DNA 表：每个特征如何在代码里落地

| DNA 特征 | 具体表现 | 代码位置 |
|---|---|---|
| 学术可信 | 固定四区母版，全篇位置不漂移 | `tokens.BANDS`、`tokens.CHROME_EXEMPT_LAYOUTS` |
| 撑满优先 | 内容区卡片填充率 ≥ 0.80 | `tokens.RHYTHM_RULES["min_content_fill"]` |
| 证据化配图 | 图表强制数据标签、强制显式高度 | `tokens.CHART` |
| 卡体克制 | 圆角 6/8、描边 1px、无阴影、无渐变 | `tokens.RADIUS`、`tokens.STROKE` |
| 层次清楚 | 三档文本色 + 全量字号阶梯 | `tokens.TEXT_COLORS`、`tokens.TYPE_SCALE` |
| 色彩受控 | 4 个品牌色 + 5 个表面色，配比预算写死 | `tokens.PALETTE`、`tokens.RATIO_BUDGET` |
| 节奏可预测 | Hero 4/12、非对称 83%、无连续 3 页 valley | `tokens.RHYTHM_RULES` |

### 0.4 内容页必须"撑满"

内容区可用高度是 `tokens.BANDS["content"]["h"] = 440`。内容页的卡片累计高度应达到内容区的 **≥ 80%**（`RHYTHM_RULES["min_content_fill"] = 0.80`，即 ≥ 352 px），元素**不得集中在画布中央 60% 区域**。

留白是封面与结尾页的专利，不是正文页的风格手段。封面/结尾是唯一两个豁免母版约束的版式：

```python
CHROME_EXEMPT_LAYOUTS = ("cover", "closing")   # tokens.py
```

---

## 1 画布与栅格

### 1.1 画布规格

| 项目 | 数值 | 换算 / 说明 |
|---|---|---|
| 画布尺寸 | `1280 × 720` px | = PowerPoint 默认 16:9 = 13.3333 × 7.5 in = 33.87 × 19.05 cm |
| px 基准密度 | 96 px/inch | 全仓库唯一的换算基准 |
| 左右安全边距 | `40` px | 内容可用宽度 = **1200 px** |
| 卡间距（gutter） | `20` px | 同一行卡片之间 |
| 顶条 A | y `0–60` | 高 60 |
| 标题块 B | y `72–140` | 高 68 |
| 内容区 C | y `200–640` | 高 440 |
| 页脚条 D | y `680–720` | 高 40，顶部 1px 分隔线 |

对应代码：

```python
CANVAS = {"width_px": 1280, "height_px": 720, "aspect": "16:9",
          "width_in": 13.3333, "height_in": 7.5,
          "width_cm": 33.87, "height_cm": 19.05, "px_per_inch": 96.0}

SAFE_MARGIN_PX = 40
CARD_GAP_PX = 20
CONTENT_WIDTH_PX = 1280 - 2 * 40          # 1200

BANDS = {"top_bar": {"y": 0,   "h": 60},
         "title":   {"y": 72,  "h": 68},
         "content": {"y": 200, "h": 440},
         "footer":  {"y": 680, "h": 40}}
```

四区之外还有一个"元素必须活在里面"的安全盒子（内容页）：

```python
SAFE_AREA = {"x": 40, "y": 60, "w": 1200, "h": 660}
```

> **注意 B 区的两种写法**：`BANDS["title"]` 给的是 `y=72, h=68`（真高）；规范原文写作"y 72–140"，那是**视觉占位区间**。写代码时用 `h=68`。

### 1.2 单位换算常数

```python
PT_PER_PX  = 0.75          # 字号
PX_PER_INCH = 96.0         # 位置
CM_PER_PX  = 2.54 / 96.0   # 0.0264583
MM_PER_PX  = 25.4 / 96.0
```

| 从 px 换算到 | 系数 | 示例 |
|---|---|---|
| 磅 pt（PowerPoint 字号） | × 0.75 | 30 px → 22.5 pt；44 px → 33 pt |
| 英寸 inch | ÷ 96（× 0.0104167） | 60 px → 0.625 in；1280 px → 13.3333 in |
| 厘米 cm | × 0.026458 | 40 px → 1.058 cm |
| EMU（python-pptx 内部） | ÷ 96 × 914400 | 1 px = 9525 EMU |
| Keynote（1920×1080） | × 1.5 | 40 px → 60 px |
| Figma（2560×1440） | × 2.0 | 40 px → 80 px |
| 4K（3840×2160） | × 3.0 | 40 px → 120 px |

完整换算表由 `deepocean units` 打印，实现见 `units.conversion_table()`，目标画布定义见 `units.TARGETS`（`pptx-16:9` / `keynote-1080p` / `figma-2x` / `4k`）。

### 1.3 四区母版骨架（全篇锁定一种）

```
┌──────────────────────────────────────────────────────────┐
│ A · 顶条 y0–60   深蓝实色 #1B3A5C                         │
│   ▪ x32,y26 8×8 青绿方块       刊名角标 右 24px / 13px 白字 │
├──────────────────────────────────────────────────────────┤
│ B · 标题块 y72–140（左右内缩 40）                          │
│   眉标 14 Bold #2E9BA6（字距 2.5）  y≈80                   │
│   主标 30 Bold #1B3A5C             y≈110                  │
│   副标 15 Regular #6B86A3          y≈136                  │
├──────────────────────────────────────────────────────────┤
│ C · 内容区 y200–640  宽 1200                               │
│   卡片 top=200，height=430–440，卡间距 20                   │
├──────────────────────────────────────────────────────────┤
│ D · 页脚 y680–720（高 40，顶部 1px #D6DCE5 分隔线）         │
│   左 x40,y692 单位名 12px #8B97A8   右 x1240 右对齐「NN/12」 │
└──────────────────────────────────────────────────────────┘
```

| 区 | 范围 | 元素与精确数值 | 代码 |
|---|---|---|---|
| **A 顶条** | y 0–60，通栏 | 深蓝实色 `#1B3A5C`；左侧 `x=32, y=26` 放 8×8 青绿方块 `#2E9BA6`；右侧距边 24 px、13 px 白字刊名（如 `ISR · 2025`） | `BANDS["top_bar"]` |
| **B 标题块** | y 72–140，左右内缩 40 | 眉标 `kicker` 14 px Bold `#2E9BA6`（**字距 2.5**）；主标 `page_title` 30 px Bold `#1B3A5C`；副标 `page_subtitle` 15 px `#6B86A3` | `TYPE_SCALE` + `BANDS["title"]` |
| **C 内容区** | y 200–640，宽 1200 | 卡片 `top=200`，`height=430/440`，左右卡间距 20；背景仅白 / 浅灰 / 浅青 | `BANDS["content"]` |
| **D 页脚** | y 680–720，高 40 | 顶部 1 px `#D6DCE5` 分隔线；左 `x=40, y=692` 单位名 12 px `#8B97A8`；右 `x=1240` 右对齐 12 px Bold `#1B3A5C` 页码「NN / 12」 | `BANDS["footer"]` |

**豁免规则**：只有 `cover` 与 `closing` 可以改动母版（封面保留深蓝顶条 60 + 左侧竖条；结尾改为加高顶条 + 底部色带）。其余 10 个版式必须严格四区齐全，且位置全篇一致。这条规则由 `CHROME_EXEMPT_LAYOUTS` 和 `schema.LAYOUTS[name]["chrome"]` 共同表达。

---

## 2 色彩系统

### 2.1 完整色板

主体 **≤ 4 色 + 中性色**（`<= 4 brand colours + neutrals`）。强调色只出现在焦点元素上，不铺满。

**品牌色（`tokens.PALETTE`，`role="brand"`）**

| Token | 色名 | Hex | 语义 / 用途 | 预算 |
|---|---|---|---|---|
| `navy` | 深海蓝 · 主色 | `#1B3A5C` | 顶条 / 主标题 / 强调数字 / 页码 / 深色卡底 | — |
| `teal` | 青绿 · 辅色 | `#2E9BA6` | 装饰条 / 互补品类 / 正向数据 / 图标 / 流程箭头 | — |
| `grayblue` | 灰蓝 · 中性 | `#6B86A3` | 副文 / 坐标轴标签 / 第三序列 / 无效应象限 | — |
| `brick` | 深砖红 · 警示 | `#C0392B` | 仅"减少 / 替代"类关键数字 | 单页 ≤ 3%，**全篇 ≤ 6%** |

**表面色（`role="surface"`）**

| Token | 色名 | Hex | 语义 / 用途 |
|---|---|---|---|
| `white` | 白 · 主背景 | `#FFFFFF` | 页面底色 / 白卡 |
| `light` | 浅灰 · 卡底 | `#F4F7FB` | 副卡片 / 图表容器 / 表格斑马 |
| `mint` | 浅青 · 高亮底 | `#E6F3F5` | 互补品类 / 关键结论条 |
| `pink` | 浅红 · 警示底 | `#FCE5E2` | 替代象限 / 负向数据卡 |
| `line` | 线框灰 | `#D6DCE5` | 描边 1 px / 表格线 / 分隔线 |

**文本色（`tokens.TEXT_COLORS`）**

| Token | 色名 | Hex | 用途 |
|---|---|---|---|
| `t1` | 文本主 | `#1A2230` | 正文主述、卡片标题 |
| `t2` | 文本副 | `#4A5568` | 说明文字、注解 |
| `t3` | 文本辅 | `#8B97A8` | 页脚、单位、来源标注 |

**语义角色（`tokens.ROLES`）**：版式代码只按角色取色，绝不写死 hex。

| 角色 | → Token | 用途 |
|---|---|---|
| `primary` | `navy` | 主色块、标题、主论证 |
| `accent` | `teal` | 强调条、箭头、正向数据 |
| `neutral` | `grayblue` | 中性说明、第三序列 |
| `danger` | `brick` | 警示、下降、替代 |
| `bg` / `surface` / `tint` / `alert_tint` / `stroke` | `white` / `light` / `mint` / `pink` / `line` | 背景与描边 |
| `ink` / `body` / `faint` | `t1` / `t2` / `t3` | 三档文字 |
| `up` / `down` / `flat` | `teal` / `brick` / `navy` | 数据升降语义 |
| `complementary` / `substitution` / `null_effect` | `teal` / `brick` / `grayblue` | 品类关系语义 |
| `neutral_number` | `navy` | 中性占比数字 |

用法：`primitives.rect(slide, 40, 200, 720, 430, fill="surface", line="stroke")`；`tokens.hex_of("accent") -> "#2E9BA6"`。

### 2.2 配比预算（`tokens.RATIO_BUDGET`，自检用）

按**渲染面积占比**计算，由 linter 的 C001/C004 检查：

| 色族 | 代码键 | 占比 | 说明 |
|---|---|---|---|
| 蓝族（`navy` + `grayblue`） | `blue_family` | 35–50% | 主导，撑起学术感 |
| 白底 | `white` | 35–55% | 让页面透气 |
| 浅青 / 浅灰 | `tint_family` | 0–20% | 卡片分区 |
| 红（警示） | `brick` | ≤ 6% | 超了就降饱和或改灰 |
| 金色 | `gold` | **0%** | 硬性禁止 |

```python
RATIO_BUDGET = {"blue_family": (35, 50), "white": (35, 55),
                "tint_family": (0, 20), "brick": (0, 6), "gold": (0, 0)}
RHYTHM_RULES["tint_family_max"] = 0.20     # 与 tint_family 上限一致
```

### 2.3 中性色要不要用红？先把对比度算出来

下表是对代码色板的**实测 WCAG 对比度**（`color.contrast_ratio()`，不是估计值）：

| Token | Hex | 白底 `#FFFFFF` | 深蓝底 `#1B3A5C` | 浅青底 `#E6F3F5` |
|---|---|---|---|---|
| `navy` | `#1B3A5C` | 11.63 | 1.00 | 10.24 |
| `teal` | `#2E9BA6` | **3.30** | 3.52 | 2.91 |
| `grayblue` | `#6B86A3` | **3.77** | 3.08 | 3.33 |
| `brick` | `#C0392B` | 5.44 | **2.14** | 4.79 |
| `white` | `#FFFFFF` | 1.00 | 11.63 | 1.13 |
| `light` | `#F4F7FB` | 1.07 | 10.82 | 1.06 |
| `mint` | `#E6F3F5` | 1.13 | 10.24 | 1.00 |
| `pink` | `#FCE5E2` | 1.20 | 9.66 | 1.06 |
| `line` | `#D6DCE5` | 1.38 | 8.43 | 1.22 |
| `t1` | `#1A2230` | 15.96 | 1.37 | 14.07 |
| `t2` | `#4A5568` | 7.53 | 1.54 | 6.63 |
| `t3` | `#8B97A8` | **2.96** | 3.92 | 2.61 |

`TYPE_RULES["min_contrast"] = 4.5`（WCAG AA）。由此得出三条**必须遵守的用法约束**：

1. `teal`、`grayblue`、`t3` 在**白底上达不到 4.5:1**（3.30 / 3.77 / 2.96）。它们只允许出现在：眉标、装饰条、轴标签、脚注、KPI 标签这类**辅助或大字号**位置，不得作为唯一承载正文信息的颜色。
2. `brick` 在**深蓝底上只有 2.14:1**，深蓝卡里不要放砖红文字；深蓝卡上的数字用白字，语义靠标签文字表达。
3. 正文请用 `t1`（15.96）或 `t2`（7.53）；深色底上用 `white`（11.63 on navy）。

### 2.4 禁用清单

机器可检的部分（`tokens.FORBIDDEN`，linter 的 C002 按色调 / 饱和度判定）：

| 规则 | 判定条件 | 说明 |
|---|---|---|
| 紫 / 粉 / 玫红 | 色相 270–345°，饱和度 ≥ 0.15 | 一律禁用 |
| 金色 | 色相 30–60°，饱和度 ≥ 0.45 | 含香槟金、土金 |
| 高饱和橙绿大色块 | 色相 85–165°，饱和度 ≥ 0.55 | 大色块禁用 |
| 纯黑大底 | hex == `#000000` | 禁用 |

只能人眼判断的部分（`tokens.BANNED_MOTIFS_ZH`，linter 的 C002/C003 报"人工确认"）：

- 彩虹渐变 / 渐变作卡片背景
- 3D、卡通、二次元、营销插画
- 楷体行书毛笔字
- 印章、烟花、金边装饰
- 同排 3 张以上等宽卡片（Hero 页 0 张）

---

## 3 字体与字号阶梯

### 3.1 字体家族（`tokens.FONTS`）

全篇**最多 2 套家族**（`max_families = 2`），由 T005 检查。

| 用途 | 字体家族（按回退顺序） | 说明 |
|---|---|---|
| 中文 | `Source Han Sans SC` → `Noto Sans CJK SC` → `Microsoft YaHei` → `PingFang SC` | 思源黑体 / 苹方回退 |
| 英文与数字 | `Inter` → `Source Sans 3` → `Segoe UI` → `Arial` → `Helvetica` | **数字统一用西文字体**，避免中文字体数字发虚 |
| 衬线（仅封面 / 引文） | `Times New Roman` → `Source Han Serif SC` | 可选，计入 2 套家族上限 |
| 等宽（文档 / 代码） | `SFMono-Regular` → `Consolas` → `Menlo` | 不用于幻灯片正文 |

PowerPoint 生成时的实际落盘字体族由 `FONTS["ppt_latin"]` / `FONTS["ppt_cjk"]` 决定；`build.patch_theme_xml()` 会把它们写进 `ppt/theme/theme1.xml` 的 `majorFont` / `minorFont`，这样 PowerPoint 自己的字体下拉框里显示的也是同一套字体。

### 3.2 字号阶梯（`tokens.TYPE_SCALE` 全表）

**px 是权威值，pt 是派生值**：`pt = px × 0.75`（`TypeToken.pt` 属性）。当前共 **23 档**（以 `deepocean tokens --md` 的输出为准，新增档位会同时出现在 HTML 的 CSS 变量里）。

| Token（role） | 中文名 | px | pt | 字重 | 颜色 | 字距 | 行高 | 用在哪 |
|---|---|---:|---:|---|---|---:|---:|---|
| `cover_title` | 封面中文主标 | 44 | 33.0 | bold | `navy` | 0 | 1.25 | 封面主标题（中/英） |
| `cover_subtitle` | 封面英文副标 | 26 | 19.5 | regular | `t1` | 0 | 1.35 | 封面副标题 |
| `cover_meta` | 封面信息 | 14 | 10.5 | regular | `t3` | 0 | 1.60 | 作者 / 单位 / 日期 |
| `section_number_lg` | 章节大数字（大） | 72 | 54.0 | bold | `navy` | 0 | 1.00 | 封面 / 核心结论页锚点 |
| `section_number` | 章节大数字 | 48 | 36.0 | bold | `teal` | 0 | 1.00 | 科学问题 02 / 03 |
| `page_title` | 页面主标 | 30 | 22.5 | bold | `navy` | 0 | 1.25 | B 区主标题 |
| `kicker` | 眉标 | 14 | 10.5 | bold | `teal` | **2.5** | 1.40 | `01 · BACKGROUND` 眉标 |
| `page_subtitle` | 页面副标 | 15 | 11.25 | regular | `grayblue` | 0 | 1.45 | 一句话副题 / 英文原题 |
| `card_title` | 卡内小标 | 18 | 13.5 | bold | `navy` | 0 | 1.35 | 卡片标题 |
| `card_title_sm` | 卡内小标（小） | 16 | 12.0 | bold | `navy` | 0 | 1.35 | 次级卡片标题 |
| `card_body` | 卡内正文 | 14 | 10.5 | regular | `t2` | 0 | 1.58 | 卡片正文，**下限 13 px** |
| `card_body_sm` | 卡内正文（小） | 13 | 9.75 | regular | `t2` | 0 | 1.55 | 密集列表 |
| `kpi_value` | KPI 巨数字 | 44 | 33.0 | bold | `teal` | 0 | 1.05 | 锚点数字（升/降/中性见 §4.2） |
| `kpi_value_sm` | KPI 巨数字（小） | 32 | 24.0 | bold | `navy` | 0 | 1.05 | 四卡并排时的次级数字 |
| `kpi_label` | KPI 标签 | 12 | 9.0 | regular | `grayblue` | 0 | 1.40 | 数字上方标签 |
| `kpi_note` | KPI 脚注 | 12 | 9.0 | regular | `t2` | 0 | 1.45 | 数字下方注解 |
| `table_head` | 表头 | 13 | 9.75 | bold | `white` | 0 | 1.35 | 白字 + 深蓝底 |
| `table_cell` | 表格正文 | 12.5 | 9.38 | regular | `t2` | 0 | 1.40 | 表格单元 |
| `node` | 流程节点 | 13 | 9.75 | bold | `white` | 0 | 1.30 | 节点文字 |
| `quote` | 金句 | 22 | 16.5 | bold | `navy` | 0 | 1.45 | 结论页金句 |
| `caption` | 注解 / 脚注 | 11.5 | 8.62 | regular | `t3` | 0 | 1.45 | 来源、单位、表号 |
| `footer` | 页脚 | 12 | 9.0 | regular | `t3` | 0 | 1.40 | 左下单位 / 来源 |
| `page_number` | 页码 | 12 | 9.0 | bold | `navy` | 0 | 1.40 | 右下 `NN / 12` |

### 3.3 排版铁律（`tokens.TYPE_RULES`，由 T001–T005 强制）

| 规则 | 常量 | 值 |
|---|---|---|
| 正文下限 | `min_px_body` | 13 px |
| 全文任意文字下限 | `min_px_any` | 11 px（仅脚注 / 注解） |
| 行高区间 | `carousel_line_height` | 1.5–1.6 |
| 字体家族上限 | `max_font_families` | 2 |
| 字重层级上限 | `max_weights` | 2（Bold + Regular） |
| 最小对比度 | `min_contrast` | 4.5（WCAG AA） |

四条必须记住的排版习惯：

1. **正文行高统一 1.5–1.6**；标题可以更紧（1.25–1.35），巨数字用 1.0–1.05。
2. **眉标必须加字距**（`kicker.letter_spacing = 2.5` px）才像学术刊头。
3. **全篇只用 2 套字重**：Bold + Regular。"Semibold" 在代码里归入 bold 档（`TypeToken.bold` 对 `semibold` 也返回 True），不要出现第三种。
4. **数字统一用西文字体**。

---

## 4 组件规格

### 4.1 卡片 Card

| 属性 | 标准值 | 变体 | 代码 |
|---|---|---|---|
| 圆角 | 6–8 px | 小卡 6，大卡 8 | `RADIUS = {"card_sm": 6, "card_lg": 8, "chip": 999, "node": 6}` |
| 描边 | 1 px `#D6DCE5` | 强调卡改 2 px 主色 / 辅色 / 警示色 | `STROKE = {"hairline": 1.0, "emphasis": 2.0, "accent_bar": 5.0}` |
| 内边距 | 上下 14–20，左右 ≥ 18 | 大卡 20–28，小卡 14–16 | `CARD_PADDING = {"sm": (14,16,14,16), "md": (18,20,18,20), "lg": (24,28,20,28)}`（顺序：上下左右） |
| 强调方式 | 左或上 4–6 px 色条 | 互补 `teal`／替代 `brick`／中性 `grayblue`／主论证 `navy` | `STROKE["accent_bar"] = 5.0` |
| 背景 | `#FFFFFF` / `#F4F7FB` / `#E6F3F5` / `#FCE5E2` | **禁止渐变**作卡背景 | `PALETTE` surface 档 |
| 深蓝实色卡 | `#1B3A5C` 底 + 白字 + 青绿小标 | 单页 ≤ 1 张，全篇 ≤ 3 张，多卡页禁用 | `role="primary"` |
| 同排卡 | 等高，高差 ≤ 8 px | 用均分，不用固定高度堆叠 | — |

**卡内五段骨架**（S1 / S3 / S4 必填）：

| 段 | 内容 | 示例 |
|---|---|---|
| S1 标题条 | 眉标 + 小标 | 「COMPLEMENTARY · 互补」+「家具 / 杂货」 |
| S2 引导句 | 一句现象描述 | 「关掉个人数据后算法只能推大众爆款」 |
| S3 主体 | 图 或 要点列表 | 柱状图 / 3 条 bullet |
| S4 关键数据 | **锚底**，必填 | 「推荐 +328% → 搜索 +26%」 |
| S5 尾部标签 | 可选 | 「Table 3」「p < 0.01」 |

在 `deck.yaml` 里，S1 的 chip、S4 的 footer 都是卡对象的字段：

```yaml
- title: 家具 / 杂货：推荐带动搜索
  chip: COMPLEMENTARY
  chip_en: 互补
  body: 需要多轮比较、决策链路长的品类，推荐位把用户送进搜索做深挖。
  items: ["家具：推荐 +328%，搜索 +26%", "杂货：推荐 +320%，搜索 +26%"]
  footer: Table 3 · 互补品类
  tone: accent
```

### 4.2 KPI 巨数字

| 属性 | 数值 | 说明 | 代码 |
|---|---|---|---|
| 数字字号 | 32 / 44 / 48 / 72 px | 24 / 33 / 36 / 54 pt | `KPI["value_sizes"]`，对应 `kpi_value_sm` / `kpi_value` / `section_number` / `section_number_lg` |
| 标签字号 | 12 px（9 pt） | `grayblue`，置于数字**上方** | `kpi_label`，间距 `KPI["label_gap"] = 6` |
| 脚注字号 | 12 px | `t2`，置于数字**下方** | `kpi_note`，间距 `KPI["note_gap"] = 4` |
| 单列最小宽度 | 150 px | 四卡并排时不得再窄 | `KPI["min_col_width"]` |
| 颜色语义 | 下降 / 负向 = `#C0392B`；上升 / 正向 = `#2E9BA6`；中性占比 = `#1B3A5C` | `tone: down / up / flat` → `ROLES` 的 `down` / `up` / `flat` | — |

```yaml
kpis:
  - {value: "−33.4%", label: 推荐渠道 浏览 PV, note: "−39.03***", tone: down}
  - {value: "+7.1%",  label: 搜索渠道 浏览 PV, note: "+8.532***", tone: up}
  - {value: "22%",    label: 浏览 PV 补偿比例, note: 搜索补回推荐损失的两成, tone: flat}
```

### 4.3 图表 Chart

| 属性 | 设置 | 说明 | 代码 |
|---|---|---|---|
| 类型 | `bar`（纵向柱）/ `line` / `doughnut` | 对比用柱；趋势用线；占比用环 | `CHART["default_type"] = "bar"` |
| 分组 | `clustered` | 多系列并排 | `CHART["grouping"]` |
| 高度 | **必须显式给**，230–400 px | 不给高度会渲染成 0 | `CHART["height_px"]`、`CHART["require_explicit_height"] = True` |
| 数据标签 | 开启 | 学术汇报要能直接读数 | `CHART["show_data_labels"] = True` |
| 系列配色 | `navy` / `teal` / `grayblue` / `brick` | 三、四系列按序取用 | `CHART["series_colors"]` |
| 轴 / 图例 / 标题 / 标签色 | 轴 `grayblue`，图例 `t2`，标题 `navy`，数据标签 `t1` | 中性灰不抢戏 | `CHART` 对应键 |
| 网格线 | `None` | 不画网格线 | `CHART["gridlines"]` |
| 数值格式 | 纯数字，带 `%` | 负数直接带 `−` 号，**不要括号** | — |

### 4.4 流程 / 机制图 Flow

| 属性 | 数值 | 说明 | 代码 |
|---|---|---|---|
| 节点尺寸 | 110–130 × 50 px | 圆角 6 | `FLOW["node_w"]` / `FLOW["node_h"]` / `RADIUS["node"]` |
| 节点底色 | 已发生 = `navy`；关键转折 = `teal` 或 `brick` | 白字 | `role="primary" / "accent" / "danger"` |
| 箭头 | 19 px 字符「→」，或 1.6 pt 直线箭头 | 互补 = `teal`；替代 = `brick` | `FLOW["arrow_px"] = 19`、`primitives.add_arrow()` |
| 节点间距 gap | 8–16 px | 横向排布 | `FLOW["gap_px"]` |

### 4.5 2×2 矩阵 Matrix

| 属性 | 数值 | 说明 | 代码 |
|---|---|---|---|
| 象限尺寸 | 380 × 190 px | 间距 20 | `MATRIX["quadrant_w"]` / `["quadrant_h"]` / `["gap_px"]` |
| 象限底色 | 互补 `mint` / 替代 `pink` / 无效 `light` | 配 2 px 同色系描边 | `STROKE["emphasis"]` |
| 中心锚点 | 20 × 20 圆点 `navy` | 十字交叉处 | `MATRIX["center_dot"]`、`center_label` |
| 象限内结构 | 编号（11 px）→ 假设名（16 px Bold）→ 条件 + 结果（12 px）→ 脚注（11 px 斜体） | **四象限结构必须一致** | 字段 `no / title / condition / result / note` |

象限书写顺序固定为 **LT → RT → LB → RB**（左上、右上、左下、右下）。

### 4.6 表格 Table

| 属性 | 数值 | 说明 | 代码 |
|---|---|---|---|
| 表头 | `#1B3A5C` 底 + 白字 Bold，13 px | — | `TABLE["head_fill"]` / `["head_text"]`、`table_head` |
| 斑马纹 | 奇数行白 / 偶数行 `#F4F7FB` | 关键格用 `#E6F3F5` 或 `#FCE5E2` 高亮 | `TABLE["zebra"]` / `["highlight"]` / `["highlight_neg"]` |
| 格线 | 1 px `#D6DCE5` | 数值居中或右对齐 | `TABLE["grid"]` |
| 字号 | 12.5–13 px（9.38–9.75 pt） | 表头 Bold | `table_cell` / `table_head` |

表格是**备用组件**：能用图就不用表；一页最多 8 行数据。

---

## 5 页面节奏规则

节奏规则写死在 `tokens.RHYTHM_RULES`，由 linter 的 L001–L003、R001–R006 检查。

| 规则 | 常量 | 值 | 含义 |
|---|---|---|---|
| Hero 页配额 | `hero_ratio` | `(4, 12)` | 12 页里 **4 页**是 peak（封面 / 主效应 / 关键发现 / 结尾） |
| 非对称版式比例 | `asymmetry_ratio` | `0.83` | ≥ 83% 的页面必须是非对称版式 |
| 等宽卡片横排上限 | `equal_width_card_rows_max` | `2` | 全篇 ≤ 2 页 |
| Hero 页等宽卡片 | `hero_equal_width_rows` | `0` | Hero 页**禁止**等宽卡片横排 |
| 连续 valley | `no_three_valleys` | `True` | 不允许连续 3 页低谷 |
| 图表页占比 | `chart_pages_max_share` | `0.40` | 「左大图 + 右侧文字」+「非对称双栏」合计 ≤ 40% |
| 内容填充率 | `min_content_fill` | `0.80` | 卡片累计高度 ≥ 内容区 80% |
| 视觉锚点 | `min_anchor_px` | `44` | 每页至少一个 ≥ 44 px 的元素，或 ≥ 40% 面积的主视觉 |
| 浅色底占比 | `tint_family_max` | `0.20` | 与 `RATIO_BUDGET["tint_family"]` 上限一致 |

`HERO_LAYOUTS = ("cover", "key_findings", "closing")` 是"哪些版式算 peak"的代码表达；`schema.LAYOUTS[name]["hero"]` 与它必须一致（见 §9）。

**版式排布规则（改页数时照此推导）**：

1. 相邻两页版式不得相同；
2. 连续 2 页对称版式必须打断（本项目只有 `data_table` 是对称版式，`schema.LAYOUTS["data_table"]["asymmetric"] == False`）；
3. 等宽 N 卡片横排全篇 ≤ 2 页；
4. Hero 页禁用等宽卡片横排；
5. 「左大图 + 右侧文字」+「非对称双栏」合计不超过全篇 40%。

---

## 6 12 页逐页坐标表

全部坐标基于 1280 × 720 画布、左上角原点，单位 px。右边缘统一收敛到 `1240`（= 1280 − 40），卡与卡之间留 20 px gutter。

| # | 页面 | 版式（layout） | 布局坐标与要点 |
|---|---|---|---|
| 01 | 封面 | `cover` | 顶条 h60；左竖条 `x0 w6 y120 h480`；主标区 `top150 left72`；分隔线 `top410 w160 h2` 青绿；作者区 `top440`；信息条 `top580`；底部色带 h8 |
| 02 | 研究背景 | `two_column` | 左卡 `x40 y200 w720 h430`（浅灰，左边框 6 px 青绿）；右卡 `x780 w460`（3 张小卡 + 1 张深蓝解法卡） |
| 03 | 三个科学问题 | `big_number` | 左大卡 `x40 w580 h430`（「01」72 px）；右上 `x640 y200 w320 h200`（「02」48 px）；右下 `y430 h210`（「03」48 px） |
| 04 | 实验设计 | `experiment_design` | 流程区 `top200 h120`（3 步 `380×80` + 24 px 箭头）；对比区 `top350 h280`（Control 白卡 / VS / Treatment 浅青 + 红框） |
| 05 | 技术路线 | `roadmap` | 左深蓝标题栏 `x40 w360 h430`；右 `x420` 三步列表（56 px 圆点序号 + 卡片，gap 18） |
| 06 | 主效应 | `chart_insight` | 图表卡 `x40 w700 h440`（Chart h390）；右侧 `x760` 4 张卡（3 KPI + 1 深蓝 IV 卡） |
| 07 | 品类异质性 | `split_cards` | 左互补卡 `x40 w660 h440`（浅青，**上**边框 6 px 青绿）；右替代卡 `x720 w520 h440`（浅灰，上边框 6 px 红） |
| 08 | 概念框架 | `concept_flow` | 左形成 `x40 w580 h440`；中央箭头 `x625 w30 y380`（`⇄` + update）；右满足 `x660 w580 h440` |
| 09 | 2×2 机制矩阵 | `matrix2x2` | 左维度说明 `x40 w340 h440`；右矩阵 `x400 w840`（4 象限 `380×190`，中心 20 px 圆点） |
| 10 | NLP 搜索词证据 | `chart_insight` | 图表卡 `x40 w720 h440`（Chart h400）；右侧 `x780 w460`（2 张解读卡 + 1 张深蓝结论卡） |
| 11 | 关键发现与启示 | `key_findings` | 核心结论横幅 `top200 h110` 通栏深蓝（内嵌 3 个 44 px 数字）；下方 `top330 h310`，首卡宽 560 + 两张均分 |
| 12 | 总结与展望 | `closing` | 加高顶条 h100；金句区 `top140`（浅青，左边框 6 px，标题 22 px）；下方 `top350 h270` 左右两卡（局限白卡 / 未来深蓝卡）；致谢条 bottom50 |

页码规则的补充：正文页 D 区页码为「NN / 12」，`cover` 与 `closing` 不画页脚（`chrome: false`）。

> **参考 deck 的页数**：仓库内置的 `examples/demo-deck.yaml` 是 **13 页**——上表 12 页（第 11 页换成 `key_findings`、第 12 页是 `closing`）之外，多出一页 `data_table` 附录，用来演示备用表格版式并承载论文 Table 1 / Table 2 的完整数值。`RHYTHM_RULES["equal_width_card_rows_max"] = 2` 之内，`data_table`（全篇唯一的对称版式）只出现这一次。

---

## 7 从规范到代码

这一节是整份文档的核心：**规范里的每个数字，在代码里都有一个唯一的家。**

### 7.1 数字 → 常量对照表

| 规范里的说法 | 代码里的唯一来源 | 举例 |
|---|---|---|
| 画布 1280 × 720 | `tokens.CANVAS["width_px"]` / `["height_px"]` | 生成器用它设 `prs.slide_width` |
| 安全边距 40 | `tokens.SAFE_MARGIN_PX` | 所有版式的左边界 |
| 内容宽度 1200 | `tokens.CONTENT_WIDTH_PX` | `1280 - 2*40` |
| 卡间距 20 | `tokens.CARD_GAP_PX` | 双栏版式的中缝 |
| 顶条 y 0–60 | `tokens.BANDS["top_bar"]["y"]` / `["h"]` | — |
| 标题块 y 72–140 | `tokens.BANDS["title"]` | `y=72, h=68` |
| 内容区 y 200–640 | `tokens.BANDS["content"]` | `y=200, h=440` |
| 页脚 y 680–720 | `tokens.BANDS["footer"]` | — |
| 主色 `#1B3A5C` | `tokens.PALETTE["navy"].hex`，或 `tokens.hex_of("navy")` | 也等于 `tokens.hex_of("primary")` |
| 页面主标 30 px / 22.5 pt | `tokens.TYPE_SCALE["page_title"].px` / `.pt` | 版式代码用 `style("page_title")` |
| 眉标字距 2.5 | `tokens.TYPE_SCALE["kicker"].letter_spacing` | 写入 OOXML 的 `a:rPr/@spc` |
| 卡片圆角 6 / 8 | `tokens.RADIUS["card_sm"]` / `["card_lg"]` | `primitives.rect(..., radius=...)` |
| 强调色条 5 px | `tokens.STROKE["accent_bar"]` | 左侧 4–6 px 色条取中值 |
| 图表高度 230–400 | `tokens.CHART["height_px"]` | 不给就报 H002 |
| 象限 380 × 190 | `tokens.MATRIX["quadrant_w"]` / `["quadrant_h"]` | `layouts.py` 的矩阵版式 |
| 流程节点 110–130 × 50 | `tokens.FLOW["node_w"]` / `["node_h"]` | — |
| 正文下限 13 px | `tokens.TYPE_RULES["min_px_body"]` | 报 T002（T001 是 11 px 硬下限） |
| 对比度 4.5:1 | `tokens.TYPE_RULES["min_contrast"]` | 报 K001，实现在 `color.contrast_ratio()` |
| 红色 ≤ 6% | `tokens.RATIO_BUDGET["brick"]` | 报 C003（只算 `#C0392B` 墨色） |
| 金色 = 0 | `tokens.RATIO_BUDGET["gold"]`、`tokens.FORBIDDEN` | 报 C002 |
| Hero 4/12 | `tokens.RHYTHM_RULES["hero_ratio"]` | 报 R002 |
| 非对称 83% | `tokens.RHYTHM_RULES["asymmetry_ratio"]` | —（人工判断） |
| 填充率 ≥ 80% | `tokens.RHYTHM_RULES["min_content_fill"]` | 报 M003 |
| 锚点 ≥ 44 px | `tokens.RHYTHM_RULES["min_anchor_px"]` | 报 A001 |
| 双栏比例 60:40 | `schema.LAYOUTS["two_column"]["fields"]["ratio"]["default"] = 0.60` | 也可在 deck 里覆写 |
| 12 个版式 | `schema.LAYOUTS`（键名即 layout 名） | `deepocean layouts` 打印 |
| 封面 / 结尾豁免母版 | `tokens.CHROME_EXEMPT_LAYOUTS`、`schema.LAYOUTS[name]["chrome"]` | — |

### 7.2 换算公式的代码位置

| 公式 | 函数 |
|---|---|
| `pt = px × 0.75` | `tokens.TypeToken.pt`、`units.px_to_pt()` |
| `inch = px / 96` | `units.px_to_inch()` |
| `cm = px × 2.54 / 96` | `units.px_to_cm()` |
| `EMU = px / 96 × 914400` | `units.px_to_emu()` |
| `target = px × (宽 / 1280)` | `units.scale_for()`、`units.scale_value()` |

### 7.3 "改 token 就改全篇"的工作方式

生成链路上没有任何一处写字面 hex 或字号：

```
tokens.py  ──┬─→ layouts.py / components.py / charts.py ─→ build.py ─→ out.pptx   （PowerPoint 几何）
             ├─→ html.py ─────────────────────────────────→ out.html              （同像素网页版）
             ├─→ check.py  ───────────────────────────────→ 自检报告                （linter 阈值）
             └─→ cli.py    ───────────────────────────────→ deepocean tokens --css  （CSS 变量）
```

`check.py` 的依赖边界是刻意的：它只依赖 `tokens` / `schema` / `spec` / `color` / `units` / `primitives`，**不依赖** `layouts` / `components` / `build`——linter 必须能审查版式代码自己产出的文件，否则就成了自证。

因此：

- 把 `PALETTE["teal"].hex` 改成另一个青绿，**pptx、html、自检报告会同时变**；
- 把 `SAFE_MARGIN_PX` 从 40 改成 32，所有版式的左右边界一起移动，`CONTENT_WIDTH_PX` 自动变成 1216；
- 把 `TYPE_SCALE["card_body"].px` 从 14 改成 15，所有版式的卡内正文（包括自检的 T001 下限判断）一起变。

**三条纪律**：

1. 版式代码只按**角色名**取色（`"accent"`、`"surface"`），不写 hex；
2. 文本只用 `style("token_name")`（`primitives.style()`），不写裸 px 字号；
3. 位置只用 `tokens.BANDS[...]` / `tokens.SAFE_MARGIN_PX` / `tokens.CARD_GAP_PX` 推导，不写魔数。

`deepocean tokens --json` 输出的就是这套单一事实来源（`tokens.summary()`），`--css` 输出的是同一份数据的 CSS 变量形式（`tokens.css_variables()`），可直接粘进网页版做设计稿。

---

## 8 版式库

12 个 layout 定义在 `schema.LAYOUTS`，由 pptx 生成器与 HTML 渲染器**共同实现**。字段说明随时用 `deepocean layouts` 或 `deepocean layouts two_column` 打印。

| 顺序 | layout | 中文用途 | Hero | 共用母版 | 非对称 | 必填字段 |
|---:|---|---|:--:|:--:|:--:|---|
| 1 | `cover` | 封面 | ✔ | ✘（自绘） | ✔ | —（全部可选） |
| 2 | `two_column` | 研究背景、非对称双栏 | ✘ | ✔ | ✔ | `left`, `right` |
| 3 | `big_number` | 科学问题、巨型数字 + 洞察 | ✘ | ✔ | ✔ | `items` |
| 4 | `experiment_design` | 实验设计（流程 + 对比） | ✘ | ✔ | ✔ | `steps`, `groups` |
| 5 | `roadmap` | 技术路线（左标题栏 + 右步骤） | ✘ | ✔ | ✔ | `aside`, `steps` |
| 6 | `chart_insight` | 主效应 / 证据（左图表 + 右洞察） | ✘ | ✔ | ✔ | `chart` |
| 7 | `split_cards` | 品类异质性（双栏对比卡） | ✘ | ✔ | ✔ | `left`, `right` |
| 8 | `concept_flow` | 概念框架（左 → 中 → 右） | ✘ | ✔ | ✔ | `left`, `center`, `right` |
| 9 | `matrix2x2` | 2×2 机制矩阵 | ✘ | ✔ | ✔ | `aside`, `quadrants` |
| 10 | `data_table` | 附录数据表（全篇唯一对称版式） | ✘ | ✔ | ✘ | `columns`, `rows` |
| 11 | `key_findings` | 关键发现（结论横幅 + 启示） | ✔ | ✔ | ✔ | `banner`, `cards` |
| 12 | `closing` | 总结与展望 | ✔ | ✘（自绘） | ✔ | `quote`, `panels` |

> 12 页参考 deck 使用其中 **11 个**版式；`data_table` 是备用版式，示例 deck 以附录页形式演示。

**别名**（`schema.ALIASES`，写 deck 时可用）：`intro`/`title` → `cover`，`two-col`/`2col` → `two_column`，`chart` → `chart_insight`，`table` → `data_table`，`matrix` → `matrix2x2`，`flow` → `concept_flow`，`end`/`thanks` → `closing`。

### 8.1 各版式的字段速查

`deepocean layouts` 是权威输出；下面是常用版式的可直接照抄形态：

```yaml
# cover
- layout: cover
  title: 推荐如何影响消费者搜索
  title_en: A Field Experiment on Recommendation and Search
  data:
    english_title: How Recommendation Affects Customer Search: A Field Experiment
    authors: 汇报人 · 你的名字
    affiliation: 单位 · 方向 · 日期
    series: ISR · 2025
    note: 样本 555,800 名用户 · 26 个产品类目
    band: Yuan, Chen, Wang & Sun (2025), ISR 36(1): 84-106

# chart_insight
- layout: chart_insight
  kicker: 05 · MAIN EFFECT
  title: 主效应：推荐塌陷，搜索只补回一小部分
  subtitle: 禁用个人数据后各渠道相对变化（%）
  hero: true
  data:
    side_ratio: 0.60
    chart:
      type: bar
      title: 推荐渠道与搜索渠道的变化幅度
      categories: [浏览 PV, 点击, 订单, 销售额]
      series:
        - {name: 推荐渠道, values: [-33.4, -83.6, -85.9, -81.1], color: navy}
        - {name: 搜索渠道, values: [7.1, 6.3, 7.1, 6.4], color: teal}
      unit: "%"
      height: 390          # 必填，230–400
      note: 所有系数在 1% 水平显著
    kpis:
      - {value: "−33.4%", label: 推荐渠道 浏览 PV, note: "−39.03***", tone: down}
    cards:
      - {title: 越靠后的漏斗环节，补偿越弱, body: 浏览 22% → 点击 7%。, tone: plain}
    takeaway: {label: IV 弹性, text: 推荐 PV 每减少 1 单位，搜索 PV 增加 0.219***}
```

其余版式的字段名与其含义见 `schema.LAYOUTS`，或运行：

```bash
deepocean layouts                 # 全部 12 个版式的字段表
deepocean layouts matrix2x2       # 单个版式
```

### 8.2 新增一个版式的四步法

1. **改 `schema.py`** —— 在 `LAYOUTS` 里加一项，声明 `zh` / `en` / `hero` / `chrome` / `asymmetric` 与 `fields`（每个字段用 `_f(type, required, note, default)`）。
2. **实现 `layouts.py`** —— 加 `render_<layout>(slide, page, ctx)`，只用 `primitives` 的几何助手与 `tokens` 的角色名，禁用裸 hex / 裸字号。
3. **实现 `html.py`** —— 加同名分支，让网页版与 pptx 同像素。
4. **加示例** —— 往 `examples/demo-deck.yaml` 加一页真实内容，`deepocean preview` 生成 pptx + html + 自检报告，`deepocean check --strict` 必须通过。

四步都完成之前，`schema.LAYOUTS` 与渲染器会不一致——这会让 HTML 预览能在 PowerPoint 里失败，是明确禁止的状态。

---

### 8.1 `image_evidence` —— 图片证据页（第 13 个版式）

论文原图是"证据化配图"最直接的形式，但它也最容易破坏版式节奏，所以规则很硬：

| 项 | 规定 |
|---|---|
| 张数 | **全篇 ≤ 2 页**（`from-paper` 默认只排 1 页）；图片是证据，不是装饰 |
| 画布 | 左侧图片卡占 `left_w = (1200 - 20) × side_ratio`（`side_ratio` 0.50–0.72，默认 0.62），高 440 |
| 图片 | 一律 **contain** 等比缩放居中，四边留 1px `#D6DCE5` 细框，绝不拉伸、绝不裁切正文 |
| 图注 | 卡内底部 11.5px `t2`；来源单独一行 11.5px `t3`，写清"第 N 页 / 文件名" |
| 右栏 | 2–3 张解读卡（`card_head`）+ 可选深蓝"解读"卡；与 `chart_insight` 同一套预算逻辑 |
| 缺图 | 画浅灰占位框并写明缺失路径（不静默跳过，也不让 build 失败） |

> 判断标准：把图拿掉，这一页的文字是否还成立？如果成立，说明你排的是"装饰"而不是"证据"。
> 想插图时优先问自己：这张图是**数据**（可读数）还是**示意**（只能看个大概）。规范只欢迎前者。

```yaml
- layout: image_evidence
  kicker: 04 · EVIDENCE
  title: 框架图：推荐如何影响搜索
  data:
    side_ratio: 0.62
    image:
      path: figures/p32-fig01.png     # 相对 deck 文件，或绝对路径
      caption: Figure 2 Conceptual Framework for Customer Search
      source: 来源：PlatStrat2023_paper_15.pdf · p32
      fit: contain
    cards:
      - {title: 图里是谁在动, body: 推荐位把用户推向搜索，箭头方向即因果方向。}
    takeaway: {label: 解读, text: 图与表一致：互补品类补回三成，替代品类几乎为零。}
```

---

## 9 规范与代码的已知差异

以下差异以 `tokens.py` 为准，列出是为了让复刻者不踩坑。**每一项都是待收敛项，不是可选风格。**

| # | 规范原文（HTML 教程） | 代码（权威） | 处理方式 |
|---|---|---|---|
| 1 | 顶条高 60、标题块"y 72–140"、内容区"y 200–640"、页脚"680–720" | `BANDS` 用 `h` 表示：`title h=68`（72–140），`content h=440`（200–640） | 数值等价，文档统一按 `BANDS` 写 |
| 2 | 卡片圆角"6–8 px（小卡 6，大卡 8）" | `RADIUS = card_sm 6 / card_lg 8` | 规范给区间，代码取两端点 |
| 3 | 强调色条"4–6 px" | `STROKE["accent_bar"] = 5.0` | 代码取中值 |
| 4 | 卡片内边距"上下 14–20，左右 ≥ 18" | `CARD_PADDING sm (14,16,14,16)` / `md (18,20,18,20)` / `lg (24,28,20,28)` | 三档离散化 |
| 5 | 眉标"字间距 2–3" | `kicker.letter_spacing = 2.5` | 代码取中值 |
| 6 | 表格字号"12–13 px" | `table_head 13` / `table_cell 12.5` | 落在区间内 |
| 7 | 卡内正文"13–15 px" | `card_body 14` / `card_body_sm 13` | 落在区间内 |
| 8 | 卡内小标"16–22 px" | `card_title 18` / `card_title_sm 16` | 落在区间内，22 px 由 `quote` 承担 |
| 9 | 章节大数字"72 / 48"配 `navy` / `teal` / `grayblue` 三色 | `section_number_lg` 只有 `navy`；`section_number` 只有 `teal` | 代码未提供 `grayblue` 变体；需要时用 `T("03", "section_number", color="grayblue")` 覆写 |
| 10 | 封面中文副标 26 px / 19.5 pt | `cover_subtitle` 26 px / 19.5 pt；`cover_meta` 14 px / 10.5 pt | 一致 |
| 11 | 页脚 / 页码 12 px，左 `grayblue`、右 `navy` Bold | `footer` 12 px 但颜色是 `t3`（`#8B97A8`）；`page_number` 12 px `navy` Bold | 色值 `#8B97A8` 相同，token 名为 `t3` |
| 12 | 「等宽 N 卡片横排 = 0」 | `RHYTHM_RULES["equal_width_card_rows_max"] = 2`（全篇最多 2 页），`hero_equal_width_rows = 0` | 代码更宽松：非 Hero 页允许 ≤ 2 页 |
| 13 | "Hero 页 4/12（封面 / 主效应 / 关键发现 / 结尾）" | `HERO_LAYOUTS = ("cover", "key_findings", "closing")`；`RHYTHM_RULES["hero_ratio"] = (4, 12)` | 代码只标记 3 个 Hero 版式；第四个 peak 由页面级 `hero: true` 显式声明（示例 deck 把第 06 页标为 `hero: true`） |
| 14 | 复刻教程路线 A 的 PowerPoint 复刻步骤 | 与 `deepocean build` 产出的主题色 / 字体一致 | 见 `docs/TUTORIAL.md` 路线 B |
| 15 | "浅青 / 浅灰底色族 0–20%" | `C004` 只把 `mint` / `pink`（强调底色）按 35% 上限判，`#F4F7FB` 是**卡片底色**、不计入 | 一张"撑满"的卡片本身就有 ~30% 画面，20% 与"卡片撑满"不可同时满足，见 §9 结尾的实测 |
| 16 | "红色 ≤ 6%" | `C003` 只统计砖红**墨色** `#C0392B`；`#FCE5E2` 浅红底归入强调底色 | 浅红底在规范里是"替代象限 / 负向数据卡"的合法底色，按红墨算会必然超标 |
| 17 | "无连续 3 页 valley" | `R003` 降为 `info` | 规范的参考 deck 自己就是 01/06/11/12 四个 Hero，必然出现 4 页连续谷底 |
| 18 | "正文 ≥ 13 px" | `T002` 只判**会换行的正文**（内容区 + ≥30 字 + ≥2 行） | `caption` 11.5 / `footer` 12 / `kpi_label` 12 是 `TYPE_SCALE` 里的合法辅助档 |

**对比度相关**：`teal` (3.30)、`grayblue` (3.77)、`t3` (2.96) 在白底上低于 `TYPE_RULES["min_contrast"] = 4.5`；`brick` 在深蓝底上为 2.14。这不是实现 bug，而是色板本身的性质，因此用法约束写在 §2.3——三色仅用于辅助 / 大字号位置。

---

**延伸阅读**

- 令牌逐个的语义、影响范围与兼容约定 → [`docs/TOKENS.md`](TOKENS.md)
- 用 CLI / PowerPoint / Keynote / Figma / Python API 复刻 → [`docs/TUTORIAL.md`](TUTORIAL.md)
- 交付前逐条自检与 CI 接入 → [`docs/CHECKLIST.md`](CHECKLIST.md)
- 参与开发 → [`CONTRIBUTING.md`](../CONTRIBUTING.md)
