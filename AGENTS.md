# AGENTS.md — 项目总入口

> 本文件是任何人/AI 接手本仓库的第一入口。读完本文件后按文末"推荐阅读顺序"继续。

## 一、项目定位

《开局一键爽玩 / One-Click Sandbox Start》是《钢铁雄心 IV》（Hearts of Iron IV）的单人沙盒开局 MOD：把科技、学说、装备、编制、库存、全国建设、特殊科研项目等重复开局操作整合为**仅限玩家**（`is_ai = no`，AI 不可执行）的零成本决议。架构为"通用核心 + PRC 增强层"：所有玩家国家可用通用功能，PRC（含 `original_tag = PRC`）额外保留顾问、军工机构特质、中国型号、民兵编制、23 座固定补给站和双电网。

- 版权人：HAPPYADONG；除 `thumbnail.png` 外采用 `GPL-3.0-only`（见 `LICENSE`、`NOTICE.md`）
- Steam 工坊物品 ID：`3767025052`（唯一对外下载入口）

## 二、当前状态快照（2026-07-27）

> **接手时先核实此快照是否过期**：对照 `git tag`、`git log`、`CHANGELOG.md` 和 `dist/` 内容确认最新版本与状态。

- 当前唯一稳定基准：**v2.1**（git 标签 `v2.1`），在 v2.0 通用版之上新增五类特殊科研项目一键完成决议（需《Gotterdammerung》DLC）。
- v2.1 已由维护者**实机验证通过并上传 Steam 工坊**（2026-07，维护者口头确认）。
- `dist/` 下 v2.0/v2.1 正式版 zip 及 v2.1 测试包的 SHA-256 均已验证通过。
- 历史基准：v1.2c（PRC 专用）、v2.0（通用化，git 标签 `v2.0`）。v2.0c 因重复 `limit` 语法错误作废，禁止复用；不得退回 v2.0/v2.0c/v2.0b/v1.2c 覆盖正式线。

## 三、当前待办（按优先级）

维护者确认：**暂无新功能开发计划**，项目处于维护状态。待办均为维护类：

1. **任何 MOD 内容修改后**（最高优先级纪律）：
   - 运行 `python tools/validate_mod.py` 静态检查通过；
   - 实机回归并保存 `error.log` / `game.log` / `setup.log` / 非空 `text.log` 及截图（覆盖面见 `docs/maintenance/测试状态与回归清单.md`）；
   - 重新运行 `python tools/build_release.py` 生成发布包，并用 `sha256sum -c` 核对 `dist/` 校验文件。
2. **下次发版时**：修正 `tools/build_release.py` 的 `BASELINE_DOCS`——目前仍把 v2.0 基准文档打进发布 zip（v2.1 zip 即如此），应换成当期版本的基准文档。
3. **可选**：补做多国扩大回归（PRC、英国、美国/苏联、无海岸小国、傀儡国），清单见 `docs/maintenance/测试状态与回归清单.md`。

## 四、目录地图

| 条目 | 用途 | 能不能动 |
| --- | --- | --- |
| `common/decisions/`、`common/scripted_effects/` | MOD 核心脚本（决议与效果） | 可改，但遵守第五节修改规则；改后必须静态检查 + 实机回归 + 重打包 |
| `events/PRC_OCS_events.txt` | 初始化与提示事件 | 同上 |
| `localisation/english/`、`localisation/simp_chinese/` | 双语本地化（yml，**必须带 UTF-8 BOM**） | 可改；两个语言文件必须同步 |
| `descriptor.mod` | MOD 内描述文件（版本号等） | 发版时更新；必须与 `packaging/` 的 .mod 文件保持一致（静态检查强制） |
| `packaging/OCS_one_click_sandbox_start_v2_0.mod` | 启动器外层 .mod 模板 | 发版时更新；文件名含 v2_0 是安装目录约定，**不要改文件名** |
| `tools/validate_mod.py` | 静态检查（必需文件、编码、描述文件一致性、花括号、关键约束标记） | 可扩展检查项，勿放松现有检查 |
| `tools/build_release.py` | 构建 `dist/` 发布 zip + SHA-256 + 内嵌 MANIFEST_SHA256.csv | 可改；注意 `BASELINE_DOCS` 已知滞留 v2.0 文档（见待办 2） |
| `tools/fix_bom.py` | 去除脚本文件误加的 UTF-8 BOM | 按需运行 |
| `docs/DEVELOPMENT.md` | 开发与发布流程（构建、回归、工坊上传、许可证边界） | 流程变化时更新 |
| `docs/maintenance/` | 交接文档四份（入口、功能与版本、技术实现、测试状态） | 状态变化时必须同步更新 |
| `docs/baseline/` | v2.0 正式版基准文档四件 | **勿动**：被 `build_release.py` 按文件名硬编码打进发布 zip |
| `docs/publishing/` | 工坊/Paradox Mods 发布文案（v2.0 历史 + v2.1 当前） | 发版时新增当期版本文案，旧版标注历史保留 |
| `dist/` | 构建产物（zip + SHA-256） | **生成目录，不进 Git**；只由 `build_release.py` 生成，不手工编辑 |
| `CHANGELOG.md` | 正式版本玩家可见变化 | 每个正式版本追加 |
| `README.md` | 中英双语项目说明 | 版本信息随发版更新 |
| `LICENSE`、`NOTICE.md` | 许可证与版权边界 | 不改（静态检查校验其内容标记） |
| `thumbnail.png` | 工坊封面图 | **版权保留，不适用 GPL**；衍生发布必须删除或替换；静态检查要求它存在 |

