from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from .media import find_english_lyric_file, find_song_pairs, get_mp3_duration_seconds
from .prompt import write_mv_prompt
from .subtitles import apply_english_translations, load_lyric_cues, write_srt
from .utils import ensure_directory, require_executable
from .video import choose_background_video, render_lyric_video


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch generate 9:16 lyric videos from matching MP3 and TXT files."
    )
    parser.add_argument("--input", required=True, type=Path, help="Folder containing .mp3 and .txt files.")
    parser.add_argument("--output", required=True, type=Path, help="Folder for generated videos.")
    parser.add_argument("--background", choices=("black", "gradient"), default="black")
    parser.add_argument("--background-root", type=Path, help="Root folder of the background video library.")
    parser.add_argument("--background-folder", type=Path, help="Specific background category folder.")
    parser.add_argument("--background-video", type=Path, help="Specific background video file.")
    parser.add_argument("--font", default="auto", help="Subtitle font name or font file path.")
    parser.add_argument("--font-size", type=int, default=72)
    parser.add_argument("--zoom-start", type=float, default=0.25)
    parser.add_argument("--zoom-end", type=float, default=1.8)
    parser.add_argument("--text-x", type=float, default=0.08)
    parser.add_argument("--text-y", type=float, default=0.25)
    parser.add_argument("--lyric-offset", type=float, default=0.0)
    parser.add_argument("--bilingual", action="store_true", help="Enable bilingual lyric mode.")
    parser.add_argument("--english-lyrics", type=Path, help="Manually specify English lyric translation file.")
    parser.add_argument("--english-scale", type=float, default=0.7)
    parser.add_argument("--english-color", default="#D8D8D8")
    parser.add_argument("--english-uppercase", dest="english_uppercase", action="store_true", default=True)
    parser.add_argument("--no-english-uppercase", dest="english_uppercase", action="store_false")
    parser.add_argument(
        "--animation-style",
        choices=("cinematic", "tiktok", "trailer"),
        default="cinematic",
    )
    parser.add_argument("--stroke-width", type=int, default=1)
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing MP4 files.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    validate_args(args)
    input_dir = args.input.resolve()
    output_dir = ensure_directory(args.output.resolve())

    if not input_dir.exists() or not input_dir.is_dir():
        raise SystemExit(f"Input folder does not exist: {input_dir}")

    require_executable("ffmpeg")
    pairs = find_song_pairs(input_dir)

    if not pairs:
        raise SystemExit(f"No matching .mp3/.txt pairs found in: {input_dir}")

    print(f"Found {len(pairs)} song pair(s).")

    for mp3_path, lyric_path in pairs:
        process_song(
            mp3_path=mp3_path,
            lyric_path=lyric_path,
            output_root=output_dir,
            background=args.background,
            background_root=args.background_root,
            background_folder=args.background_folder,
            background_video=args.background_video,
            font=args.font,
            font_size=args.font_size,
            zoom_start=args.zoom_start,
            zoom_end=args.zoom_end,
            text_x=args.text_x,
            text_y=args.text_y,
            lyric_offset=args.lyric_offset,
            bilingual=args.bilingual,
            english_lyrics=args.english_lyrics,
            english_scale=args.english_scale,
            english_color=args.english_color,
            english_uppercase=args.english_uppercase,
            animation_style=args.animation_style,
            stroke_width=args.stroke_width,
            width=args.width,
            height=args.height,
            fps=args.fps,
            overwrite=args.overwrite,
        )

    print("Done.")
    return 0


