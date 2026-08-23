# AGENTS.md — 一键开局项目入口

## 维护与重构流程（强制入口）

任何维护、重构、新功能与文档改动，动手前必须先按 `docs/maintenance/维护与重构标准流程.md` 的三级流程执行：新功能/大重构走 A 六步全流程（对齐需求→调研→再次对齐→分步方案→高级 AI 复检→经机主确认提交），小修走 B 轻流程，加功能/重构走 C 维护升级流程；三扇门（需求对齐/方案拍板/提交确认）必须等机主拍板。三扇门报告带选项——每次到门 AI 报告同步给 2–4 个建议选项（推荐第一标「（推荐）」、每项一句取舍），机主点选或回「选 n」/「按推荐」即拍板生效，自由回复不锁死；弹窗不可用降级正文编号列表；推送永不进选项。高级 AI 复检用本机 kimi CLI 调 `moonshot/k3`（专用 key 不入库），只指出问题位置与修改思路，修到通过。未经机主确认不得 git 提交；推送仅凭「推送」二字。改动后的验证与发布仍按下方「验证与发布门禁」执行。

## 项目与当前基准

《开局一键爽玩 / One-Click Sandbox Start》是《钢铁雄心 IV》单人沙盒开局 MOD。所有功能仅供玩家国家使用（`is_ai = no`，AI 不可执行），架构为“通用核心 + PRC 增强层”。

- 当前稳定基准：**v2.9**。维护者于 2026-08-23 明确要求发布 Steam 工坊；正式包由 `tools/build_release.py` 构建（SHA-256 `c0c1f4319944c98ffc2f658dc9c0024499ed4b83f1dff63401279a58951477e7`，34 文件），本地标签 `v2.9` 指向提交 `1304b3f`；Steam 工坊物品 `3767025052` 已上传 v2.9（Manifest `3014636165754564201`）。Git 分支与标签未获“推送”授权，仍仅在本地。v2.9 在 v2.8 之上扩展按年份研究、政治外交与法案控制、装备设计/库存、全国建设和大型设施，并接入 CWTools 本地语义门禁；核能最终实机点验为民用核反应堆 1、普通核反应堆 0，`error.log`/`text.log` 为空。v2.9-test6 其余统一清单未逐项补录，不得写成全量实机通过。本次两文件核能小修按维护者明确指示免除 K3 复检。
- 上一稳定基准：**v2.8**。Steam 工坊物品 `3767025052` 的 v2.8 Manifest 为 `6381266305931940230`；正式包 SHA-256 `e34f0e462b07e5b7d0f810655eb7a31069a893ae5cb00d2eb60860c074c8b6e9`，标签提交 `d4085e7`。
- v2.8 在 v2.7 稳定基准之上，完成：情报机构「本地化训练中心」升级补齐（B1）；支援/补给船选项 tooltip 官方科技效果（B2/B5）；史前喷气科技与满改设计 BBA 反门（B3）；特殊科研 42 组选项官方中文文案（B4）；核能「石墨/重水」设计选择（B6）；巡洋潜艇 MtG 模块解锁（N1）；陆地巡洋舰/超重型榴弹炮/海军/火箭 22 组互斥装备加成组（L1）；「拉满军工机构资金与规模」决议（F6）；其余机构默认路线改功能最强（F7）；陆军 9 项正面 generic 装备加成；共享 MIO 表机构守卫（DLC 门禁＋PRC 双覆盖，354 个 DLC 守卫）与自检套件 51 用例（含共享 MIO 路线链用例）。玩家「一般通」对 v2.8-test5 完成 8 项点验、总体「可发包」；工坊「特别致谢」按玩家意愿匿名。
- 2026-08-02 跨机器字节审计确认：v2.6 官方附件由单位机混合 LF/CRLF 工作区构建，与标签源码的文本在统一换行后完全一致，但不能从干净标签检出字节级复现；这是历史发布溯源缺陷，不推翻实机功能结论。当前构建器会在暂存区统一文本为 LF、保留本地化 BOM；v2.6 标签的规范化审计重建 SHA-256 为 `9b4cc601ca9c82e59541665a076f16c972dab9c18d6871677f4887e2df1e7467`，后续版本必须以该门禁保证跨机器一致。
- v2.6 在 v2.5 稳定基准之上，完成特殊科研原型奖励·逐项选择版 26 组扩展：`tools/generate_special_project_choice_events.py` 按 reward 生成唯一事件 id/flag（映射见 `docs/analysis/v2.6_特殊科研组事件映射.json`），同 project 多组互不遮蔽；`tools/finish_choice_events.py` 幂等生成四专精菜单（事件 48–51）与双语本地化；组事件选项末返回本专精菜单，新增陆/核"选择原型奖励"决议，空军/海军主菜单 `.e` 续入口，菜单 z 设专精完成 flag 隐藏决议。修复 `tools/publish_workshop.py`：英文简介 ASCII 引号改弯引号并压缩至 4832 字符后方可上传；本地部署回归脚本 `tools/deploy_to_local_mod.ps1`。
- v2.5 在 v2.4 修复集正式化之上，新增间谍情报条线（需《La Resistance》DLC）：`PRC_OCS_create_intelligence_agency` 一键创建间谍机构、`PRC_OCS_unlock_all_agency_upgrades` 一键点满情报/防御/行动/特工训练/密码破译五大部门；0 成本、无科技国策前置、无等待，每国独立一次，无 DLC 不可见。
- v2.4 在 v2.3 全国家通用 MIO、通用进化编制、每国一次性标志与跨国家切换修复之上，完成：一级/二级雷达归位空军特殊科研（完成后 1–5 级全亮）；直升机/装甲支援车/中型喷火坦克 III型 移入进化效果后设计与库存同现；船坞/民用工厂改为可重复点至上限 20；全地图碉堡移除陆地 `bunker`（防空/海岸要塞保留）；政治点/指挥点/三军经验剥离为独立决议 `PRC_OCS_add_points`；修复本地部署加载结构。
- v2.3 的共享 MIO 由生成器维护全国家通用公司表：444家公司、4945个目标特质均先确认当前国家实际拥有，再直接进入对应 `mio:` 作用域；不存在的公司跳过，不使用国家 tag 分支。德国沿用test7的319项，英国按test8补为177项，test9/test10的日苏澳捷意美实际已点路线共1190项；其余公司使用确定性的最大合法路线。PRC原有4家专属MIO继续独立维护。仍不增加资金或额外等级，MIO方针由玩家手动选择。v2.4 沿用该生成表。
- 分类使用 `allowed = { always = yes }` 为所有国家实例化，仍由分类/决议的 `visible`、所有决议的 `available = { is_ai = no }` 与 `ai_will_do = 0` 阻止AI使用；维护者实机确认同局切换国家后分类正常出现。
- 当前待办以 `docs/maintenance/功能与版本交接单.md` 的“v2.9 后续待办”及 `docs/analysis/v2.9_QQ交流群反馈整理与评估_2026-08-23.md` 为准：P1 先只读审计特殊科研互斥选择是否被预授予叠加；界面精简遵循“合并入口、不合并语义”；宣传事件、市场准入、反向抵抗、一键海军与 AI 沙盒导演均先调研，不直接实现。

