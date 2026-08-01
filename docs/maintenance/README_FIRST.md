# 一键开局维护入口

> 本文已于2026-08-01按v2.4状态更新（回归通过、正式包已构建；标签与工坊上传另行完成）。

## 当前版本状态

- 正式版本：**v2.4**（继承v2.3正式基准的修复集，维护者已确认v2.4-test1实机回归通过，正式包SHA-256已确定性重建）。
- 上一稳定基准：v2.3（Steam工坊物品 `3767025052`，旧 Manifest `7223939852636260892` 已被 v2.4 覆盖）。
- 状态说明：v2.4 已于 2026-08-01 完成实机回归、构建正式包、推送 Git 标签 `v2.4`、挂附件 GitHub Release，并上传 Steam 工坊物品 `3767025052`（Manifest `385131838239799795`）；工坊物品ID不变。
- 实机状态：维护者已确认v2.4-test1逐项实机通过，四份日志干净（`error.log`仅原版网络噪音、`game.log`仅原版Conflict Risk杂音、`setup.log`正常加载PRC_OCS分类/决议/事件、`text.log` 0字节）。
- GitHub：正式源码位于 `main`；正式标签按发版门禁创建，自 v2.4 起 Release 挂正式包 ZIP 附件（ASCII 文件名 + 中文显示名）便于维护取用。

v2.4在v2.3全国家通用MIO路线、通用进化编制与跨国家切换功能基础上，完成雷达科技归位空军特殊科研、进化装备设计与库存同步、船坞/民用工厂可重复点至上限、全地图碉堡收敛、点数/经验剥离为独立决议，并修复本地部署加载结构。共享MIO生成表仍覆盖444家公司、4945项目标特质，不额外增加资金或等级，方针由玩家手动选择。

标签注意事项：旧 `v2.0` 标签误落在源码导入之前，不能作为MOD源码使用；真正的v2.0源码基准为提交 `9593154`，补充标签为 `v2.0-source-baseline`。`v2.1`标签内游戏内容正确，但旧构建器会误装v2.0基准文档。今后标签必须在构建器、基准文档和源码全部定稿后创建。

## 建议阅读顺序

1. 根目录 `AGENTS.md`：当前状态、修改红线与发布门禁。
2. `docs/maintenance/功能与版本交接单.md`：功能边界与版本演进。
3. `docs/maintenance/技术实现与通用化边界.md`：脚本架构、作用域与踩坑记录。
4. `docs/maintenance/测试状态与回归清单.md`：实机结论与待扩展样本。
5. `docs/DEVELOPMENT.md`：构建、验证、发布与工坊上传。

## 维护纪律

- v2.4为当前稳定基准，后续不得退回旧版本继续开发。
- `PRC_OCS_`前缀是稳定键名，不做批量重命名。
- 通用玩家决议必须保留AI守卫；PRC增强层同时覆盖 `tag = PRC` 与 `original_tag = PRC`。
- 建设只处理当前国家拥有且控制的州；同一作用域不得出现多个 `limit`。
- 不修改原版国策、国家历史与事件链。
- `dist/`只由 `tools/build_release.py`生成。

## 快速验证

```powershell
python tools/generate_universal_mio_effect.py --check
python tools/validate_mod.py
python -m unittest tools.test_validate_mod
python tools/build_release.py
```

正式包哈希使用：

```powershell
Get-FileHash -Algorithm SHA256 dist\开局一键爽玩_v2.4_正式版.zip
```