def validate_args(args: argparse.Namespace) -> None:
    if args.zoom_start <= 0:
        raise SystemExit("--zoom-start must be greater than 0.")
    if args.zoom_end <= 0:
        raise SystemExit("--zoom-end must be greater than 0.")
    if args.zoom_end <= args.zoom_start:
        raise SystemExit("--zoom-end must be greater than --zoom-start.")
    if not 0 <= args.text_x <= 1:
        raise SystemExit("--text-x must be between 0 and 1.")
    if not 0 <= args.text_y <= 1:
        raise SystemExit("--text-y must be between 0 and 1.")
    if args.stroke_width < 0:
        raise SystemExit("--stroke-width must be 0 or greater.")
    if args.width <= 0 or args.height <= 0:
        raise SystemExit("--width and --height must be greater than 0.")
    if args.fps <= 0:
        raise SystemExit("--fps must be greater than 0.")
    if args.english_scale <= 0:
        raise SystemExit("--english-scale must be greater than 0.")
    validate_hex_color(args.english_color)


def validate_hex_color(value: str) -> None:
    cleaned = value.strip().lstrip("#")
    if len(cleaned) != 6:
        raise SystemExit("--english-color must be a hex color like #D8D8D8.")
    try:
        int(cleaned, 16)
    except ValueError as exc:
        raise SystemExit("--english-color must be a hex color like #D8D8D8.") from exc


def process_song(
    *,
    mp3_path: Path,
    lyric_path: Path,
    output_root: Path,
    background: str,
    background_root: Optional[Path],
    background_folder: Optional[Path],
    background_video: Optional[Path],
    font: str,
    font_size: int,
    zoom_start: float,
    zoom_end: float,
    text_x: float,
    text_y: float,
    lyric_offset: float,
    bilingual: bool,
    english_lyrics: Optional[Path],
    english_scale: float,
    english_color: str,
    english_uppercase: bool,
    animation_style: str,
    stroke_width: int,
    width: int,
    height: int,
    fps: int,
    overwrite: bool,
) -> None:
    song_name = mp3_path.stem
    song_output_dir = ensure_directory(output_root / song_name)
    srt_path = song_output_dir / f"{song_name}_lyrics.srt"
    legacy_srt_path = song_output_dir / f"{song_name}.srt"
    video_path = song_output_dir / f"{song_name}.mp4"
    prompt_path = song_output_dir / f"{song_name}_MV_prompt.txt"

    print(f"Processing: {song_name}")

    duration = get_mp3_duration_seconds(mp3_path)
    cues = load_lyric_cues(lyric_path, duration)
    english_path = english_lyrics.resolve() if english_lyrics else find_english_lyric_file(mp3_path)
    if english_path and not english_path.exists():
        raise FileNotFoundError(f"English lyric file does not exist: {english_path}")
    if english_path:
        cues = apply_english_translations(
            cues,
            english_path,
            duration,
            english_uppercase=english_uppercase,
        )
    elif bilingual:
        print("  Bilingual requested, but no English lyric file was found.")
    lyrics = [cue.text for cue in cues]

    if overwrite and legacy_srt_path.exists():
        legacy_srt_path.unlink()
    write_srt(srt_path, cues)
    write_mv_prompt(prompt_path, song_name, duration, lyrics)

    selected_background_video = choose_background_video(
        background_video=background_video,
        background_folder=background_folder,
        background_root=background_root,
    )

    render_lyric_video(
        mp3_path=mp3_path,
        cues=cues,
        output_path=video_path,
        duration_seconds=duration,
        width=width,
        height=height,
        fps=fps,
        background=background,
        background_video=selected_background_video,
        font=font,
        font_size=font_size,
        zoom_start=zoom_start,
        zoom_end=zoom_end,
        text_x=text_x,
        text_y=text_y,
        lyric_offset=lyric_offset,
        english_scale=english_scale,
        english_color=english_color,
        english_uppercase=english_uppercase,
        animation_style=animation_style,
        stroke_width=stroke_width,
        overwrite=overwrite,
    )

    print(f"  SRT: {srt_path}")
    if english_path:
        print(f"  English: {english_path}")
    if selected_background_video:
        print(f"  Background: {selected_background_video}")
    print(f"  MP4: {video_path}")
    print(f"  Prompt: {prompt_path}")
