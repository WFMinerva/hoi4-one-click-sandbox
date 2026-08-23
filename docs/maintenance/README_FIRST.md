# 一键开局维护入口

> 本文已于2026-08-23按v2.9状态更新（Steam 工坊、开发分支与正式标签均已推送完成）。

## 当前版本状态

- 正式版本：**v2.9**（按年份研究、政治外交与法案控制、装备设计/库存、全国建设和大型设施扩展；CWTools 本地门禁；见 `docs/baseline/` 与 `CHANGELOG.md`）。
- 上一稳定基准：v2.7（Steam工坊物品 `3767025052`，Manifest `8538688044863448269`；一键骷髅师、开发占领区与补给站加速）。
- 状态说明：v2.9 正式包 SHA-256 `c0c1f4319944c98ffc2f658dc9c0024499ed4b83f1dff63401279a58951477e7`（34 文件）；标签 `v2.9` 指向 `1304b3f` 并已推送；开发分支已推送至 `b8736f4`；Steam 工坊物品 `3767025052` 已上传并更新简介（Manifest `3014636165754564201`，2026-08-23 22:44 日志 `Upload finished ... : OK`）。
- 实机状态：v2.9-test1 有完整归档；最终核能路径已实机点验——暂停状态执行大型设施即可建民用核反应堆，随后完成核能特殊科研，首都为民用堆 1、普通核堆 0；`error.log`、`text.log` 均为 0 字节。test6 其余统一清单未逐项补录。本次核能小修按维护者指示免除 K3。
- GitHub：正式源码位于 `main`；正式标签按发版门禁创建，自 v2.4 起 Release 挂正式包 ZIP 附件（ASCII 文件名 + 中文显示名）便于维护取用。

v2.7 在 v2.6 稳定基准之上，新增一键骷髅师决议（复用成熟被动经验方案，无需训练/演习状态、持续7天可刷新、暂停不生效）、开发占领区决议与补给站建设加速决议，并为特殊科研「选择原型奖励」各选项补齐具体数值与取舍说明（`custom_effect_tooltip` 双语键）。

标签注意事项：旧 `v2.0` 标签误落在源码导入之前，不能作为MOD源码使用；真正的v2.0源码基准为提交 `9593154`，补充标签为 `v2.0-source-baseline`。`v2.1`标签内游戏内容正确，但旧构建器会误装v2.0基准文档。v2.6 官方附件来自单位机混合换行工作区，统一换行后内容与标签一致，但不能字节级复现；当前规范化审计重建 SHA-256 为 `9b4cc601ca9c82e59541665a076f16c972dab9c18d6871677f4887e2df1e7467`。今后标签必须在构建器、基准文档和源码全部定稿后创建。

## 建议阅读顺序

1. `docs/maintenance/维护与重构标准流程.md`：动手前的强制流程（三级流程+三扇门+K3 复检）。
2. 根目录 `AGENTS.md`：当前状态、修改红线与发布门禁。
3. `docs/maintenance/功能与版本交接单.md`：功能边界与版本演进。
4. `docs/maintenance/技术实现与通用化边界.md`：脚本架构、作用域与踩坑记录。
5. `docs/maintenance/测试状态与回归清单.md`：实机结论与待扩展样本。
6. `docs/DEVELOPMENT.md`：构建、验证、发布与工坊上传。

## 维护纪律

- v2.9为当前稳定基准，后续不得退回旧版本继续开发。
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
Get-FileHash -Algorithm SHA256 dist\开局一键爽玩_v2.9_正式版.zip
```
