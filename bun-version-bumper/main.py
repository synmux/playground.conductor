"""Update Bun versions across package.json files in subdirectories.

Targets three possible Bun references in each package.json:
  - engines.bun              (semver range, e.g. "^1.3.10")
  - packageManager           (exact, e.g. "bun@1.3.10")
  - devDependencies.@types/bun (semver range, e.g. "^1.3.10")

By default, fetches the latest Bun release from GitHub. Pass a version
argument to override (e.g. `uv run main.py 1.3.11`).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import httpx

GITHUB_LATEST_RELEASE_URL = "https://api.github.com/repos/oven-sh/bun/releases/latest"
BUN_TAG_PATTERN = re.compile(r"^bun-v(.+)$")


def fetch_latest_bun_version() -> str:
    """Fetch the latest Bun version from GitHub releases."""
    response = httpx.get(
        GITHUB_LATEST_RELEASE_URL,
        headers={"Accept": "application/vnd.github+json"},
        timeout=15,
    )
    response.raise_for_status()
    tag_name: str = response.json()["tag_name"]
    match = BUN_TAG_PATTERN.match(tag_name)
    if not match:
        print(f"Error: unexpected tag format '{tag_name}'", file=sys.stderr)
        sys.exit(1)
    return match.group(1)


def preserve_semver_prefix(existing_value: str, new_version: str) -> str:
    """Keep whatever semver range prefix (^, ~, >=, etc.) the existing value uses.

    If the existing value has no recognisable prefix, return the bare version.
    """
    prefix_match = re.match(r"^([^\d]*)", existing_value)
    prefix = prefix_match.group(1) if prefix_match else ""
    return f"{prefix}{new_version}"


def compute_changes(data: dict, version: str) -> list[tuple[str, str, str]]:
    """Compute (field, old_value, new_value) tuples for Bun-related fields."""
    changes: list[tuple[str, str, str]] = []

    # 1. engines.bun
    engines = data.get("engines")
    if isinstance(engines, dict) and "bun" in engines:
        old_value = engines["bun"]
        new_value = preserve_semver_prefix(old_value, version)
        if old_value != new_value:
            changes.append(("engines.bun", old_value, new_value))

    # 2. packageManager
    package_manager = data.get("packageManager")
    if isinstance(package_manager, str) and package_manager.startswith("bun@"):
        new_value = f"bun@{version}"
        if package_manager != new_value:
            changes.append(("packageManager", package_manager, new_value))

    # 3. devDependencies.@types/bun
    dev_deps = data.get("devDependencies")
    if isinstance(dev_deps, dict) and "@types/bun" in dev_deps:
        old_value = dev_deps["@types/bun"]
        new_value = preserve_semver_prefix(old_value, version)
        if old_value != new_value:
            changes.append(("devDependencies.@types/bun", old_value, new_value))

    return changes


def apply_changes(data: dict, changes: list[tuple[str, str, str]]) -> None:
    """Mutate data in-place to apply the computed changes."""
    for field, _old, new in changes:
        if field == "engines.bun":
            data["engines"]["bun"] = new
        elif field == "packageManager":
            data["packageManager"] = new
        elif field == "devDependencies.@types/bun":
            data["devDependencies"]["@types/bun"] = new


def update_package_json(filepath: Path, version: str, *, dry_run: bool = False) -> list[str]:
    """Update Bun-related fields in a single package.json. Returns human-readable change lines."""
    text = filepath.read_text(encoding="utf-8")
    data = json.loads(text)
    changes = compute_changes(data, version)

    if changes and not dry_run:
        apply_changes(data, changes)
        trailing_newline = text.endswith("\n")
        output = json.dumps(data, indent=2, ensure_ascii=False)
        if trailing_newline:
            output += "\n"
        filepath.write_text(output, encoding="utf-8")

    suffix = " (dry run)" if dry_run else ""
    return [f"  {field}: {old} -> {new}{suffix}" for field, old, new in changes]


def find_package_json_files(root: Path) -> list[Path]:
    """Find package.json files exactly one subdirectory deep from root."""
    results: list[Path] = []
    for child in sorted(root.iterdir()):
        if child.is_dir() and not child.name.startswith("."):
            candidate = child / "package.json"
            if candidate.is_file():
                results.append(candidate)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Update Bun versions in package.json files across subdirectories.",
    )
    parser.add_argument(
        "version",
        nargs="?",
        default=None,
        help="Target Bun version (e.g. 1.3.11). Fetches latest from GitHub if omitted.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Root directory to scan for subdirectories (default: current directory).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing files.",
    )
    args = parser.parse_args()

    # Resolve the target version
    if args.version:
        version = args.version.lstrip("v")
    else:
        print("No version specified — fetching latest from GitHub...")
        version = fetch_latest_bun_version()
        print(f"Latest Bun version: {version}")

    root: Path = args.root.resolve()
    package_files = find_package_json_files(root)

    if not package_files:
        print(f"No package.json files found in subdirectories of {root}")
        sys.exit(0)

    print(f"\nScanning {len(package_files)} package.json file(s) under {root}")
    print(f"Target version: {version}\n")

    total_changes = 0
    for filepath in package_files:
        relative_path = filepath.relative_to(root)
        changes = update_package_json(filepath, version, dry_run=args.dry_run)
        if changes:
            print(f"{relative_path}:")
            for change in changes:
                print(change)
            total_changes += len(changes)
        else:
            print(f"{relative_path}: already up to date")

    action = "would be made" if args.dry_run else "made"
    print(f"\n{total_changes} change(s) {action} across {len(package_files)} file(s).")


if __name__ == "__main__":
    main()
