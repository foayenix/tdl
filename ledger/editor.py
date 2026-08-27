"""Handing a block of text to `$EDITOR` and reading back what came out."""

from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
from pathlib import Path


def edit(text: str, *, suffix: str = ".md") -> str | None:
    """Open `text` in `$EDITOR`. Returns the edited text, or None if unchanged."""
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "vi"

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / f"ledger{suffix}"
        path.write_text(text)

        subprocess.run([*shlex.split(editor), str(path)], check=True)

        edited = path.read_text()

    return None if edited == text else edited
