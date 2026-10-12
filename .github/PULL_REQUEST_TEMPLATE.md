## 这个 PR 做了什么

<!-- 一句话说明，并关联 issue：Closes #123 -->

## 类型

- [ ] 修复排版 / 渲染 bug
- [ ] 新增或调整版式（`schema.py` + `layouts.py` + `html.py`）
- [ ] 设计令牌变更（颜色、字号、边距、配比）
- [ ] CLI / 工具链
- [ ] 文档 / 示例
- [ ] 其它

## 提交前检查

- [ ] `python -m pytest -q` 通过
- [ ] `python -m deepocean demo -o out` 成功
- [ ] `python -m deepocean check out/deep-ocean-demo.pptx --strict` 无 error
- [ ] 改了示例数据时运行过 `python tools/sync_examples.py`
- [ ] 新增/修改版式时，`schema.py`、`layouts.py`、`html.py`、示例四处都同步了
- [ ] 未引入调色板以外的颜色、渐变、投影或装饰插画

## 视觉证据

<!-- 贴改动前后的页面截图；纯文档改动可写 N/A -->
