# 开发与发布流程

> 总入口与状态快照见根目录 `AGENTS.md`；本文档是构建、验证、发布与工坊上传的权威流程。

## 稳定基准

v2.5 是当前稳定基准，在v2.4修复集正式化之上新增间谍情报条线（需《La Resistance》DLC）：一键创建间谍机构、一键点满情报/防御/行动/特工训练/密码破译五大部门升级，0成本、无科技国策前置、无等待，每国独立一次、无DLC不可见。后续修改必须基于当前仓库，不得退回旧版本覆盖正式线。

历史标签说明：旧 `v2.0` 标签误落在源码导入之前，只含 `README.md`，不能用于恢复 MOD；真正的 v2.0 源码基准是提交 `9593154`，补充标签为 `v2.0-source-baseline`。已公开的错误标签不强制移动，避免破坏已有克隆中的引用。

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
```

静态检查会验证文件、编码、描述文件、本地化键对应关系和脚本结构，并逐块检查以下项目红线：

- 所有玩家决议的 `visible`、`available` 均含 `is_ai = no`，且 `ai_will_do = { factor = 0 }`；
- 同一作用域不得出现多个 `limit`；
- PRC 分支同时包含 `tag = PRC` 和 `original_tag = PRC`；
- `any_owned_state` / `every_owned_state` 均限制为 `is_controlled_by = ROOT`；
- scripted effect 不得重名。

第二条命令是检查器自身的回归测试，确认重复 `limit`、缺失 AI 限制、PRC 判断缺半边和州控制条件缺失等坏样例确实会被拦截。静态检查不能替代实机测试。推送到 GitHub 后，CI（`.github/workflows/validate.yml`）会再次运行两项检查、实际生成发布包，并连续构建两次确认 ZIP 哈希一致。

## 实机回归

每轮至少保存并检查：

- `error.log`
- `game.log`
- `setup.log`
- `text.log`（必须检查并保存；0字节表示未记录文本/本地化错误，可判为干净）
- 建设、模板、设计和新增部队截图

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

脚本先执行静态检查，从 `descriptor.mod` 读取版本号生成包名。版本号含 `test` 时生成“测试版”包并选取 `docs/testing/` 的同版本文档；其他版本生成“正式版”包并选取 `docs/baseline/` 的同版本基准文档。随后将源码、启动器 `.mod` 文件和配套文档写入 `dist/` 下的 ZIP，同时生成 SHA-256 文件。ZIP 的文件顺序、时间戳、权限和存储方式固定，相同输入会生成相同字节；生成后脚本会按内嵌 `MANIFEST_SHA256.csv` 逐文件复核。`dist/` 是生成目录，不进入 Git。

同版本配套文档是构建的硬性条件：测试版检查 `docs/testing/`，正式版检查 `docs/baseline/`；找不到时构建直接失败。

新版本应同步更新：

- `descriptor.mod`
- `packaging/OCS_one_click_sandbox_start_v2_0.mod`
- `CHANGELOG.md`
- README 与发布文案中的版本信息

正式发版顺序固定为：

`修改源码 → 静态检查 → 实机回归 → 更新文档与发布文案 → 构建 ZIP → 核对 SHA-256 → 维护者确认 → 创建 Git 标签与 GitHub Release`

Git 标签必须指向能够直接重建该版本正式包的最后一个提交，禁止先打标签再补构建器或基准文档。只有实机验证通过并由维护者确认后，才能创建正式 Git 标签和 GitHub Release。自 v2.4 起 GitHub Release 挂正式包 ZIP 附件（ASCII 文件名 + 中文显示名），便于维护取用；既有附件文件名规则参考故障排查经验。下载入口仍以 Steam 创意工坊（物品 ID `3767025052`）为主。

## 工坊上传

推荐使用仓库自带脚本 `tools/publish_workshop.py`（自动同步暂存目录、按当期 `docs/publishing/Steam工坊中文简介_v2.x_BBCode.txt` 生成 VDF 的 description 与 changenote，再调用 steamcmd）：

```powershell
# 本机实际安装于 D:\steamcmd（旧文档记录的 F:\steamcmd 已过时，以实际盘符为准）
python tools/publish_workshop.py --steamcmd D:\steamcmd\steamcmd.exe --username <Steam用户名>
```

steamcmd 是交互式控制台程序，AI 执行环境的键盘输入无法实时转发（会读空密码导致 Invalid Password）。正确做法是**弹出独立窗口让维护者交互登录**：

```powershell
# 1. 先跑脚本生成 VDF 与暂存目录（无需登录也会完成；D:\steamcmd\hoi4_ocs_workshop.vdf 与
#    D:\steamcmd\workshop_content\OCS_one_click_sandbox_start_v2_0\ 已就绪）
python tools/publish_workshop.py --steamcmd D:\steamcmd\steamcmd.exe
# 2. 弹出独立窗口（VDF 已生成，直接调用 steamcmd；密码由维护者在窗口输入，不回显属正常）
cmd /c start "OCS Workshop Upload" cmd /K "D:\steamcmd\steamcmd.exe +login <账号> +workshop_build_item D:\steamcmd\hoi4_ocs_workshop.vdf +quit"
```

上传成功后从 `D:\steamcmd\logs\workshop_log.txt` 判读：应含 `Upload finished for workshop item 3767025052 : OK` 与 `Uploaded new content ( ManifestID xxx )`；把 Manifest 号同步到 `AGENTS.md`、`docs/maintenance/` 与 `docs/baseline/` 相关文档。

steamcmd 注意事项：

- 始终更新已有物品 `3767025052`，不要新建工坊条目，否则订阅数被分流。
- steamcmd 更新内容、预览图和 changenote；在 VDF 中加入 `title`/`description` 字段可一并更新工坊标题和简介（不加则保持现状；标签仍需网页手动编辑）。简介文案在 `docs/publishing/`。
- VDF 中的路径用正斜杠（`F:/steamcmd/...`）：反斜杠序列如 `\t` 会被 VDF 解析器转义成制表符，导致 `Failed to read preview file`。
- 密码和 Steam Guard 验证码不要写进命令行，按提示交互输入；命令中的用户名直接写账号名本身（PowerShell 里 `<` `>` 是保留符号，带尖括号会报语法错误）。
- 上传成功标志：输出 `Committing update...Success`，或 steamcmd 日志中 `Upload finished ... : OK`。
- 与项目无关的通用流程指南在 `D:\steamcmd\STEAMCMD_工坊上传指南.md`（仓库外）。

## 故障排查经验

- **git push 报 "Connection was reset"**（本机网络偶发）：改用 HTTP/1.1 重试即可——`git -c http.version=HTTP/1.1 push`。
- **GitHub Release 附件中文文件名会被强制剥离**（变成 `_v2.1_.zip` 之类）：挂附件时用 ASCII 文件名上传 + 中文显示名（label）。自 v2.4 起改为挂正式包 ZIP 附件，ASCII 文件名示例 `OCS_one_click_sandbox_start_v2.4.zip`。
- **Windows 控制台处理中文注意 GBK/UTF-8 编码**：`gh` 命令输出或写入中文出现乱码时，先切换终端到 UTF-8 再重试，并以 API 返回的实际存储值为准。
- **本地化 yml 的 UTF-8 BOM 容易在编辑过程中丢失**：游戏缺 BOM 会读不出中文。每次改动 `localisation/` 后必须确认 BOM 仍在（`validate_mod.py` 会检查）。

## 许可证边界

除 `thumbnail.png` 外，仓库源码、文本和文档采用 `GPL-3.0-only`。发布修改版时必须遵守 GPLv3，并保留 `LICENSE` 与 `NOTICE.md`。

`thumbnail.png` 保留全部权利，不适用 GPL。衍生版本必须删除或替换该图片后才能发布。
