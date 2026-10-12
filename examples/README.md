# 示例 / Examples

这两个示例 deck 由 `src/deepocean/examples_data.py` 通过 `tools/sync_examples.py` 生成，
不要直接改这里的文件（CI 会检查是否同步）。

| 文件 | 页数 | 说明 |
|---|---:|---|
| `demo-deck.yaml` / `.json` | 13 | 完整参考实现：覆盖全部 12 个版式，数据来自 Yuan, Chen, Wang & Sun (2025), *ISR* 36(1): 84-106 |
| `minimal-deck.yaml` / `.json` | 3 | 最小可用模板，`deepocean init` 写出的就是这个 |

同一份 deck 同时提供 YAML 与 JSON：带 `PyYAML` 的环境用 YAML（更适合手写），
没装 `PyYAML` 时用 JSON（零依赖）。

## 试着跑一遍

```bash
# 生成 PPTX + 单文件 HTML
deepocean preview examples/demo-deck.yaml --out out

# 只做自检（规范第 09 节的自动部分）
deepocean check examples/demo-deck.yaml

# 不改文件，打印某一页用到的字段结构
deepocean layouts chart_insight
```

## 自己改一页

1. 复制 `minimal-deck.yaml` 到你的目录；
2. 用 `deepocean layouts` 查到目标版式的字段名；
3. 改完先 `deepocean check` 再 `deepocean build`——linter 会告诉你越界、字号过小、
   用了调色板以外的颜色，或者在 `data` 里留下了 `TODO`。

```bash
deepocean init mytalk          # 生成 3 页模板
deepocean init mytalk --demo    # 生成完整 13 页示例
```
