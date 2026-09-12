from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

APP_NAME = "JAR Vietnamese Translator"


def portable_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def main() -> int:
    root = portable_root()
    app_root = root / "app"
    bootstrap = app_root / "bootstrap.py"
    if not bootstrap.is_file():
        raise RuntimeError(
            f"Không tìm thấy module ứng dụng: {bootstrap}\n"
            "Vui lòng giữ nguyên thư mục 'app' cạnh file EXE."
        )
    os.environ.setdefault("JVT_PORTABLE_ROOT", str(root))
    sys.path.insert(0, str(app_root))
    runpy.run_path(str(bootstrap), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
