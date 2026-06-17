from __future__ import annotations

from pathlib import Path
from typing import Optional


def get_mp3_duration_seconds(path: Path) -> float:
    try:
        from mutagen.mp3 import MP3
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The Python package 'mutagen' is required to read MP3 duration. "
            "Install it with: pip install -r requirements.txt"
        ) from exc

    audio = MP3(path)
    duration = float(audio.info.length)
    if duration <= 0:
        raise ValueError(f"MP3 duration is invalid: {path}")
    return duration


def find_song_pairs(input_dir: Path) -> list[tuple[Path, Path]]:
    mp3_files = sorted(input_dir.glob("*.mp3"))
    pairs: list[tuple[Path, Path]] = []

    for mp3_path in mp3_files:
        lyric_path = find_lyric_file(mp3_path)
        if lyric_path.exists():
            pairs.append((mp3_path, lyric_path))

    return pairs


def find_lyric_file(mp3_path: Path) -> Path:
    lrc_path = mp3_path.with_suffix(".lrc")
    if lrc_path.exists():
        return lrc_path
    return mp3_path.with_suffix(".txt")


def find_english_lyric_file(mp3_path: Path) -> Optional[Path]:
    candidates = [
        mp3_path.with_name(f"{mp3_path.stem}.en.txt"),
        mp3_path.with_name(f"{mp3_path.stem}_en.txt"),
        mp3_path.with_name(f"{mp3_path.stem}.en.lrc"),
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None
