# bun-version-bumper

Batch-update Bun versions across `package.json` files in a monorepo or multi-project directory.

## What it does

Scans subdirectories one level deep for `package.json` files and updates up to three Bun-related fields in each:

| Field | Example value | Updated to |
|---|---|---|
| `engines.bun` | `"^1.3.10"` | `"^1.3.11"` |
| `packageManager` | `"bun@1.3.10"` | `"bun@1.3.11"` |
| `devDependencies.@types/bun` | `"~1.3.10"` | `"~1.3.11"` |

Any of the three fields may be absent — only present fields are updated. Semver range prefixes (`^`, `~`, `>=`, etc.) are preserved.

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager

## Installation

```bash
uv sync
```

## Usage

```bash
# Auto-fetch the latest Bun version from GitHub and apply
uv run main.py

# Specify an explicit version
uv run main.py 1.3.11

# Preview changes without writing (dry run)
uv run main.py --dry-run

# Scan a different root directory
uv run main.py --root /path/to/monorepo

# Combine options
uv run main.py 1.3.11 --root /path/to/monorepo --dry-run
```

### Arguments

| Argument | Required | Description |
|---|---|---|
| `version` | No | Target Bun version (e.g. `1.3.11`). If omitted, fetches the latest release from the [oven-sh/bun](https://github.com/oven-sh/bun) GitHub repository. |
| `--root PATH` | No | Root directory to scan (default: current working directory). |
| `--dry-run` | No | Show what would change without modifying any files. |

### Example output

```plaintext
No version specified — fetching latest from GitHub...
Latest Bun version: 1.3.11

Scanning 3 package.json file(s) under /path/to/monorepo
Target version: 1.3.11

project-a/package.json:
  engines.bun: ^1.3.10 -> ^1.3.11
  packageManager: bun@1.3.10 -> bun@1.3.11
  devDependencies.@types/bun: ^1.3.10 -> ^1.3.11
project-b/package.json:
  packageManager: bun@1.2.0 -> bun@1.3.11
project-c/package.json: already up to date

4 change(s) made across 3 file(s).
```

## Testing

```bash
uv run pytest -v
```

21 tests cover semver prefix preservation, change detection, file I/O, dry-run safety, and directory scanning logic.

## How it works

1. **Version resolution** — if no version argument is provided, queries the GitHub API (`GET /repos/oven-sh/bun/releases/latest`) and strips the `bun-v` prefix from the release tag.
2. **Discovery** — iterates direct (non-hidden) subdirectories of the root, collecting any that contain a `package.json`.
3. **Change detection** — for each file, checks the three Bun-related fields and computes updates, preserving existing semver range prefixes.
4. **Application** — writes updated JSON back to disk (round-tripped through `json.dumps` with 2-space indent), preserving trailing newline conventions. Skipped entirely in `--dry-run` mode.

The script is idempotent — running it again with the same version reports "already up to date" and makes no changes.
