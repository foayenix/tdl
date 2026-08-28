# The Deposit Ledger — see BUILD.md §7 for the definition of done.

# Python 3.12+ is required (BUILD.md §3). Prefer a local .venv when one exists,
# so a machine whose `python3` is older still runs the checks on the right one.
py := if path_exists(".venv/bin/python") == "true" { ".venv/bin/python" } else { "python3" }

# The target triple the sidecar filename carries (BUILD.md §3).
triple := `rustc --print host-tuple 2>/dev/null || echo unknown`

# The Tauri CLI. `npx tauri` is the same binary as a global `cargo-tauri` and
# needs no separate install, so it is the default; a global one wins if present.
tauri := if `command -v cargo-tauri >/dev/null 2>&1 && echo yes || echo no` == "yes" { "cargo tauri" } else { "npx --no-install tauri" }

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
    just sidecar
    cargo fmt --check --manifest-path src-tauri/Cargo.toml
    cargo clippy --manifest-path src-tauri/Cargo.toml --all-targets -- -D warnings
    cargo test --manifest-path src-tauri/Cargo.toml
    # Not in BUILD.md §7's four commands. Added in session 12 because from
    # here on the frontend is the work, and without this nothing checks it.
    if [ -d node_modules ]; then
        npx tsc --noEmit
    fi

# Install everything a fresh clone needs.
setup: venv
    npm install
    @just sidecar
    @echo ""
    @echo "ready."
    @echo "  just dev            opens the window"
    @echo "  just check          runs the checks"
    @echo "  .venv/bin/ledger    the CLI"

# The CLI itself is stdlib only (BUILD.md §3). These three are the tools §7 and
# session 30 name — pytest and ruff for the checks, pyinstaller for the freeze —
# and none of them is imported by `ledger/`.
#
# Build the development virtualenv.
venv:
    #!/usr/bin/env bash
    set -euo pipefail
    python3.12 -m venv .venv 2>/dev/null || python3 -m venv .venv
    .venv/bin/python -m pip install --quiet --upgrade pip
    .venv/bin/python -m pip install --quiet pytest ruff pyinstaller
    # Editable, so `.venv/bin/ledger` is the CLI you are working on. It has no
    # dependencies of its own — this only puts the entry point on a path.
    .venv/bin/python -m pip install --quiet -e .
    version="$(.venv/bin/python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    case "$version" in
        3.1[2-9]|3.[2-9]*) ;;
        *) echo "warning: .venv is Python $version; BUILD.md §3 asks for 3.12+" >&2 ;;
    esac

# `cargo tauri dev` starts Vite itself (tauri.conf.json's beforeDevCommand), so
# this is the only command you need.
#
#   just dev                        against ~/Documents/ledger.sqlite
#   just dev /tmp/scratch.sqlite    against somewhere else
#
# Open the window.
dev db="":
    #!/usr/bin/env bash
    set -euo pipefail
    if ! command -v cargo-tauri >/dev/null 2>&1; then
        echo "cargo-tauri is missing. Install it once with:" >&2
        echo "    cargo install tauri-cli --version '^2'" >&2
        exit 1
    fi
    [ -d node_modules ] || { echo "run 'just setup' first" >&2; exit 1; }
    just sidecar

    database="{{db}}"
    [ -n "$database" ] || database="$HOME/Documents/ledger.sqlite"

    # The app never migrates — Python owns the schema (BUILD.md §3) — so an
    # absent ledger would open on `no ledger at …`. The justfile is allowed to
    # run the CLI, and this is the CLI doing it.
    if [ ! -f "$database" ]; then
        echo "no ledger at $database — creating one"
        {{py}} -m ledger --db "$database" migrate
        echo ""
    fi

    export LEDGER_DB="$database"
    cargo tauri dev


# Write the database out as text. `dump/ledger.sql` is what gets committed —
# the .db is binary and never does (BUILD.md §4).
#
# Not `sqlite3 ledger.sqlite .dump`: that emits tables alphabetically, which
# cannot restore this schema (a claim table lands before `monograph` exists and
# both the foreign keys and the sourcing triggers fail), and it has no answer
# for the FTS5 shadow tables. See STATE.md, sessions 06 and 10.
#
# Write the database out as text, and stage it.
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

