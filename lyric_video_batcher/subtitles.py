from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


LRC_TIME_RE = re.compile(r"\[(\d{1,2}):(\d{2})(?:[.:](\d{1,3}))?\]")


@dataclass(frozen=True)
class LyricCue:
    start: float
    end: float
    text: str
    english_text: str = ""


def load_lyric_cues(path: Path, duration_seconds: float) -> list[LyricCue]:
    if path.suffix.lower() == ".lrc":
        cues = load_lrc_cues(path, duration_seconds)
        if cues:
            return cues

    lines = read_lyric_lines(path)
    return build_evenly_timed_cues(lines, duration_seconds)


def read_lyric_lines(path: Path) -> list[str]:
    text = read_text(path)
    return [line.strip() for line in text.splitlines() if line.strip()]


def read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def load_lrc_cues(path: Path, duration_seconds: float) -> list[LyricCue]:
    timed_lines: list[tuple[float, str]] = []

    for raw_line in read_text(path).splitlines():
        timestamps = list(LRC_TIME_RE.finditer(raw_line))
        if not timestamps:
            continue

        text = LRC_TIME_RE.sub("", raw_line).strip()
        if not text:
            continue

        for timestamp in timestamps:
            timed_lines.append((parse_lrc_time(timestamp), text))

    timed_lines.sort(key=lambda item: item[0])
    cues: list[LyricCue] = []

    for index, (start, text) in enumerate(timed_lines):
        if start >= duration_seconds:
            continue
        if index + 1 < len(timed_lines):
            end = min(timed_lines[index + 1][0], duration_seconds)
        else:
            end = duration_seconds
        if end > start:
            cues.append(LyricCue(start=start, end=end, text=text))

    return cues


def parse_lrc_time(match: re.Match[str]) -> float:
    minutes = int(match.group(1))
    seconds = int(match.group(2))
    fraction = match.group(3) or "0"
    if len(fraction) == 1:
        milliseconds = int(fraction) * 100
    elif len(fraction) == 2:
        milliseconds = int(fraction) * 10
    else:
        milliseconds = int(fraction[:3])
    return minutes * 60 + seconds + milliseconds / 1000


def build_evenly_timed_cues(lines: list[str], duration_seconds: float) -> list[LyricCue]:
    if not lines:
        lines = [" "]

    cue_length = duration_seconds / len(lines)
    cues: list[LyricCue] = []

    for index, line in enumerate(lines):
        start = index * cue_length
        end = duration_seconds if index == len(lines) - 1 else (index + 1) * cue_length
        cues.append(LyricCue(start=start, end=end, text=line))

    return cues


def format_srt_timestamp(seconds: float) -> str:
    milliseconds_total = max(0, int(round(seconds * 1000)))
    milliseconds = milliseconds_total % 1000
    total_seconds = milliseconds_total // 1000
    secs = total_seconds % 60
    total_minutes = total_seconds // 60
    mins = total_minutes % 60
    hours = total_minutes // 60
    return f"{hours:02d}:{mins:02d}:{secs:02d},{milliseconds:03d}"


def build_srt(cues: list[LyricCue]) -> str:
    blocks: list[str] = []

    for index, cue in enumerate(cues, start=1):
        text_lines = [cue.text]
        if cue.english_text:
            text_lines.append(cue.english_text)
        blocks.append(
            "\n".join(
                [
                    str(index),
                    f"{format_srt_timestamp(cue.start)} --> {format_srt_timestamp(cue.end)}",
                    *text_lines,
                ]
            )
        )

    return "\n\n".join(blocks) + "\n"


def write_srt(path: Path, cues: list[LyricCue]) -> None:
    path.write_text(build_srt(cues), encoding="utf-8-sig")


def apply_english_translations(
    cues: list[LyricCue],
    english_path: Path,
    duration_seconds: float,
    *,
    english_uppercase: bool,
) -> list[LyricCue]:
    english_lines = load_english_lines(english_path, duration_seconds)
    translated: list[LyricCue] = []

    for index, cue in enumerate(cues):
        english_text = english_lines[index] if index < len(english_lines) else ""
        english_text = normalize_english_translation(english_text, english_uppercase)
        translated.append(
            LyricCue(
                start=cue.start,
                end=cue.end,
                text=cue.text,
                english_text=english_text,
            )
        )

    return translated


def load_english_lines(path: Path, duration_seconds: float) -> list[str]:
    if path.suffix.lower() == ".lrc":
        lrc_cues = load_lrc_cues(path, duration_seconds)
        if lrc_cues:
            return [cue.text for cue in lrc_cues]
    return read_lyric_lines(path)


def normalize_english_translation(text: str, uppercase: bool) -> str:
    normalized = " ".join(text.strip().split())
    return normalized.upper() if uppercase else normalized
