# The Deposit Ledger — see BUILD.md §7 for the definition of done.

# Python 3.12+ is required (BUILD.md §3). Prefer a local .venv when one exists,
# so a machine whose `python3` is older still runs the checks on the right one.
py := if path_exists(".venv/bin/python") == "true" { ".venv/bin/python" } else { "python3" }

default:
    @just --list

# Definition of done. Runs in the order given in BUILD.md §7.
check:
    #!/usr/bin/env bash
    set -euo pipefail
    if {{py}} -m ruff --version >/dev/null 2>&1; then
        {{py}} -m ruff check ledger/
    elif command -v ruff >/dev/null 2>&1; then
        ruff check ledger/
    fi
    {{py}} -m pytest ledger/tests -q
    # The Rust core arrives in session 12. Until src-tauri/ exists there is
    # nothing for cargo to check, so these steps are skipped rather than failed.
    if [ -d src-tauri ]; then
        cargo fmt --check --manifest-path src-tauri/Cargo.toml
        cargo clippy --manifest-path src-tauri/Cargo.toml -- -D warnings
        cargo test --manifest-path src-tauri/Cargo.toml
    fi

# Create the development virtualenv the checks run in.
venv:
    python3.12 -m venv .venv || python3 -m venv .venv
    .venv/bin/python -m pip install --quiet --upgrade pip
    .venv/bin/python -m pip install --quiet pytest ruff
