# 开发与发布流程

> 总入口与状态快照见根目录 `AGENTS.md`；本文档是构建、验证、发布与工坊上传的权威流程。

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

静态检查只能发现文件缺失、编码、描述文件、括号和部分关键约束问题，不能替代实机测试。推送到 GitHub 后会由 CI（`.github/workflows/validate.yml`）自动再跑一遍同一检查。

## 实机回归

每轮至少保存并检查：

- `error.log`
- `game.log`
- `setup.log`
- 非空的 `text.log`
- 建设、模板、设计和新增部队截图

建议覆盖 PRC、英国、美国或苏联、无海岸小国及傀儡国。详细项目见 `docs/maintenance/测试状态与回归清单.md`。

## 实机测试协作（维护者已授权的分工）

- 构建测试包后可直接覆盖安装到本机 MOD 目录（`文档\Paradox Interactive\Hearts of Iron IV\mod\`），安装前清理旧版本；安装文件夹名 `OCS_one_click_sandbox_start_v2_0` 永不更改。
- 维护者进游戏点验后，由 AI 直接读取 `logs\` 下的日志确认结果，无需维护者手动收集。
- 日志判读经验：`error.log` 为 0 字节即干净；`game.log` 中 "Conflict Risk" 相关输出是原版自身杂音（无 MOD 也会出现），与本 MOD 无关，不必处理。

## 构建发布包

```powershell
python tools/build_release.py
```

脚本先执行静态检查，从 `descriptor.mod` 读取版本号生成发布包文件名，再将源码、启动器 `.mod` 文件和 `docs/baseline/` 下当期版本的基准文档写入 `dist/` 下的 ZIP，同时生成 SHA-256 文件。`dist/` 是生成目录，不进入 Git。发新正式版前记得在 `docs/baseline/` 补上当期版本的基准文档，否则发布包会缺少基准文档（脚本只警告不拦截）。

新版本应同步更新：

- `descriptor.mod`
- `packaging/OCS_one_click_sandbox_start_v2_0.mod`
- `CHANGELOG.md`
- README 与发布文案中的版本信息

实机验证通过并由维护者确认后，才能创建正式 Git 标签和 GitHub Release。GitHub Release 只放更新说明，不挂发布包附件；下载入口只有 Steam 创意工坊（物品 ID `3767025052`）。

## 工坊上传

使用 steamcmd（装在 `F:\steamcmd`，配置 `F:\steamcmd\hoi4_ocs_workshop.vdf`）：

```powershell
# 暂存内容 = 仓库根目录的 MOD 内容（common、events、localisation、descriptor.mod、
# thumbnail.png、LICENSE、NOTICE.md）原样复制到
# F:\steamcmd\workshop_content\OCS_one_click_sandbox_start_v2_0\
# 登录与 Steam Guard 由用户本人完成：
F:\steamcmd\steamcmd.exe +login <Steam用户名> +workshop_build_item F:\steamcmd\hoi4_ocs_workshop.vdf +quit
```

上传前确认暂存目录与仓库逐文件一致，并更新 VDF 里的 `changenote`。

steamcmd 注意事项：

- 始终更新已有物品 `3767025052`，不要新建工坊条目，否则订阅数被分流。
- steamcmd 只更新内容和 changenote，**不更新工坊页面的标题和简介**——简介需在工坊网页手动更新（文案在 `docs/publishing/`）。
- 密码和 Steam Guard 验证码不要写进命令行，按提示交互输入；命令中的用户名直接写账号名本身（PowerShell 里 `<` `>` 是保留符号，带尖括号会报语法错误）。
- 上传成功标志：输出 `Committing update...Success`，或 steamcmd 日志中 `Upload finished ... : OK`。
- 与项目无关的通用流程指南在 `F:\steamcmd\STEAMCMD_工坊上传指南.md`（仓库外）。

## 故障排查经验

- **git push 报 "Connection was reset"**（本机网络偶发）：改用 HTTP/1.1 重试即可——`git -c http.version=HTTP/1.1 push`。
- **GitHub Release 附件中文文件名会被强制剥离**（变成 `_v2.1_.zip` 之类）：如确需挂附件，用 ASCII 文件名上传 + 中文显示名（label）。当前策略是不挂附件，此条仅作历史经验。
- **Windows 控制台处理中文注意 GBK/UTF-8 编码**：`gh` 命令输出或写入中文出现乱码时，先切换终端到 UTF-8 再重试，并以 API 返回的实际存储值为准。
- **本地化 yml 的 UTF-8 BOM 容易在编辑过程中丢失**：游戏缺 BOM 会读不出中文。每次改动 `localisation/` 后必须确认 BOM 仍在（`validate_mod.py` 会检查）。

## 许可证边界

除 `thumbnail.png` 外，仓库源码、文本和文档采用 `GPL-3.0-only`。发布修改版时必须遵守 GPLv3，并保留 `LICENSE` 与 `NOTICE.md`。

`thumbnail.png` 保留全部权利，不适用 GPL。衍生版本必须删除或替换该图片后才能发布。
