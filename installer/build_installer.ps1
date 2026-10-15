#requires -Version 5
<#
    Build the 14th_ua's MoE Calculator Windows installer (setup.exe) with Inno Setup.

    Prerequisites:
      1. The mod .wotmod must already be built into ..\dist by the Python 2.7 build:
             & "C:\Python27\python.exe" build\build_wotmod.py
      2. Inno Setup must be installed (provides ISCC.exe):
             winget install -e --id JRSoftware.InnoSetup
      3. The bundled vendor .wotmod dependencies must be present under installer\vendor\
         (net.openwg.gameface_1.2.2.wotmod, aslain.modmenu_2.1.04.wotmod,
          me.poliroid.modslistapi_1.8.0.wotmod).

    Usage:
        pwsh installer\build_installer.ps1
    Output:
        dist\MoECalculator-Setup-<version>.exe
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$InstallerDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot     = Split-Path -Parent $InstallerDir
$Iss          = Join-Path $InstallerDir 'moe_calculator-setup.iss'
$ModWotmod    = Join-Path $RepoRoot 'dist\com.14th_ua.moe_calculator_8.0.0.wotmod'
$OpenWg       = Join-Path $InstallerDir 'vendor\net.openwg.gameface_1.2.2.wotmod'
$Msa          = Join-Path $InstallerDir 'vendor\aslain.modmenu_2.1.04.wotmod'
$ModsList     = Join-Path $InstallerDir 'vendor\me.poliroid.modslistapi_1.8.0.wotmod'

function Find-ISCC {
    $candidates = @(
        (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
        (Join-Path $env:ProgramFiles        'Inno Setup 6\ISCC.exe'),
        (Join-Path $env:LOCALAPPDATA        'Programs\Inno Setup 6\ISCC.exe')
    )
    foreach ($c in $candidates) { if ($c -and (Test-Path $c)) { return $c } }
    $cmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

# --- preflight ---------------------------------------------------------------
if (-not (Test-Path $ModWotmod)) {
    throw "Mod package not found: $ModWotmod`nBuild it first:`n    & `"C:\Python27\python.exe`" build\build_wotmod.py"
}
if (-not (Test-Path $OpenWg)) {
    throw "Bundled OpenWG dependency not found: $OpenWg"
}
if (-not (Test-Path $Msa)) {
    throw "Bundled Aslain ModMenu dependency not found: $Msa"
}
if (-not (Test-Path $ModsList)) {
    throw "Bundled Mods List API dependency not found: $ModsList"
}
$iscc = Find-ISCC
if (-not $iscc) {
    throw "ISCC.exe (Inno Setup compiler) not found. Install it:`n    winget install -e --id JRSoftware.InnoSetup"
}

Write-Host "ISCC:       $iscc"
Write-Host "Mod:        $ModWotmod"
Write-Host "OpenWG:     $OpenWg"
Write-Host "ModMenu:    $Msa"
Write-Host "ModsList:   $ModsList"
Write-Host "Script:     $Iss"
Write-Host ''

# --- compile -----------------------------------------------------------------
& $iscc $Iss
if ($LASTEXITCODE -ne 0) {
    throw "ISCC failed with exit code $LASTEXITCODE"
}

$out = Get-ChildItem (Join-Path $RepoRoot 'dist') -Filter 'MoECalculator-Setup-*.exe' |
       Sort-Object LastWriteTime -Descending | Select-Object -First 1

# The installer's own self-updater (see moe_calculator-setup.iss's DownloadAndRun) refuses
# to run a downloaded update without a matching "<exe>.sha256" release asset -- emit it here
# so a release upload is never missing the file the update check depends on.
# .NET hash -- Get-FileHash is unavailable under `powershell -NoProfile` here.
$sha = [System.Security.Cryptography.SHA256]::Create()
$fs = [System.IO.File]::OpenRead($out.FullName)
try { $hash = ([BitConverter]::ToString($sha.ComputeHash($fs)) -replace '-', '').ToLower() } finally { $fs.Dispose() }
[System.IO.File]::WriteAllText("$($out.FullName).sha256", $hash)
if (-not (Test-Path "$($out.FullName).sha256")) { throw "SHA-256 sidecar was not written: $($out.FullName).sha256" }

Write-Host ''
Write-Host "Built installer: $($out.FullName)" -ForegroundColor Green
Write-Host "SHA-256:         $($out.FullName).sha256 ($hash)" -ForegroundColor Green
