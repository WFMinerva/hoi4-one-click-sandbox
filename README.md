# 开局一键爽玩 / One-Click Sandbox Start

[中文](#中文说明) · [English](#english)

## 中文说明

这是一个面向《钢铁雄心 IV》单人沙盒玩法的开局准备框架。它把大量重复的开局操作整合成仅限玩家使用的决议，方便快速配置科技、学说、装备、编制、库存和建设。

- 当前稳定基准：v2.4
- 支持游戏版本：Hearts of Iron IV 1.19.*
- 推荐环境：全 DLC、单人游戏
- AI：不能执行本 MOD 的决议
- Steam 工坊：[3767025052](https://steamcommunity.com/sharedfiles/filedetails/?id=3767025052)

### 安装

1. 运行 `python tools/build_release.py` 生成发布 ZIP。
2. 解压后，将 `OCS_one_click_sandbox_start_v2_0` 文件夹和同名 `.mod` 文件放入 Hearts of Iron IV 的 `mod` 目录。
3. 在 Paradox Launcher 中启用本 MOD。

### 开发与验证

```powershell
python tools/validate_mod.py
python tools/build_release.py
```

MOD 源码位于仓库根目录；启动器描述文件模板位于 `packaging/`；维护、基准和发布文档位于 `docs/`。修改前请先阅读：

- `AGENTS.md`（总入口：状态快照、待办、目录地图与通用规则）
- `docs/maintenance/README_FIRST.md`
- `docs/maintenance/功能与版本交接单.md`
- `docs/maintenance/技术实现与通用化边界.md`
- `docs/maintenance/测试状态与回归清单.md`

v2.4 是当前稳定基准。`PRC_OCS_` 前缀属于稳定键名，不应仅为重命名而修改。

### 许可证

除 `thumbnail.png` 外，源码、脚本、本地化文本和文档采用 [GNU GPL v3.0 only](LICENSE)。版权人为 HAPPYADONG。

`thumbnail.png` 不适用 GPL，版权归 HAPPYADONG 所有并保留全部权利。发布衍生版本前必须删除或替换该图片。完整范围见 [NOTICE.md](NOTICE.md)。

---

## English

[![Steam Workshop](https://img.shields.io/badge/Steam-Workshop-1b2838?logo=steam&logoColor=white)](https://steamcommunity.com/sharedfiles/filedetails/?id=3767025052)

A sandbox startup framework for **Hearts of Iron IV**.

This mod transforms many repetitive early-game setup operations into convenient player-only decisions, allowing players to quickly create their preferred starting conditions and focus on strategic gameplay.

Designed for single-player sandbox experiences.

---

## Features

### One-Click Setup Decisions

The mod integrates many common setup operations into a simplified decision system.

Instead of repeatedly using console commands or manually configuring dozens of options, players can prepare their campaign through dedicated decisions.

---

## Included Functions

Depending on the selected setup, the mod can provide:

### Technology and Doctrine Setup

- Research assistance
- Doctrine preparation
- Advanced starting capabilities

### Military Preparation

- Division templates
- Army organization
- Equipment preparation
- Deployment assistance

### Industrial and Economic Setup

- Construction support
- Industrial expansion
- Infrastructure preparation

### Military Industry

- Military industrial organization setup
- Equipment design preparation
- Production-oriented configuration

---

## Sandbox Philosophy

This mod is not designed around historical balance.

Its purpose is to provide:

- Faster campaign preparation
- More freedom for experimentation
- Easier testing of strategies
- A powerful single-player sandbox environment

Players can quickly move from preparation into the strategic part of the game.

---

## Design Principles

The project follows these principles:

- Player-only decisions
- AI cannot use sandbox functions
- No forced changes to unrelated countries
- No replacement of vanilla focus trees
- No alteration of normal historical events unless required
- Separate tools rather than permanent gameplay changes

---

## Compatibility

Designed for:

- Hearts of Iron IV 1.19.x
- Vanilla-focused gameplay

The mod is tested in-game before stable releases.

---

## Development

Created by **HAPPYADONG**

Steam Workshop:

https://steamcommunity.com/profiles/76561198024627348

---

## Related Projects

Other Hearts of Iron IV projects:

- Hearts of Iron IV Character Biographies
- One-Click Navy Builder

---

## Author's Note

This project started as a personal quality-of-life tool to reduce repetitive setup work during testing and sandbox campaigns.

It has gradually evolved into a more comprehensive framework for creating customized Hearts of Iron IV starting experiences.

---

## License

Except for `thumbnail.png`, the source code, scripts, localisation, and documentation are licensed under [GNU GPL v3.0 only](LICENSE), Copyright (C) 2026 HAPPYADONG.

`thumbnail.png` is excluded from the GPL license. Copyright (C) 2026 HAPPYADONG. All rights reserved. It must be removed or replaced before distributing a derivative release. See [NOTICE.md](NOTICE.md).
