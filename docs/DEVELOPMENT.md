# 开发与发布流程

## 稳定基准

v2.1 是当前唯一稳定基准，在 v2.0（用户实机验证通过的 v2.0c2）之上新增特殊科研项目决议。后续修改必须基于当前仓库，不得退回 v2.0、v2.0c、v2.0b 或 v1.2c 覆盖正式线。

## 修改规则

1. 不批量重命名 `PRC_OCS_` 键名；这些名称可能被事件、本地化和存档标志引用。
2. 通用功能只面向 `is_ai = no` 的玩家国家。
3. PRC 增强层同时检查 `tag = PRC` 和 `original_tag = PRC`。
4. 建设只处理当前国家拥有且控制的州。
5. 同一作用域只能保留一个 `limit` 块；多个条件必须放进同一个块内。
6. 不修改原版国策、国家历史和事件链。

## 本地检查

在仓库根目录运行：

```powershell
python tools/validate_mod.py
```

静态检查只能发现文件缺失、编码、描述文件、括号和部分关键约束问题，不能替代实机测试。

## 实机回归

每轮至少保存并检查：

- `error.log`
- `game.log`
- `setup.log`
- 非空的 `text.log`
- 建设、模板、设计和新增部队截图

建议覆盖 PRC、英国、美国或苏联、无海岸小国及傀儡国。详细项目见 `docs/maintenance/测试状态与回归清单.md`。

## 构建发布包

```powershell
python tools/build_release.py
```

脚本先执行静态检查，再将源码、启动器 `.mod` 文件和 v2.0 基准文档写入 `dist/` 下的 ZIP，同时生成 SHA-256 文件。`dist/` 是生成目录，不进入 Git。

新版本应同步更新：

- `descriptor.mod`
- `packaging/OCS_one_click_sandbox_start_v2_0.mod`
- `CHANGELOG.md`
- README 与发布文案中的版本信息

实机验证通过并由维护者确认后，才能创建正式 Git 标签和 GitHub Release。

## 许可证边界

除 `thumbnail.png` 外，仓库源码、文本和文档采用 `GPL-3.0-only`。发布修改版时必须遵守 GPLv3，并保留 `LICENSE` 与 `NOTICE.md`。

`thumbnail.png` 保留全部权利，不适用 GPL。衍生版本必须删除或替换该图片后才能发布。
