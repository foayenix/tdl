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

# Write the database out as text. `dump/ledger.sql` is what gets committed —
# the .db is binary and never does (BUILD.md §4).
#
# Not `sqlite3 ledger.sqlite .dump`: that emits tables alphabetically, which
# cannot restore this schema (a claim table lands before `monograph` exists and
# both the foreign keys and the sourcing triggers fail), and it has no answer
# for the FTS5 shadow tables. See STATE.md, sessions 06 and 10.
dump db="~/Documents/ledger.sqlite":
    {{py}} -m ledger --db {{db}} dump --to dump/ledger.sql
    git add dump/ledger.sql schema/

# Rebuild a database from the committed dump.
restore db out="/tmp/ledger-restored.sqlite":
    {{py}} -m ledger --db {{out}} restore --from {{db}} --force

# Point git at .githooks, so the pre-commit hook keeps the dump current.
hooks:
    git config core.hooksPath .githooks
    @echo "core.hooksPath = .githooks"
