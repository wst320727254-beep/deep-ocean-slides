# 贡献指南

> **这份文件解决什么问题**：把"怎么把这个仓库跑起来、怎么改、怎么提交、什么条件下能合并"写清楚。读完它你应该能独立完成一次从 fork 到 PR 合并的闭环。
>
> **谁该读它**：任何要向本仓库提交代码、版式、示例或文档的人。

## 目录

| 章节 | 内容 |
|---|---|
| [1](#1-环境搭建) | 克隆、可编辑安装、验证 |
| [2](#2-跑测试) | `pytest`、示例同步检查、产物自检 |
| [3](#3-代码地图) | 每个模块负责什么，改动该落在哪 |
| [4](#4-新增一个版式) | 四处同步的四步法 |
| [5](#5-新增一个组件) | 组件层与 linter 的配合 |
| [6](#6-改设计令牌) | 令牌变更的连带影响 |
| [7](#7-代码风格) | Python 3.9、English docstrings、中文用户可见文案 |
| [8](#8-提交信息规范) | Conventional Commits |
| [9](#9-pr-检查清单) | 合并门禁 |

---

## 1 环境搭建

```bash
git clone https://github.com/wst320727254-beep/deep-ocean-slides.git
cd deep-ocean-slides
pip install -e ".[dev]"
```

`[dev]` 会装上 `pytest`、`PyYAML`；运行期依赖是 `python-pptx >= 0.6.23` 与 `Pillow >= 9.0`。

| 额外依赖组 | 装什么 | 什么时候要 |
|---|---|---|
| `.[yaml]` | PyYAML | 读 `.yaml` deck（只写 JSON 时可省） |
| `.[dev]` | pytest + PyYAML | 开发与测试 |
| `.[all]` | PyYAML | 只想用全功能但不开发 |

**不需要**额外依赖的能力：`import deepocean` 本身不导入 python-pptx。`tokens` / `spec` / `schema` / `color` / `units` 可以在没有 python-pptx 的环境里单独使用；`primitives` / `layouts` / `build` / `html` / `charts` 是按需惰性导入的（见 `src/deepocean/__init__.py` 的 `__getattr__`）。

装好后验证：

```bash
deepocean version              # Deep Ocean 深海学术风 v1.0.0 · MIT
deepocean check examples/demo-deck.yaml
```

> 控制台脚本名是 `deepocean`（`pyproject.toml` 的 `[project.scripts]`）。如果它不在 PATH 上，用等价的模块入口 `python -m deepocean.cli <args>`，或者 `python -c "from deepocean import cli; raise SystemExit(cli.main(['check','examples/demo-deck.yaml']))"`。

---

## 2 跑测试

```bash
python -m pytest                # 全部测试（pyproject 已配 testpaths=tests、pythonpath=src、-q）
python -m pytest tests/test_check.py -q
python -m pytest -k layout -q
```

测试布局：

| 文件 | 覆盖什么 |
|---|---|
| `tests/test_tokens.py` | 令牌自洽：色板唯一性、字号阶梯、`pt = px × 0.75`、CSS/JSON 导出 |
| `tests/test_spec.py` | deck 文档模型、YAML/JSON 读写、必填字段校验 |
| `tests/test_check.py` | linter 的每一条规则（正例 + 反例） |
| `tests/test_units.py` | 单位换算与缩放系数 |
| `tests/check_examples.py` | 每个 `schema.LAYOUTS` 里的版式都被示例覆盖（CI 的 `examples` job 单独跑它） |

除单元测试外，提交前请跑一遍**端到端**的三件事：

```bash
# 1. 参考 deck 能生成 pptx + 单文件 html
deepocean demo -o out

# 2. 产物自检：几何 / 排版 / 色彩规则只在这一步覆盖
deepocean check out/deep-ocean-demo.pptx

# 3. 示例与内置数据不漂移（改过 examples_data.py 时必须跑）
python tools/sync_examples.py --check
```

`tools/sync_examples.py` 负责把 `src/deepocean/examples_data.py` 里的 `DEMO_DECK` / `MINIMAL_DECK` 同步成 `examples/*.yaml` 与 `examples/*.json`。**示例文件是生成物，不要手改**——CI 会检查是否同步。

生成 README 用的预览图（可选，需要 LibreOffice + poppler）：

```bash
python tools/make_preview.py --pages 1,6,7,9,11,12 --cols 2 --scale 0.5
```

---

## 3 代码地图

| 模块 | 职责 | 改动风险 |
|---|---|---|
| `tokens.py` | **单一事实来源**：颜色、字号、四区母版、组件几何、节奏阈值 | 高：影响全篇与 linter |
| `units.py` | px ↔ pt / inch / cm / mm / EMU，目标画布缩放 | 低：纯函数 |
| `color.py` | hex 解析、HLS、WCAG 对比度、禁用色判定、色板审计 | 中：影响 `C001`/`C002`/`K001` |
| `schema.py` | 12 个版式的**字段契约**与别名解析 | 高：是 deck 文档的接口 |
| `spec.py` | deck 文档模型（`Deck` / `Page` / `DeckMeta`）、YAML/JSON 读写、结构校验 | 高：影响所有 deck |
| `primitives.py` | 用**设计 px** 说话的 python-pptx 底层封装、文字度量 | 中：所有版式都经过它 |
| `layouts.py` | 12 个版式的 pptx 几何实现（`render_<layout>`） | 中 |
| `components.py` | 可复用组件（卡片、KPI、图表容器、象限等） | 中 |
| `charts.py` | 图表生成（系列配色、数据标签、显式高度） | 中 |
| `html.py` | 单文件 HTML 渲染器，与 pptx 同像素 | 中 |
| `build.py` | 编译器：画布、主题 XML、文档属性、页循环 | 中 |
| `check.py` | linter：`check_deck`（静态）+ `check_pptx`（产物） | 高：规则码是公共 API |
| `cli.py` | 命令行入口与参数 | 中：CLI 是冻结接口 |
| `examples_data.py` | 内置示例 deck 的数据（论文真实数值） | 低，但要跑同步 |

**一条硬边界**：`check.py` 只许依赖 `tokens` / `schema` / `spec` / `color` / `units` / `primitives`，**不得**依赖 `layouts` / `components` / `build`。linter 必须能审查版式代码自己产出的文件，否则就成了自证。

---

## 4 新增一个版式

版式是"一个 layout 名 + 一套字段 + 两种渲染"。四处必须同步，缺一处就会造成"HTML 预览能看、PowerPoint 里崩掉"的假象，这是明确禁止的状态。

1. **`schema.py`** —— 往 `LAYOUTS` 加一项，声明元信息与字段：

   ```python
   "timeline": {
       "zh": "时间轴",
       "en": "Timeline",
       "hero": False,
       "chrome": True,          # 是否绘制共用母版（仅 cover / closing 为 False）
       "asymmetric": True,
       "fields": {
           "events": _f("list", True, "[{date, title, body, tone}]，3–6 项"),
           "takeaway": _f("str", note="底部一句话"),
       },
   },
   ```

   若该版式算 peak 页，`hero=True`，并同步 `tokens.HERO_LAYOUTS`（两边必须一致）。需要缩写的话加进 `ALIASES`。

2. **`layouts.py`** —— 实现 `render_timeline(slide, page, ctx)`。规则：
   - 坐标一律从 `tokens.BANDS` / `SAFE_MARGIN_PX` / `CARD_GAP_PX` 推导，不写魔数；
   - 颜色一律用角色名（`"primary"` / `"accent"` / `"surface"` …），不写 hex；
   - 文字一律 `primitives.style("token_name")`，不写裸 px 字号；
   - 用 `components.py` 里已有的卡片 / KPI / 标签，不要复制粘贴几何。

3. **`html.py`** —— 实现同名分支，让网页版与 pptx 同像素（同一套 token，同一套坐标）。

4. **示例** —— 往 `examples_data.py` 的 `DEMO_DECK` 加一页真实内容，然后：

   ```bash
   python tools/sync_examples.py            # 重新生成 examples/*.yaml|json
   deepocean demo -o out
   deepocean check out/deep-ocean-demo.pptx
   python -m pytest -q
   ```

`tests/check_examples.py` 会验证"每个版式至少被示例覆盖一次"，所以第 4 步不是可选的。

---

## 5 新增一个组件

组件是版式之间的复用单元（卡片、KPI 列、图表容器、流程节点、象限、表格）。

1. 先在 `tokens.py` 里确认几何常量存在；缺了就**加 token**（如 `TIMELINE = {"dot": 12, "gap_px": 24}`），不要往组件代码里塞数字。
2. 在 `components.py` 实现函数，签名风格与现有一致：接受 `slide` + 设计 px 坐标 + 语义化的关键字参数（`tone` / `items` / `footer`）。
3. 若组件会画出新的形状类型，确认 `check.py` 的产物探测能正确读到它的字号与填充色（新形状类型要在 `_ShapeInfo` 的探测里被覆盖）。
4. 在至少两个版式里复用它，证明抽象站得住；只服务一个版式的东西放 `layouts.py` 里更合适。
5. 加测试：几何（坐标 / 尺寸落在 token 区间内）+ 一条 `check_pptx` 用例。

---

## 6 改设计令牌

令牌值变更影响面很大，按这份清单走：

1. **改 `tokens.py`**（唯一允许的修改点），不要在任何其它模块里写字面值。
2. **同步文档**：`docs/TOKENS.md`（值 + 影响范围）、必要时 `docs/STYLE.md`（规范表）。
3. **同步 `CHANGELOG.md`**：值变更进 `Changed`，新增进 `Added`，改名/删除进 `Changed` 并说明是 **breaking**。
4. **检查 linter**：若改的是 `TYPE_RULES` / `RHYTHM_RULES` / `RATIO_BUDGET` / `FORBIDDEN`，`check.py` 的阈值是**从 token 读的**，规则行为会跟着变——请同步更新 `docs/CHECKLIST.md` 里对应的规则说明，并补/改 `tests/test_check.py`。
5. **跑完整验证**：`python -m pytest`、`deepocean demo -o out`、`deepocean check out/deep-ocean-demo.pptx`、`python tools/sync_examples.py --check`。

改名规则（详见 `docs/TOKENS.md` §10）：**token 名属于公共 API**，改名或删除必须走大版本；新增走小版本；只改值走 patch/minor。

---

## 7 代码风格

### 基础约定

| 项 | 约定 |
|---|---|
| Python 版本 | **3.9+**（`requires-python = ">=3.9"`；`ruff` 的 `target-version = "py39"`） |
| 行宽 | **110**（`[tool.ruff] line-length`） |
| 未来注解 | 每个模块开头 `from __future__ import annotations` |
| 类型标注 | 公共函数必须有；用 `typing` 的 `Dict` / `List` / `Optional`，不要用 3.10 的 `X \| Y` |
| 文件头 | `# -*- coding: utf-8 -*-` |
| 数据模型 | 优先 `@dataclass`（`frozen=True` 用于不可变值对象，如 `Swatch` / `TypeToken`） |
| 有序映射 | 需要稳定顺序时用 `OrderedDict`（`PALETTE` / `TEXT_COLORS` / `TYPE_SCALE`） |

### 注释与字符串

- **docstring 用英文**。模块级 docstring 说明这个模块解决什么问题、和谁协作；函数级用一行祈使句（`"""Compile ``deck`` to a .pptx file."""`）。
- **用户可见文案用中文**：CLI 帮助、报错信息、linter 的 `RULE_CODES` 描述、生成到幻灯片上的默认文字。
- **代码标识符用英文**：变量、函数、字段名、token key 一律英文小写下划线。
- 注释解释**为什么**，不解释**是什么**。数值型常量旁注明来源（如 `# 72 - 140`）。

### 中文排版注意

- 源文件统一 UTF-8；不要用全角标点写代码（字符串里的中文文案除外）。
- 中文字符串与变量之间留空格：`f"第 {index} 页"`。
- 面向用户的中文尽量用直角引号「」或西文双引号，不要混用。

### 一个必须遵守的架构约束

**幻灯片几何只允许用设计 px 表达**，EMU 的换算只能在 `primitives` 内部出现一次。任何地方再乘一次 `9525` 都会产生双重换算 bug。

---

## 8 提交信息规范

采用 [Conventional Commits](https://www.conventionalcommits.org/)：

```
<type>(<scope>): <subject>

<body>

<footer>
```

**type**：

| type | 用途 |
|---|---|
| `feat` | 新功能（新版式、新组件、新 CLI 子命令、新规则码） |
| `fix` | 修 bug（渲染错位、溢出误判、字段解析失败） |
| `docs` | 只改文档 |
| `style` | 只改格式，不改行为 |
| `refactor` | 既不是新功能也不是修 bug 的重构 |
| `perf` | 性能 |
| `test` | 测试 |
| `build` | 打包 / 依赖 / 构建系统 |
| `ci` | CI 配置 |
| `chore` | 杂项（`.gitignore`、版本号） |

**scope** 用模块名：`tokens` `schema` `spec` `primitives` `layouts` `components` `charts` `html` `build` `check` `cli` `examples` `docs`。

**subject**：中文或英文均可，祈使句、不加句号、不超过 50 字符。

示例：

```
feat(schema): 新增 timeline 版式（时间轴）

- schema.LAYOUTS 增加 timeline 条目与字段表
- layouts.render_timeline / html 分支同步实现
- examples_data.DEMO_DECK 补一页真实内容并同步 examples/

Closes #42
```

```
fix(check): closing 页不再被 M002 误判为压顶条

closing 属于 CHROME_EXEMPT_LAYOUTS，自绘加高顶条，
M002 应跳过 chrome=False 的版式。

Fixes #57
```

**BREAKING CHANGE**：改名或删除 token / layout 名 / 必填字段时，在 footer 写明：

```
BREAKING CHANGE: tokens.PALETTE 的 `grayblue` 改名为 `slate`；
所有 deck 与自定义版式需同步更新。
```

---

## 9 PR 检查清单

提交前逐条确认（与 `.github/PULL_REQUEST_TEMPLATE.md` 一致）：

- [ ] `python -m pytest -q` 通过
- [ ] `deepocean demo -o out` 成功
- [ ] `deepocean check out/deep-ocean-demo.pptx --strict` 无 error
- [ ] `deepocean check examples/demo-deck.yaml --strict` 通过
- [ ] 改了 `examples_data.py` 时运行过 `python tools/sync_examples.py`，且工作区无漂移
- [ ] 新增 / 修改版式时，`schema.py`、`layouts.py`、`html.py`、示例**四处都同步**了
- [ ] 未引入调色板以外的颜色、渐变、投影或装饰插画
- [ ] 改了 token 值时，`docs/TOKENS.md`、`docs/STYLE.md`、`CHANGELOG.md` 同步了
- [ ] 新增规则码时，`check.RULE_CODES`、`RULE_META`、`docs/CHECKLIST.md` 三处同步了
- [ ] PR 描述里有视觉证据（改动前后的页面截图；纯文档改动写 `N/A`）

CI 会跑两个 job：`test`（ubuntu + windows × py3.9/3.12：单测 → 生成参考 deck → 产物自检 → 静态严格自检）与 `examples`（`tests/check_examples.py`：每个版式都被示例覆盖）。

**关于 `--strict`**：它的语义是"存在任何 `error` 或 `warn` 即非零退出"（`info` 不拦）。参考 deck 的静态检查与产物检查**都通过 `--strict`**，所以 PR 门禁就是 `deepocean check --strict`。新增规则码时，请同时在 `tests/test_check.py` 里给出正例与反例，否则新规则无法被回归保护。

---

**延伸阅读**

- 设计规范与全部数值 → [`docs/STYLE.md`](docs/STYLE.md)
- 令牌参考与兼容约定 → [`docs/TOKENS.md`](docs/TOKENS.md)
- 使用与复刻教程 → [`docs/TUTORIAL.md`](docs/TUTORIAL.md)
- 自检清单与规则码含义 → [`docs/CHECKLIST.md`](docs/CHECKLIST.md)
