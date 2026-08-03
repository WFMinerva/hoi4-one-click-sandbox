# 一键开局维护入口

> 本文已于2026-08-03按v2.7状态更新（一键骷髅师实机生效；正式包已构建）。

## 当前版本状态

- 正式版本：**v2.7**（在v2.6稳定基准之上新增一键骷髅师、开发占领区、补给站建设加速，并完成科研选项效果描述优化；见 `docs/baseline/` 与 `CHANGELOG.md`）。
- 上一稳定基准：v2.6（Steam工坊物品 `3767025052`，Manifest `3609146315690391433`；特殊科研原型奖励逐项选择版26组扩展）。
- 状态说明：v2.7 测试包已完成实机回归（一键骷髅师实机生效、四份日志洁净）；正式包由 `tools/build_release.py` 构建（SHA-256 `3587cdadf60764465900afb7f5a7e9cfc98cdfae51096367b311e7801bb45080`）；Git 标签 `v2.7`（提交 `3a5901a`）与 GitHub Release 已完成，Steam 工坊物品 `3767025052` 已更新（Manifest `8538688044863448269`）。
- 实机状态：维护者确认「一键骷髅师」（被动经验方案）实机生效；`error.log` 仅原版网络噪音、`text.log` 0 字节。
- GitHub：正式源码位于 `main`；正式标签按发版门禁创建，自 v2.4 起 Release 挂正式包 ZIP 附件（ASCII 文件名 + 中文显示名）便于维护取用。

v2.7 在 v2.6 稳定基准之上，新增一键骷髅师决议（复用成熟被动经验方案，无需训练/演习状态、持续7天可刷新、暂停不生效）、开发占领区决议与补给站建设加速决议，并为特殊科研「选择原型奖励」各选项补齐具体数值与取舍说明（`custom_effect_tooltip` 双语键）。

标签注意事项：旧 `v2.0` 标签误落在源码导入之前，不能作为MOD源码使用；真正的v2.0源码基准为提交 `9593154`，补充标签为 `v2.0-source-baseline`。`v2.1`标签内游戏内容正确，但旧构建器会误装v2.0基准文档。v2.6 官方附件来自单位机混合换行工作区，统一换行后内容与标签一致，但不能字节级复现；当前规范化审计重建 SHA-256 为 `9b4cc601ca9c82e59541665a076f16c972dab9c18d6871677f4887e2df1e7467`。今后标签必须在构建器、基准文档和源码全部定稿后创建。

## 建议阅读顺序

1. 根目录 `AGENTS.md`：当前状态、修改红线与发布门禁。
2. `docs/maintenance/功能与版本交接单.md`：功能边界与版本演进。
3. `docs/maintenance/技术实现与通用化边界.md`：脚本架构、作用域与踩坑记录。
4. `docs/maintenance/测试状态与回归清单.md`：实机结论与待扩展样本。
5. `docs/DEVELOPMENT.md`：构建、验证、发布与工坊上传。

## 维护纪律

- v2.7为当前稳定基准，后续不得退回旧版本继续开发。
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
Get-FileHash -Algorithm SHA256 dist\开局一键爽玩_v2.7_正式版.zip
```
