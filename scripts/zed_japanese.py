#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / ".cache"
ZED_SOURCE_DIR = CACHE_DIR / "zed-upstream"
TRANSLATION_FILE = ROOT / "translations" / "ja-JP.json"
UPSTREAM_URL = "https://github.com/zed-industries/zed.git"


class CommandError(RuntimeError):
    pass


@dataclass(frozen=True)
class ZedBuild:
    version: str
    commit: str
    binary: str
    raw: str


def run(
    args: list[str],
    *,
    cwd: Path | None = None,
    capture: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        check=False,
    )
    if check and result.returncode != 0:
        details = ""
        if capture:
            details = f"\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        raise CommandError(f"command failed: {' '.join(args)}{details}")
    return result


def find_zed() -> str:
    configured = os.environ.get("ZED_BIN")
    if configured:
        return configured

    found = shutil.which("zed")
    if found:
        return found

    candidates = [
        "/mnt/c/Users/o9oem/AppData/Local/Programs/Zed/bin/zed",
        "/mnt/c/Users/o9oem/AppData/Local/Programs/Zed/Zed.exe",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate

    raise CommandError("Zed binary was not found. Set ZED_BIN=/path/to/zed.")


def detect_zed() -> ZedBuild:
    binary = find_zed()
    result = run([binary, "--version"], capture=True)
    raw = result.stdout.strip()
    match = re.search(r"Zed\s+([0-9][^\s]*)\s+([0-9a-f]{40})", raw)
    if not match:
        raise CommandError(f"could not parse Zed version output: {raw}")
    return ZedBuild(
        version=match.group(1),
        commit=match.group(2),
        binary=binary,
        raw=raw,
    )


def cmd_detect(_: argparse.Namespace) -> None:
    build = detect_zed()
    print(json.dumps(build.__dict__, ensure_ascii=False, indent=2))


def ensure_source(commit: str) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if not ZED_SOURCE_DIR.exists():
        run(["git", "clone", UPSTREAM_URL, str(ZED_SOURCE_DIR)])
    else:
        run(["git", "fetch", "--tags", "origin"], cwd=ZED_SOURCE_DIR)

    run(["git", "checkout", "--detach", commit], cwd=ZED_SOURCE_DIR)
    run(["git", "clean", "-fd"], cwd=ZED_SOURCE_DIR)
    run(["git", "reset", "--hard", commit], cwd=ZED_SOURCE_DIR)


def cmd_sync(_: argparse.Namespace) -> None:
    build = detect_zed()
    ensure_source(build.commit)
    print(f"checked out Zed {build.version} at {build.commit}")


def load_translations() -> dict[str, str]:
    with TRANSLATION_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise CommandError(f"{TRANSLATION_FILE} must contain a JSON object")
    return {str(key): str(value) for key, value in data.items()}


def rust_string_literal(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)


def patch_file(path: Path, translations: dict[str, str]) -> tuple[int, list[str]]:
    original = path.read_text(encoding="utf-8")
    updated = original
    applied = 0
    missed: list[str] = []

    for source, target in translations.items():
        source_literal = rust_string_literal(source)
        target_literal = rust_string_literal(target)
        count = updated.count(source_literal)
        if count == 0:
            missed.append(source)
            continue
        updated = updated.replace(source_literal, target_literal)
        applied += count

    if updated != original:
        path.write_text(updated, encoding="utf-8")

    return applied, missed


def candidate_source_files() -> list[Path]:
    roots = [
        ZED_SOURCE_DIR / "crates" / "zed" / "src",
        ZED_SOURCE_DIR / "crates" / "workspace" / "src",
        ZED_SOURCE_DIR / "crates" / "command_palette" / "src",
        ZED_SOURCE_DIR / "crates" / "ui" / "src",
        ZED_SOURCE_DIR / "crates" / "project_panel" / "src",
        ZED_SOURCE_DIR / "crates" / "outline_panel" / "src",
        ZED_SOURCE_DIR / "crates" / "terminal_view" / "src",
        ZED_SOURCE_DIR / "crates" / "git_ui" / "src",
        ZED_SOURCE_DIR / "assets",
    ]
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        files.extend(
            path
            for path in root.rglob("*")
            if path.suffix in {".rs", ".json", ".toml"}
        )
    return sorted(files)


def cmd_patch(_: argparse.Namespace) -> None:
    if not ZED_SOURCE_DIR.exists():
        raise CommandError("Zed source is missing. Run `sync` first.")

    translations = load_translations()
    total = 0
    missed_by_file: dict[str, int] = {key: 0 for key in translations}

    for path in candidate_source_files():
        applied, missed = patch_file(path, translations)
        total += applied
        for item in missed:
            missed_by_file[item] += 1

    found_anywhere = [
        key for key, misses in missed_by_file.items() if misses < len(candidate_source_files())
    ]
    missing_everywhere = [
        key for key, misses in missed_by_file.items() if misses == len(candidate_source_files())
    ]

    print(f"applied replacements: {total}")
    print(f"translation keys found: {len(found_anywhere)} / {len(translations)}")
    if missing_everywhere:
        print("missing translation keys:")
        for key in missing_everywhere:
            print(f"  - {key}")


def cmd_prepare(args: argparse.Namespace) -> None:
    cmd_sync(args)
    cmd_patch(args)


def cmd_build(_: argparse.Namespace) -> None:
    if not ZED_SOURCE_DIR.exists():
        raise CommandError("Zed source is missing. Run `prepare` first.")
    run(["cargo", "run", "--release"], cwd=ZED_SOURCE_DIR)


def main() -> int:
    parser = argparse.ArgumentParser(description="Local Japanese Zed build helper")
    subcommands = parser.add_subparsers(dest="command", required=True)

    subcommands.add_parser("detect").set_defaults(func=cmd_detect)
    subcommands.add_parser("sync").set_defaults(func=cmd_sync)
    subcommands.add_parser("patch").set_defaults(func=cmd_patch)
    subcommands.add_parser("prepare").set_defaults(func=cmd_prepare)
    subcommands.add_parser("build").set_defaults(func=cmd_build)

    args = parser.parse_args()
    try:
        args.func(args)
    except CommandError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

