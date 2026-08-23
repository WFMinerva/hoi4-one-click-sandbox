# 开发与发布流程

> 总入口与状态快照见根目录 `AGENTS.md`；本文档是构建、验证、发布与工坊上传的权威流程。

## 稳定基准

v2.8 是当前稳定基准，在 v2.7 之上完成情报机构训练中心升级补齐、支援/补给船 tooltip 修复、史前喷气 BBA 反门、特殊科研 42 组选项官方文案、核能石墨/重水选择、巡洋潜艇 MtG 模块与陆军/海军/火箭 22 组互斥装备奖励补全、MIO 资金规模拉满与功能最强路线、陆军 9 项正面 generic 装备加成，并为共享 MIO 表补齐机构守卫。后续修改必须基于当前仓库，不得退回旧版本覆盖正式线。

历史标签说明：旧 `v2.0` 标签误落在源码导入之前，只含 `README.md`，不能用于恢复 MOD；真正的 v2.0 源码基准是提交 `9593154`，补充标签为 `v2.0-source-baseline`。已公开的错误标签不强制移动，避免破坏已有克隆中的引用。

v2.6 也是已知历史例外：官方附件 SHA-256 `484030065363ab1366604d17e2f92ee114208b2edb7ffe13b001a0172de48ff1` 来自单位机混合 LF/CRLF 工作区；文件内容在统一换行后与标签一致，但干净标签检出无法重建同一字节。官方附件不替换，当前构建器对暂存文本统一 LF 后的审计重建 SHA-256 为 `9b4cc601ca9c82e59541665a076f16c972dab9c18d6871677f4887e2df1e7467`。

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
python -m unittest tools/test_validate_mod.py
python tools/generate_universal_mio_effect.py --check
```

静态检查会验证文件、编码、描述文件、本地化键对应关系和脚本结构，并逐块检查以下项目红线：

- 所有玩家决议的 `visible`、`available` 均含 `is_ai = no`，且 `ai_will_do = { factor = 0 }`；
- 同一作用域不得出现多个 `limit`；
- PRC 分支同时包含 `tag = PRC` 和 `original_tag = PRC`；
- `any_owned_state` / `every_owned_state` 均限制为 `is_controlled_by = ROOT`；
- scripted effect 不得重名。

第二条命令是检查器自身的回归测试，第三条命令确认共享 MIO 生成器与已提交产物一致；两者分别拦截结构规则回归和生成产物漂移。静态检查不能替代实机测试。推送到 GitHub 后，CI（`.github/workflows/validate.yml`）会再次运行三项检查、实际生成发布包，并连续构建两次确认 ZIP 哈希一致。 CI 的 MIO 检查在 runner 无 HOI4 原版目录时使用 --check --no-vanilla 与提交清单。

## CWTools 本地语义检查

`tools/run_cwtools.ps1` 提供可复现的本地语义检查，不依赖 Docker、全局安装或 `cwtools-action`。脚本固定并校验以下供应链输入：

- CWTools Rust release `v2.6.1` Windows x86_64 资产，SHA-256 `ab6d69b3216870e688c1e77e6a3a1ed6960558971ce816dca63f5c6f4411554c`；该资产内二进制的 `--version` 实际回报 `cwtools 2.6.0`，记录此差异但以发布资产哈希为固定依据；
- HOI4 rules commit `ab1fda2a599ab4318d6f24ecba380e579e37006a`，codeload ZIP SHA-256 `e06f44412f88471a403bbfc37e332a66373b20feccef43f1e2125d9697240a48`。

首次运行会下载到 `%LOCALAPPDATA%\OCS\cwtools`，之后每次仍校验归档哈希；原版路径沿用 `tools/hoi4_paths.py` 的 `--vanilla`、`HOI4_VANILLA_PATH` 和已知位置解析规则。报告写入已忽略的 `artifacts/cwtools/`。

```powershell
# 首次下载并扫描；第一阶段默认不阻断，便于观察规则噪音
powershell -ExecutionPolicy Bypass -File .\tools\run_cwtools.ps1

# 已有缓存时完全离线；错误级诊断使命令失败，可作本地门禁
powershell -ExecutionPolicy Bypass -File .\tools\run_cwtools.ps1 -Offline -FailOn error

