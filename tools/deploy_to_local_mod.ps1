# Deploy the repository to the local HOI4 mod folder for in-game verification.
# Usage:
#   powershell -ExecutionPolicy Bypass -File tools/deploy_to_local_mod.ps1
#
# Contract (see docs/DEVELOPMENT.md "实机测试协作" and
# docs/maintenance/开发状态快照与交接.md §6):
#   - Fixed install folder name, never renamed:
#       C:\Users\Admin\Documents\Paradox Interactive\Hearts of Iron IV\mod\OCS_one_click_sandbox_start_v2_0
#   - Copies common/, events/, localisation/, descriptor.mod, thumbnail.png,
#     LICENSE, NOTICE.md over the existing install (deleting stale files).
#   - Updates the registry .mod (same folder, extension file) version/name to
#     match descriptor.mod, keeping its existing path value, written as UTF-8
#     without BOM.
#   - Copies the matching version testing docs (README + checklist) into the
#     mod root folder (they are not part of the zip install folder).
#   - Ensures dlc_load.json enables the local registry .mod, not the workshop
#     stub; backs up dlc_load.json to dlc_load.json.bak before any edit.

$ErrorActionPreference = 'Stop'

$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$paradoxRoot = 'C:\Users\Admin\Documents\Paradox Interactive\Hearts of Iron IV'
$modRoot = Join-Path $paradoxRoot 'mod'
$install = Join-Path $modRoot 'OCS_one_click_sandbox_start_v2_0'
$registry = Join-Path $modRoot 'OCS_one_click_sandbox_start_v2_0.mod'
$dlcLoad = Join-Path $paradoxRoot 'dlc_load.json'
$dlcLoadBak = Join-Path $paradoxRoot 'dlc_load.json.bak'

# --- 1. Read the version from the repository descriptor.mod (source of truth). ---
$descriptorPath = Join-Path $repo 'descriptor.mod'
$descriptorText = [System.IO.File]::ReadAllText($descriptorPath)
$version = [regex]::Match($descriptorText, 'version\s*=\s*"([^"]+)"').Groups[1].Value
if (-not $version) { throw "Cannot read version from $descriptorPath" }
$name = [regex]::Match($descriptorText, 'name\s*=\s*"([^"]+)"').Groups[1].Value
if (-not $name) { throw "Cannot read name from $descriptorPath" }

Write-Host "Deploying v$version to $install"

# --- 2. Create the install folder if needed. ---
if (-not (Test-Path $install)) {
    New-Item -ItemType Directory -Path $install | Out-Null
}

# --- 3. Mirror the three script directories and copy the loose files. ---
$dirs = @('common', 'events', 'localisation')
foreach ($d in $dirs) {
    $src = Join-Path $repo $d
    if (-not (Test-Path $src)) { throw "Missing repository directory: $src" }
    robocopy $src (Join-Path $install $d) /MIR /NFL /NDL /NJH /NJS | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy failed for $d with exit code $LASTEXITCODE" }
}
foreach ($f in 'descriptor.mod', 'thumbnail.png', 'LICENSE', 'NOTICE.md') {
    $src = Join-Path $repo $f
    if (-not (Test-Path $src)) { throw "Missing repository file: $src" }
    Copy-Item $src (Join-Path $install $f) -Force
}

# --- 4. Verify the installed descriptor.mod exists and matches version. ---
$installedDescriptor = Join-Path $install 'descriptor.mod'
if (-not (Test-Path $installedDescriptor)) { throw 'descriptor.mod missing after deploy' }
$installedText = [System.IO.File]::ReadAllText($installedDescriptor)
$installedVersion = [regex]::Match($installedText, 'version\s*=\s*"([^"]+)"').Groups[1].Value
if ($installedVersion -ne $version) {
    throw "Installed descriptor.mod version $installedVersion != expected $version"
}

# --- 5. Update the registry .mod (extension file next to the folder). ---
if (-not (Test-Path $registry)) { throw "Registry .mod missing: $registry" }
$registryText = [System.IO.File]::ReadAllText($registry)
$registryText = [regex]::Replace($registryText, '(?m)^\s*version\s*=\s*"[^"]*"', "version=`"$version`"")
$registryText = [regex]::Replace($registryText, '(?m)^\s*name\s*=\s*"[^"]*"', "name=`"$name`"")
# UTF-8 without BOM: the game/launcher expects plain UTF-8 here.
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($registry, $registryText, $utf8NoBom)

# --- 6. Copy the version-matched testing docs to the mod root. ---
$docsDir = Join-Path $repo 'docs'
$testingDir = Join-Path $docsDir 'testing'
if (-not (Test-Path $testingDir)) { throw "Missing docs/testing: $testingDir" }
$docFiles = Get-ChildItem -Path $testingDir -File | Where-Object {
    $_.Name -like "*v${version}_*"
}
foreach ($doc in $docFiles) {
    Copy-Item $doc.FullName (Join-Path $modRoot $doc.Name) -Force
    Write-Host "  doc: $($doc.Name)"
}

# --- 7. Ensure dlc_load.json enables the local registry .mod. ---
$targetEntry = 'mod/OCS_one_click_sandbox_start_v2_0.mod'
if (-not (Test-Path $dlcLoad)) { throw "Missing $dlcLoad" }
$loadText = [System.IO.File]::ReadAllText($dlcLoad)
$load = $loadText | ConvertFrom-Json
$enabled = @($load.enabled_mods)
if ($enabled -notcontains $targetEntry) {
    Copy-Item $dlcLoad $dlcLoadBak -Force
    Write-Host "  backed up $dlcLoad -> $dlcLoadBak"
    $enabled = @($targetEntry)
    $load.enabled_mods = $enabled
    $json = $load | ConvertTo-Json -Compress
    # Keep the same compact single-line shape the launcher writes.
    [System.IO.File]::WriteAllText($dlcLoad, $json, $utf8NoBom)
    Write-Host "  dlc_load.json updated to enable $targetEntry"
} else {
    Write-Host "  dlc_load.json already enables $targetEntry"
}

# --- 8. Final verification report. ---
Write-Host ''
Write-Host "VERIFY  installed descriptor.mod version: $installedVersion"
Write-Host "VERIFY  registry .mod version:             $([regex]::Match([System.IO.File]::ReadAllText($registry), 'version\s*=\s*"([^"]+)"').Groups[1].Value)"
Write-Host "VERIFY  registry .mod name:                $([regex]::Match([System.IO.File]::ReadAllText($registry), 'name\s*=\s*"([^"]+)"').Groups[1].Value)"
Write-Host "VERIFY  dlc_load enabled:                  $([System.IO.File]::ReadAllText($dlcLoad))"
Write-Host ''
Write-Output 'DEPLOYED'