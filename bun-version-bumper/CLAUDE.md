# bun-version-bumper

## Overview

A Python CLI tool that batch-updates Bun version references across `package.json` files in subdirectories. Managed with `uv`.

## Project structure

```plaintext
main.py          # Entry point and all application logic
test_main.py     # pytest test suite (21 tests)
pyproject.toml   # uv project config, dependencies, script entry point
package.json     # Example package.json for reference (not processed by the tool)
```

## Key design decisions

- **Single-file script** — all logic lives in `main.py`. No package directory; the script entry point is `main:main`.
- **One-level-deep scanning** — only `<root>/<subdir>/package.json` files are targeted, not recursive. Hidden directories (`.git`, `.venv`) are skipped.
- **Semver prefix preservation** — uses regex `^([^\d]*)` to capture any prefix before the version digits, so `^`, `~`, `>=`, and bare versions all work without a hardcoded whitelist.
- **JSON round-trip** — files are parsed with `json.loads` and written with `json.dumps(indent=2)`. This guarantees valid JSON output but may reorder keys or normalise whitespace.
- **Trailing newline preservation** — if the original file ended with `\n`, the output does too.

## Commands

```bash
uv sync              # Install dependencies
uv run main.py       # Run the tool (auto-fetches latest Bun version)
uv run pytest -v     # Run all tests
```

## Dependencies

- **Runtime**: `httpx` — for fetching the latest Bun release from the GitHub API.
- **Dev**: `pytest` — test runner.

## Three update targets

The tool looks for these fields in each `package.json`:

1. `engines.bun` — semver range (e.g. `"^1.3.10"`)
2. `packageManager` — exact version after `bun@` (e.g. `"bun@1.3.10"`)
3. `devDependencies.@types/bun` — semver range (e.g. `"^1.3.10"`)

All three are optional. Non-Bun `packageManager` values (e.g. `pnpm@9.0.0`) are ignored.
