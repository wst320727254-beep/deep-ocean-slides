# Changelog

本项目的所有重要变更都记录在这里。

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

约定（与 `docs/TOKENS.md` §10 一致）：

- **新增**令牌 / 版式 / 规则码 → `minor`
- **只改值**（hex、px、阈值）→ `patch` 或 `minor`
- **改名或删除**令牌名 / layout 名 / 必填字段 → `major`，并在条目里写明 **BREAKING**

## [Unreleased]

### Added

- **`deepocean from-paper <pdf>`**：论文 PDF → 摘要包（章节 / 数字 / 表格 / 候选配图）→ 可编译的 `deck.yaml` 初稿。
  - `deepocean/paper.py`：离线提取（pypdf），标题用页面最大字号识别，数字带原文页码，配图自动过滤图标并按"图注关键词 + 形状"排序。
  - `deepocean/author.py`：离线骨架（只用原文内容，绝不编造）与 `--llm` 模型出稿（OpenAI 兼容端点，输出过 schema 校验，失败自动纠一轮）。
  - 表格只在"网格一致 + 填充率高 + 含数字"时才成页；配图页默认 1 页、上限 2 页。
- **第 13 个版式 `image_evidence`**（图片证据页）：论文配图 + 图注 + 来源 + 右侧解读卡；PPTX 与 HTML 两个渲染器同时实现，图片按 contain 等比缩放并加 1px 细框，HTML 版内联 base64 保持单文件。
- `primitives.picture()` / `fit_box()` / `resolve_asset()`：px 单位的等比插图原语，相对路径按 deck 文件所在目录解析。
- `tools/make_preview.py --deck`：可预览任意 deck（不再只限内置示例）。
- 可选依赖 `[paper]`（pypdf）；`tests/test_paper.py` 15 个测试。

### Fixed

- 无。

### Docs

- 贡献指南 `CONTRIBUTING.md`：环境搭建、测试、版式与组件扩展流程、Conventional Commits、PR 门禁。
- 设计文档集 `docs/`：`STYLE.md`（风格规范与代码对照）、`TOKENS.md`（令牌参考手册）、`TUTORIAL.md`（复刻路线与 FAQ）、`CHECKLIST.md`（交付前自检清单与 CI 接入）。

## [1.0.0] - 2026-10-12

首个公开发布。把《Deep Ocean 学术风 PPT · 风格规范与制作教程》里的一份手工设计规范，工程化为可执行、可自检、可迁移的代码。

### Added

**设计令牌（单一事实来源）**

- `deepocean.tokens`：整套设计系统的唯一定义处——四区母版（A 顶条 60 / B 标题 72–140 / C 内容 200–640 / D 页脚 680–720）、安全边距 40 px、卡间距 20 px、12 个色板 token（`navy` `teal` `grayblue` `brick` `white` `light` `mint` `pink` `line` + `t1` `t2` `t3`）、22 档字号阶梯、组件几何（圆角 / 描边 / 内边距 / KPI / 图表 / 流程 / 矩阵 / 表格）与节奏阈值。
- 语义角色表 `tokens.ROLES`：版式代码按角色取色（`primary` / `accent` / `down` / `complementary` …），不写死 hex。
- 配比预算 `tokens.RATIO_BUDGET` 与机器可检的禁用色规则 `tokens.FORBIDDEN`（紫粉玫红、金色、高饱和橙绿、纯黑大底）。
- 导出接口：`tokens.summary()`（JSON）、`tokens.css_variables()`（CSS 自定义属性）、`tokens.hex_of()` / `swatch()` / `type_token()` / `allowed_hexes()`。
- `deepocean.units`：`pt = px × 0.75`、`inch = px / 96`、`cm = px × 0.0264583`、EMU 换算，以及四档目标画布缩放系数 `TARGETS`（1280×720 ×1.0 / 1920×1080 ×1.5 / 2560×1440 ×2.0 / 3840×2160 ×3.0）。
- `deepocean.color`：hex 解析、HLS、WCAG 相对亮度与对比度、禁用色判定、色板审计、混色与色阶。

**页面契约与生成器**

- `deepocean.schema`：12 个版式的字段契约——`cover` `two_column` `big_number` `experiment_design` `roadmap` `chart_insight` `split_cards` `concept_flow` `matrix2x2` `data_table` `key_findings` `closing`，每个版式声明中英文名、Hero 标记、是否绘制共用母版、是否非对称、必填与可选字段；并提供别名解析（`two-col` / `chart` / `matrix` …）与 Markdown 字段表输出。
- `deepocean.spec`：deck 文档模型（`Deck` / `Page` / `DeckMeta`）、YAML 与 JSON 双向读写、结构校验。YAML 支持是可选依赖，缺失时给出带指引的错误。
- `deepocean.primitives`：用 **1280×720 设计 px** 说话的 python-pptx 底层封装（`rect` / `oval` / `add_text` / `add_arrow` / `bullets` / `shape_with_text` / `hairline`），以及 CJK 友好的文字度量（`measure_text` / `wrap_lines` / `text_height` / `fit_size` / `truncate`）。
- `deepocean.layouts`：12 个版式的 PowerPoint 几何实现。
- `deepocean.components` / `deepocean.charts`：可复用组件与图表生成（系列配色、强制数据标签、强制显式高度）。
- `deepocean.build`：编译器。设定 1280×720 画布、写入文档属性，并把 Deep Ocean 的颜色槽与字体写进 `ppt/theme/theme1.xml`，使 PowerPoint 自己的颜色与字体选择器与研究者的选择一致。

