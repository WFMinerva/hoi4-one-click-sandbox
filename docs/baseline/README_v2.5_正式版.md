# 开局一键爽玩 / One-Click Sandbox Start v2.5

状态：维护者已于2026-08-01完成实机回归（间谍情报条线功能正常，四份日志干净）并认定为稳定版；已推送 Git 标签 `v2.5`，并于 2026-08-01 上传 Steam 工坊既有物品 `3767025052`。

适用环境：Hearts of Iron IV 1.19.*，全 DLC，单人游戏。AI 不会执行本 MOD 决议。间谍情报条线需要《La Resistance》DLC；特殊科研项目及二阶段编制需《Gotterdammerung》等 DLC。

## 定位

v2.5 在 v2.4 修复集正式化基础上，新增"间谍情报条线"：让玩家国家一键创建间谍机构、一键点满全部部门升级，省去科技/国策前置与漫长的部门建设等待。

## v2.5 新增

- 新决议"一键组建间谍机构"（`PRC_OCS_create_intelligence_agency`）：0 成本，直接为当前玩家国家创建间谍机构，无需任何科技与国策前置；无《La Resistance》DLC 时不可见、不可用。
- 新决议"一键升满机构部门"（`PRC_OCS_unlock_all_agency_upgrades`）：0 成本，将情报、防御、行动、特工训练、密码破译五大部门全部升级拉满，无等待时间。
- 两个决议仅为玩家国家专属（`visible`/`available` 含 `is_ai = no`，`ai_will_do = 0`）；执行一次后对当前国家永久隐藏，切换到其他玩家国家后可独立执行。
- 中英双语本地化同步（英/简中各 6 键，UTF-8 带 BOM）。

## 已接受边界

- MIO 方针无法通过当前原版已公开脚本效果为指定机构自动选择，继续由玩家手动处理。
- 不修改原版国策、国家历史文件或事件链，不创建舰船设计或舰队。
- 间谍行动（operation）与特工招募仍走游戏内 La Resistance UI，不在本 MOD 范围内。
- 特殊研发科技强度优化不在本版范围（见交接文档待办）。

## 安装

将 `OCS_one_click_sandbox_start_v2_0` 文件夹和 `OCS_one_click_sandbox_start_v2_0.mod` 放入 Hearts of Iron IV 的 mod 目录，然后在启动器中启用。

本正式包仅由 `tools/build_release.py` 从仓库构建，包内逐文件校验见 `MANIFEST_SHA256.csv`。