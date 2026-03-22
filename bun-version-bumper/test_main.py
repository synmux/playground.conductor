"""Tests for the Bun version updater."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from main import (
    apply_changes,
    compute_changes,
    find_package_json_files,
    preserve_semver_prefix,
    update_package_json,
)


class TestPreserveSemverPrefix:
    """Test that semver range prefixes are preserved correctly."""

    def test_caret_prefix(self) -> None:
        assert preserve_semver_prefix("^1.3.10", "1.4.0") == "^1.4.0"

    def test_tilde_prefix(self) -> None:
        assert preserve_semver_prefix("~1.1.0", "1.3.11") == "~1.3.11"

    def test_gte_prefix(self) -> None:
        assert preserve_semver_prefix(">=2.0.0", "3.0.0") == ">=3.0.0"

    def test_no_prefix(self) -> None:
        assert preserve_semver_prefix("1.3.10", "1.4.0") == "1.4.0"

    def test_empty_string(self) -> None:
        assert preserve_semver_prefix("", "1.0.0") == "1.0.0"


class TestComputeChanges:
    """Test change detection across all three Bun fields."""

    def test_all_three_fields_present(self) -> None:
        data = {
            "engines": {"bun": "^1.3.10"},
            "packageManager": "bun@1.3.10",
            "devDependencies": {"@types/bun": "^1.3.10"},
        }
        changes = compute_changes(data, "1.3.11")
        assert len(changes) == 3
        assert changes[0] == ("engines.bun", "^1.3.10", "^1.3.11")
        assert changes[1] == ("packageManager", "bun@1.3.10", "bun@1.3.11")
        assert changes[2] == ("devDependencies.@types/bun", "^1.3.10", "^1.3.11")

    def test_only_package_manager(self) -> None:
        data = {"packageManager": "bun@1.2.0"}
        changes = compute_changes(data, "1.3.11")
        assert len(changes) == 1
        assert changes[0] == ("packageManager", "bun@1.2.0", "bun@1.3.11")

    def test_only_types_bun(self) -> None:
        data = {"devDependencies": {"@types/bun": "~1.1.0", "vitest": "^2.0.0"}}
        changes = compute_changes(data, "1.3.11")
        assert len(changes) == 1
        assert changes[0] == ("devDependencies.@types/bun", "~1.1.0", "~1.3.11")

    def test_no_bun_fields(self) -> None:
        data = {"name": "no-bun", "dependencies": {"vue": "^3.5.0"}}
        changes = compute_changes(data, "1.3.11")
        assert len(changes) == 0

    def test_already_up_to_date(self) -> None:
        data = {
            "engines": {"bun": "^1.3.11"},
            "packageManager": "bun@1.3.11",
            "devDependencies": {"@types/bun": "^1.3.11"},
        }
        changes = compute_changes(data, "1.3.11")
        assert len(changes) == 0

    def test_non_bun_package_manager_ignored(self) -> None:
        data = {"packageManager": "pnpm@9.0.0"}
        changes = compute_changes(data, "1.3.11")
        assert len(changes) == 0

    def test_engines_without_bun(self) -> None:
        data = {"engines": {"node": "^22.0.0"}}
        changes = compute_changes(data, "1.3.11")
        assert len(changes) == 0


class TestApplyChanges:
    """Test that changes are applied in-place correctly."""

    def test_applies_all_changes(self) -> None:
        data = {
            "engines": {"bun": "^1.3.10", "node": "^24.0.0"},
            "packageManager": "bun@1.3.10",
            "devDependencies": {"@types/bun": "^1.3.10"},
        }
        changes = [
            ("engines.bun", "^1.3.10", "^1.3.11"),
            ("packageManager", "bun@1.3.10", "bun@1.3.11"),
            ("devDependencies.@types/bun", "^1.3.10", "^1.3.11"),
        ]
        apply_changes(data, changes)
        assert data["engines"]["bun"] == "^1.3.11"
        assert data["engines"]["node"] == "^24.0.0"  # untouched
        assert data["packageManager"] == "bun@1.3.11"
        assert data["devDependencies"]["@types/bun"] == "^1.3.11"


class TestUpdatePackageJson:
    """Integration test for reading, updating, and writing package.json files."""

    def test_updates_file_on_disk(self, tmp_path: Path) -> None:
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({
            "name": "test",
            "engines": {"bun": "^1.2.0"},
            "packageManager": "bun@1.2.0",
        }, indent=2) + "\n")

        changes = update_package_json(pkg, "1.3.11")
        assert len(changes) == 2

        result = json.loads(pkg.read_text())
        assert result["engines"]["bun"] == "^1.3.11"
        assert result["packageManager"] == "bun@1.3.11"

    def test_dry_run_does_not_modify(self, tmp_path: Path) -> None:
        original = json.dumps({"packageManager": "bun@1.2.0"}, indent=2) + "\n"
        pkg = tmp_path / "package.json"
        pkg.write_text(original)

        changes = update_package_json(pkg, "1.3.11", dry_run=True)
        assert len(changes) == 1
        assert "(dry run)" in changes[0]
        assert pkg.read_text() == original  # file unchanged

    def test_preserves_trailing_newline(self, tmp_path: Path) -> None:
        pkg = tmp_path / "package.json"
        pkg.write_text('{"packageManager": "bun@1.0.0"}\n')
        update_package_json(pkg, "1.3.11")
        assert pkg.read_text().endswith("\n")

    def test_no_trailing_newline_preserved(self, tmp_path: Path) -> None:
        pkg = tmp_path / "package.json"
        pkg.write_text('{"packageManager": "bun@1.0.0"}')
        update_package_json(pkg, "1.3.11")
        assert not pkg.read_text().endswith("\n")


class TestFindPackageJsonFiles:
    """Test subdirectory scanning logic."""

    def test_finds_one_level_deep(self, tmp_path: Path) -> None:
        sub = tmp_path / "project"
        sub.mkdir()
        (sub / "package.json").write_text("{}")
        results = find_package_json_files(tmp_path)
        assert len(results) == 1
        assert results[0] == sub / "package.json"

    def test_skips_hidden_directories(self, tmp_path: Path) -> None:
        hidden = tmp_path / ".hidden"
        hidden.mkdir()
        (hidden / "package.json").write_text("{}")
        results = find_package_json_files(tmp_path)
        assert len(results) == 0

    def test_skips_nested_subdirectories(self, tmp_path: Path) -> None:
        deep = tmp_path / "a" / "b"
        deep.mkdir(parents=True)
        (deep / "package.json").write_text("{}")
        # a/package.json doesn't exist, a/b/package.json should not be found
        results = find_package_json_files(tmp_path)
        assert len(results) == 0

    def test_returns_sorted(self, tmp_path: Path) -> None:
        for name in ["zeta", "alpha", "mu"]:
            sub = tmp_path / name
            sub.mkdir()
            (sub / "package.json").write_text("{}")
        results = find_package_json_files(tmp_path)
        assert [path.parent.name for path in results] == ["alpha", "mu", "zeta"]
