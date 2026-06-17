from __future__ import annotations

import math
from pathlib import Path


def build_mv_prompt(song_title: str, duration_seconds: float, lyrics: list[str]) -> str:
    storyboard_count = max(1, math.ceil(duration_seconds / 5))
    lyric_mood = summarize_lyric_mood(lyrics)

    sections = [
        "MASTER CHARACTER",
        (
            "A cinematic lead performer with expressive eyes, modern minimalist styling, "
            "and a calm emotional presence, standing in a dramatic music video world. "
            f"The visual mood is {lyric_mood}. Ultra detailed, cinematic lighting, "
            "4K, 9:16 vertical format."
        ),
        "",
    ]

    for number in range(1, storyboard_count + 1):
        sections.extend(
            [
                f"STORYBOARD {number}",
                build_storyboard_line(number, storyboard_count, song_title, lyric_mood),
                "",
            ]
        )

    return "\n".join(sections).rstrip() + "\n"


def summarize_lyric_mood(lyrics: list[str]) -> str:
    sample = " ".join(lyrics[:8]).lower()
    sad_words = ("tears", "cry", "alone", "lost", "goodbye", "sad")
    hopeful_words = ("dream", "light", "hope", "fly", "sun", "future")

    if any(word in sample for word in sad_words):
        return "melancholic, intimate, and poetic"
    if any(word in sample for word in hopeful_words):
        return "hopeful, luminous, and emotionally uplifting"
    return "emotional, cinematic, and atmospheric"


def build_storyboard_line(number: int, total: int, song_title: str, mood: str) -> str:
    progress = number / total

    if progress < 0.25:
        scene = "an opening close-up with soft rim light and slow camera movement"
    elif progress < 0.5:
        scene = "a wider urban night scene with reflective surfaces and floating particles"
    elif progress < 0.75:
        scene = "an emotional performance scene with dynamic light beams and gentle motion"
    else:
        scene = "a final cinematic scene with powerful backlight and a memorable ending pose"

    return (
        f"For the song '{song_title}', create {scene}. "
        f"Keep the tone {mood}, with premium music video composition, realistic texture, "
        "cinematic depth of field, elegant color contrast, no text on screen, "
        "4K, 9:16 vertical format."
    )


def write_mv_prompt(path: Path, song_title: str, duration_seconds: float, lyrics: list[str]) -> None:
    path.write_text(build_mv_prompt(song_title, duration_seconds, lyrics), encoding="utf-8")
