# AGENTS.md — 一键开局项目入口

《开局一键爽玩 / One-Click Sandbox Start》是《钢铁雄心 IV》单人沙盒开局 MOD。所有功能仅供玩家国家使用（`is_ai = no`，AI 不可执行），架构为“通用核心 + PRC 增强层”。

## 自然语言任务路由

- **普通讨论、问答和只读检查**：直接处理，不启动维护流程。
- **小型、可逆、范围明确的文案、纯文档和机械性小修**：一句话对齐后即可实施；不强制独立复检，不强制留档；完成后仍须机主明确说出「提交」才可 git commit。
- **命中以下任一条件即升级为重流程**，走 `docs/maintenance/维护与重构标准流程.md` 的 A/C 流程，保留方案拍板、强制独立复检与对应验证：MOD 语义、事件或作用域、生成器、AI 守卫、编码与本地化契约、存档兼容、跨模块、实机结果、构建或发布。
- **明确授权词**：日常任务可用自然语言启动与执行；但「提交」与「推送」分别需机主明确说出（自然语言表达即可），不得从「确认」「照批」「按推荐」等拍板词推断。

## 当前状态

当前版本、发布状态、Manifest 与分支概况的唯一人类可读权威入口是 `docs/maintenance/README_FIRST.md`（带核实日期）；分支、提交、标签等机器可查询事实以 Git 本身为权威，本文不重复登记。功能史、测试史与发布细节分别见 `docs/maintenance/功能与版本交接单.md`、`docs/maintenance/测试状态与回归清单.md`、`docs/DEVELOPMENT.md`，不集中复制。

## 修改红线

1. 不批量重命名 `PRC_OCS_` 键名，避免破坏事件、本地化和存档引用。
2. 通用决议必须同时保留 `is_ai = no` 与 `ai_will_do = { factor = 0 }`。
3. PRC 增强层必须同时覆盖 `tag = PRC` 和 `original_tag = PRC`。
4. 建设以当前国家**控制**的州为准：**工业类建设**（共享槽位、石化、船坞、民用工业）继续只处理**拥有且控制**的州（`every_owned_state` + 单一 `limit` 中的 `is_controlled_by = ROOT`，避免非核心州工厂产出惩罚）；**占领区基建**（基础设施、防空、机场/港口）在**控制但非拥有**的州上由独立决议 `PRC_OCS_develop_occupied_territory` 处理（`every_controlled_state` + `NOT = { is_owned_by = ROOT }`）；补给站加速为国家级 modifier。
5. 同一作用域只能有一个 `limit` 块；多条件合并其中。禁止复活 v2.0c 的 `Multiple limits in target effect` 错误。
6. 不修改原版国策、国家历史和事件链。
7. `common/`、`events/` 脚本必须是 UTF-8 无 BOM；`localisation/` yml 必须是 UTF-8 带 BOM，英/简中同步。
8. 不手工编辑 `dist/`；只由 `tools/build_release.py` 生成。
9. `packaging/OCS_one_click_sandbox_start_v2_0.mod` 的文件名和安装目录约定不得更改；其版本信息必须与 `descriptor.mod` 一致。
10. `thumbnail.png` 版权保留、不适用 GPL；衍生发布必须删除或替换。`LICENSE`、`NOTICE.md` 不得随意修改。

## 验证与发布底线

MOD 内容改动后必须通过静态门禁与维护者实机回归；发布按固定顺序执行（源码 → 静态检查 → 实机回归 → 文档 → 构建与 SHA → 维护者确认 → 标签/Release），只有实机通过并经维护者确认后才能创建正式标签与 Release。验证命令、CWTools、实机回归归档、构建、发布与工坊上传的操作细节以 `docs/DEVELOPMENT.md` 为唯一权威；发布类操作动手前先列出 `tools/` 并读该文档对应章节，确认仓库现成脚本与方法，不得绕开现成工具自造轮子。

## 关键目录

- MOD 源码：`common/decisions/`、`common/scripted_effects/`、`events/`
- 双语本地化：`localisation/english/`、`localisation/simp_chinese/`
- 验证与构建：`tools/validate_mod.py`、`tools/test_validate_mod.py`、`tools/build_release.py`
- 正式/测试证据：`docs/baseline/`、`docs/testing/`
- 流程与发布：`docs/DEVELOPMENT.md`、`docs/maintenance/`、`docs/publishing/`
- 生成产物：`dist/`（不进 Git）

改代码前按需阅读对应源码头部注释和 `docs/maintenance/技术实现与通用化边界.md`；发版前阅读 `docs/DEVELOPMENT.md` 及当期发布文案。文档使用中文，README、发布文案和本地化保持中英双语；提交信息使用中文摘要式短句。