# A development stand-in for the frozen sidecar.
#
# tauri.conf.json declares `externalBin`, so every cargo invocation needs the
# file to exist. This shim runs the CLI from source and behaves identically from
# Rust's side; `just freeze` replaces it with the real thing, and this recipe
# will not overwrite that. It lives in src-tauri/binaries/, which is gitignored.
#
# Write a development stand-in for the frozen sidecar.
sidecar:
    #!/usr/bin/env bash
    set -euo pipefail
    mkdir -p src-tauri/binaries
    target="src-tauri/binaries/ledger-{{triple}}"
    root="$(pwd)"

    # Never overwrite a real frozen binary. `check` calls this recipe, so a
    # `just check` after a `just freeze` would otherwise put the shim back and
    # `cargo tauri build` would bundle it (found in session 30).
    if [ -e "$target" ] && ! head -c 2 "$target" | grep -q '#!'; then
        echo "$target is a frozen binary; leaving it alone"
        exit 0
    fi

    # Otherwise always rewrite: the shim hard-codes paths, and a stale one
    # fails in a way that only shows up inside the running app (session 19).
    printf '#!/usr/bin/env bash\ncd %q\nexec %q -m ledger "$@"\n' "$root" "$root/{{py}}" > "$target"
    chmod +x "$target"

# Freeze the CLI into the sidecar the app ships (BUILD.md §3, session 30).
#
# The frozen binary carries schema/ because Python owns migrations and Rust
# never does one — a sidecar with no schema could not migrate either. The file
# on disk carries the target triple, which is what Tauri looks for.
#
# Freeze the CLI into the sidecar the app ships. Run this on the target machine.
freeze:
    #!/usr/bin/env bash
    set -euo pipefail
    {{py}} -m PyInstaller --clean --noconfirm \
        --distpath build/dist --workpath build/work ledger.spec
    mkdir -p src-tauri/binaries
    install -m 755 build/dist/ledger "src-tauri/binaries/ledger-{{triple}}"
    echo "froze src-tauri/binaries/ledger-{{triple}}"

# `check` runs first: a build of a red tree is not a release.
#
# Build the shippable bundle.
release: check freeze
    #!/usr/bin/env bash
    set -euo pipefail
    npm run build
    {{tauri}} build

# Stamp a version across tauri.conf.json, Cargo.toml, package.json and
# pyproject.toml, so a bundle never claims a version the tag disagrees with.
#
# Stamp a version across every file that carries one.
version v:
    @python3 scripts/set-version.py {{v}}

# Build the macOS .dmg. Runs on macOS only — see .github/workflows/release.yml,
# which runs exactly this on a runner when you push a tag.
#
# The sidecar is frozen first, so the checks run against the binary that
# ships rather than the development shim.
#
# Build the macOS .dmg. macOS only.
dmg:
    #!/usr/bin/env bash
    set -euo pipefail
    # Checked before anything is built: `freeze` and `check` take minutes, and
    # failing after them on a machine that was never going to work is rude.
    if [ "$(uname -s)" != "Darwin" ]; then
        echo "a .dmg can only be built on macOS." >&2
        echo "to build one without a Mac, push a tag:" >&2
        echo "    just tag 0.2.0 && git push origin HEAD --tags" >&2
        exit 1
    fi
    just freeze
    just check
    npm run build
    {{tauri}} build --bundles dmg
    find src-tauri/target/release/bundle/dmg -name '*.dmg' -print

# Cut a release: stamp the version, commit it, tag it, push.
#
# The tag is what the workflow watches; pushing it is what builds the .dmg.
#
# Cut a release: stamp, commit, tag.
tag v:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -n "$(git status --porcelain)" ]; then
        echo "the tree is dirty. commit first — a release should be a known tree." >&2
        exit 1
    fi
    python3 scripts/set-version.py {{v}}
    git add -A
    # The first tag of a version already stamped has nothing to commit, and
    # that is not an error — tag the commit that is already there.
    if git diff --cached --quiet; then
        echo "already at {{v}}; tagging the current commit"
    else
        git commit -m "Release v{{v}}"
    fi
    git tag -a "v{{v}}" -m "v{{v}}"
    echo ""
    echo "tagged v{{v}}. push it to build the .dmg:"
    echo "    git push origin HEAD --tags"

# Prove the sidecar runs where there is no Python at all.
verify-freeze:
    #!/usr/bin/env bash
    set -euo pipefail
    scrubbed="$(mktemp -d)/bin"
    mkdir -p "$scrubbed"
    for tool in bash ls cat rm mkdir; do ln -sf "$(command -v $tool)" "$scrubbed/$tool"; done
    if env -i PATH="$scrubbed" "$scrubbed/bash" -c 'command -v python3' >/dev/null 2>&1; then
        echo "the scrubbed PATH still has python; this proves nothing" >&2
        exit 1
    fi
    db="$(mktemp -d)/ledger.sqlite"
    env -i PATH="$scrubbed" HOME="$(dirname "$db")" ./build/dist/ledger --db "$db" migrate
    env -i PATH="$scrubbed" HOME="$(dirname "$db")" ./build/dist/ledger --db "$db" log --minutes 20
    echo "the frozen sidecar runs with no Python present"