# 跨机器显式指定原版目录
powershell -ExecutionPolicy Bypass -File .\tools\run_cwtools.ps1 -VanillaPath 'D:\SteamLibrary\steamapps\common\Hearts of Iron IV'
```

`tools/cwtools_ignore_hashes.txt` 只保留一个精确诊断哈希：规则包把 1.19.2 原版已使用的 `ingame_set_template_counter` 判为未知字段。不得按错误码或文件通配抑制；规则或游戏版本更新后应先用 `-RefreshVanillaCache` 重跑并重新审计。当前不接入旧 `cwtools-action` 或提交原版缓存：其浮动 Docker/CLI/rules 与旧 HOI4 缓存不满足可复现和原版版权边界。

已知生成债：`generate_special_project_choice_events.py` 全量重跑会按原版清单重写映射，丢失后来手工补入的事件 70 映射，并回退事件 43/44 的既有 tooltip 修复；在该生成器完成专项修复前，不得把其全量输出直接覆盖当前产物。仅运行 `finish_choice_events.py` 已验证为幂等，会保留并重建事件 70 与自检本地化。

## 实机回归

每轮实测按 `docs/testing/实机回归归档制度.md` 归档入库（强制可复核，2026-08-19 起）：

- 每轮至少保存并检查：`error.log`、`game.log`、`setup.log`、`text.log`（必须检查并保存；0字节表示未记录文本/本地化错误，可判为干净）以及建设、模板、设计和新增部队截图。
- 判读统一走 `python tools/check_logs.py --logs <日志目录> --round <版本-轮次>`：白名单过滤＋`OCS_TEST` 标记提取＋游戏版本绑定，产出 `result.json`；判定铁律（0 标记＝无效、标记数＝用例清单数且全 PASS）见工具头注释。
- 归档目录 `docs/testing/<版本-轮次>/`：README＋result.json＋逐项必填清单＋脱敏日志副本＋截图＋SHA256SUMS；逐项必填、缺证据＝`FAIL_NOT_EVIDENCED`，不得只记维护者结论。
- 固定复现路径与黄金存档见 `docs/testing/黄金存档制度.md`（哈希入仓、二进制不入 git）。

实机结论必须区分“维护者确认”和“仓库内可独立复核证据”。测试清单应逐项填写结果，并记录日志、截图或外部归档位置；若历史轮次只有维护者结论和日志摘要、没有原始文件或逐项记录，必须如实注明，不得事后猜测补填。原始日志可能含用户名、路径等本机信息，提交前应先脱敏（见归档制度第四节）。

建议覆盖 PRC、英国、美国或苏联、无海岸小国及傀儡国。详细项目见 `docs/maintenance/测试状态与回归清单.md`。

## 实机测试协作（维护者已授权的分工）

- 构建测试包后可直接覆盖安装到本机 MOD 目录（`文档\Paradox Interactive\Hearts of Iron IV\mod\`），安装前清理旧版本；安装文件夹名 `OCS_one_click_sandbox_start_v2_0` 永不更改。
- 维护者进游戏点验后，由 AI 直接读取 `logs\` 下的日志确认结果，无需维护者手动收集。
- 日志判读经验：`error.log` 为 0 字节即干净；`game.log` 中 "Conflict Risk" 相关输出是原版自身杂音（无 MOD 也会出现），与本 MOD 无关，不必处理。
- `text.log` 用于文本/本地化问题记录；中文本地化已正确显示且文件为0字节时，应判为未发现文本错误，不得为了形式要求人为制造内容。

## 构建测试包或发布包

```powershell
python tools/build_release.py
```

脚本先执行静态检查，从 `descriptor.mod` 读取版本号生成包名。版本号含 `test` 时生成“测试版”包并选取 `docs/testing/` 的同版本文档；其他版本生成“正式版”包并选取 `docs/baseline/` 的同版本基准文档。随后将源码、启动器 `.mod` 文件和配套文档复制到暂存区；所有文本在暂存区统一为 LF，本地化 UTF-8 BOM 保留，二进制文件不改动。最后写入 `dist/` 下的 ZIP 并生成 SHA-256 文件。ZIP 的文件顺序、时间戳、权限和存储方式固定，因此不受仓库绝对路径与 Git 工作区换行影响；生成后脚本会按内嵌 `MANIFEST_SHA256.csv` 逐文件复核。`dist/` 是生成目录，不进入 Git。

同版本配套文档是构建的硬性条件：测试版检查 `docs/testing/`，正式版检查 `docs/baseline/`；找不到时构建直接失败。

新版本应同步更新：

- `descriptor.mod`
- `packaging/OCS_one_click_sandbox_start_v2_0.mod`
- `CHANGELOG.md`
- README 与发布文案中的版本信息
- `AGENTS.md`、`docs/DEVELOPMENT.md`、`docs/maintenance/README_FIRST.md` 与 `docs/maintenance/测试状态与回归清单.md` 的当前稳定基准
- `docs/publishing/v<版本>工坊更新摘要.txt`（供工坊上传脚本生成 changenote）

正式发版顺序固定为：

`修改源码 → 静态检查 → 实机回归 → 更新文档与发布文案 → 构建 ZIP → 核对 SHA-256 → 维护者确认 → 创建 Git 标签与 GitHub Release`

正式标签一旦创建，该版本会进入 ZIP 的 MOD 内容、外层 .mod 与 docs/baseline/ 配套文档即冻结。上传后才获得的 Manifest、下载状态等信息只更新 AGENTS.md 和维护文档，不回写已发布版本的包内基准文档；否则同一标签将无法重建同一 SHA-256。v2.6 的混合换行问题是已记录的历史例外，不作为后续版本放宽门禁的先例。

Git 标签必须指向能够直接重建该版本正式包的最后一个提交，禁止先打标签再补构建器或基准文档。只有实机验证通过并由维护者确认后，才能创建正式 Git 标签和 GitHub Release。自 v2.4 起 GitHub Release 挂正式包 ZIP 附件（ASCII 文件名 + 中文显示名），便于维护取用；既有附件文件名规则参考故障排查经验。下载入口仍以 Steam 创意工坊（物品 ID `3767025052`）为主。

## 工坊上传

推荐使用仓库自带脚本 `tools/publish_workshop.py`（自动同步暂存目录、按当期 `docs/publishing/Steam工坊中文简介_v2.x_BBCode.txt` 生成 VDF 的 description 与 changenote，再调用 steamcmd）：

```powershell
# 路径说明：单位机安装于 D:\steamcmd；F:\steamcmd 是家用机（Codex 维护环境）记录的路径，
# 两者均为真实路径，按当前机器选用并传给 --steamcmd
python tools/publish_workshop.py --steamcmd D:\steamcmd\steamcmd.exe --username <Steam用户名>
```
>
> 注释中的 D:\steamcmd 以单位机为准；家用机上把 `--steamcmd` 换成 `F:\steamcmd\steamcmd.exe` 即可（`publish_workshop.py` 的 `--steamcmd` 参数天然支持任意盘符）。

steamcmd 是交互式控制台程序，AI 执行环境的键盘输入无法实时转发（会读空密码导致 Invalid Password）。正确做法是**弹出独立窗口让维护者交互登录**：

```powershell
# 1. 先跑脚本生成 VDF 与暂存目录（不会启动 steamcmd；D:\steamcmd\hoi4_ocs_workshop.vdf 与
#    D:\steamcmd\workshop_content\OCS_one_click_sandbox_start_v2_0\ 已就绪）
python tools/publish_workshop.py --steamcmd D:\steamcmd\steamcmd.exe --prepare-only
# 2. 弹出独立窗口（VDF 已生成，直接调用 steamcmd；密码由维护者在窗口输入，不回显属正常）
cmd /c start "OCS Workshop Upload" cmd /K "D:\steamcmd\steamcmd.exe +login <账号> +workshop_build_item D:\steamcmd\hoi4_ocs_workshop.vdf +quit"
```

上传成功后从 `D:\steamcmd\logs\workshop_log.txt` 判读：应含 `Upload finished for workshop item 3767025052 : OK` 与 `Uploaded new content ( ManifestID xxx )`；把 Manifest 号同步到 `AGENTS.md` 与 `docs/maintenance/`，不得回写已经进入正式 ZIP 的 `docs/baseline/` 配套文档。

steamcmd 注意事项：

- 始终更新已有物品 `3767025052`，不要新建工坊条目，否则订阅数被分流。
- steamcmd 更新内容、预览图和 changenote；在 VDF 中加入 `title`/`description` 字段可一并更新工坊标题和简介（不加则保持现状；标签仍需网页手动编辑）。简介文案在 `docs/publishing/`。
- VDF 中的路径用正斜杠（单位机 `D:/steamcmd/...`，家用机 `F:/steamcmd/...`）：反斜杠序列如 `\t` 会被 VDF 解析器转义成制表符，导致 `Failed to read preview file`。
- 密码和 Steam Guard 验证码不要写进命令行，按提示交互输入；命令中的用户名直接写账号名本身（PowerShell 里 `<` `>` 是保留符号，带尖括号会报语法错误）。
- 上传成功标志：输出 `Committing update...Success`，或 steamcmd 日志中 `Upload finished ... : OK`。
- 与项目无关的通用流程指南在 `D:\steamcmd\STEAMCMD_工坊上传指南.md`（家用机在 `F:\steamcmd\STEAMCMD_工坊上传指南.md`，仓库外）。

## 故障排查经验

- **git push 报 "Connection was reset"**（本机网络偶发）：改用 HTTP/1.1 重试即可——`git -c http.version=HTTP/1.1 push`。
- **GitHub Release 附件中文文件名会被强制剥离**（变成 `_v2.1_.zip` 之类）：挂附件时用 ASCII 文件名上传 + 中文显示名（label）。自 v2.4 起改为挂正式包 ZIP 附件，ASCII 文件名示例 `OCS_one_click_sandbox_start_v2.4.zip`。
- **Windows 控制台处理中文注意 GBK/UTF-8 编码**：`gh` 命令输出或写入中文出现乱码时，先切换终端到 UTF-8 再重试，并以 API 返回的实际存储值为准。
- **本地化 yml 的 UTF-8 BOM 容易在编辑过程中丢失**：游戏缺 BOM 会读不出中文。每次改动 `localisation/` 后必须确认 BOM 仍在（`validate_mod.py` 会检查）。

## 许可证边界

除 `thumbnail.png` 外，仓库源码、文本和文档采用 `GPL-3.0-only`。发布修改版时必须遵守 GPLv3，并保留 `LICENSE` 与 `NOTICE.md`。

`thumbnail.png` 保留全部权利，不适用 GPL。衍生版本必须删除或替换该图片后才能发布。
