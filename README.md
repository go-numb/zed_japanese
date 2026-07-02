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

- Git
- Python 3.11 or later
- Rust toolchain for building Zed
- Platform dependencies required by Zed

Zed's official build docs:

- Windows: https://zed.dev/docs/development/windows
- Linux: https://zed.dev/docs/development/linux
- macOS: https://zed.dev/docs/development/macos

## Workflow

Normal update flow:

```sh
python3 scripts/zed_japanese.py update --install
```

This runs:

1. `sync`: follow the commit used by the installed stable Zed.
2. `patch`: apply local Japanese translations.
3. `build`: build patched Zed with `cargo build --release`.
4. `install`: copy the built artifact to a side-by-side local install
   directory.

The official Zed installation is not overwritten by default. The local Japanese
build is installed separately so the official auto-updated Zed can continue to
track stable releases. After official Zed updates, rerun `update --install`.

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

Install side-by-side:

```sh
python3 scripts/zed_japanese.py install
```

Use a custom install directory:

```sh
python3 scripts/zed_japanese.py install --dest ~/apps/zed-japanese
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
- Never patch the official installed executable in place.
- Build a Japanese variant from the exact source commit reported by
  `zed --version`.
- Install the Japanese build side-by-side.
- Keep translation data small and reviewable in this repository.
- Let upstream churn happen; missing strings are reported and can be translated
  incrementally.

Default install locations:

- Windows Python: `%LOCALAPPDATA%\Programs\Zed Japanese`
- Linux/macOS/WSL Python: `~/.local/zed-japanese`

When running from WSL against a Windows Zed install, the tool can still detect
the Windows Zed version. Building a Windows executable should be done from a
Windows Rust environment; building from WSL produces a Linux build.

## Design Notes

- The installed Zed commit is the source of truth.
- Translation data is local and reusable across Zed updates.
- Missing strings should be reported, not treated as a hard failure.
- Runtime hooks and DLL injection are avoided.
- Upstream changes are expected; the patch step should remain idempotent.
- Local installs are side-by-side and reversible.
