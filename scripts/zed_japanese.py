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
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / ".cache"
ZED_SOURCE_DIR = CACHE_DIR / "zed-upstream"
TRANSLATION_FILE = ROOT / "translations" / "ja-JP.json"
INSTALL_MANIFEST = CACHE_DIR / "install-manifest.json"
UPSTREAM_URL = "https://github.com/zed-industries/zed.git"


class CommandError(RuntimeError):
    pass


@dataclass(frozen=True)
class ZedBuild:
    version: str
    commit: str
    binary: str
    installed_exe_path: str | None
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


def is_wsl() -> bool:
    try:
        return "microsoft" in Path("/proc/version").read_text(encoding="utf-8").lower()
    except OSError:
        return False


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


def detect_zed_from_env() -> ZedBuild | None:
    version = os.environ.get("ZED_VERSION")
    commit = os.environ.get("ZED_COMMIT")
    if not version and not commit:
        return None
    if not version or not commit:
        raise CommandError("set both ZED_VERSION and ZED_COMMIT, or neither")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise CommandError("ZED_COMMIT must be a 40-character git commit SHA")
    return ZedBuild(
        version=version,
        commit=commit,
        binary=os.environ.get("ZED_BIN", "<env>"),
        installed_exe_path=os.environ.get("ZED_INSTALLED_EXE_PATH"),
        raw=os.environ.get("ZED_VERSION_RAW", f"Zed {version} {commit}"),
    )


def localize_windows_path(path: str) -> str:
    normalized = path
    if normalized.startswith("\\\\?\\"):
        normalized = normalized[4:]
    if is_wsl():
        match = re.match(r"^([A-Za-z]):\\(.*)$", normalized)
        if match:
            drive = match.group(1).lower()
            rest = match.group(2).replace("\\", "/")
            return f"/mnt/{drive}/{rest}"
    return normalized


def parse_installed_exe_path(raw: str, binary: str) -> str | None:
    # Windows builds print the resolved executable path after an en dash.
    match = re.search(r"[–-]\s+(.+?Zed\.exe)\s*$", raw)
    if match:
        return localize_windows_path(match.group(1))

    binary_path = Path(binary)
    if binary_path.name.lower() == "zed.exe":
        return str(binary_path)

    sibling = binary_path.parent.parent / "Zed.exe"
    if sibling.exists():
        return str(sibling)

    return None


def detect_zed() -> ZedBuild:
    env_build = detect_zed_from_env()
    if env_build:
        return env_build

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
        installed_exe_path=parse_installed_exe_path(raw, binary),
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


def source_head() -> str | None:
    if not (ZED_SOURCE_DIR / ".git").exists():
        return None
    result = run(["git", "rev-parse", "HEAD"], cwd=ZED_SOURCE_DIR, capture=True)
    return result.stdout.strip()


def source_dirty() -> bool:
    if not (ZED_SOURCE_DIR / ".git").exists():
        return False
    result = run(["git", "status", "--porcelain"], cwd=ZED_SOURCE_DIR, capture=True)
    return bool(result.stdout.strip())


def cmd_status(_: argparse.Namespace) -> None:
    build = detect_zed()
    head = source_head()
    status = {
        "installed_zed": build.__dict__,
        "source_dir": str(ZED_SOURCE_DIR),
        "source_present": ZED_SOURCE_DIR.exists(),
        "source_head": head,
        "source_matches_installed": head == build.commit,
        "source_dirty": source_dirty(),
        "translation_file": str(TRANSLATION_FILE),
        "translation_entries": len(load_translations()),
        "install_manifest": str(INSTALL_MANIFEST),
        "install_manifest_present": INSTALL_MANIFEST.exists(),
        "running_under_wsl": is_wsl(),
    }
    print(json.dumps(status, ensure_ascii=False, indent=2))


def cmd_prepare(args: argparse.Namespace) -> None:
    cmd_sync(args)
    cmd_patch(args)


def cmd_build(args: argparse.Namespace) -> None:
    if not ZED_SOURCE_DIR.exists():
        raise CommandError("Zed source is missing. Run `prepare` first.")
    cargo_args = ["cargo", "build"]
    if args.release:
        cargo_args.append("--release")
    run(cargo_args, cwd=ZED_SOURCE_DIR)


def artifact_candidates(release: bool = True) -> list[Path]:
    profile = "release" if release else "debug"
    target_dir = ZED_SOURCE_DIR / "target" / profile
    names = [
        "Zed.exe",
        "zed.exe",
        "cli.exe",
        "zed",
        "cli",
    ]
    return [target_dir / name for name in names]


def locate_artifact(release: bool = True) -> Path:
    for candidate in artifact_candidates(release):
        if candidate.exists() and candidate.is_file():
            return candidate
    searched = "\n".join(f"  - {candidate}" for candidate in artifact_candidates(release))
    raise CommandError(f"build artifact was not found. Searched:\n{searched}")


