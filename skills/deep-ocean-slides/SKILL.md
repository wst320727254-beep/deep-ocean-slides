---
name: deep-ocean-slides
description: 完全离线地把论文 PDF、组会材料或一个主题做成 Deep Ocean 学术风 16:9 汇报 PPT（真·可编辑 .pptx + 单文件 HTML + 自动排版自检 + 论文配图页），不需要任何 API key 或付费服务。当用户要"做文献汇报/组会 PPT/开题答辩 PPT"、给一篇论文要成品幻灯片、或要求用 Deep Ocean 学术风排版时使用。
---

# Deep Ocean Slides · 离线论文到汇报流水线

**这个技能不需要联网、不需要 API key、不产生任何费用。** 提取、排版、配色、自检、导出全部本地完成；
"读懂论文并写成中文叙事"这一步由 **你（agent）自己** 完成——你就是那个模型。

产出：真·可编辑的 `.pptx`（PowerPoint 里能继续改）+ 单文件 `.html`（浏览器 Ctrl+P 导出 PDF）
+ 逐页预览图，并且 `deepocean check --strict` 必须 **0 错误 / 0 警告**。

## 前置（只有一条）

```bash
python -c "import deepocean" 2>/dev/null || pip install "deep-ocean-slides[yaml,paper] @ git+https://github.com/wst320727254-beep/deep-ocean-slides.git"
```

- 需要 Python 3.9+。依赖只有 python-pptx / Pillow / PyYAML / pypdf，**无需任何密钥**。
- 若用户**主动要求**由远端模型改写叙事，才用 `--llm`（那时才需要 `DEEPSEEK_API_KEY`/`OPENAI_API_KEY`）。
  默认不要提这个选项，也不要把任何 key 写进文件。

## 标准流程（五步，全部离线）

```bash
# ① 提取：PDF → 摘要包 + 配图 + 结构骨架（纯本地，不联网）
deepocean from-paper "<论文.pdf>" --digest "<论文.digest.md>" --figures "<目录>/figures" --max-figures 1

# ② 写作：这是你的活。读 digest.md，按 docs/AUTHORING.md 的契约写 中文 deck.yaml
#    - 每页标题写成"判断"（结论），不是话题
#    - 数字只从 digest 里搬，且把页码写进 note/footer
#    - 骨架 deck.yaml 只作参考：保留了原文要点，需要你改写成中文叙事
#    （写作契约：docs/AUTHORING.md，含 13 个版式的可复制示例）

# ③ 离线修结构：列宽、序列长度、tone、hero 占比（不编内容）
deepocean normalize "<论文.deck.yaml>"

# ④ 自检：必须 0 error / 0 warn，否则照规则码改
deepocean check "<论文.deck.yaml>" --strict

# ⑤ 出片 + 目视验收
deepocean preview "<论文.deck.yaml>" --out "<目录>/out"
python tools/make_preview.py --deck "<论文.deck.yaml>" --out "<目录>/preview.png" --pages 1,2,4,5,8
```

## 写作契约（离线能做与不能做）

- **能做**：选版式、写判断式标题、把 digest 里的句子改写成中文、把数字排版进图表/KPI/表格、写解读。
- **不能做**：编造 digest 里没有的数字、结论或引用。缺内容就写"自动提取未覆盖，请对照原文第 N 页补充"。
- **版式字段**：先 `deepocean layouts <layout>` 查契约再写；13 个版式的可复制示例见 `docs/AUTHORING.md`。
- **配图**：只用 `--figures` 导出的 PNG；`image_evidence` 全篇 ≤ 2 页（默认 1 页）。
- **配色**：只用调色板 token（`navy/teal/grayblue/brick/white/light/mint/pink/line`、文本 `t1/t2/t3`），不要手填 hex。
- **字号**：正文 ≥ 13px（`card_body`），辅助文字 ≥ 11px。

## 质量闸门（做不到就不要交付）

1. `deepocean check --strict` → **0 error / 0 warn**。
2. **逐页渲染后真的看过图**（第 ⑤ 步的 preview.png）：自检抓不到"字压出卡片""横轴标签被截断"
   "图片没解析到（显示'配图缺失'）"这三类。
3. 数字全部可追溯到原文页码（`digest.md` 里带 `p<页>`）。
4. 配图 ≤ 2 页；没有合适配图就不用 `image_evidence`。
5. 至少一页是"峰值页"（`big_number` / `chart_insight` / `key_findings`），Hero 占比 25%–45%。

## 常见故障处置（全部离线可修）

| 症状 | 处置 |
|---|---|
| `L002` 缺少 `title`/`number`/`label` | 嵌套项名字写错。卡片统一 `{title, body, items, tone}`；KPI 用 `{value, label, note, tone}` |
| `L002` chart.categories 为空 / 数值与类目不等长 | 补 categories 与等长 values（纯数字，不带 `%`），或 `deepocean normalize` |
| `L002` rows 单元格数不一致 | `deepocean normalize` 自动补齐/截断 |
| `R002` Hero 占比超 45% | `deepocean normalize` 自动收敛 |
| 页面出现"图表数据缺失"灰框 | 渲染器的防崩兜底：回到 `deck.yaml` 补数据即可 |
| 出现"配图缺失 · image not found" | 路径要相对 deck 文件（如 `figures/x.png`）或绝对路径 |
| 缺少 PyYAML/pypdf | `pip install -e ".[yaml,paper]"` |
| 提取不到矢量图（公式、线稿流程图） | 让用户截图放进 `figures/`，再加一页 `image_evidence` |

## 交付时一并告诉用户（三件人工事）

1. **数字回原文核对**：工具只搬运不解释，页码在 `digest.md` 与页脚。
2. **叙事再改一遍**：初稿是"能讲的版本"，但上台前请用户按自己的理解重写每页最后那句判断。
3. **补图**：需要论文原图时截图放入 `figures/`，加 `image_evidence` 页（全篇 ≤ 2 页）。

## 参考

- 手写契约（13 版式示例 + 规则码对照）：`docs/AUTHORING.md`
- 设计规范与全部数值：`docs/STYLE.md` · 令牌：`docs/TOKENS.md` · 交付清单：`docs/CHECKLIST.md`
- 最短上手与五条复刻路线：`docs/TUTORIAL.md`
- 版式字段速查：`deepocean layouts`（13 个版式）
