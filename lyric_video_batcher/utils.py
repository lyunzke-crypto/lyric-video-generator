from __future__ import annotations

import shutil
from pathlib import Path


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def require_executable(name: str) -> str:
    executable = shutil.which(name)
    if not executable:
        raise RuntimeError(
            f"Required executable '{name}' was not found in PATH. "
            "Install FFmpeg and reopen your terminal."
        )
    return executable


def read_text_lines(path: Path) -> list[str]:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            text = path.read_text(encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = path.read_text(encoding="utf-8", errors="replace")

    return [line.strip() for line in text.splitlines() if line.strip()]


def safe_int_seconds(seconds: float) -> int:
    return max(1, int(round(seconds)))
