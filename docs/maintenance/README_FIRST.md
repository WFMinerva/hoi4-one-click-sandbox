# 一键开局维护入口

> 本文已于2026-07-31按v2.3正式发布状态更新。

## 当前唯一正式基准

- 正式版本：**v2.3**。
- Steam工坊：物品 `3767025052`，Manifest `7223939852636260892`。
- 实机状态：维护者已确认v2.3-test13关键回归通过，包括同局切换至开局由AI控制的国家后，整个决议分类仍会出现并可分别初始化。
- GitHub：正式源码位于 `main`，配套标签与无附件Release均为 `v2.3`；唯一下载入口仍为Steam工坊。

v2.3在v2.2基础上完成全国家通用MIO路线、通用进化编制、中自火纠正、每国一次性标志与跨国家切换修复。共享MIO生成表覆盖444家公司、4945项目标特质；只处理当前国家实际拥有的公司，不额外增加资金或等级，方针仍由玩家手动选择。PRC原有4家专属路线保持独立。

标签注意事项：旧 `v2.0` 标签误落在源码导入之前，不能作为MOD源码使用；真正的v2.0源码基准为提交 `9593154`，补充标签为 `v2.0-source-baseline`。`v2.1`标签内游戏内容正确，但旧构建器会误装v2.0基准文档。今后标签必须在构建器、基准文档和源码全部定稿后创建。

## 建议阅读顺序

1. 根目录 `AGENTS.md`：当前状态、修改红线与发布门禁。
2. `docs/maintenance/功能与版本交接单.md`：功能边界与版本演进。
3. `docs/maintenance/技术实现与通用化边界.md`：脚本架构、作用域与踩坑记录。
4. `docs/maintenance/测试状态与回归清单.md`：实机结论与待扩展样本。
5. `docs/DEVELOPMENT.md`：构建、验证、发布与工坊上传。

## 维护纪律

- v2.3为当前稳定基准，后续不得退回旧版本继续开发。
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
Get-FileHash -Algorithm SHA256 dist\开局一键爽玩_v2.3_正式版.zip
```