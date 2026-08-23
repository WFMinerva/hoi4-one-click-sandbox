[CmdletBinding()]
param(
    [string]$VanillaPath = '',
    [string]$CacheRoot = (Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'OCS\cwtools'),
    [string]$OutputDirectory = '',
    [ValidateSet('none', 'error', 'warning', 'info', 'hint')]
    [string]$FailOn = 'none',
    [switch]$Offline,
    [switch]$RefreshVanillaCache,
    [switch]$SetupOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$CliRelease = 'v2.6.1'
$CliArchiveSha256 = 'ab6d69b3216870e688c1e77e6a3a1ed6960558971ce816dca63f5c6f4411554c'
$CliArchiveUrl = 'https://github.com/MillenniumDawn/cwtools/releases/download/v2.6.1/cwtools-rs-windows-x86_64.zip'
$RulesCommit = 'ab1fda2a599ab4318d6f24ecba380e579e37006a'
$RulesArchiveSha256 = 'e06f44412f88471a403bbfc37e332a66373b20feccef43f1e2125d9697240a48'
$RulesArchiveUrl = "https://codeload.github.com/cwtools/cwtools-hoi4-config/zip/$RulesCommit"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $RepoRoot 'artifacts\cwtools'
}

# GitHub requires TLS 1.2; keep any stronger protocol already enabled.
[Net.ServicePointManager]::SecurityProtocol =
    [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

function Get-Sha256 {
    param([Parameter(Mandatory = $true)][string]$Path)

    $stream = [System.IO.File]::OpenRead($Path)
    try {
        $sha256 = [System.Security.Cryptography.SHA256]::Create()
        try {
            $bytes = $sha256.ComputeHash($stream)
        }
        finally {
            $sha256.Dispose()
        }
    }
    finally {
        $stream.Dispose()
    }
    return ([System.BitConverter]::ToString($bytes)).Replace('-', '').ToLowerInvariant()
}

function Get-PinnedArchive {
    param(
        [Parameter(Mandatory = $true)][string]$Uri,
        [Parameter(Mandatory = $true)][string]$Destination,
        [Parameter(Mandatory = $true)][string]$ExpectedSha256
    )
    if (-not (Test-Path -LiteralPath $Destination -PathType Leaf)) {
        if ($Offline) {
            throw "Offline cache file is missing: $Destination"
        }
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Destination) | Out-Null
        Invoke-WebRequest -UseBasicParsing -Uri $Uri -OutFile $Destination
    }
    $actual = Get-Sha256 -Path $Destination
    if ($actual -ne $ExpectedSha256) {
        throw "Cached file SHA-256 mismatch: $Destination (actual $actual)"
    }
}

$CliRoot = Join-Path $CacheRoot "cli-$CliRelease"
$CliArchive = Join-Path $CliRoot 'cwtools-rs-windows-x86_64.zip'
$CliExtract = Join-Path $CliRoot 'extracted'
Get-PinnedArchive -Uri $CliArchiveUrl -Destination $CliArchive -ExpectedSha256 $CliArchiveSha256
if (-not (Test-Path -LiteralPath $CliExtract -PathType Container)) {
    Expand-Archive -LiteralPath $CliArchive -DestinationPath $CliExtract
}
$CwtoolsExe = Get-ChildItem -LiteralPath $CliExtract -Filter 'cwtools.exe' -File -Recurse | Select-Object -First 1
if ($null -eq $CwtoolsExe) {
    throw "cwtools.exe was not found in the pinned archive: $CliExtract"
}

$RulesRoot = Join-Path $CacheRoot "rules-$RulesCommit"
$RulesArchive = Join-Path $RulesRoot 'cwtools-hoi4-config.zip'
$RulesExtract = Join-Path $RulesRoot 'extracted'
Get-PinnedArchive -Uri $RulesArchiveUrl -Destination $RulesArchive -ExpectedSha256 $RulesArchiveSha256
if (-not (Test-Path -LiteralPath $RulesExtract -PathType Container)) {
    Expand-Archive -LiteralPath $RulesArchive -DestinationPath $RulesExtract
}
$RulesConfig = Get-ChildItem -LiteralPath $RulesExtract -Directory -Recurse |
    Where-Object { $_.Name -eq 'Config' } |
    Select-Object -First 1
if ($null -eq $RulesConfig) {
    throw "Config was not found in the pinned rules archive: $RulesExtract"
}

$ActualVersion = & $CwtoolsExe.FullName --version
Write-Host "CWTools release pin: $CliRelease; binary reports: $ActualVersion"
Write-Host "Rules commit pin: $RulesCommit"
if ($SetupOnly) {
    return
}

$PathArgs = @()
if (-not [string]::IsNullOrWhiteSpace($VanillaPath)) {
    $PathArgs += @('--vanilla', $VanillaPath)
}
$ResolverOutput = & python (Join-Path $PSScriptRoot 'hoi4_paths.py') @PathArgs
$ResolverExitCode = $LASTEXITCODE
$ResolvedVanilla = $ResolverOutput | Select-Object -Last 1
if ($ResolverExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($ResolvedVanilla)) {
    throw 'Could not resolve the HOI4 vanilla directory.'
}
$ResolvedVanilla = $ResolvedVanilla.Trim()
if (-not (Test-Path -LiteralPath (Join-Path $ResolvedVanilla 'common') -PathType Container)) {
    throw "Resolved HOI4 directory is missing common/: $ResolvedVanilla"
}

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$Report = Join-Path $OutputDirectory 'report.json'
$Hashes = Join-Path $OutputDirectory 'diagnostic-hashes.txt'
$Arguments = @(
    'validate',
    '--game', 'hoi4',
    '--directory', $RepoRoot,
    '--rules', $RulesConfig.FullName,
    '--vanilla', $ResolvedVanilla,
    '--report-type', 'json',
    '--output-file', $Report,
    '--output-hashes', $Hashes,
    '--ignore-hashes', (Join-Path $PSScriptRoot 'cwtools_ignore_hashes.txt'),
    '--loc-language', 'english',
    '--loc-language', 'simp_chinese',
    '--fail-on', $FailOn
)
if ($RefreshVanillaCache) {
    $Arguments += '--refresh-vanilla-cache'
}

& $CwtoolsExe.FullName @Arguments
if ($LASTEXITCODE -ne 0) {
    throw "CWTools returned exit code $LASTEXITCODE; report: $Report"
}
Write-Host "CWTools report: $Report"
