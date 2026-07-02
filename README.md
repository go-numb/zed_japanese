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

Run all steps except build:

```sh
python3 scripts/zed_japanese.py prepare
```

## Directory Layout

- `.cache/zed-upstream/`: cloned Zed source
- `translations/ja-JP.json`: Japanese UI translation entries
- `scripts/zed_japanese.py`: update-aware local build helper

## Design Notes

- The installed Zed commit is the source of truth.
- Translation data is local and reusable across Zed updates.
- Missing strings should be reported, not treated as a hard failure.
- Runtime hooks and DLL injection are avoided.
- Upstream changes are expected; the patch step should remain idempotent.