# Check every prerequisite and say which one is missing. Nothing here changes
# anything; it only looks.
#
# Diagnose a setup that will not run.
doctor:
    #!/usr/bin/env bash
    # Deliberately not `set -e`: the point is to report every problem, not to
    # stop at the first one.
    ok=0; bad=0
    say() { printf '  %-22s %s\n' "$1" "$2"; }
    good() { say "$1" "ok — $2"; ok=$((ok+1)); }
    fail() { say "$1" "MISSING — $2"; bad=$((bad+1)); }

    echo "tools"
    command -v cargo    >/dev/null 2>&1 && good cargo "$(cargo --version 2>/dev/null | cut -d' ' -f2)" \
        || fail cargo "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
    command -v cargo-tauri >/dev/null 2>&1 && good cargo-tauri "$(cargo tauri --version 2>/dev/null)" \
        || fail cargo-tauri "cargo install tauri-cli --version '^2'"
    command -v node     >/dev/null 2>&1 && good node "$(node --version)" \
        || fail node "brew install node"
    command -v npm      >/dev/null 2>&1 && good npm "$(npm --version)" \
        || fail npm "comes with node"

    if [ -x .venv/bin/python ]; then
        good venv "$(.venv/bin/python --version 2>&1 | cut -d' ' -f2)"
    else
        fail venv "just setup"
    fi

    echo ""
    echo "this checkout"
    [ -d node_modules ] && good node_modules "installed" || fail node_modules "just setup"
    [ -x .venv/bin/ledger ] && good "ledger CLI" ".venv/bin/ledger" || fail "ledger CLI" "just setup"

    triple="$(rustc --print host-tuple 2>/dev/null || echo unknown)"
    if [ -e "src-tauri/binaries/ledger-$triple" ]; then
        good sidecar "ledger-$triple"
    else
        fail sidecar "just sidecar   (needed by every cargo command)"
    fi

    echo ""
    echo "the ledger"
    database="${LEDGER_DB:-$HOME/Documents/ledger.sqlite}"
    if [ -f "$database" ]; then
        version="$({{py}} -c "import sqlite3,sys; print(sqlite3.connect(sys.argv[1]).execute('PRAGMA user_version').fetchone()[0])" "$database" 2>/dev/null || echo '?')"
        good "$(basename "$database")" "schema v$version at $database"
    else
        say "$(basename "$database")" "absent — 'just dev' will create it"
    fi

    echo ""
    echo "runtime"
    if command -v lsof >/dev/null 2>&1 && lsof -i :5173 >/dev/null 2>&1; then
        say "port 5173" "IN USE — something else has it; 'just dev' will fail"
        bad=$((bad+1))
    else
        good "port 5173" "free"
    fi

    echo ""
    if [ "$bad" -eq 0 ]; then
        echo "nothing missing. 'just dev' should open a window."
        echo "the first run compiles Tauri and takes several minutes with little output."
    else
        echo "$bad thing(s) to fix above."
    fi

# Regenerate the browser preview's answer set from a database.
#
# preview_dump calls the same library functions the window calls, so the
# preview cannot drift from the app: what it shows is what the real queries
# returned. Point it at a scratch ledger, never a real one — the answers end
# up in a file that gets published.
#
# Regenerate the browser preview's answer set.
preview-data db="/tmp/demo.sqlite":
    cargo run --quiet --manifest-path src-tauri/Cargo.toml --example preview_dump -- {{db}} > preview/data.json
    @echo "preview/data.json  $(wc -c < preview/data.json) bytes"

# Build the read-only browser preview as one self-contained HTML file.
#
# Same screens, same CSS, same modules as the app; `./invoke` resolves to a
# stub that answers from preview/data.json instead of calling Rust, and every
# write is refused. See src/preview.ts.
#
# Build the read-only browser preview as one HTML file.
preview:
    #!/usr/bin/env bash
    set -euo pipefail
    PREVIEW=1 npx vite build
    node scripts/inline-preview.mjs
    echo "dist/preview.html  $(wc -c < dist/preview.html) bytes"
