# PyInstaller spec for the `ledger` sidecar.
#
# The frozen binary ships inside the app so enrichment works on a machine with
# no Python (BUILD.md §3). It carries the schema because Python owns migrations
# and Rust never does one.

block_cipher = None

a = Analysis(
    ["scripts/ledger_entry.py"],
    pathex=["."],
    binaries=[],
    # The migrations, read at runtime by `ledger migrate`.
    datas=[("schema", "schema")],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    # stdlib only (BUILD.md §3), so nothing here is a dependency of the CLI.
    excludes=["tkinter", "unittest", "pydoc", "pytest", "PyInstaller"],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="ledger",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    # Sign the collected binaries ad-hoc, so the Python framework this unpacks
    # at run time and the process unpacking it carry the same (absent) Team ID.
    # Ignored off macOS.
    codesign_identity="-",
    entitlements_file="entitlements.plist",
)
