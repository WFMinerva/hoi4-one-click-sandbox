# 维护文档入口（README_FIRST）

> 总入口与状态快照见根目录 `AGENTS.md`；本文档是 `docs/maintenance/` 交接资料包的导读。
> 本文已于 2026-07-27 按仓库现状重写（此前版本引用旧交接包的 `01_当前稳定版/` 等目录，已不存在）。

## 当前唯一正式基准

- 正式版本：**v2.1**（git 标签 `v2.1`，发布包 `dist/开局一键爽玩_v2.1_正式版.zip`）
- 来源：v2.0（用户实机验证通过的 v2.0c2 正式化）之上新增特殊科研项目决议；v2.1 经维护者实机验证通过并已上传 Steam 工坊
- 游戏环境：Hearts of Iron IV 1.19.*，全 DLC，单人游戏
- AI：所有本 MOD 决议均不可执行

## 首先阅读的文件

1. 根目录 `AGENTS.md`：项目定位、状态快照、待办、目录地图与通用规则。
2. `docs/maintenance/功能与版本交接单.md`：功能边界、版本状态和后续工作规则。
3. `docs/maintenance/技术实现与通用化边界.md`：通用核心与 PRC 增强层的实现说明。
4. `docs/maintenance/测试状态与回归清单.md`：已验证内容和仍建议补做的多国家回归。
5. `docs/DEVELOPMENT.md`：构建、实机回归、发布和工坊上传流程。

MOD 源码即仓库根目录（`common/`、`events/`、`localisation/` 等），与正式包一致；发布包由 `python tools/build_release.py` 从仓库生成。

## 版本规则

- v2.1 为当前稳定基准，后续不得退回 v2.0、v2.0c、v2.0b 或 v1.2c 继续开发。
- v2.0c 存在重复 `limit` 语法错误，已被 v2.0c1 修复，禁止复用。
- v1.2c 仅作为 PRC 专用稳定历史基准与技术参考，不能覆盖通用正式线。
- 新功能必须基于当前仓库修改，使用新的测试版本号，经实机验证并由维护者确认后才能形成新的正式基准。

## 校验

各发布包的 SHA-256 以 `dist/` 下同名的 `*_SHA256.txt` 为准；发布 zip 内另附 `MANIFEST_SHA256.csv` 逐文件清单。验证方式：

```powershell
cd dist
sha256sum -c 开局一键爽玩_v2.1_正式版_SHA256.txt
```

修改任何进入发布包的文件（MOD 内容、`docs/baseline/`、许可证文件等）后，必须重新运行 `python tools/build_release.py` 生成新包与校验文件，并验证通过。