## 五、通用规则

### 构建与测试

```powershell
python tools/validate_mod.py    # 静态检查（修改后、提交前必跑）
python tools/build_release.py   # 先静态检查，再生成 dist/ 发布包 + SHA-256
```

静态检查不能替代实机测试。实机回归流程与日志要求见 `docs/DEVELOPMENT.md` 和 `docs/maintenance/测试状态与回归清单.md`。

### 修改规则（违反会破坏功能或存档兼容）

1. 不批量重命名 `PRC_OCS_` 键名——可能被事件、本地化和存档标志引用。
2. 通用功能只面向 `is_ai = no` 的玩家国家；`ai_will_do = { factor = 0 }` 不可少。
3. PRC 增强层同时检查 `tag = PRC` 和 `original_tag = PRC`。
4. 建设只处理当前国家**拥有且控制**的州（`every_owned_state` + `is_controlled_by = ROOT`）。
5. 同一作用域只能保留一个 `limit` 块，多条件放进同一个块（v2.0c 在此翻车：`Multiple limits in target effect`）。
6. 不修改原版国策、国家历史和事件链。

### 编码红线

- `common/`、`events/` 脚本：**UTF-8 无 BOM**（有 BOM 跑 `python tools/fix_bom.py`）。
- `localisation/` yml：**UTF-8 带 BOM**（HOI4 要求，缺 BOM 游戏读不出中文）。BOM 容易在编辑过程中丢失，每次改动 yml 后必须重新确认（`validate_mod.py` 会检查）。

### 实机测试分工（维护者已授权）

构建测试包后可直接覆盖安装到本机 MOD 目录并清理旧版；维护者进游戏点验后，由 AI 直接读取游戏 `logs\` 目录确认结果。`error.log` 0 字节即干净；`game.log` 的 "Conflict Risk" 输出是原版杂音。环境路径与细节见 `docs/DEVELOPMENT.md` 和 `docs/maintenance/技术实现与通用化边界.md` 的"环境配置"。

### 语言与提交规范

- 文档用中文；`README.md`、发布文案中英双语；本地化英/简中双文件同步。
- 提交信息用中文摘要式短句（参照 `git log`，如"新增特殊科研项目决议：一键完成五类专精并授予全部衍生科技"）。
- 只有实机验证通过并经维护者确认后才打正式 Git 标签和 GitHub Release；Release 只放更新说明不挂附件，下载入口只有 Steam 工坊。
- 工坊上传走 steamcmd（`F:\steamcmd`，配置 `F:\steamcmd\hoi4_ocs_workshop.vdf`），细节见 `docs/DEVELOPMENT.md`。

## 六、推荐阅读顺序

1. `AGENTS.md`（本文件）：定位、状态、待办、规则。
2. `README.md`：面向玩家的功能概览与安装。
3. `docs/DEVELOPMENT.md`：开发/验证/发布/上传全流程。
4. `docs/maintenance/功能与版本交接单.md`：版本演进史与功能边界。
5. `docs/maintenance/技术实现与通用化边界.md`：架构与实现细节、踩坑记录。
6. `docs/maintenance/测试状态与回归清单.md`：已验证内容与待补回归。
7. `CHANGELOG.md`：各版本玩家可见变化。
8. 改代码时：`common/` 与 `events/` 源码（脚本头部注释含设计说明）。
9. 发版时：`docs/publishing/` 当期版本文案 + `docs/DEVELOPMENT.md` 的"工坊上传"节。
