---
name: deep-ocean-slides
description: 把论文 PDF、组会材料或一个主题做成 Deep Ocean 学术风 16:9 汇报 PPT（真·可编辑 .pptx + 单文件 HTML + 自动排版自检 + 论文配图页）。当用户要"做文献汇报/组会 PPT/开题答辩 PPT"、给一篇论文要成品幻灯片、或要求用 Deep Ocean 学术风排版时使用。
---

# Deep Ocean Slides · 论文到汇报的完整流水线

把一篇论文变成一份**可编辑、可自检、不编造**的中文汇报初稿。排版与配色由工具链保证，
叙事由你（agent）用模型改写，最后由 linter 卡住所有越界与不规范。

## 前置检查（缺一不可）

```bash
python -c "import deepocean" || pip install -e ".[yaml,paper]"     # 需要 Python 3.9+
python -c "import os;print(bool(os.environ.get('DEEPSEEK_API_KEY') or os.environ.get('OPENAI_API_KEY')))"
```

- 没有装包：`pip install "deep-ocean-slides[yaml,paper] @ git+https://github.com/wst320727254-beep/deep-ocean-slides.git"`
- 没有 API key：只能用 `--llm` 之外的**离线骨架**（不调用模型，只用原文句子与数字）。
  让用户自己设置 `DEEPSEEK_API_KEY`（或 `OPENAI_API_KEY`）；**不要**把 key 写进任何文件或提交。

## 标准流程（四步，别跳）

```bash
# 1. 论文 → 摘要包 + 初稿（--llm 让模型改写成中文叙事；2–3 轮自动自修）
deepocean from-paper "<论文.pdf>" --journal "<刊名 · 年份>" --max-figures 1 --llm --build

# 2. 自检：必须 0 error / 0 warn 才算过
deepocean check "<论文.deck.yaml>" --strict

# 3. 网页版（可选，但交付时很加分）
deepocean html "<论文.deck.yaml>" -o "<论文.html>"

# 4. 逐页目视验收（不要只看报告）
python tools/make_preview.py --deck "<论文.deck.yaml>" --out "<目录>/preview.png" --pages 1,2,4,5,8
```

产物：`*.digest.md`（带页码的数字清单）、`*.figures/`（提取的配图）、`*.deck.yaml`（源文件）、
`*.pptx`（成品）、`*.html`、`*.png`（预览）。

## 质量闸门（做不到就不要交付）

1. `deepocean check --strict` 必须 **0 error / 0 warn**。
2. **逐页渲染后真的看过图**：本仓库最容易翻车的三处是 ①文字压到卡片外 ②图表横轴标签残缺
   ③图片没解析到（显示"配图缺失"）。只看自检报告发现不了 ①③。
3. 数字必须能追溯到原文页码；`digest.md` 里每个数字都带 `p<页>`，交付时把这些页码一并给出。
4. 配图 ≤ 2 页（默认 1 页）；没有合适配图就不要放 `image_evidence`。
5. 不编造：写不出结论就用原文最近的句子，或明确标注"自动提取未覆盖，请对照原文补充"。

## 常见故障与处置

| 症状 | 原因 | 处置 |
|---|---|---|
| `check` 报 L002「缺少 title/number/label」 | 模型用错嵌套字段名 | 照报错改 `deck.yaml`（卡片统一 `{title, body, items, tone}`；KPI 用 `{value, label, note, tone}`） |
| 报 L002「chart.categories 不能为空」 | 图表数据没给全 | 补 categories 与等长的 series.values（纯数字，不带 `%`） |
| 页面出现「图表数据缺失」灰框 | 同上，渲染器兜住了 | 同上；这是防崩设计，不是 bug |
| 出现「配图缺失 · image not found」 | 路径相对 deck 文件解析不到 | 用相对 deck 的路径（`figures/xx.png`）或绝对路径 |
| `from-paper` 报无侧栏/无 PyYAML | 少装依赖 | `pip install -e ".[yaml,paper]"` |
| 模型出稿 3 轮仍未过 | 论文结构特殊 | 退回 `deepocean from-paper <pdf>`（离线骨架）再人工补，别硬刚模型 |
| 提取不到矢量图（公式、线稿流程图） | pypdf 只能取内嵌位图 | 让用户截图放进 `figures/`，再加一页 `image_evidence` |

## 交付时一并告诉用户（三件人工事）

1. **数字回原文核对**：工具只搬运不解释，页码在 `digest.md` 与页脚。
2. **改写叙事**：初稿是通顺的搬运，每页最后那句判断要按用户自己的理解重写。
3. **补图**：需要贴论文原图时截图放入 `figures/` 并加 `image_evidence` 页（全篇 ≤ 2 页）。

## 参考

- 设计规范与全部数值：`docs/STYLE.md`
- 令牌与单位换算：`docs/TOKENS.md`
- 交付前清单与规则码：`docs/CHECKLIST.md`
- 最短上手与路线 F（PDF → 初稿）：`docs/TUTORIAL.md`
- 版式字段速查：`deepocean layouts`（13 个版式）
