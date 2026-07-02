param(
    [ValidateSet("status", "prepare", "update", "build", "install")]
    [string]$Command = "update",
    [switch]$NoBuild,
    [switch]$NoInstall,
    [switch]$SideBySide,
    [string]$Dest,
    [string]$Image = "zed-japanese-tool:latest",
    [string]$ZedVersion,
    [string]$ZedCommit
)

$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Get-ZedCommand {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Zed\bin\zed.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Zed\bin\zed"),
        (Join-Path $env:LOCALAPPDATA "Programs\Zed\Zed.exe")
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    $command = Get-Command zed -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    throw "Zed was not found. Install official Zed first."
}

function Get-ZedBuild {
    if ($ZedVersion -or $ZedCommit) {
        if (!$ZedVersion -or !$ZedCommit) {
            throw "Specify both -ZedVersion and -ZedCommit."
        }
        if ($ZedCommit -notmatch "^[0-9a-f]{40}$") {
            throw "-ZedCommit must be a 40-character git commit SHA."
        }
        return [pscustomobject]@{
            Version = $ZedVersion
            Commit = $ZedCommit
            Command = "<explicit>"
            InstalledExe = $null
            Raw = "Zed $ZedVersion $ZedCommit"
        }
    }

    $zed = Get-ZedCommand
    $raw = (& $zed --version) -join "`n"
    if ($raw -notmatch "Zed\s+([0-9][^\s]*)\s+([0-9a-f]{40})") {
        throw "Could not parse Zed version output: $raw"
    }
    $version = $Matches[1]
    $commit = $Matches[2]

    $installedExe = Join-Path $env:LOCALAPPDATA "Programs\Zed\Zed.exe"
    if ($raw -match "[–-]\s+(.+?Zed\.exe)\s*$") {
        $installedExe = $Matches[1]
        if ($installedExe.StartsWith("\\?\")) {
            $installedExe = $installedExe.Substring(4)
        }
    }

    [pscustomobject]@{
        Version = $version
        Commit = $commit
        Command = $zed
        InstalledExe = $installedExe
        Raw = $raw
    }
}

function Ensure-DockerImage {
    param([string]$RepoRoot)

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        docker image inspect $Image 1>$null 2>$null
        $imageExists = $LASTEXITCODE -eq 0
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($imageExists) {
        return
    }

    docker build -f (Join-Path $RepoRoot "docker\tooling.Dockerfile") -t $Image $RepoRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to build Docker image: $Image"
    }
}

function Invoke-ZedJapaneseDocker {
    param(
        [string]$RepoRoot,
        [object]$Build,
        [string[]]$CommandArgs
    )

    $mount = "${RepoRoot}:/work"
    $dockerArgs = @(
        "run",
        "--rm",
        "-e", "ZED_VERSION=$($Build.Version)",
        "-e", "ZED_COMMIT=$($Build.Commit)",
        "-e", "ZED_BIN=$($Build.Command)",
        "-e", "ZED_INSTALLED_EXE_PATH=$($Build.InstalledExe)",
        "-e", "ZED_VERSION_RAW=$($Build.Raw)",
        "-v", $mount,
        $Image
    ) + $CommandArgs

    docker @dockerArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Docker command failed: $($CommandArgs -join ' ')"
    }
}

