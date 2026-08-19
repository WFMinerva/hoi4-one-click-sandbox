# 实机回归全链路编排（A 立项「实机监测机制」步骤5 交付）
#
# 编排：部署测试包 → 备份旧日志 → 提示维护者实机操作（含 -debug_mode 确认项）→
# 回收日志 → 跑 tools/check_logs.py 判读 → （check_save.py 存在才跑）→ 按
# docs/testing/实机回归归档制度.md 归档到 docs/testing/<轮次>/。
#
# 半自动分工（门一结论 3）：启动游戏与点验由维护者执行；判读、脱敏、归档由本脚本＋AI 完成。
# 用法：
#   powershell -ExecutionPolicy Bypass -File tools\run_regression.ps1 [-Round v2.8-test5] [-SkipDeploy] [-RefreshSumsOnly]
#   -RefreshSumsOnly：跳过部署/备份/实测/判读/日志副本，仅重建 SHA256SUMS.txt（截图等补完后的哈希刷新）。
param(
    [Parameter(Mandatory = $false)]
    [string]$ParadoxRoot = (Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Paradox Interactive\Hearts of Iron IV'),
    [Parameter(Mandatory = $false)]
    [string]$Round = '',
    [Parameter(Mandatory = $false)]
    [switch]$SkipDeploy,
    [Parameter(Mandatory = $false)]
    [switch]$RefreshSumsOnly
)

$ErrorActionPreference = 'Stop'
# pwsh 7.3+ 新增变量；显式置 $false：check_logs 判 FAIL（exit 1）属业务结果，
# 不得被升级为终止错误而中断归档（Windows PowerShell 5.1 下为无害赋值）。
$PSNativeCommandUseErrorActionPreference = $false
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$paradoxRoot = [System.IO.Path]::GetFullPath($ParadoxRoot)
if (-not (Test-Path -LiteralPath $paradoxRoot -PathType Container)) {
    throw "Paradox user directory not found: $paradoxRoot (pass -ParadoxRoot explicitly on this machine)"
}
$logsDir = Join-Path $paradoxRoot 'logs'
$descriptorText = [System.IO.File]::ReadAllText((Join-Path $repo 'descriptor.mod'))
$version = [regex]::Match($descriptorText, '(?m)^version\s*=\s*"([^"]+)"').Groups[1].Value
if (-not $version) { throw "Cannot read version from descriptor.mod" }
if (-not $Round) { $Round = $version }
if ($Round -notmatch '^v') { $Round = 'v' + $Round }
$archiveDir = Join-Path $repo (Join-Path 'docs\testing' $Round)
$caseSource = Join-Path $repo 'common\scripted_effects\PRC_OCS_selftest_effects.txt'
if (-not (Test-Path $caseSource)) { throw "Self-test effects missing: $caseSource" }

Write-Host "=== 实机回归编排 ==="
Write-Host "版本线: $version  轮次: $Round  归档: $archiveDir"

if ($RefreshSumsOnly) {
    if (-not (Test-Path -LiteralPath $archiveDir -PathType Container)) {
        throw "-RefreshSumsOnly：归档目录不存在，请先完整跑一轮实测：$archiveDir"
    }
    Write-Host '[refresh] 仅刷新 SHA256SUMS.txt（跳过部署/备份/实测/判读/日志副本）。'
    # 刷新路径下 README 已存在则不重写；若存在但缺 README（上轮第 6 步前中断），
    # 占位模板插值需有值，先给显式占位。
    $checkLogsExit = -1
    $saveNote = 'N/A（仅刷新哈希）'
}
else {

# --- 1. 部署测试包（复用 deploy_to_local_mod.ps1，红线 9） ---
if (-not $SkipDeploy) {
    Write-Host '[1/6] 部署测试包到本机 MOD 目录...'
    # 部署脚本自身用 throw＋$ErrorActionPreference='Stop' 传播真实失败；其内部
    # robocopy 成功返回 1–7，残留 $LASTEXITCODE 不得用于判成败（K3 diff 块2 修正）。
    & (Join-Path $PSScriptRoot 'deploy_to_local_mod.ps1') -ParadoxRoot $ParadoxRoot
}
else {
    Write-Host '[1/6] -SkipDeploy：跳过部署，沿用当前安装。'
}

# --- 2. 备份旧日志（改名留档，不删除） ---
if (Test-Path -LiteralPath $logsDir -PathType Container) {
    $backup = "$logsDir.prev-" + (Get-Date -Format 'yyyyMMdd-HHmmss')
    Move-Item -LiteralPath $logsDir -Destination $backup
    Write-Host "[2/6] 旧日志已备份到 $backup"
}
else {
    Write-Host '[2/6] 无旧日志目录，跳过备份。'
}

# --- 3. 维护者实机操作提示（含 -debug_mode 确认项，K3 第 7 轮附记） ---
Write-Host ''
Write-Host '[3/6] 请维护者执行实机操作（按回车键前完成以下全部步骤）：'
Write-Host '  1. 用启动器「以调试模式打开游戏」启动 HOI4（等效 hoi4.exe -gdpr-compliant -debug_mode）；确认已开启 -debug_mode（否则自检命令不可用、本轮将被判无效）。'
Write-Host '  2. 载入黄金存档（docs/testing/黄金存档制度.md 登记档）；控制台切国：tag PRC。'
Write-Host '  3. 按固定序列操作（详见 docs/testing/实机回归归档制度.md）：'
Write-Host '     一键开局 → 一键骷髅师（7 天窗口内完成后续步骤）→ 一键拉满 MIO 资金与规模 → 空军特殊科研 →'
Write-Host '     海军特殊科研·巡洋潜艇取 MtG 分支 → 核能菜单「设计选择」取重水 → 全部 43 个选择组逐项点选。'
Write-Host '  4. 控制台执行自检：effect PRC PRC_OCS_selftest_run_suite（或 event PRC_OCS_selftest.1 PRC）；只执行一次（重复执行＝标记翻倍＝本轮无效）。'
Write-Host '  5. 控制台保存判定档（文件名必须 ASCII，如 save v2.8test5verdict——中文名会保存失败）；退出游戏。'
Write-Host '  6. 回到本窗口按回车。'
Read-Host '（完成后按回车继续）' | Out-Null

# --- 4. 回收日志与判读 ---
if (-not (Test-Path -LiteralPath $logsDir -PathType Container)) {
    throw "logs directory not found after session: $logsDir"
}
Write-Host '[4/6] 判读日志（check_logs）...'
New-Item -ItemType Directory -Path $archiveDir -Force | Out-Null
$resultJson = Join-Path $archiveDir 'result.json'
$checkLogs = Join-Path $repo 'tools\check_logs.py'
& python $checkLogs --logs $logsDir --round $Round --case-source $caseSource --out $resultJson
$checkLogsExit = $LASTEXITCODE

$saveNote = ''
$checkSave = Join-Path $repo 'tools\check_save.py'
if (Test-Path $checkSave) {
    Write-Host '[4/6] check_save 存在，执行存档断言...'
    & python $checkSave
    $saveNote = "check_save 已执行（exit $LASTEXITCODE）"
}
else {
    $saveNote = 'check_save 不存在（步骤4 存档断言暂缓，跳过）'
}

# --- 5. 脱敏日志副本归档 ---
Write-Host '[5/6] 归档脱敏日志副本...'
$archiveLogs = Join-Path $archiveDir 'logs'
New-Item -ItemType Directory -Path $archiveLogs -Force | Out-Null
$redactTargets = @($env:USERNAME, $env:USERPROFILE, $env:COMPUTERNAME) | Where-Object { $_ }
foreach ($file in Get-ChildItem -LiteralPath $logsDir -File) {
    $text = [System.IO.File]::ReadAllText($file.FullName)
    foreach ($target in $redactTargets) {
        # -replace 默认大小写不敏感；[regex]::Escape 防路径字符被当正则
        $text = $text -replace [regex]::Escape($target), '<REDACTED>'
    }
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText((Join-Path $archiveLogs $file.Name), $text, $utf8)
}
$screenshotsDir = Join-Path $archiveDir 'screenshots'
New-Item -ItemType Directory -Path $screenshotsDir -Force | Out-Null

}  # if (-not $RefreshSumsOnly)

# --- 6. SHA256SUMS 与 README 占位（SHA256SUMS 在 README 写入之后生成，保证 README 也入清单） ---
Write-Host '[6/6] 生成 README 占位与 SHA256SUMS...'
$readmePath = Join-Path $archiveDir 'README.md'
if (-not (Test-Path $readmePath)) {
    $readme = @"
# $Round 实机回归归档

> 由 tools/run_regression.ps1 自动归档（半自动分工：实机操作由维护者执行，判读/脱敏/归档自动完成）。

- 版本线：$version（轮次 $Round）
- 测试包 SHA-256：待维护者填写（以 dist 侧 SHA256 文件为准）。
- 判定：见 result.json（check_logs 输出；exit $checkLogsExit）。
- 存档断言：$saveNote
- 逐项清单：请补建 清单.md（逐项必填，缺证据＝FAIL_NOT_EVIDENCED，见 docs/testing/实机回归归档制度.md）。
- 问题清单：待维护者填写。
- 例外说明：待维护者填写。
- 截图：请按 NN_<检查项简称>.png 命名放入 screenshots/，然后刷新 SHA256SUMS.txt（本脚本已归档一次；补截图后可用 -RefreshSumsOnly 仅刷新哈希）。
- 结论：待维护者填写。
"@
    [System.IO.File]::WriteAllText($readmePath, $readme, (New-Object System.Text.UTF8Encoding($false)))
}
else {
    Write-Host '[6/6] README 已存在，跳过覆盖（保留维护者已填内容）。'
}
$hashLines = @()
foreach ($file in Get-ChildItem -LiteralPath $archiveDir -Recurse -File) {
    if ($file.Name -eq 'SHA256SUMS.txt') { continue }
    $rel = $file.FullName.Substring($archiveDir.Length + 1).Replace('\', '/')
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash.ToLower()
    $hashLines += "$hash  $rel"
}
# 行尾统一 LF：跨机 `sha256sum -c` 可直接校验（WriteAllLines 在 Windows 会写 CRLF，改用显式 LF 拼接）
[System.IO.File]::WriteAllText((Join-Path $archiveDir 'SHA256SUMS.txt'),
    (($hashLines | Sort-Object) -join "`n") + "`n", (New-Object System.Text.UTF8Encoding($false)))

Write-Host ''
Write-Host '=== 归档完成 ==='
Write-Host "归档目录: $archiveDir"
if (-not $RefreshSumsOnly) {
    Write-Host "check_logs exit: $checkLogsExit（0＝PASS；1＝FAIL/INVALID；2＝参数错误）"
}
Write-Host '后续：按归档制度填写 清单.md 与截图，更新 README 结论；证据齐备后本轮实测闭环。'