状态冲突时，以本文件、Git HEAD/标签、`docs/baseline/`、实机证据和维护者确认依次核对；工程检查不能代替实机确认。版本史与详细证据见：

- `docs/maintenance/README_FIRST.md`
- `docs/maintenance/功能与版本交接单.md`
- `docs/maintenance/技术实现与通用化边界.md`
- `docs/maintenance/测试状态与回归清单.md`

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

## 验证与发布门禁

任何 MOD 内容修改后必须依次完成：

```powershell
python tools/validate_mod.py
python -m unittest tools.test_validate_mod
python tools/generate_universal_mio_effect.py --check
python tools/build_release.py
```

随后核对生成的 SHA-256，并由维护者实机回归；保存和检查 `error.log`、`game.log`、`setup.log`、`text.log` 及必要截图。`error.log` 0字节表示干净；`game.log` 的 `Conflict Risk` 是已知原版杂音；`text.log` 0字节可以表示未发现文本错误。具体覆盖范围见测试清单。

**实机监测机制（2026-08-19 起）**：实机回归按 `docs/testing/实机回归归档制度.md` 归档（逐项必填、缺证据＝FAIL_NOT_EVIDENCED）；判读统一走 `tools/check_logs.py`（白名单＋`OCS_TEST` 标记＋版本绑定），全链路用 `tools/run_regression.ps1` 编排（部署→备份旧日志→提示维护者实机操作→回收→判读→归档）。上列工具存在才生效——若仓库尚无该工具（历史版本），按本节原口径执行即可。

**发布/构建/上传纪律**：任何发布、构建、工坊上传、GitHub Release 类操作，动手前必须先 `list_files tools/` 并读 `docs/DEVELOPMENT.md` 对应章节，确认仓库是否已有现成脚本（如 `tools/publish_workshop.py`、`tools/build_release.py`）与已验证方法，再决定执行或新建；不得绕开现成工具自造轮子。发布类操作详见 `docs/DEVELOPMENT.md` 的「构建测试包或发布包」「工坊上传」以及本文件经验文档。

工坊发布必须同时核对并更新 `title`、`description` 与 `changenote`。标题从 `descriptor.mod` 的 `name` 自动写入 VDF；简介必须保留以“不想每次开局都重复输入控制台……”开头的两段核心文案，未经维护者明确同意不得改写。`tools/publish_workshop.py` 与单元测试必须对此失败关闭，不能依赖 AI 或维护者事后记忆。

正式顺序为“源码 → 静态检查 → 实机回归 → 文档 → 构建与 SHA → 维护者确认 → Git 标签/Release”。只有实机通过并经维护者确认后才能创建正式标签和 Release；标签必须指向可重建正式包的最后提交。自 v2.4 起 GitHub Release 挂正式包 ZIP 附件（ASCII 文件名 + 中文显示名）便于维护取用；唯一下载入口仍以 Steam 工坊为准。

测试包必须带版本号、README、SHA-256 和测试清单，不得冒充正式基准。正式版本变化同步更新 `README.md`、`CHANGELOG.md`、`docs/baseline/`、维护文档及当期发布文案。

## 关键目录

- MOD 源码：`common/decisions/`、`common/scripted_effects/`、`events/`
- 双语本地化：`localisation/english/`、`localisation/simp_chinese/`
- 验证与构建：`tools/validate_mod.py`、`tools/test_validate_mod.py`、`tools/build_release.py`
- 正式/测试证据：`docs/baseline/`、`docs/testing/`
- 流程与发布：`docs/DEVELOPMENT.md`、`docs/maintenance/`、`docs/publishing/`
- 生成产物：`dist/`（不进 Git）

改代码前按需阅读对应源码头部注释和技术实现文档；发版前阅读 `docs/DEVELOPMENT.md` 及当期发布文案。文档使用中文，README、发布文案和本地化保持中英双语；提交信息使用中文摘要式短句。
