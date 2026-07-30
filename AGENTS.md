# AGENTS.md — 一键开局项目入口

## 项目与当前基准

《开局一键爽玩 / One-Click Sandbox Start》是《钢铁雄心 IV》单人沙盒开局 MOD。所有功能仅供玩家国家使用（`is_ai = no`，AI 不可执行），架构为“通用核心 + PRC 增强层”。

- 当前稳定基准：**v2.3**。维护者于2026-07-31确认实机回归通过，已上传 Steam 工坊既有物品 `3767025052`（Manifest `7223939852636260892`）；Git标签与无附件Release在发布分支合并后创建。
- v2.3 的共享 MIO 由生成器维护全国家通用公司表：444家公司、4945个目标特质均先确认当前国家实际拥有，再直接进入对应 `mio:` 作用域；不存在的公司跳过，不使用国家 tag 分支。德国沿用test7的319项，英国按test8补为177项，test9/test10的日苏澳捷意美实际已点路线共1190项；其余公司使用确定性的最大合法路线。PRC原有4家专属MIO继续独立维护。仍不增加资金或额外等级，MIO方针由玩家手动选择。
- v2.3 同时完成通用进化编制、中自火纠正、每国一次性标志与跨国家切换修复。分类使用 `allowed = { always = yes }` 为所有国家实例化，仍由分类/决议的 `visible`、所有决议的 `available = { is_ai = no }` 与 `ai_will_do = 0` 阻止AI使用；维护者实机确认同局切换国家后分类正常出现。
- 除完成上述测试线与可选多国扩大回归外，暂无新功能计划。

状态冲突时，以本文件、Git HEAD/标签、`docs/baseline/`、实机证据和维护者确认依次核对；工程检查不能代替实机确认。版本史与详细证据见：

- `docs/maintenance/README_FIRST.md`
- `docs/maintenance/功能与版本交接单.md`
- `docs/maintenance/技术实现与通用化边界.md`
- `docs/maintenance/测试状态与回归清单.md`

## 修改红线

1. 不批量重命名 `PRC_OCS_` 键名，避免破坏事件、本地化和存档引用。
2. 通用决议必须同时保留 `is_ai = no` 与 `ai_will_do = { factor = 0 }`。
3. PRC 增强层必须同时覆盖 `tag = PRC` 和 `original_tag = PRC`。
4. 建设只能处理当前国家拥有且控制的州：`every_owned_state` + 单一 `limit` 中的 `is_controlled_by = ROOT`。
5. 同一作用域只能有一个 `limit` 块；多条件合并其中。禁止复活 v2.0c 的 `Multiple limits in target effect` 错误。
6. 不修改原版国策、国家历史和事件链。
7. `common/`、`events/` 脚本必须是 UTF-8 无 BOM；`localisation/` yml 必须是 UTF-8 带 BOM，英/简中同步。
8. 不手工编辑 `dist/`；只由 `tools/build_release.py` 生成。
9. `packaging/OCS_one_click_sandbox_start_v2_0.mod` 的文件名和安装目录约定不得更改；其版本信息必须与 `descriptor.mod` 一致。
10. `thumbnail.png` 版权保留、不适用 GPL；衍生发布必须删除或替换。`LICENSE`、`NOTICE.md` 不得随意修改。

## 验证与发布门禁

任何 MOD 内容修改后必须依次完成：

```powershell
python tools/validate_mod.py
python -m unittest tools.test_validate_mod
python tools/build_release.py
```

随后核对生成的 SHA-256，并由维护者实机回归；保存和检查 `error.log`、`game.log`、`setup.log`、`text.log` 及必要截图。`error.log` 0字节表示干净；`game.log` 的 `Conflict Risk` 是已知原版杂音；`text.log` 0字节可以表示未发现文本错误。具体覆盖范围见测试清单。

正式顺序为“源码 → 静态检查 → 实机回归 → 文档 → 构建与 SHA → 维护者确认 → Git 标签/Release”。只有实机通过并经维护者确认后才能创建正式标签和 Release；标签必须指向可重建正式包的最后提交。Release 不挂附件，唯一下载入口是 Steam 工坊。

测试包必须带版本号、README、SHA-256 和测试清单，不得冒充正式基准。正式版本变化同步更新 `README.md`、`CHANGELOG.md`、`docs/baseline/`、维护文档及当期发布文案。

## 关键目录

- MOD 源码：`common/decisions/`、`common/scripted_effects/`、`events/`
- 双语本地化：`localisation/english/`、`localisation/simp_chinese/`
- 验证与构建：`tools/validate_mod.py`、`tools/test_validate_mod.py`、`tools/build_release.py`
- 正式/测试证据：`docs/baseline/`、`docs/testing/`
- 流程与发布：`docs/DEVELOPMENT.md`、`docs/maintenance/`、`docs/publishing/`
- 生成产物：`dist/`（不进 Git）

改代码前按需阅读对应源码头部注释和技术实现文档；发版前阅读 `docs/DEVELOPMENT.md` 及当期发布文案。文档使用中文，README、发布文案和本地化保持中英双语；提交信息使用中文摘要式短句。
