#!/usr/bin/env python3
"""Stamp one version across the four files that carry it.

A release is a tag, and everything in the bundle should agree with it: the
About box, the Cargo crate, the npm package, and the CLI that ships inside
the app. Left alone they drift, and a .dmg that says 0.1.0 six releases
later is worse than no version at all.

    python3 scripts/set-version.py 0.2.0
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# PEP 440 for pyproject, semver everywhere else. The overlap is what we allow.
VERSION = re.compile(r"^\d+\.\d+\.\d+$")


def set_json(path: Path, version: str) -> None:
    data = json.loads(path.read_text())
    data["version"] = version
    # npm keeps a second copy of the root version inside the lockfile, and
    # `npm ci` refuses to run when the two disagree.
    root = data.get("packages", {}).get("")
    if root is not None:
        root["version"] = version
    path.write_text(json.dumps(data, indent=2) + "\n")


def set_toml(path: Path, version: str) -> None:
    """Rewrite the version in [package] only — never a dependency's."""
    text = path.read_text()
    head, sep, rest = text.partition("\n[")
    stamped, count = re.subn(
        r'^version = "[^"]*"$', f'version = "{version}"', head, count=1, flags=re.M
    )
    if count != 1:
        raise SystemExit(f"{path}: no version line in [package]")
    path.write_text(stamped + sep + rest)


def set_lock(path: Path, version: str) -> None:
    """The [[package]] entry for this crate in Cargo.lock.

    Cargo would rewrite it on the next build anyway, but a tag should point at
    a tree that already agrees with itself.
    """
    text = path.read_text()
    stamped, count = re.subn(
        r'(\[\[package\]\]\nname = "ledger-app"\nversion = )"[^"]*"',
        rf'\g<1>"{version}"',
        text,
        count=1,
    )
    if count != 1:
        raise SystemExit(f"{path}: no ledger-app entry")
    path.write_text(stamped)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2

    version = sys.argv[1].removeprefix("v")
    if not VERSION.match(version):
        print(f"not a version: {version} (want MAJOR.MINOR.PATCH)", file=sys.stderr)
        return 2

    set_json(ROOT / "src-tauri/tauri.conf.json", version)
    set_json(ROOT / "package.json", version)
    set_json(ROOT / "package-lock.json", version)
    set_toml(ROOT / "src-tauri/Cargo.toml", version)
    set_toml(ROOT / "pyproject.toml", version)
    set_lock(ROOT / "src-tauri/Cargo.lock", version)

    print(f"stamped {version}")
    print("  src-tauri/tauri.conf.json   the About box and the bundle")
    print("  src-tauri/Cargo.toml        the crate, and Cargo.lock")
    print("  package.json                the frontend, and its lockfile")
    print("  pyproject.toml              the CLI inside the app")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