**HTML 渲染器**

- `deepocean.html`：与 pptx 同像素的**单文件** HTML 渲染器，无外部资源依赖，可直接在任意浏览器打开或 Ctrl/Cmd + P 导出 PDF。

**自动排版自检（linter）**

- `deepocean.check`：两层检查，共 31 条规则码。
  - `check_deck`（静态，13 条）：`D001` `D002` `L001` `L002` `L003` `R001`–`R006` `X001` `X002`。
  - `check_pptx`（产物，18 条）：`M001`–`M004` `T001`–`T005` `C001`–`C005` `K001` `A001` `H001` `H002`。
- 产物检查把每个形状换算回设计 px 实测：安全边距、顶条预留区、内容撑满、最小字号、字体家族与字重上限、文字溢出、色板合规、禁用色、砖红与浅色底占比、对比度（≥ 32 px 大字放宽到 3.0）、视觉锚点、图表数据标签与显式高度。
- 报告对象提供 `to_text(color=True)` / `to_json()` / `ok()` / `errors()` / `warnings()` / `infos()` / `by_code()` / `counts()`。
- 严格的依赖边界：`check` 只依赖 `tokens` / `schema` / `spec` / `color` / `units` / `primitives`，不依赖 `layouts` / `components` / `build`，因此能审计版式代码自己产出的文件。

**命令行**

- `deepocean` CLI：`build` / `html` / `check` / `preview` / `init` / `layouts` / `tokens` / `units` / `demo` / `version`。
- `deepocean check` 支持 `--json`（机器可读）与 `--strict`（存在任何警告即非零退出），可直接用作交付门禁与 CI 门禁。
- `deepocean tokens` 支持 `--json` / `--md` / `--css` 三种导出，供文档、机器消费与设计稿复用。
- `deepocean preview` 一次产出 pptx + html + 自检报告。

**示例**

- `examples/demo-deck.yaml` / `.json`：13 页参考实现，覆盖全部 12 个版式，数值来自 Yuan, Chen, Wang & Sun (2025), *Information Systems Research* 36(1): 84–106（DOI 10.1287/isre.2022.0294），无占位文字。
- `examples/minimal-deck.yaml` / `.json`：3 页最小模板，即 `deepocean init` 写出的内容。
- 示例文件由 `tools/sync_examples.py` 从 `src/deepocean/examples_data.py` 生成，保证内置数据与仓库示例不会漂移；CI 校验同步状态。
- `tools/make_preview.py`：从真实 pptx 经 LibreOffice + poppler 渲染出接触印相图，供 README 使用。

**测试与持续集成**

- `tests/`：令牌自洽、文档模型与序列化、单位换算、linter 每条规则的正反例，以及"每个版式都被示例覆盖"的校验。
- `.github/workflows/ci.yml`：ubuntu 与 windows × Python 3.9 / 3.12 跑单测、导出令牌、生成参考 deck 并做产物严格自检；另有独立 job 校验示例与 schema 的一致性。

**文档**

- `README.md`：项目定位、安装、最短上手路径与预览图。
- `docs/STYLE.md`：风格规范（设计哲学、画布与栅格、色彩系统与配比预算、字号阶梯、组件规格、页面节奏、12 页逐页坐标），以及新增章节「从规范到代码」与「版式库」。
- `docs/TOKENS.md`：令牌参考手册（名称、值、语义、代码位置、影响范围）、单位换算与目标画布、CLI 导出格式、版本与向后兼容约定。
- `docs/TUTORIAL.md`：五条路线（CLI / 手工 PowerPoint / Keynote / Figma 与 Canva / Python API 写自定义版式）与常见问题。
- `docs/CHECKLIST.md`：交付前自检清单（规范原文逐条 + 对应规则码），以及 `deepocean check --strict` 的 CI 接入方式。
- `CONTRIBUTING.md`：环境搭建、测试、新增版式与组件、代码风格、提交信息规范、PR 检查清单。

### Notes

- **本包尚未发布到 PyPI。** 请从 GitHub 克隆后 `pip install -e ".[yaml]"`；`pip install deep-ocean-slides` 目前不会从 PyPI 取到任何东西。
- `python-pptx >= 0.6.23` 与 `Pillow >= 9.0` 是运行期依赖；PyYAML 仅在读写 `.yaml` deck 时需要。
- `import deepocean` 本身不导入 python-pptx：令牌、文档模型、单位与颜色工具可以在没有 Office 相关依赖的环境里独立使用。

[Unreleased]: https://github.com/wst320727254-beep/deep-ocean-slides/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/wst320727254-beep/deep-ocean-slides/releases/tag/v1.0.0
