# Deep Ocean 设计令牌参考（TOKENS）

> **这份文件解决什么问题**：`src/deepocean/tokens.py` 是整套设计系统的**单一事实来源**。这份手册逐个说明每个令牌的名称、值、语义、在代码里的位置，以及"改它会影响什么"。需要精确取值时查这里，不要在版式里写死数字。
>
> **谁该读它**：要改设计令牌的人、要把令牌接到别的工具（CSS / Figma / 内部设计稿）的人、要写新版式或新组件的贡献者，以及需要确认"这个 token 名能不能改"的 API 使用者。

## 目录

| 章节 | 内容 |
|---|---|
| [1](#1-令牌的分层) | 身份 / 画布 / 色彩 / 字体 / 组件 / 规则 |
| [2](#2-身份令牌) | `NAME` `VERSION` `HOMEPAGE` … |
| [3](#3-画布与栅格令牌) | `CANVAS` `BANDS` `SAFE_MARGIN_PX` `CARD_GAP_PX` `SAFE_AREA` |
| [4](#4-色彩令牌) | `PALETTE` `TEXT_COLORS` `ROLES` `RATIO_BUDGET` `FORBIDDEN` |
| [5](#5-字体令牌) | `FONTS` `TYPE_SCALE` `TYPE_RULES` |
| [6](#6-组件几何令牌) | `RADIUS` `STROKE` `CARD_PADDING` `KPI` `CHART` `FLOW` `MATRIX` `TABLE` |
| [7](#7-节奏令牌) | `RHYTHM_RULES` `HERO_LAYOUTS` `CHROME_EXEMPT_LAYOUTS` |
| [8](#8-单位换算与目标画布) | `units` 公式、`TARGETS` 缩放系数、换算表 |
| [9](#9-cli-输出格式) | `deepocean tokens` 的 JSON / Markdown / CSS 三种导出 |
| [10](#10-版本与向后兼容约定) | token 名属于公共 API |

---

## 1 令牌的分层

`tokens.py` 自上而下分六层，每层只依赖它上面的层：

| 层 | 内容 | 谁消费 |
|---|---|---|
| 身份 | `NAME` `NAME_ZH` `VERSION` `TAGLINE_*` `LICENSE` `HOMEPAGE` | CLI `version`、pptx 文档属性、HTML `<title>` |
| 画布 | `CANVAS` `SAFE_MARGIN_PX` `CARD_GAP_PX` `CONTENT_WIDTH_PX` `BANDS` `SAFE_AREA` | 所有版式的坐标基准 |
| 色彩 | `PALETTE` `TEXT_COLORS` `ROLES` `RATIO_BUDGET` `FORBIDDEN` `BANNED_MOTIFS_ZH` | 版式取色、linter 色彩规则 |
| 字体 | `FONTS` `TYPE_SCALE` `TYPE_RULES` | 所有文字、linter 排版规则 |
| 组件 | `RADIUS` `STROKE` `CARD_PADDING` `KPI` `CHART` `FLOW` `MATRIX` `TABLE` | 组件绘制、linter 结构规则 |
| 节奏 | `RHYTHM_RULES` `HERO_LAYOUTS` `CHROME_EXEMPT_LAYOUTS` | 版式选择、linter 节奏规则 |

三组**派生函数**把令牌交给外部世界：

| 函数 | 返回 | 用途 |
|---|---|---|
| `tokens.swatch(key)` | `Swatch` 对象 | 按 key 取色板条目，未知 key 抛 `KeyError` |
| `tokens.hex_of(key)` | `"#RRGGBB"` 大写 | 接受调色板 key、角色名、或直接传 `#hex` |
| `tokens.css_variables()` | CSS `:root{...}` 文本 | HTML 渲染器 / 设计稿 |
| `tokens.summary()` | 可 JSON 序列化的字典 | `deepocean tokens --json` |
| `tokens.allowed_hexes()` | 允许出现的全部 hex 列表 | linter 的 C001 |
| `tokens.type_token(key)` | `TypeToken` | 版式取字号，未知 key 抛 `KeyError` |

---

## 2 身份令牌

| 常量 | 值 | 用在哪 |
|---|---|---|
| `NAME` | `"Deep Ocean"` | pptx 主题名（`build.patch_theme_xml`）、HTML 页标题 |
| `NAME_ZH` | `"深海学术风"` | 中文文档与 CLI 帮助 |
| `VERSION` | `"1.0.0"` | `deepocean.__version__`、`deepocean version`、pptx 注释属性 |
| `TAGLINE_ZH` | `"像论文，不像海报"` | 文档扉页 |
| `TAGLINE_EN` | `"Reads like a paper, not a poster."` | 英文文档 |
| `LICENSE` | `"MIT"` | pptx 文档属性、`pyproject.toml` |
| `HOMEPAGE` | `"https://github.com/wst320727254-beep/deep-ocean-slides"` | pptx 注释属性、错误提示 |

`tokens.VERSION` 与 `pyproject.toml` 的 `version`、`CHANGELOG.md` 的最新条目必须三者一致；`tokens.VERSION` 同时是 `deepocean.__version__` 的来源。

**改它的影响**：只影响元数据，不影响版面。改 `VERSION` 前先读 §10。

---

## 3 画布与栅格令牌

### 3.1 `CANVAS`

| 键 | 值 | 语义 |
|---|---:|---|
| `width_px` | `1280` | 设计画布宽，**一切 px 的基准** |
| `height_px` | `720` | 设计画布高 |
| `aspect` | `"16:9"` | 人读用 |
| `width_in` | `13.3333` | PowerPoint 宽屏默认 |
| `height_in` | `7.5` | PowerPoint 宽屏默认 |
| `width_cm` | `33.87` | 公制标注 |
| `height_cm` | `19.05` | 公制标注 |
| `px_per_inch` | `96.0` | 与 `units.PX_PER_INCH` 一致 |

`build.new_presentation()` 用前两个键设定 `prs.slide_width` / `slide_height`。

### 3.2 栅格常量

| 常量 | 值 | 语义 | 影响范围 |
|---|---:|---|---|
| `SAFE_MARGIN_PX` | `40` | 左右安全边距 | 所有版式左右边界 |
| `CARD_GAP_PX` | `20` | 同排卡片 gutter | 双栏 / 多卡版式中缝 |
| `CONTENT_WIDTH_PX` | `1200` | `1280 − 2×40` | 卡片宽度上限 |

`SAFE_MARGIN_PX` 是**派生链的源头**：`CONTENT_WIDTH_PX` 由它算出，`SAFE_AREA` 也由它算出。改成 32，内容宽度自动变成 1216，所有版式一起移动——这正是"改 token 就改全篇"的示例。

### 3.3 `BANDS`（四区母版）

| 键 | `y` | `h` | 覆盖区间 | 内容 |
|---|---:|---:|---|---|
| `top_bar` | 0 | 60 | 0–60 | 深蓝顶条、青绿方块、刊名角标 |
| `title` | 72 | 68 | 72–140 | 眉标 14 / 主标 30 / 副标 15 |
| `content` | 200 | 440 | 200–640 | 卡片，`min_content_fill` 判定区 |
| `footer` | 680 | 40 | 680–720 | 左侧来源注、右侧页码 |

### 3.4 `SAFE_AREA`

```python
SAFE_AREA = {"x": 40, "y": 60, "w": 1200, "h": 660}
```

`y=60`（顶条下沿）到 `720`（画布底），即 `h = 720 − 60 = 660`。这是**元素必须活在里面**的盒子，`cover` / `closing` 除外。

---

## 4 色彩令牌

### 4.1 `PALETTE`（品牌 + 表面，`OrderedDict[str, Swatch]`）

| key | `name_zh` | `name_en` | `hex` | `role` | `budget` |
|---|---|---|---|---|---|
| `navy` | 深海蓝 · 主色 | Deep Ocean Navy | `#1B3A5C` | `brand` | — |
| `teal` | 青绿 · 辅色 | Tide Teal | `#2E9BA6` | `brand` | — |
| `grayblue` | 灰蓝 · 中性 | Slate Blue | `#6B86A3` | `brand` | — |
| `brick` | 深砖红 · 警示 | Warning Brick | `#C0392B` | `brand` | `<=6% overall` |
| `white` | 白 · 主背景 | Paper White | `#FFFFFF` | `surface` | — |
| `light` | 浅灰 · 卡底 | Mist Grey | `#F4F7FB` | `surface` | — |
| `mint` | 浅青 · 高亮底 | Tide Tint | `#E6F3F5` | `surface` | — |
| `pink` | 浅红 · 警示底 | Warning Tint | `#FCE5E2` | `surface` | — |
| `line` | 线框灰 | Hairline | `#D6DCE5` | `surface` | — |

`Swatch` 还有两个中英双语的 `use_zh` / `use_en` 用途说明字段，以及一个 `rgb` 属性（`#1B3A5C` → `(27, 58, 92)`）。

**key 名是稳定契约**：deck 文档、`layouts.py`、`html.py`、linter 全部按 key 引用颜色，不按 hex。

### 4.2 `TEXT_COLORS`

| key | `name_zh` | `hex` | 用途 | 白底对比度 |
|---|---|---|---|---|
| `t1` | 文本主 | `#1A2230` | 正文主述、卡片标题 | 15.96 |
| `t2` | 文本副 | `#4A5568` | 说明文字、注解 | 7.53 |
| `t3` | 文本辅 | `#8B97A8` | 页脚、单位、来源标注 | **2.96** |

`t3` 低于 `TYPE_RULES["min_contrast"] = 4.5`，因此只用于脚注 / 单位这类辅助信息。详见 `docs/STYLE.md` §2.3。

### 4.3 `ROLES`（角色 → 调色板 key）

版式代码**只写角色名**。完整映射：

| 角色 | → key | 语义 |
|---|---|---|
| `primary` | `navy` | 主色块、标题、主论证 |
| `accent` | `teal` | 强调条、箭头、正向 |
| `neutral` | `grayblue` | 中性说明、第三序列 |
| `danger` | `brick` | 警示、下降、替代 |
| `bg` | `white` | 页面底色 |
| `surface` | `light` | 副卡片底 |
| `tint` | `mint` | 高亮底 |
| `alert_tint` | `pink` | 警示底 |
| `stroke` | `line` | 描边 |
| `ink` | `t1` | 正文主色 |
| `body` | `t2` | 正文副色 |
| `faint` | `t3` | 辅助文字 |
| `up` | `teal` | 上升 / 正向数字 |
| `down` | `brick` | 下降 / 负向数字 |
| `flat` | `navy` | 中性占比数字 |
| `complementary` | `teal` | 互补品类 |
| `substitution` | `brick` | 替代品类 |
| `null_effect` | `grayblue` | 无效应象限 |
| `neutral_number` | `navy` | 中性数字 |

```python
from deepocean import tokens
tokens.hex_of("accent")        # '#2E9BA6'
tokens.hex_of("up")            # '#2E9BA6'  （走 ROLES）
tokens.hex_of("#00ff00")       # '#00FF00'  （原样透传）
```

### 4.4 `RATIO_BUDGET`（面积配比预算，单位 %）

| 键 | 区间 | 说明 |
|---|---|---|
| `blue_family` | `(35, 50)` | `navy` + `grayblue` |
| `white` | `(35, 55)` | 白底 |
| `tint_family` | `(0, 20)` | `light` + `mint` |
| `brick` | `(0, 6)` | 硬上限 |
| `gold` | `(0, 0)` | 硬禁止 |

### 4.5 `FORBIDDEN`（机器可检的禁用规则）

| `kind` | 条件 | 理由 |
|---|---|---|
| `hue` | 270–345°，`min_sat` 0.15 | 紫色 / 粉色 / 玫红一律禁用 |
| `hue` | 30–60°，`min_sat` 0.45 | 金色禁用（含香槟金、土金） |
| `hue` | 85–165°，`min_sat` 0.55 | 高饱和橙绿大色块禁用 |
| `hex` | `#000000` | 纯黑大底禁用 |

判定实现在 `color.forbidden_reason()`（转 HLS 取 hue/sat）与 `color.audit_colour()`（一次性给出 `on_palette` / `token` / `forbidden` / `hue` / `saturation` / `contrast_on_white`）。

### 4.6 `BANNED_MOTIFS_ZH`（只能人眼判断的禁用项）

```python
["彩虹渐变 / 渐变作卡片背景",
 "3D、卡通、二次元、营销插画",
 "楷体行书毛笔字",
 "印章、烟花、金边装饰",
 "同排 3 张以上等宽卡片（Hero 页 0 张）"]
```

---

## 5 字体令牌

### 5.1 `FONTS`

| 键 | 值 | 说明 |
|---|---|---|
| `cjk` | `Source Han Sans SC` → `Noto Sans CJK SC` → `Microsoft YaHei` → `PingFang SC` → `sans-serif` | 中文回退链 |
| `latin` | `Inter` → `Source Sans 3` → `Segoe UI` → `Arial` → `Helvetica` → `sans-serif` | 西文 / 数字回退链 |
| `serif` | `Times New Roman` → `Source Han Serif SC` → `serif` | **仅**封面与引文 |
| `mono` | `SFMono-Regular` → `Consolas` → `Menlo` → `monospace` | 文档 / 代码，不用于幻灯片正文 |
| `max_families` | `2` | 全篇家族上限（T005 检查） |
| `ppt_latin` | `"Segoe UI"` | 落盘到 pptx 主题的 `a:latin` |
| `ppt_cjk` | `"Microsoft YaHei"` | 落盘到 pptx 主题的 `a:ea` |

`build.patch_theme_xml()` 会把这套字体写进 `ppt/theme/theme1.xml` 的 `majorFont` / `minorFont`，让 PowerPoint 自己的字体下拉框与研究者的选择一致。

### 5.2 `TYPE_SCALE`（23 档）

每个条目是一个 `TypeToken`，字段：`key` `name_zh` `px` `weight`（`bold` / `semibold` / `regular`）`color`（调色板 key）`letter_spacing`（px）`line_height` `use_zh` `use_en`，另有派生属性 `pt`（`px × 0.75`）与 `bold`（`weight in ("bold", "semibold")`）。

> 档数会随版本增长（`deepocean tokens --md` 是权威清单）。**不要在别处硬编码档数**——CSS 变量的数量、linter 的字号判定都直接由这个 `OrderedDict` 驱动。

完整取值表见 [`docs/STYLE.md` §3.2](STYLE.md#32-字号阶梯tokenstype_scale-全表)。按语义分组：

| 组 | token |
|---|---|
| 封面 | `cover_title` `cover_subtitle` `cover_meta` |
| 大数字 | `section_number_lg` `section_number` |
| 标题块 | `page_title` `kicker` `page_subtitle` |
| 卡内 | `card_title` `card_title_sm` `card_body` `card_body_sm` |
| KPI | `kpi_value` `kpi_value_sm` `kpi_label` `kpi_note` |
| 表格与节点 | `table_head` `table_cell` `node` |
| 收尾与注脚 | `quote` `caption` `footer` `page_number` |

`tokens.TYPE_SCALE` 是 `OrderedDict`，**顺序即 CSS 变量的输出顺序**。

### 5.3 `TYPE_RULES`

| 键 | 值 | 强制内容 | 违反时的规则码 |
|---|---:|---|---|
| `min_px_body` | `13` | 正文下限 | T001 |
| `min_px_any` | `11` | 全文任意文字下限 | T002 |
| `carousel_line_height` | `(1.5, 1.6)` | 正文行高区间 | T004 |
| `max_font_families` | `2` | 家族上限 | T005 |
| `max_weights` | `2` | 字重层级上限 | T005 |
| `min_contrast` | `4.5` | WCAG AA 对比度 | T003 |

---

## 6 组件几何令牌

### 6.1 `RADIUS`

| 键 | 值 | 用在 |
|---|---:|---|
| `card_sm` | `6` | 小卡、流程节点 |
| `card_lg` | `8` | 大卡 |
| `chip` | `999` | 胶囊标签（等效全圆角） |
| `node` | `6` | 流程节点 |

### 6.2 `STROKE`

| 键 | 值 | 用在 |
|---|---:|---|
| `hairline` | `1.0` | 常规描边、表格线、分隔线 |
| `emphasis` | `2.0` | 强调卡描边、象限描边 |
| `accent_bar` | `5.0` | 卡片左 / 上强调色条（规范区间 4–6 取中值） |

### 6.3 `CARD_PADDING`（顺序：上 右 下 左）

| 键 | 值 | 用在 |
|---|---|---|
| `sm` | `(14, 16, 14, 16)` | 小卡 |
| `md` | `(18, 20, 18, 20)` | 标准卡 |
| `lg` | `(24, 28, 20, 28)` | 大卡 / 主卡 |

### 6.4 `KPI`

| 键 | 值 | 语义 |
|---|---|---|
| `value_sizes` | `[32, 44, 48, 72]` | 四档巨数字（对应 `kpi_value_sm` / `kpi_value` / `section_number` / `section_number_lg`） |
| `label_gap` | `6` | 标签与数字间距 px |
| `note_gap` | `4` | 脚注与数字间距 px |
| `min_col_width` | `150` | 单列最小宽度 px |

### 6.5 `CHART`

| 键 | 值 | 语义 |
|---|---|---|
| `default_type` | `"bar"` | 未指定时的图表类型 |
| `grouping` | `"clustered"` | 多系列并排 |
| `height_px` | `(230, 400)` | 高度区间，**必须显式给** |
| `series_colors` | `["navy", "teal", "grayblue", "brick"]` | 系列取色顺序 |
| `axis_color` | `"grayblue"` | 坐标轴 |
| `legend_color` | `"t2"` | 图例 |
| `title_color` | `"navy"` | 图表标题 |
| `data_label_color` | `"t1"` | 数据标签 |
| `show_data_labels` | `True` | 强制可读数 |
| `gridlines` | `None` | 不画网格线 |
| `require_explicit_height` | `True` | 缺高度即报错（否则渲染为 0） |

### 6.6 `FLOW`

| 键 | 值 | 语义 |
|---|---|---|
| `node_w` | `(110, 130)` | 节点宽区间 |
| `node_h` | `50` | 节点高 |
| `arrow_px` | `19` | 「→」字符字号 |
| `gap_px` | `(8, 16)` | 节点间距区间 |

### 6.7 `MATRIX`

| 键 | 值 | 语义 |
|---|---|---|
| `quadrant_w` | `380` | 象限宽 |
| `quadrant_h` | `190` | 象限高 |
| `gap_px` | `20` | 象限间距 |
| `center_dot` | `20` | 中心锚点直径 |

### 6.8 `TABLE`

| 键 | 值 | 语义 |
|---|---|---|
| `head_fill` | `"navy"` | 表头底色 |
| `head_text` | `"white"` | 表头文字 |
| `zebra` | `"light"` | 斑马行底 |
| `grid` | `"line"` | 格线色 |
| `highlight` | `"mint"` | 正向高亮 |
| `highlight_neg` | `"pink"` | 负向高亮 |

---

## 7 节奏令牌

### 7.1 `RHYTHM_RULES`

| 键 | 值 | 语义 | 规则码 |
|---|---|---|---|
| `hero_ratio` | `(4, 12)` | 12 页里 4 页 peak | L001 |
| `asymmetry_ratio` | `0.83` | 非对称版式比例下限 | R001 |
| `equal_width_card_rows_max` | `2` | 等宽卡片横排页数上限 | R002 |
| `hero_equal_width_rows` | `0` | Hero 页禁止等宽横排 | R003 |
| `no_three_valleys` | `True` | 不允许连续 3 页低谷 | L002 |
| `chart_pages_max_share` | `0.40` | 图表页 + 双栏页合计占比上限 | R004 |
| `min_content_fill` | `0.80` | 内容填充率下限 | X002 |
| `min_anchor_px` | `44` | 每页视觉锚点最小尺寸 | A001 |
| `tint_family_max` | `0.20` | 浅色底面积占比上限 | C004（实装口径：只算 mint/pink 强调底，上限 35%；浅灰卡底不计入） |

### 7.2 版式集合

```python
HERO_LAYOUTS = ("cover", "key_findings", "closing")   # 算 peak 的版式
CHROME_EXEMPT_LAYOUTS = ("cover", "closing")          # 可改动母版的版式
```

这两个常量必须与 `schema.LAYOUTS[name]["hero"]` / `["chrome"]` 保持一致：`HERO_LAYOUTS` 的成员，在 `schema` 里 `hero` 必须是 `True`（反之亦然）；`CHROME_EXEMPT_LAYOUTS` 的成员，在 `schema` 里 `chrome` 必须是 `False`。页面级声明 `hero: true/false` 可以覆盖版式默认值（`spec.is_hero()`）。

---

## 8 单位换算与目标画布

### 8.1 公式（`src/deepocean/units.py`）

| 常量 / 函数 | 值 / 公式 | 说明 |
|---|---|---|
| `PX_PER_INCH` | `96.0` | 基准密度 |
| `EMU_PER_INCH` | `914400` | OOXML 英制公制单位 |
| `PT_PER_PX` | `0.75` | 字号换算是乘法 |
| `CM_PER_PX` | `2.54 / 96.0` = `0.0264583…` | — |
| `MM_PER_PX` | `25.4 / 96.0` = `0.264583…` | — |
| `px_to_pt(px)` | `px × 0.75` | PowerPoint 字号 |
| `px_to_inch(px)` | `px / 96` | PowerPoint 位置 |
| `px_to_cm(px)` | `px × 0.0264583` | 公制 |
| `px_to_mm(px)` | `px × 0.264583` | 公制 |
| `px_to_emu(px)` | `round(px / 96 × 914400)` = `px × 9525` | python-pptx 内部 |
| `pt_to_px(pt)` | `pt / 0.75` | 反向 |
| `inch_to_px(inch)` | `inch × 96` | 反向 |
| `scale_for(w)` | `w / 1280` | 目标画布缩放系数 |
| `scale_value(px, w)` | `px × (w / 1280)` | 缩放单个数值 |

### 8.2 `TARGETS`（目标画布与缩放系数）

| key | 画布 | 系数 | 典型用途 |
|---|---|---:|---|
| `pptx-16:9` | 1280 × 720 | **1.0** | 设计尺寸，PowerPoint 原生 |
| `keynote-1080p` | 1920 × 1080 | **1.5** | Keynote 16:9 默认、Canva、Figma @1.5× |
| `figma-2x` | 2560 × 1440 | **2.0** | Figma @2×、Retina 导出 |
| `4k` | 3840 × 2160 | **3.0** | 4K 导出 |

缩放规则：**所有 px 值（位置、尺寸、字号、圆角、描边、间距）乘同一个系数**。1920 宽画布上，40 px 边距 → 60 px，30 px 标题 → 45 px。注意此时字号单位是 px 还是 pt 取决于目标工具：Keynote 里按 px 填、PowerPoint 里按 pt 填。

### 8.3 换算表

`units.conversion_table()` 的默认输出（`deepocean units` 打印的就是它）：

| px | pt (PowerPoint) | inch | cm | Keynote 1920 | Figma 2560 |
|---:|---:|---:|---:|---:|---:|
| 8 | 6.00 | 0.0833 | 0.212 | 12.0 | 16.0 |
| 12 | 9.00 | 0.1250 | 0.318 | 18.0 | 24.0 |
| 14 | 10.50 | 0.1458 | 0.370 | 21.0 | 28.0 |
| 20 | 15.00 | 0.2083 | 0.529 | 30.0 | 40.0 |
| 40 | 30.00 | 0.4167 | 1.058 | 60.0 | 80.0 |
| 60 | 45.00 | 0.6250 | 1.587 | 90.0 | 120.0 |
| 72 | 54.00 | 0.7500 | 1.905 | 108.0 | 144.0 |
| 120 | 90.00 | 1.2500 | 3.175 | 180.0 | 240.0 |
| 200 | 150.00 | 2.0833 | 5.292 | 300.0 | 400.0 |
| 440 | 330.00 | 4.5833 | 11.642 | 660.0 | 880.0 |

常用版式坐标的英寸值（手工复刻时直接照填）：

| px | inch | 用途 |
|---:|---:|---|
| 32 | 0.3333 | 顶条青绿方块 x |
| 40 | 0.4167 | 安全边距 |
| 60 | 0.6250 | 顶条高 |
| 100 | 1.0417 | 结尾页加高顶条 |
| 140 | 1.4583 | 标题块下沿 / 结尾金句区上沿 |
| 200 | 2.0833 | 内容区上沿 |
| 430 / 440 | 4.4792 / 4.5833 | 卡片高 |
| 640 | 6.6667 | 内容区下沿 |
| 680 | 7.0833 | 页脚上沿 |
| 692 | 7.2083 | 页脚文字基线 |
| 720 | 7.5000 | 画布高 |
| 1200 | 12.5000 | 内容可用宽度 |
| 1240 | 12.9167 | 右边缘（右对齐基准 x） |
| 1280 | 13.3333 | 画布宽 |

---

## 9 CLI 输出格式

```bash
deepocean tokens            # 默认：终端里带缩进的人读清单
deepocean tokens --json     # 机器读：tokens.summary() 的 JSON
deepocean tokens --md       # Markdown 表格（色板 / 字号 / 规则），可直接粘进文档或 issue
deepocean tokens --css      # CSS 自定义属性，直接给网页版 / 设计稿
```

`--json`、`--md`、`--css` 三个开关互斥；不传开关时打印终端友好的清单（对齐的色板行 + 字号行 + 规则行）。

### `--json` 输出片段

`tokens.summary()` 的键固定为 `name` `name_zh` `version` `canvas` `safe_margin_px` `card_gap_px` `bands` `palette` `text_colors` `roles` `type_scale` `ratio_budget` `type_rules` `rhythm_rules`：

```json
{
  "name": "Deep Ocean",
  "name_zh": "深海学术风",
  "version": "1.0.0",
  "canvas": {"width_px": 1280, "height_px": 720, "aspect": "16:9",
             "width_in": 13.3333, "height_in": 7.5,
             "width_cm": 33.87, "height_cm": 19.05, "px_per_inch": 96.0},
  "safe_margin_px": 40,
  "card_gap_px": 20,
  "bands": {"top_bar": {"y": 0, "h": 60}, "title": {"y": 72, "h": 68},
            "content": {"y": 200, "h": 440}, "footer": {"y": 680, "h": 40}},
  "palette": {"navy": {"hex": "#1B3A5C", "name_zh": "深海蓝 · 主色",
                       "name_en": "Deep Ocean Navy"}},
  "roles": {"primary": "navy", "accent": "teal", "down": "brick"},
  "type_scale": {"page_title": {"px": 30, "pt": 22.5, "weight": "bold", "color": "navy"}},
  "rhythm_rules": {"hero_ratio": [4, 12], "asymmetry_ratio": 0.83}
}
```

### `--css` 输出片段

`tokens.css_variables()` 生成 `--do-<token>` 前缀的变量，颜色在前、几何在中、字号在后：

```css
:root{
  --do-navy:#1B3A5C;
  --do-teal:#2E9BA6;
  --do-grayblue:#6B86A3;
  --do-brick:#C0392B;
  --do-white:#FFFFFF;
  --do-light:#F4F7FB;
  --do-mint:#E6F3F5;
  --do-pink:#FCE5E2;
  --do-line:#D6DCE5;
  --do-t1:#1A2230;
  --do-t2:#4A5568;
  --do-t3:#8B97A8;
  --do-margin:40px;
  --do-gap:20px;
  --do-cover_title:44px;
  --do-cover_subtitle:26px;
  --do-cover_meta:14px;
  --do-section_number_lg:72px;
  ...
}
```

命名规则可直接推导：`--do-` + 调色板 / 文本色 key；`--do-margin` / `--do-gap` 两个几何变量；`--do-` + `TYPE_SCALE` 的 key 表示字号 px 值。HTML 渲染器与网页版设计稿都消费这份输出。

### `--md` 输出片段

`--md` 输出的是**现成的 Markdown 表格**，给文档用，可整段粘进 `docs/` 或 issue：

```markdown
# Deep Ocean 深海学术风 · 设计令牌 v1.0.0

- 画布：`1280 x 720` px = `13.3333 x 7.5` inch（16:9）
- 安全边距：`40` px · 卡片间距：`20` px
- 换算：`pt = px × 0.75`，`inch = px / 96`

## 色板

| token | hex | 中文名 | English | 用途 |
|---|---|---|---|---|
| `navy` | `#1B3A5C` | 深海蓝 · 主色 | Deep Ocean Navy | 顶条 / 主标题 / 强调数字 / 页码 / 深色卡底 |
| `teal` | `#2E9BA6` | 青绿 · 辅色 | Tide Teal | 装饰条 / 互补品类 / 正向数据 / 图标 / 流程箭头 |
```

CI 里有一条 `python -m deepocean tokens --md > tokens.md`，用途就是让令牌随时能整份导出（`RULE_CODES` 式的可引用输出）。若你的环境里 `python -m deepocean` 报 `No module named deepocean.__main__`，改用等价的 `python -m deepocean.cli tokens --md`，或直接用已安装的 `deepocean tokens --md`。

---

## 10 版本与向后兼容约定

**令牌名属于公共 API。** 具体含义：

| 变更类型 | 允许的版本号 | 例子 |
|---|---|---|
| 改**值**（hex、px、系数）而不改名 | **patch** 或 **minor** | `PALETTE["teal"].hex` 微调；`SAFE_MARGIN_PX` 40 → 32 |
| 新增 token / 新增常量键 | **minor** | 新增 `TYPE_SCALE["table_note"]` |
| 重命名或删除 token、改 `BANDS` 的键名、改 `ROLES` 的映射方向 | **major** | `grayblue` → `slate`；删除 `section_number` |
| 改 `schema.LAYOUTS` 的 layout 名 | **major** | `two_column` → `two_col` |
| 新增 layout | **minor** | 新增 `timeline` |
| 改 layout 的**必填字段** | **major**（若从可选变必填）/ **minor**（若新增可选字段） | `chart.height` 变为必填 |

约定：

1. **不重命名既有 token。** 需要新语义时新增一个 token，旧 token 保留并标为 deprecated。
2. **不改变 `hex` 的语义分配。** `down` 永远指向警示红族，`up` 永远指向青绿族；换色可以，换语义不行。
3. **改值必须同步三处**：`tokens.py`、本手册、`CHANGELOG.md`。若新值会影响 linter 阈值，必须同时更新 `docs/CHECKLIST.md` 的规则说明。
4. **`SPEC` 兼容性跟随令牌**：deck 文档只引用 layout 名与字段名，不改这两者就保证旧 deck 继续可编译。
5. 消费方若必须锁死版本，用 `deepocean.__version__`（等于 `tokens.VERSION`）做运行时校验：

```python
import deepocean
assert deepocean.__version__.startswith("1."), "本 deck 依赖 Deep Ocean 1.x 令牌"
```

---

**延伸阅读**

- 令牌背后的设计规范与全部数值 → [`docs/STYLE.md`](STYLE.md)
- 把令牌搬到 PowerPoint / Keynote / Figma / Python → [`docs/TUTORIAL.md`](TUTORIAL.md)
- 交付前自检与 CI → [`docs/CHECKLIST.md`](CHECKLIST.md)
- 参与开发流程 → [`CONTRIBUTING.md`](../CONTRIBUTING.md)
