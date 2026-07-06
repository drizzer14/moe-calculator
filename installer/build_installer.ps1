#requires -Version 5
<#
    Build the 14th_ua's MoE Calculator Windows installer (setup.exe) with Inno Setup.

    Prerequisites:
      1. The mod .wotmod must already be built into ..\dist by the Python 2.7 build:
             & "C:\Python27\python.exe" build\build_wotmod.py
      2. Inno Setup must be installed (provides ISCC.exe):
             winget install -e --id JRSoftware.InnoSetup
      3. The bundled vendor .wotmod dependencies must be present under installer\vendor\
         (net.openwg.gameface_1.1.6.wotmod, izeberg.modssettingsapi_1.7.0.wotmod).

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
$ModWotmod    = Join-Path $RepoRoot 'dist\com.14th_ua.moe_calculator_0.1.0.wotmod'
$OpenWg       = Join-Path $InstallerDir 'vendor\net.openwg.gameface_1.1.6.wotmod'
$Msa          = Join-Path $InstallerDir 'vendor\izeberg.modssettingsapi_1.7.0.wotmod'

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
    throw "Bundled ModsSettingsAPI dependency not found: $Msa"
}
$iscc = Find-ISCC
if (-not $iscc) {
    throw "ISCC.exe (Inno Setup compiler) not found. Install it:`n    winget install -e --id JRSoftware.InnoSetup"
}

Write-Host "ISCC:       $iscc"
Write-Host "Mod:        $ModWotmod"
Write-Host "OpenWG:     $OpenWg"
Write-Host "MSA:        $Msa"
Write-Host "Script:     $Iss"
Write-Host ''

# --- compile -----------------------------------------------------------------
& $iscc $Iss
if ($LASTEXITCODE -ne 0) {
    throw "ISCC failed with exit code $LASTEXITCODE"
}

$out = Get-ChildItem (Join-Path $RepoRoot 'dist') -Filter 'MoECalculator-Setup-*.exe' |
       Sort-Object LastWriteTime -Descending | Select-Object -First 1
Write-Host ''
Write-Host "Built installer: $($out.FullName)" -ForegroundColor Green