function Test-CommandAvailable {
    param([string]$Name)
    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Import-VsDevEnvironment {
    if (Test-CommandAvailable "cl.exe") {
        return
    }

    $vswhereCandidates = @(
        "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe",
        "$env:ProgramFiles\Microsoft Visual Studio\Installer\vswhere.exe"
    )
    $vswhere = $vswhereCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (!$vswhere) {
        return
    }

    $installationPath = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if (!$installationPath) {
        return
    }

    $devCmd = Join-Path $installationPath "Common7\Tools\VsDevCmd.bat"
    if (!(Test-Path $devCmd)) {
        return
    }

    $envLines = cmd /s /c "`"$devCmd`" -arch=x64 -host_arch=x64 >nul && set"
    foreach ($line in $envLines) {
        if ($line -match "^([^=]+)=(.*)$") {
            [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], "Process")
        }
    }
}

function Assert-HostBuildDependencies {
    Import-VsDevEnvironment

    $missing = @()
    if (!(Test-CommandAvailable "cargo.exe")) {
        $missing += "Rust/cargo"
    }
    if (!(Test-CommandAvailable "cl.exe")) {
        $missing += "MSVC C++ build tools"
    }
    if (!(Test-CommandAvailable "cmake.exe")) {
        $missing += "CMake"
    }

    if ($missing.Count -gt 0) {
        throw @"
Missing Windows build dependencies: $($missing -join ", ")

Install Visual Studio Build Tools or Visual Studio with:
- Desktop development with C++
- MSVC x64/x86 build tools
- MSVC Spectre-mitigated libs
- Windows 10/11 SDK
- CMake

VS Code is not sufficient. After installing, rerun this command from PowerShell.
"@
    }
}

function Invoke-HostBuild {
    param([string]$RepoRoot)

    $sourceDir = Join-Path $RepoRoot ".cache\zed-upstream"
    if (!(Test-Path $sourceDir)) {
        throw "Zed source is missing. Run prepare first."
    }

    Assert-HostBuildDependencies

    Push-Location $sourceDir
    try {
        cargo build --release
        if ($LASTEXITCODE -ne 0) {
            throw "cargo build --release failed"
        }
    }
    finally {
        Pop-Location
    }
}

function Find-ZedArtifact {
    param([string]$RepoRoot)

    $candidates = @(
        (Join-Path $RepoRoot ".cache\zed-upstream\target\release\Zed.exe"),
        (Join-Path $RepoRoot ".cache\zed-upstream\target\release\zed.exe"),
        (Join-Path $RepoRoot ".cache\zed-upstream\target\release\cli.exe")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }
    throw "Build artifact was not found under .cache\zed-upstream\target\release."
}

function Install-Overlay {
    param(
        [object]$Build,
        [string]$Artifact,
        [string]$RepoRoot
    )

    if (!$Build.InstalledExe) {
        throw "Official Zed.exe path is unknown. Install official Zed first, or use -SideBySide -Dest <path>."
    }
    if (!(Test-Path $Build.InstalledExe)) {
        throw "Official Zed.exe was not found: $($Build.InstalledExe)"
    }

    $backupDir = Join-Path (Split-Path $Build.InstalledExe -Parent) ".zed-japanese-backups"
    New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
    $stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddHHmmss")
    $backup = Join-Path $backupDir "Zed.exe.$($Build.Version).$($Build.Commit.Substring(0, 12)).$stamp.bak"

    Copy-Item -Force $Build.InstalledExe $backup
    Copy-Item -Force $Artifact $Build.InstalledExe

    $manifest = [ordered]@{
        installed_at = (Get-Date).ToUniversalTime().ToString("o")
        mode = "official"
        source_version = $Build.Version
        source_commit = $Build.Commit
        artifact = $Artifact
        installed_path = $Build.InstalledExe
        backup_path = $backup
    }
    $cacheDir = Join-Path $RepoRoot ".cache"
    New-Item -ItemType Directory -Force -Path $cacheDir | Out-Null
    $manifest | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $cacheDir "install-manifest.json")
    Write-Host "installed: $($Build.InstalledExe)"
    Write-Host "backup: $backup"
}

function Install-SideBySide {
    param(
        [string]$Artifact,
        [string]$Dest
    )

    if (!$Dest) {
        $Dest = Join-Path $env:LOCALAPPDATA "Programs\Zed Japanese"
    }
    New-Item -ItemType Directory -Force -Path $Dest | Out-Null
    $target = Join-Path $Dest (Split-Path $Artifact -Leaf)
    Copy-Item -Force $Artifact $target
    Write-Host "installed: $target"
}

$repoRoot = Get-RepoRoot
$build = Get-ZedBuild
Ensure-DockerImage -RepoRoot $repoRoot

switch ($Command) {
    "status" {
        Invoke-ZedJapaneseDocker -RepoRoot $repoRoot -Build $build -CommandArgs @("status")
    }
    "prepare" {
        Invoke-ZedJapaneseDocker -RepoRoot $repoRoot -Build $build -CommandArgs @("update", "--no-build")
    }
    "update" {
        Invoke-ZedJapaneseDocker -RepoRoot $repoRoot -Build $build -CommandArgs @("update", "--no-build")
        if (!$NoBuild) {
            Invoke-HostBuild -RepoRoot $repoRoot
        }
        if (!$NoInstall) {
            $artifact = Find-ZedArtifact -RepoRoot $repoRoot
            if ($SideBySide) {
                Install-SideBySide -Artifact $artifact -Dest $Dest
            }
            else {
                Install-Overlay -Build $build -Artifact $artifact -RepoRoot $repoRoot
            }
        }
    }
    "build" {
        Invoke-HostBuild -RepoRoot $repoRoot
    }
    "install" {
        $artifact = Find-ZedArtifact -RepoRoot $repoRoot
        if ($SideBySide) {
            Install-SideBySide -Artifact $artifact -Dest $Dest
        }
        else {
            Install-Overlay -Build $build -Artifact $artifact -RepoRoot $repoRoot
        }
    }
}
