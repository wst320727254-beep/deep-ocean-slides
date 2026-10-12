# 复刻与使用教程

> **这份文件解决什么问题**：把 Deep Ocean 这套风格搬到你的机器上——不管你是想用本仓库的 CLI 直接出片，还是要在 PowerPoint / Keynote / Figma 里手工复刻，或者用 Python API 写自己的版式。五条路线互不排斥，可以混用。
>
> **谁该读它**：第一次使用本项目的同学（走路线 A）、要手工做 PPT 的师兄师姐（路线 B/C/D）、要扩展版式的开发者（路线 E）、以及所有撞过坑的人（结尾 FAQ）。

## 目录

| 路线 | 适合谁 | 需要什么 |
|---|---|---|
| [A · 用本仓库 CLI](#路线-a--用本仓库的-cli最短路径) | 想最快出一份 12 页汇报 | Python ≥ 3.9 |
| [B · 手工 PowerPoint](#路线-b--手工-powerpoint) | 不用代码、要逐页微调 | PowerPoint |
| [C · Keynote](#路线-c--keynote15-倍) | macOS 用户 | Keynote |
| [D · Figma / Canva](#路线-d--figma--canva-与在线工具) | 要团队协作改设计 | Figma / Canva |
| [E · Python API](#路线-e--用-python-api-写自定义版式) | 要写新版式 / 接自动化 | Python + python-pptx |
| [常见问题](#常见问题-faq) | 所有人 | — |

---

## 路线 A · 用本仓库的 CLI（最短路径）

### A.1 安装

**本包尚未发布到 PyPI**，请从 GitHub 克隆后以可编辑模式安装：

```bash
git clone https://github.com/wst320727254-beep/deep-ocean-slides.git
cd deep-ocean-slides
pip install -e ".[yaml]"
```

- `[yaml]` 装上 PyYAML，用于读 `.yaml` / `.yml` 的 deck。**只写 JSON deck 时可以省略**，即 `pip install -e .`。
- 需要跑测试再装开发依赖：`pip install -e ".[dev]"`。

验证安装：

```bash
deepocean version        # 打印版本（应为 1.0.0）
deepocean units          # 打印 px→pt/inch/cm 换算表
deepocean layouts        # 打印 12 个版式的字段说明
```

> **装完 `deepocean` 不在 PATH 上？** 用等价的模块入口：`python -m deepocean.cli version`。
> 若该 Python 环境没有以可编辑模式安装本仓库，模块入口同样会报 `No module named deepocean`——此时先用 `pip install -e .` 装好，或临时设 `PYTHONPATH=src`（仅用于源码目录内调试，不要写进脚本）。

### A.2 生成起始模板

```bash
deepocean init mytalk              # 在 ./mytalk/ 写出 3 页起始 deck
deepocean init mytalk --demo       # 直接写出完整 13 页示例
```

> `deepocean init` 写出的 3 页模板 = `examples/minimal-deck.yaml`（`cover` + `two_column` + `key_findings`）；
> `--demo` 写出的是 13 页参考 deck（覆盖全部 12 个版式，含附录数据表页），也就是 `examples/demo-deck.yaml`。

### A.3 完整 CLI 参考

```
deepocean build <deck.yaml|deck.json> [-o out.pptx] [--no-check]   # 生成 PowerPoint
deepocean html <deck> [-o out.html]                                # 生成单文件网页版
deepocean check <deck|out.pptx> [--json] [--strict]                # 自动排版自检
deepocean preview <deck> [--out DIR]                               # 一次产出 pptx + html + 自检报告
deepocean init [DIR] [--demo]                                      # 写出起始 deck 模板
deepocean layouts [LAYOUT]                                         # 打印 12 个版式的字段说明
deepocean tokens [--json|--md|--css]                               # 打印设计令牌
deepocean units                                                    # 打印单位换算表
deepocean demo [-o DIR]                                            # 生成内置参考示例（13 页）
deepocean version
```

| 命令 | 做什么 | 常用参数 |
|---|---|---|
| `build` | deck → `.pptx`，顺带跑一次结构自检 | `-o` 输出路径；`--no-check` 跳过自检；`--strict` 结构性错误直接中止 |
| `html` | deck → **单文件** HTML（无外部依赖，可双击打开 / 打印 PDF） | `-o` 输出路径；`--fragment` 只输出 body 片段 |
| `check` | 自动排版自检；可查 deck，也可查已生成的 pptx | `--json` 机器可读；`--strict` 有警告即非零退出；`--no-color` |
| `preview` | 一次拿到 pptx + html + 自检报告 | `--out DIR` 输出目录；`--json`；`--strict` |
| `init` | 写出一份可编译的起始 deck | `--demo` 写完整 13 页示例而不是 3 页模板 |
| `layouts` | 查版式字段（写 deck 时的权威参考） | 传版式名只看一个 |
| `tokens` | 查设计令牌 | `--json` / `--md` / `--css`（互斥） |
| `units` | 查 px→pt/inch/cm 换算 | — |
| `demo` | 生成内置参考 deck（论文真实数值） | `-o DIR` 输出目录；`--no-html`；`--check`；`--strict` |
| `version` | 打印版本号 | — |

`check` 一次只接受**一个**目标（deck 或 pptx）。要批量检查多个产物，在 shell 里循环：

```bash
for f in out/*.pptx; do deepocean check "$f" --strict || exit 1; done
```

> **`check` 的两个层次**：`deepocean check deck.yaml` 只能做静态检查（结构、必填字段、节奏、占位文字）；坐标 / 字号 / 颜色 / 对比度必须检查**渲染产物**。所以完整流程是先 `demo`/`build`/`preview`，再 `check *.pptx`。详见 [`docs/CHECKLIST.md`](CHECKLIST.md#3-两类检查静态检查与产物检查)。

### A.4 典型工作流

```bash
deepocean init mytalk --demo          # 1. 起模板（13 页参考 deck 的内容）
deepocean preview mytalk/deck.yaml    # 2. 出 pptx + html + 自检报告，边看边改
deepocean check mytalk/deck.yaml --strict   # 3. 静态关：结构 / 节奏 / 占位文字
deepocean check out/mytalk.pptx --strict    # 4. 产物关：几何 / 排版 / 色彩
deepocean build mytalk/deck.yaml -o 组会汇报.pptx
```

`--strict` 是最有用的一步：它让自检的**警告**变成**非零退出码**，可以直接挂到 CI 或 git hook 上（见 `docs/CHECKLIST.md` 的 CI 一节）。

> 参考 deck（`examples/demo-deck.yaml`）的静态检查与产物检查在 `--strict` 下**都通过**（0 error / 0 warn，另有 59 条说明性 `info`）。所以 `--strict` 报错时先看规则码：`error` 是真问题；`warn` 需要判断——其中 `teal`/`grayblue`/`t3` 压浅底属色板固有条目（见 [`docs/STYLE.md` §2.3](STYLE.md#23-中性色要不要用红先把对比度算出来)），而顶条方块与 12px 辅助文字都已按规范原文校准，不会误报。完整口径见 [`docs/CHECKLIST.md`](CHECKLIST.md#2-规则码总表) 第 2 节末尾的"已知取舍"。

### A.5 一个可复制的 `deck.yaml`

下面是**已经过渲染验证**的最小可用片段：封面 + 一页非对称双栏。字段名与 `schema.LAYOUTS` 完全一致。

```yaml
meta:
  title: 推荐如何影响消费者搜索
  subtitle: How Recommendation Affects Customer Search
  kicker: 组会文献汇报
  journal: ISR · 2025
  authors: [Yuan, Chen, Wang, Sun]
  affiliation: 管理科学与工程 · 2026
  date: "2026-10"
  source_note: 组会文献汇报 · ISR 2025, 36(1): 84-106 · DOI 10.1287/isre.2022.0294

pages:
  # 01 封面 —— 只有 cover / closing 可以不带母版
  - layout: cover
    title: 推荐如何影响消费者搜索
    title_en: A Field Experiment on Recommendation and Search
    data:
      english_title: How Recommendation Affects Customer Search: A Field Experiment
      authors: 汇报人 · 你的名字
      affiliation: 管理科学与工程 · 文献组会 · 2026 年 10 月
      series: ISR · 2025
      note: 样本 555,800 名用户 · 26 个产品类目 · 一个无大促的常规日
      band: Yuan, Chen, Wang & Sun (2025), Information Systems Research 36(1): 84-106

  # 02 研究背景 —— 非对称双栏 60:40
  - layout: two_column
    kicker: 01 · BACKGROUND
    title: 研究背景
    subtitle: 算法推荐与主动搜索，是替代还是互补？
    data:
      ratio: 0.60                      # 左栏宽度占比，0.5–0.7
      left:                            # 左主卡（必填）
        title: 个性化推荐正在替用户做选择
        body: 电商平台用协同过滤把个人历史行为压缩成推荐位。当个人数据被切断，算法只能退回大众爆款。
        items:
          - 推荐位流量高度依赖个人数据
          - 搜索由用户自己表达需求
          - 已有研究缺少随机实验证据
        footer: 文献缺口：缺少在同一实验里同时观察推荐与搜索的田野证据
        tone: tint                     # plain | tint | primary | accent | neutral | danger | alert
      right:                           # 右栏卡片列（必填）
        - chip: IDENTIFICATION
          chip_en: 识别策略
          title: 切断个人数据
          body: 处理组推荐算法只输入商品与商家特征，个人数据被禁用。
          tone: tint
        - chip: SCALE
          chip_en: 实验规模
          title: 555,800 名用户
          body: 头部电商平台，20 亿+ 商品、数千万卖家、数亿买家。
          tone: plain
        - title: 本文答案：品类决定关系
          body: 互补品类的搜索被推荐带动，替代品类的搜索几乎补不回来。
          tone: primary               # 深蓝实色卡：单页 ≤ 1 张
```

几个写 deck 时的高频约定：

- **`data:` 之外的一级键是版式无关的公共字段**：`layout` `title` `title_en` `kicker` `subtitle` `hero`。任何其它一级键会被自动当作 `data` 的内容（便于手写）。
- **`hero: true/false` 可显式覆盖**版式默认的 peak 判定（`spec.is_hero()`）。示例 deck 就把第 06 页 `chart_insight` 显式标为 `hero: true`。
- **`tone` 决定卡片配色**，取值 `plain | tint | primary | accent | neutral | danger | alert`（`schema.TONES`）。
- 图表**必须给 `height`**（230–400），否则渲染高度为 0。

其余版式的字段形态，直接查：

```bash
deepocean layouts chart_insight
deepocean layouts matrix2x2
```

---

## 路线 B · 手工 PowerPoint

不用写代码，用 PowerPoint 原生功能复刻。**换算总则**：画布 1280×720 px 与 PowerPoint 宽屏 16:9 的 13.333×7.5 英寸 **1:1 对应**（96 px = 1 英寸），所有 px 乘 **0.75** 得 pt 字号，除以 **96** 得英寸位置（等价于乘 0.010417）。

### B.1 八步复刻

1. **设画布** —— 设计 → 幻灯片大小 → 宽屏 (16:9)。得到 13.333 × 7.5 英寸，与 1280 × 720 px 一一对应。
2. **建主题色** —— 设计 → 变体 → 颜色 → 自定义颜色，按下表填，保存为「Deep Ocean」：

   | PowerPoint 颜色槽 | Hex |
   |---|---|
   | 深色 1（文本/背景 - 深色 1） | `#1A2230` |
   | 浅色 1（文本/背景 - 浅色 1） | `#FFFFFF` |
   | 深色 2 | `#1B3A5C` |
   | 浅色 2 | `#F4F7FB` |
   | 着色 1（强调文字 1） | `#1B3A5C` |
   | 着色 2 | `#2E9BA6` |
   | 着色 3 | `#6B86A3` |
   | 着色 4 | `#C0392B` |
   | 着色 5 | `#E6F3F5` |
   | 着色 6 | `#D6DCE5` |

   > 这份槽位映射与代码一致：`build.THEME_COLOURS`（`dk1→t1`、`lt1→white`、`dk2→navy`、`lt2→light`、`accent1→navy`、`accent2→teal`、`accent3→grayblue`、`accent4→brick`、`accent5→mint`、`accent6→line`）。也就是说，用 CLI 生成的 pptx 里，PowerPoint 的颜色选择器已经长这样。

   还需要两个备用色（不占主题槽，手工用时记在便签上）：高亮浅红 `#FCE5E2`、线框灰 `#D6DCE5`。

3. **建主题字体** —— 设计 → 变体 → 字体 → 自定义。中文「思源黑体 / 微软雅黑」，西文「Inter / Arial」。全篇只用这两套家族。
4. **做幻灯片母版** —— 视图 → 幻灯片母版：
   - 顶条：`0, 0`，宽 `13.333 in`，高 `0.625 in`，填充 `#1B3A5C`；
   - 青绿方块：`0.333 in, 0.271 in`，`8 × 8 px`（≈ `0.083 in`），填充 `#2E9BA6`；
   - 页脚：从 `y = 7.083 in` 到底部，顶部一条 1 px（≈ 0.75 pt）`#D6DCE5` 分隔线；
   - 右下角插入「幻灯片编号」占位符，字号 12 px（9 pt）、加粗、`#1B3A5C`。

   关闭母版视图后所有页自动继承。
5. **拖参考线** —— 视图 → 参考线，右键「添加水平/垂直参考线」后逐个输入：

   | 方向 | px | 英寸 |
   |---|---:|---:|
   | 水平 | 60 | 0.625 |
   | 水平 | 140 | 1.458 |
   | 水平 | 200 | 2.083 |
   | 水平 | 640 | 6.667 |
   | 水平 | 680 | 7.083 |
   | 垂直 | 40 | 0.417 |
   | 垂直 | 1240 | 12.917 |

6. **按逐页表摆元素** —— 照 [`docs/STYLE.md` §6](STYLE.md#6-12-页逐页坐标表) 的坐标，用「大小和位置」窗格精确填 x/y/宽/高（单位选英寸，px ÷ 96）。卡片用「形状填充 + 无阴影」，左侧色条直接用矩形叠加（宽 5 px ≈ 0.052 in）。
7. **插图表** —— 插入 → 图表 → 簇状柱形图。右键设置数据系列格式，逐个改填充色为 `#1B3A5C` / `#2E9BA6`；**开启数据标签**；坐标轴文字改 `#6B86A3`，图例 `#4A5568`，标题 `#1B3A5C`；删掉网格线。
8. **自检** —— 对照 [`docs/CHECKLIST.md`](CHECKLIST.md) 逐条打勾；有 Python 环境的话，把 pptx 交给 `deepocean check 你的文件.pptx` 也能跑一遍机器检查。

### B.2 字号对照表（px → pt，直接照填字号框）

| 层级 | px | **pt** | 字重 | 颜色 |
|---|---:|---:|---|---|
| 封面中文主标 | 44 | **33** | Bold | `#1B3A5C` |
| 封面英文副标 | 26 | **19.5** | Regular | `#1A2230` |
| 封面信息（作者/单位/日期） | 14 | **10.5** | Regular | `#8B97A8` |
| 章节大数字（大） | 72 | **54** | Bold | `#1B3A5C` |
| 章节大数字 | 48 | **36** | Bold | `#2E9BA6` |
| 页面主标 | 30 | **22.5** | Bold | `#1B3A5C` |
| 眉标 | 14 | **10.5** | Bold | `#2E9BA6`（字距 2.5 px） |
| 页面副标 | 15 | **11.25** | Regular | `#6B86A3` |
| 卡内小标 | 18 | **13.5** | Bold | `#1B3A5C` |
| 卡内小标（小） | 16 | **12** | Bold | `#1B3A5C` |
| 卡内正文 | 14 | **10.5** | Regular | `#4A5568` |
| 卡内正文（小） | 13 | **9.75** | Regular | `#4A5568` |
| KPI 巨数字 | 44 | **33** | Bold | `#2E9BA6` / `#C0392B` / `#1B3A5C` |
| KPI 巨数字（小） | 32 | **24** | Bold | `#1B3A5C` |
| KPI 标签 | 12 | **9** | Regular | `#6B86A3` |
| KPI 脚注 | 12 | **9** | Regular | `#4A5568` |
| 表头 | 13 | **9.75** | Bold | `#FFFFFF`（配深蓝底） |
| 表格正文 | 12.5 | **9.38** | Regular | `#4A5568` |
| 流程节点 | 13 | **9.75** | Bold | `#FFFFFF` |
| 金句 | 22 | **16.5** | Bold | `#1B3A5C` |
| 注解 / 脚注 | 11.5 | **8.62** | Regular | `#8B97A8` |
| 页脚 | 12 | **9** | Regular | `#8B97A8` |
| 页码 | 12 | **9** | Bold | `#1B3A5C` |

> PowerPoint 的字号框通常只接受 0.5 pt 步进，`8.62` / `9.38` / `11.25` 这类值取最接近的档（8.5 / 9.5 / 11.5），差异在 0.1 pt 量级，肉眼不可见。行高改「多倍行距」：标题 1.25–1.35，正文 1.5–1.6，巨数字 1.0–1.05。

### B.3 手工复刻的坐标速查（英寸）

| 元素 | x (in) | y (in) | 宽 (in) | 高 (in) |
|---|---:|---:|---:|---:|
| 顶条 | 0 | 0 | 13.333 | 0.625 |
| 内容区左边界 | 0.417 | 2.083 | 12.5 | 4.583 |
| 左主卡（60:40 双栏） | 0.417 | 2.083 | 7.5 | 4.479 |
| 右栏起点 | 8.125 | 2.083 | 4.792 | — |
| 页脚分隔线 | 0.417 | 7.083 | 12.5 | 1 px |
| 右边缘（右对齐基准） | 12.917 | — | — | — |

---

## 路线 C · Keynote（×1.5 倍）

Keynote 默认 16:9 就是 1920×1080，因此**全部 px 值 × 1.5**：

| 项目 | 1280×720 设计值 | Keynote 1920×1080 |
|---|---:|---:|
| 画布 | 1280 × 720 | 1920 × 1080 |
| 左右安全边距 | 40 | **60** |
| 卡间距 | 20 | **30** |
| 顶条高 | 60 | **90** |
| 标题块上沿 | 72 | **108** |
| 内容区上沿 | 200 | **300** |
| 卡片高 | 430 / 440 | **645 / 660** |
| 页脚上沿 | 680 | **1020** |
| 页面主标 | 30 | **45** |

做法：

1. 文稿 → 幻灯片大小 → 1920 × 1080（或用「宽屏」默认）。
2. 主题色在「格式 → 高级 → 颜色」里按 `#1B3A5C` / `#2E9BA6` / `#6B86A3` / `#C0392B` / `#F4F7FB` / `#E6F3F5` 填入，存为自定义主题。
3. 字号同样 × 1.5（30 px → 45），Keynote 的「点」在这里与 px 等比，视觉大小与 pptx 一致。
4. 若要用 2560×1440 画布，则 × **2.0**（40 → 80 px）。

---

## 路线 D · Figma / Canva 与在线工具

画布设 **1920×1080（×1.5）** 或 **2560×1440（×2.0）**，然后把令牌存成工具里的"设计系统"：

| 工具里的东西 | 对应令牌 | 怎么建 |
|---|---|---|
| 项目色板 / 品牌色 | `tokens.PALETTE` + `TEXT_COLORS` | 直接粘 `deepocean tokens --css` 的输出，或用取色器填 12 个 hex |
| 文字样式（Text Styles） | `tokens.TYPE_SCALE`（`deepocean tokens --md` 列出的全部档位） | 每档建一个样式：字号 = px × 缩放系数，行高 = `line_height`，字重 = bold/regular，字距 = `letter_spacing` × 系数 |
| 组件（Component） | 卡片 / KPI / 图表容器 / 象限 | 按 `CARD_PADDING`、`RADIUS`、`STROKE` 建变体 |
| 自动布局间距 | `SAFE_MARGIN_PX`、`CARD_GAP_PX` | 边距 40×系数，间距 20×系数 |

这样换内容时只改文字，样式自动继承。字号在 Figma 里是直接用 px 的，所以 2560 宽画布上页面主标填 **60**（30 × 2），边距填 **80**。

> 在线 AI 生成类工具（即梦、Gamma 等）只能保证色板一致，字距、四区母版这类硬约束无法可靠继承，建议只用于找版式灵感。

---

## 路线 E · 用 Python API 写自定义版式

用于：批量生成、接数据管道，或者要写一个 `schema` 里还没有的版式。

### E.1 最小可运行示例（已实测通过）

下面这段代码画出一页完整的"四区母版 + 主卡 + KPI + 页脚"，输出一个 `.pptx`。它只用公共 API：`tokens`、`units`、`primitives`。

```python
# my_slide.py —— python my_slide.py
from pptx import Presentation
from pptx.util import Emu

from deepocean import tokens, units
from deepocean.primitives import P, T, add_text, add_arrow, bullets, rect

# 1. 画布：1280 x 720 px（= 13.333 x 7.5 in）
prs = Presentation()
prs.slide_width = Emu(units.px_to_emu(tokens.CANVAS["width_px"]))
prs.slide_height = Emu(units.px_to_emu(tokens.CANVAS["height_px"]))
slide = prs.slides.add_slide(prs.slide_layouts[6])       # 6 = 空白版式

B = tokens.BANDS            # 四区母版的 y / h
M = tokens.SAFE_MARGIN_PX   # 40

# 2. A 区：顶条 + 青绿方块
rect(slide, 0, 0, tokens.CANVAS["width_px"], B["top_bar"]["h"], fill="primary")
rect(slide, 32, 26, 8, 8, fill="accent")

# 3. B 区：眉标 + 主标
add_text(slide, M, 80, 1200, 30, P("01 · BACKGROUND", "kicker"))
add_text(slide, M, 110, 1200, 40, P("研究背景", "page_title"))

# 4. C 区：一张主卡（浅灰底 + 5px 左侧青绿色条）
rect(slide, M, B["content"]["y"], 700, 430,
     fill="surface", line="stroke", radius=tokens.RADIUS["card_sm"])
rect(slide, M, B["content"]["y"], 5, 430, fill="accent")
add_text(slide, M + 28, 224, 640, 40, P("个性化推荐正在替用户做选择", "card_title"))
bullets(slide, M + 28, 272, 640, 200,
        ["推荐位依赖个人数据", "搜索由用户自己表达需求", "缺少随机实验证据"])

# 5. C 区右侧：一个下降的 KPI 巨数字
add_text(slide, 780, 224, 460, 80, [P(T("−33.4%", "kpi_value", color="down"), align="left")])
add_text(slide, 780, 300, 460, 24, P("推荐渠道 浏览 PV", "kpi_label"))
add_arrow(slide, 760, 415, 780, 415, color="accent")

# 6. D 区：页脚分隔线 + 左来源 / 右页码
rect(slide, M, B["footer"]["y"], 1200, 1, fill="stroke")
add_text(slide, M, B["footer"]["y"] + 12, 700, 20, P("组会文献汇报 · ISR 2025", "footer"))
add_text(slide, 940, B["footer"]["y"] + 12, 300, 20,
         P(T("01 / 12", "page_number"), align="right"))

prs.save("my_slide.pptx")
```

API 要点：

- **所有坐标都是 1280×720 的 px**，`primitives` 内部换算成 EMU；不要自己乘 9525。
- **颜色一律传角色名或 token 名**（`"primary"` `"surface"` `"stroke"` `"accent"` `"down"`），不要传 `#RRGGBB`——这样 linter 才能判断你用的颜色在不在色板上。
- **文字一律用 `style("token_name")`**：`P("文本", "card_title")` 或 `P("文本", align="right", ...)`；混合样式用 `T()`：

  ```python
  P([T("浏览 PV ", "card_title"), T("−33.4%", "kpi_value", color="down")])
  ```

  注意 `P()` 的第二个位置参数是 `align`，要指定字号 token 必须用 `T()` 包一层。
- 文本自动换行与溢出估算可用 `primitives.wrap_lines()` / `text_height()` / `fit_size()`；它们对 CJK 按字断行，与 PowerPoint 行为接近。

### E.2 直接用编译器

拿到一个 `spec.Deck` 之后交给编译器，主题色与字体由 `build` 负责：

```python
from deepocean import build, spec

deck = spec.Deck.load("deck.yaml")          # 也可以用 spec.Deck.from_dict({...})
result = build.build(deck, "out.pptx")      # check=True 时顺带跑结构校验
print(result.ok, result.path, result.pages, result.problems)

# 一行版：
build.build_file("deck.yaml", "out.pptx", strict=True)
```

`build.build()` 会：设好 1280×720 画布 → 写入 pptx 文档属性 → 逐页调用 `layouts.build_page()` → 保存 → 用 `build.patch_theme_xml()` 把 Deep Ocean 的颜色槽与字体写进 `ppt/theme/theme1.xml`。

生成之后建议立刻自检一次，并**把 deck 一起传给产物检查**，这样 `cover` / `closing` 的版式豁免才生效：

```python
from deepocean import build, check, spec

deck = spec.Deck.load("deck.yaml")
result = build.build(deck, "out.pptx")

report = check.check_pptx(result.path, deck)   # 传 deck 才有版式上下文
print(report.counts())                          # {'error': ..., 'warn': ..., 'info': ...}
if not report.ok():
    print(report.to_text(color=True))
```

### E.3 写一个全新版式

按 [`docs/STYLE.md` §8.2](STYLE.md#82-新增一个版式的四步法)：改 `schema.py` → 实现 `layouts.py` 的 `render_<layout>` → 实现 `html.py` 的同名分支 → 往示例 deck 加一页真实内容，最后跑 `deepocean check` 确认新页面没有引入**新的**规则问题（当前参考 deck 本身还有若干待收敛的告警，见 [`docs/CHECKLIST.md`](CHECKLIST.md#2-规则码总表) 末尾的"已知限制"）。

---

## 常见问题（FAQ）

### F1 中文显示成方框 / 字体不对

**现象**：生成的 pptx 在别人电脑上中文变成方块，或 PowerPoint 用默认宋体渲染。

**原因与处理**：

1. 生成端没装思源黑体不影响落盘——字体名会写进文件，**在打开文件的机器上找字体**。若打开端也没有，PowerPoint 会回退到系统默认。
2. 让同事在打开端装 **思源黑体（Source Han Sans SC）** 或确认系统有 **微软雅黑 / 苹方**（`tokens.FONTS["cjk"]` 的回退链里就有）。
3. 代码里落盘的字体名是 `tokens.FONTS["ppt_cjk"]`（默认 `Microsoft YaHei`）与 `ppt_latin`（默认 `Segoe UI`）。要换成思源黑体，改这两个键，或改主题字体（见 `docs/TOKENS.md` §5.1）。
4. 导 PDF 交付可以彻底规避字体问题：`deepocean html` 出的单文件网页在浏览器里 Ctrl/Cmd + P 导出 PDF，网页里是 CSS 字体栈，回退更宽容。

### F2 图表高度为 0 / 图表不见了

**现象**：网页版或 pptx 里图表区一片空白。

**原因**：`chart.height` 缺失。`tokens.CHART["require_explicit_height"] = True` 是硬规则，缺高度会渲染为 0 并被 linter 报出来。

**处理**：给图表显式高度，取值 230–400：

```yaml
chart:
  type: bar
  height: 390        # ← 必须
  categories: [浏览 PV, 点击, 订单, 销售额]
  series:
    - {name: 推荐渠道, values: [-33.4, -83.6, -85.9, -81.1], color: navy}
```

图表卡的高（如 440）要大于图表高 + 标题 + 注脚，否则会溢出卡片。

### F3 报错 `reading .yaml decks needs PyYAML`

**现象**：`deepocean build deck.yaml` 提示需要 PyYAML。

**原因**：`spec.load_yaml()` 只在真要读 YAML 时才导入 PyYAML，没装就抛出带指引的 `SpecError`。

**三种处理**：

```bash
pip install -e ".[yaml]"     # 装上 PyYAML（推荐）
```

或者把 deck 写成 JSON（`deck.json`），只写 JSON 时不需要 PyYAML：

```bash
deepocean build deck.json -o out.pptx
```

或者 `pip install PyYAML` 单独装。

### F4 单位换算踩坑

| 坑 | 表现 | 正解 |
|---|---|---|
| 把 px 当 pt 填 | 字号看起来大了 1/3 | `pt = px × 0.75`；30 px → 22.5 pt |
| 把 pt 当 px 填 | 版面偏小 | `px = pt / 0.75`；22.5 pt → 30 px |
| 用 cm 反推 px | 误差累积 | 一律走 `units.px_to_inch()` / `px_to_cm()`，别手算 |
| 在 Keynote 里按 ×2 填 | 元素跑到画布外 | Keynote 1920 宽用 **×1.5**，2560 宽才用 ×2 |
| 自己乘 9525 转 EMU | 与 `primitives` 双算 | 传 px 给 `primitives`，EMU 只在 `primitives` 内部出现一次 |
| 页脚和卡片用不同基准 | 右边缘不齐 | 统一右边缘 `x = 1240`（= 1280 − 40） |

### F5 如何在组会 / 开题 / 答辩复用这套模板

| 场合 | 建议页数 | 复用方式 |
|---|---|---|
| 文献组会 | 12 页（默认） | `deepocean init mytalk --demo` 起 13 页参考 deck（12 页正文 + 1 页附录），只替换数值与文案 |
| 开题报告 | 12–16 页 | 用 `two_column`（背景/缺口）+ `roadmap`（技术路线）+ `experiment_design`（方案）+ `closing`（计划与风险）；不要塞满 26 个品类那种细节 |
| 中期检查 | 10–12 页 | 用 `chart_insight` 放结果图，`key_findings` 放阶段性结论，`data_table` 放附加表 |
| 答辩 | 15–20 页 | 在 12 页骨架上加附录页（`data_table`），把答辩可能被追问的表放在最后；正文保持 12 页不变 |
| 换一篇论文重做 | 12 页 | **版式与配色完全复用**，只替换 `examples_data.PAPER` 对应的数值与每页文字 |

换论文时的固定动作：

1. `meta` 里改标题、期刊、作者、`source_note`；
2. 每页 `kicker` 的编号按实际章节顺序重排；
3. 只改**数值与文案**，不动 `layout`；若要增删页，回到 [`docs/STYLE.md` §5](STYLE.md#5-页面节奏规则) 的排布规则重新推导；
4. `deepocean check --strict` 必须通过（尤其是 L001 的 Hero 配额和 L002 的连续 valley 规则）。

### F6 页面看起来"太挤"或"太空"

- 太挤：正文降到 `card_body_sm`（13 px）之前，先减**字数**而不是减字号——13 px 是 `TYPE_RULES["min_px_body"]` 的硬下限。
- 太空：内容填充率低于 0.80 会被报 X002。把两张卡改成三张、或给主卡补一条 S4 关键数据（卡片五段骨架的锚底是必填的）。
- 想判断具体是哪一条规则没过，直接看报告：`deepocean check deck.yaml --json`。

---

**延伸阅读**

- 设计规范与全部数值 → [`docs/STYLE.md`](STYLE.md)
- 令牌逐个说明与影响范围 → [`docs/TOKENS.md`](TOKENS.md)
- 交付前逐条自检与 CI → [`docs/CHECKLIST.md`](CHECKLIST.md)
- 参与开发 → [`CONTRIBUTING.md`](../CONTRIBUTING.md)