def default_install_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "Programs" / "Zed Japanese"
    return Path.home() / ".local" / "zed-japanese"


def backup_path_for(dest: Path, build: ZedBuild) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    backup_dir = dest.parent / ".zed-japanese-backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir / f"{dest.name}.{build.version}.{build.commit[:12]}.{stamp}.bak"


def install_artifact(artifact: Path, dest: Path, build: ZedBuild, mode: str) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    backup: Path | None = None
    if dest.exists():
        backup = backup_path_for(dest, build)
        shutil.copy2(dest, backup)
    shutil.copy2(artifact, dest)
    manifest = {
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "source_version": build.version,
        "source_commit": build.commit,
        "artifact": str(artifact),
        "installed_path": str(dest),
        "backup_path": str(backup) if backup else None,
    }
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    INSTALL_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return dest


def install_side_by_side(artifact: Path, dest_dir: Path, build: ZedBuild) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / artifact.name
    return install_artifact(artifact, dest, build, "side-by-side")


def official_install_path(build: ZedBuild) -> Path:
    if not build.installed_exe_path:
        raise CommandError("could not determine the installed official Zed.exe path")
    return Path(build.installed_exe_path)


def validate_overlay_artifact(artifact: Path, dest: Path) -> None:
    if artifact.resolve() == dest.resolve():
        raise CommandError("artifact and destination are the same file")
    if dest.suffix.lower() == ".exe" and artifact.suffix.lower() != ".exe":
        raise CommandError(
            "refusing to overlay a Windows Zed.exe with a non-.exe artifact. "
            "Run the build from Windows, or provide a Windows artifact with --artifact."
        )


def cmd_locate_artifact(args: argparse.Namespace) -> None:
    print(locate_artifact(args.release))


def cmd_install(args: argparse.Namespace) -> None:
    build = detect_zed()
    artifact = Path(args.artifact).resolve() if args.artifact else locate_artifact(args.release)
    if args.mode == "official":
        dest = official_install_path(build)
        validate_overlay_artifact(artifact, dest)
        if is_wsl() and str(dest).startswith("/mnt/c/"):
            print("warning: overlaying Windows Zed from WSL; close Zed before replacing files.", file=sys.stderr)
        installed = install_artifact(artifact, dest, build, "official")
    else:
        dest_dir = Path(args.dest).expanduser().resolve() if args.dest else default_install_dir()
        installed = install_side_by_side(artifact, dest_dir, build)
    print(f"installed: {installed}")


def cmd_update(args: argparse.Namespace) -> None:
    cmd_sync(args)
    cmd_patch(args)
    if args.no_build:
        return
    cmd_build(args)
    if args.install:
        cmd_install(args)


def main() -> int:
    parser = argparse.ArgumentParser(description="Local Japanese Zed build helper")
    subcommands = parser.add_subparsers(dest="command", required=True)

    subcommands.add_parser("detect").set_defaults(func=cmd_detect)
    subcommands.add_parser("status").set_defaults(func=cmd_status)
    subcommands.add_parser("sync").set_defaults(func=cmd_sync)
    subcommands.add_parser("patch").set_defaults(func=cmd_patch)
    subcommands.add_parser("prepare").set_defaults(func=cmd_prepare)

    build_parser = subcommands.add_parser("build")
    build_parser.add_argument("--debug", action="store_false", dest="release")
    build_parser.set_defaults(func=cmd_build, release=True)

    artifact_parser = subcommands.add_parser("locate-artifact")
    artifact_parser.add_argument("--debug", action="store_false", dest="release")
    artifact_parser.set_defaults(func=cmd_locate_artifact, release=True)

    install_parser = subcommands.add_parser("install")
    install_parser.add_argument("--artifact")
    install_parser.add_argument("--dest")
    install_parser.add_argument(
        "--mode",
        choices=["official", "side-by-side"],
        default="official",
        help="official overlays the installed Zed.exe with a backup; side-by-side copies elsewhere.",
    )
    install_parser.add_argument("--debug", action="store_false", dest="release")
    install_parser.set_defaults(func=cmd_install, release=True)

    update_parser = subcommands.add_parser("update")
    update_parser.add_argument("--debug", action="store_false", dest="release")
    update_parser.add_argument("--no-build", action="store_true")
    update_parser.add_argument("--install", action="store_true")
    update_parser.add_argument("--artifact")
    update_parser.add_argument("--dest")
    update_parser.add_argument(
        "--mode",
        choices=["official", "side-by-side"],
        default="official",
        help="install target used with --install.",
    )
    update_parser.set_defaults(func=cmd_update, release=True)

    args = parser.parse_args()
    try:
        args.func(args)
    except CommandError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
