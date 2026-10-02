"""Phase7 browser fixture: attested disposable PostgreSQL and fake email only."""

import sys

from phase05_browser_fixture import create_browser_app
from phase05_browser_fixture import main as phase05_main
from phase06_browser_fixture import clean

__all__ = ["create_browser_app"]

if __name__ == "__main__":
    try:
        if len(sys.argv) == 2 and sys.argv[1] == "clean":
            clean()
        else:
            phase05_main()
    except Exception:  # noqa: BLE001 -- no sensitive fixture traceback
        print("Controlled phase7 fixture failed; sensitive diagnostics suppressed", file=sys.stderr)
        raise SystemExit(1) from None
