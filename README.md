# zed_japanese

Local Japanese build tooling for Zed.

This project is intentionally not a long-lived fork. Zed updates frequently, so
the workflow follows the Zed version already installed on this machine:

1. Detect the installed Zed version and git commit from `zed --version`.
2. Fetch `zed-industries/zed`.
3. Check out the exact commit used by the installed stable build.
4. Apply local Japanese UI string patches.
5. Build the patched source locally.

The goal is to preserve Zed's runtime characteristics. Translation is applied at
build time, not by injecting DLLs, hooking UI calls, or running a translation
layer while Zed is open.

## Current Status

This repository currently contains the update-aware build scaffold. The
translation patcher starts conservatively and will be expanded as we identify
stable UI string locations in Zed's source.

## Requirements

Choose one tooling path:

- Python path: Git, Python 3.11 or later
- Docker path on Windows: Docker Desktop and PowerShell

Both paths still need:

- Rust toolchain for building Zed
- Platform dependencies required by Zed
- Visual Studio or Visual Studio Build Tools with the C++ toolchain on Windows

Zed's official build docs:

- Windows: https://zed.dev/docs/development/windows
- Linux: https://zed.dev/docs/development/linux
- macOS: https://zed.dev/docs/development/macos

## Workflow

Windows 11 with Docker Desktop and no Python:

```powershell
git clone https://github.com/go-numb/zed_japanese.git
cd zed_japanese
powershell -ExecutionPolicy Bypass -File .\scripts\zed_japanese.ps1 -Command update
```

Japanese install guide:

- [docs/usage-ja.md](docs/usage-ja.md)

The Japanese guide includes the known install/update blockers seen in practice:
missing Docker image, Docker argument forwarding, missing CMake, missing Windows
SDK libraries such as `kernel32.lib`, and long first-time clone/build steps.

Normal update flow:

```sh
python3 scripts/zed_japanese.py update --install
```

This runs:

1. `sync`: follow the commit used by the installed stable Zed.
2. `patch`: apply local Japanese translations.
3. `build`: build patched Zed with `cargo build --release`.
4. `install`: back up the official `Zed.exe`, then overlay it with the
   Japanese build.

The official Zed installation is the primary target by default. This keeps the
same app identity, user data, extensions, history, settings, and launcher
behavior. If anything goes wrong, reinstalling official Zed restores the normal
build. Official updates may also replace the Japanese build; rerun
`update --install` after updating Zed.

Windows without Python:

```powershell
.\scripts\zed_japanese.ps1 -Command update
```

The PowerShell wrapper detects official Zed on the host, runs the Python
sync/patch steps inside Docker, builds with host `cargo`, then overlays the
official `Zed.exe`.

The Windows build still requires Visual Studio or Visual Studio Build Tools with
the C++ toolchain. VS Code is a different product and is not sufficient. The
wrapper tries to load `VsDevCmd.bat` automatically when Build Tools are
installed; if that fails, run it from "Developer PowerShell for VS".

Required Visual Studio components:

- Desktop development with C++
- MSVC x64/x86 build tools
- MSVC Spectre-mitigated libs
- Windows 10/11 SDK
- CMake

If only CMake is missing:

```powershell
winget install -e --id Kitware.CMake
Get-Command cmake
```

If linking fails with `cannot open input file 'kernel32.lib'`, install the
Windows 10/11 SDK from Visual Studio Installer and rerun from a new PowerShell
or "Developer PowerShell for VS".

If official Zed is not installed yet, install it first for the normal overlay
flow. To only test source checkout and patching on a machine without Zed,
provide the version and commit explicitly:

```powershell
.\scripts\zed_japanese.ps1 -Command prepare `
  -ZedVersion 1.9.0 `
  -ZedCommit ced90fc636c4ede05402befc38a63bae7fd741bd
```

That explicit mode can prepare/build, but official overlay install requires an
installed official Zed path.

Check current state:

```sh
python3 scripts/zed_japanese.py status
```

Detect the local Zed build:

```sh
python3 scripts/zed_japanese.py detect
```

Fetch and check out the matching source:

```sh
python3 scripts/zed_japanese.py sync
```

Apply Japanese translations:

```sh
python3 scripts/zed_japanese.py patch
```

Build:

```sh
python3 scripts/zed_japanese.py build
```

Locate the built executable:

```sh
python3 scripts/zed_japanese.py locate-artifact
```

Install over the official Zed executable:

```sh
python3 scripts/zed_japanese.py install
```

Install side-by-side instead:

```sh
python3 scripts/zed_japanese.py install --mode side-by-side --dest ~/apps/zed-japanese
```

Run all steps except build:

```sh
python3 scripts/zed_japanese.py prepare
```

Run sync and patch only:

```sh
python3 scripts/zed_japanese.py update --no-build
```

## Directory Layout

- `.cache/zed-upstream/`: cloned Zed source
- `.cache/install-manifest.json`: last local install metadata
- `translations/ja-JP.json`: Japanese UI translation entries
- `scripts/zed_japanese.py`: update-aware local build helper

## Install and Update Policy

- Treat the official Zed install as the source of truth for stable updates.
- Build a Japanese variant from the exact source commit reported by
  `zed --version`.
- Overlay the official `Zed.exe` by default, after backing it up.
- Keep the app identity unchanged so settings, extensions, history, and caches
  continue to use Zed's normal user data directories.
- Keep side-by-side install available for experiments.
- Keep translation data small and reviewable in this repository.
- Let upstream churn happen; missing strings are reported and can be translated
  incrementally.

Default official overlay target:

- The `Zed.exe` path reported by `zed --version`, for example
  `%LOCALAPPDATA%\Programs\Zed\Zed.exe`.

Default side-by-side install locations:

- Windows Python: `%LOCALAPPDATA%\Programs\Zed Japanese`
- Linux/macOS/WSL Python: `~/.local/zed-japanese`

When running from WSL against a Windows Zed install, the tool can still detect
the Windows Zed version. Building and overlaying a Windows executable should be
done from a Windows Rust environment; building from WSL produces a Linux build
and is refused when the target is Windows `Zed.exe`.

When Windows has Docker but not Python, use `scripts\zed_japanese.ps1`. Docker
provides Python and Git for the patching steps; Windows still provides Cargo and
the Windows build dependencies.

## Design Notes

- The installed Zed commit is the source of truth.
- Translation data is local and reusable across Zed updates.
- Missing strings should be reported, not treated as a hard failure.
- Runtime hooks and DLL injection are avoided.
- Upstream changes are expected; the patch step should remain idempotent.
- Official overlays are backed up and reversible by reinstalling official Zed.
- Side-by-side installs remain available for testing.
