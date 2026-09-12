"""Development-compatible entry point.

Portable releases use launcher.py. Keeping app.py allows existing developer scripts/tests
to continue working without changing the engine/UI contract.
"""
from launcher import main

if __name__ == "__main__":
    raise SystemExit(main())
