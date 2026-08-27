"""Entry point for the frozen sidecar.

`ledger/__main__.py` uses a relative import, which is right for
`python -m ledger` and wrong for PyInstaller: the frozen script runs as
`__main__` with no package around it. This module imports absolutely.
"""

import sys

from ledger.cli import main

if __name__ == "__main__":
    sys.exit(main())
