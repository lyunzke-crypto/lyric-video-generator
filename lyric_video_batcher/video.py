from __future__ import annotations

import math
import random
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .subtitles import LyricCue


VIDEO_EXTENSIONS = {".mp4"}

ANIMATION_STYLES = {
    "cinematic": {
        "blur": 0.010,
        "glow": 0.12,
        "glow_radius": 8,
        "perspective": -0.035,
        "shadow": 0.36,
        "hold_near": 0.14,
    },
    "tiktok": {
        "blur": 0.014,
        "glow": 0.14,
        "glow_radius": 7,
        "perspective": -0.030,
        "shadow": 0.38,
        "hold_near": 0.08,
    },
    "trailer": {
        "blur": 0.018,
        "glow": 0.16,
        "glow_radius": 10,
        "perspective": -0.045,
        "shadow": 0.42,
        "hold_near": 0.18,
    },
}


def choose_background_video(
    *,
    background_video: Optional[Path],
    background_folder: Optional[Path],
    background_root: Optional[Path],
) -> Optional[Path]:
    if background_video:
        video = background_video.expanduser().resolve()
        if not video.exists() or not video.is_file():
            raise FileNotFoundError(f"Background video does not exist: {video}")
        return video

    search_dir = background_folder or background_root
    if not search_dir:
        return None

    search_dir = search_dir.expanduser().resolve()
    if not search_dir.exists() or not search_dir.is_dir():
        raise FileNotFoundError(f"Background folder does not exist: {search_dir}")

    videos = [
        path
        for path in search_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    ]
    if not videos:
        raise FileNotFoundError(f"No .mp4 background videos found in: {search_dir}")

    return random.choice(videos)


def render_lyric_video(
    *,
    mp3_path: Path,
    cues: list[LyricCue],
    output_path: Path,
    duration_seconds: float,
    width: int,
    height: int,
    fps: int,
    background: str,
    background_video: Optional[Path],
    font: str,
    font_size: int,
    zoom_start: float,
    zoom_end: float,
    text_x: float,
    text_y: float,
    lyric_offset: float,
    english_scale: float,
    english_color: str,
    english_uppercase: bool,
    animation_style: str,
    stroke_width: int,
    overwrite: bool,
) -> None:
    try:
        from moviepy.editor import AudioFileClip, CompositeVideoClip
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "MoviePy is required for frame-by-frame lyric rendering. "
            "Install dependencies with: pip install -r requirements.txt"
        ) from exc

    if output_path.exists() and not overwrite:
        raise FileExistsError(f"Output video already exists: {output_path}")

    audio_clip = AudioFileClip(str(mp3_path)).subclip(0, duration_seconds)
    background_clip = build_background_clip(
        background=background,
        background_video=background_video,
        duration_seconds=duration_seconds,
        width=width,
        height=height,
        fps=fps,
    )
    cue_positions: dict[int, tuple[float, float]] = {}
    lyric_clip = build_lyric_animation_clip(
        cues=cues,
        cue_positions=cue_positions,
        duration_seconds=duration_seconds,
        width=width,
        height=height,
        fps=fps,
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
    )

    final_clip = CompositeVideoClip([background_clip, lyric_clip], size=(width, height))
    final_clip = final_clip.set_audio(audio_clip).set_duration(duration_seconds).set_fps(fps)

    try:
        final_clip.write_videofile(
            str(output_path),
            fps=fps,
            codec="libx264",
            audio_codec="aac",
            audio_bitrate="192k",
            preset="medium",
            threads=4,
            ffmpeg_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
        )
    finally:
        final_clip.close()
        lyric_clip.close()
        background_clip.close()
        audio_clip.close()


def build_background_clip(
    *,
    background: str,
    background_video: Optional[Path],
    duration_seconds: float,
    width: int,
    height: int,
    fps: int,
):
    if background_video:
        return build_video_background_clip(background_video, duration_seconds, width, height, fps)

    if background == "black":
        return build_black_clip(duration_seconds, width, height, fps)

    if background == "gradient":
        return build_gradient_clip(duration_seconds, width, height, fps)

    raise ValueError(f"Unsupported background: {background}")


def build_video_background_clip(
    background_video: Path, duration_seconds: float, width: int, height: int, fps: int
):
    from moviepy.editor import VideoFileClip, vfx

    clip = VideoFileClip(str(background_video), audio=False)
    scale = max(width / clip.w, height / clip.h)
    clip = clip.resize(scale)
    clip = clip.crop(x_center=clip.w / 2, y_center=clip.h / 2, width=width, height=height)
    clip = clip.fx(vfx.loop, duration=duration_seconds).subclip(0, duration_seconds)
    return clip.set_fps(fps)


def build_black_clip(duration_seconds: float, width: int, height: int, fps: int):
    from moviepy.editor import ColorClip

    return ColorClip((width, height), color=(0, 0, 0), duration=duration_seconds).set_fps(fps)


def build_gradient_clip(duration_seconds: float, width: int, height: int, fps: int):
    from moviepy.editor import VideoClip

    y = np.linspace(0, 1, height, dtype=np.float32)[:, None]
    r = (18 + 18 * y).astype(np.uint8)
    g = (12 + 10 * y).astype(np.uint8)
    b = (28 + 55 * y).astype(np.uint8)
    frame = np.dstack(
        [
            np.repeat(r, width, axis=1),
            np.repeat(g, width, axis=1),
            np.repeat(b, width, axis=1),
        ]
    )

    return VideoClip(lambda _t: frame, duration=duration_seconds).set_fps(fps)


def build_lyric_animation_clip(
    *,
    cues: list[LyricCue],
    cue_positions: dict[int, tuple[float, float]],
    duration_seconds: float,
    width: int,
    height: int,
    fps: int,
    font: str,
    font_size: int,
    zoom_start: float,
    zoom_end: float,
    text_x: float,
    text_y: float,
    lyric_offset: float,
    english_scale: float,
    english_color: str,
    english_uppercase: bool,
    animation_style: str,
    stroke_width: int,
):
    from moviepy.editor import VideoClip

    font_path = resolve_font_path(font)

    def make_rgb_frame(t: float) -> np.ndarray:
        rgba = render_lyric_rgba_frame(
            t=t,
            cues=cues,
            cue_positions=cue_positions,
            width=width,
            height=height,
            font_path=font_path,
            base_font_size=font_size,
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
        )
        return np.asarray(rgba.convert("RGB"))

    def make_mask_frame(t: float) -> np.ndarray:
        rgba = render_lyric_rgba_frame(
            t=t,
            cues=cues,
            cue_positions=cue_positions,
            width=width,
            height=height,
            font_path=font_path,
            base_font_size=font_size,
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
        )
        return np.asarray(rgba.getchannel("A"), dtype=np.float32) / 255.0

    lyric_clip = VideoClip(make_rgb_frame, duration=duration_seconds).set_fps(fps)
    lyric_clip.mask = VideoClip(make_mask_frame, ismask=True, duration=duration_seconds).set_fps(fps)
    return lyric_clip


def render_lyric_rgba_frame(
    *,
    t: float,
    cues: list[LyricCue],
    width: int,
    height: int,
    font_path: Path,
    base_font_size: int,
    zoom_start: float,
    zoom_end: float,
    text_x: float,
    text_y: float,
    lyric_offset: float,
    english_scale: float,
    english_color: str,
    english_uppercase: bool,
    animation_style: str,
    stroke_width: int,
    cue_positions: Optional[dict[int, tuple[float, float]]] = None,
) -> Image.Image:
    frame = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    active = find_active_cue(cues, t - lyric_offset)
    if active is None:
        return frame
    cue_index, cue = active

    style = get_animation_style(animation_style)
    cue_time = t - lyric_offset
    progress = normalized_progress((cue_time - cue.start) / max(0.001, cue.end - cue.start))
    motion = lyric_push_motion(progress, zoom_start, zoom_end, text_x, text_y)
    scale = motion["scale"]
    opacity = int(round(255 * motion["opacity"]))
    if opacity <= 0:
        return frame
    font_size = max(8, int(round(base_font_size * scale)))
    display_text = normalize_lyric_text(cue.text)
    active_font_path = resolve_cjk_font_path() if contains_cjk(display_text) else font_path
    font = ImageFont.truetype(str(active_font_path), font_size)
    lines = wrap_text(display_text, font, max_width=int(width * 0.55))
    english_text = normalize_english_display_text(cue.english_text, english_uppercase)
    if english_text:
        english_font_size = max(8, int(round(font_size * english_scale)))
        english_font = ImageFont.truetype(str(font_path), english_font_size)
        english_lines = wrap_text(english_text, english_font, max_width=int(width * 0.58))
        block = render_bilingual_text_block(
            primary_lines=lines,
            english_lines=english_lines,
            primary_font=font,
            english_font=english_font,
            opacity=opacity,
            stroke_width=stroke_width,
            style=style,
            english_color=parse_hex_color(english_color),
        )
    else:
        block = render_text_block(
            lines=lines,
            font=font,
            opacity=opacity,
            stroke_width=stroke_width,
            style=style,
        )
    block = apply_perspective(block, style["perspective"] * (1.0 - motion["depth"]))

    blur_distance = int(round(width * style["blur"] * (1.0 - motion["depth"])))
    if blur_distance > 0:
        block = apply_directional_motion_blur(block, blur_distance)

    x = int(width * motion["x"]) - int(round(block.width * float(motion["anchor_x"])))
    y = int(height * motion["y"]) - int(round(block.height * float(motion["anchor_y"])))
    alpha_composite_clipped(frame, block, x, y)
    return frame


def alpha_composite_clipped(base: Image.Image, overlay: Image.Image, x: int, y: int) -> None:
    left = max(0, x)
    top = max(0, y)
    right = min(base.width, x + overlay.width)
    bottom = min(base.height, y + overlay.height)

    if right <= left or bottom <= top:
        return

    crop_left = left - x
    crop_top = top - y
    crop_right = crop_left + (right - left)
    crop_bottom = crop_top + (bottom - top)
    cropped = overlay.crop((crop_left, crop_top, crop_right, crop_bottom))
    base.alpha_composite(cropped, (left, top))


def render_text_block(
    *,
    lines: list[str],
    font: ImageFont.FreeTypeFont,
    opacity: int,
    stroke_width: int,
    style: dict[str, float],
) -> Image.Image:
    line_gap = max(2, int(font.size * 0.04))
    shadow_offset = max(1, int(font.size * 0.028))
    padding = max(12, int(font.size * 0.14)) + stroke_width * 3 + shadow_offset * 2
    block_width = max(text_width(line, font) for line in lines) + padding * 2
    block_height = sum(text_height(line, font) for line in lines)
    block_height += line_gap * (len(lines) - 1) + padding * 2

    glow = Image.new("RGBA", (block_width, block_height), (0, 0, 0, 0))
    text_layer = Image.new("RGBA", glow.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    text_draw = ImageDraw.Draw(text_layer)
    y = padding

    for line in lines:
        glow_draw.text(
            (padding, y),
            line,
            font=font,
            fill=(242, 242, 242, int(opacity * style["glow"])),
            stroke_width=stroke_width,
            stroke_fill=(242, 242, 242, int(opacity * style["glow"])),
        )
        text_draw.text(
            (padding + shadow_offset, y + shadow_offset),
            line,
            font=font,
            fill=(0, 0, 0, int(opacity * style["shadow"])),
            stroke_width=stroke_width,
            stroke_fill=(0, 0, 0, int(opacity * style["shadow"])),
        )
        text_draw.text(
            (padding, y),
            line,
            font=font,
            fill=(242, 242, 242, opacity),
            stroke_width=stroke_width,
            stroke_fill=(0, 0, 0, int(opacity * 0.42)),
        )
        y += text_height(line, font) + line_gap

    block = glow.filter(ImageFilter.GaussianBlur(radius=style["glow_radius"]))
    block.alpha_composite(text_layer)
    return block


def render_bilingual_text_block(
    *,
    primary_lines: list[str],
    english_lines: list[str],
    primary_font: ImageFont.FreeTypeFont,
    english_font: ImageFont.FreeTypeFont,
    opacity: int,
    stroke_width: int,
    style: dict[str, float],
    english_color: tuple[int, int, int],
) -> Image.Image:
    primary_gap = max(2, int(primary_font.size * 0.04))
    bilingual_gap = max(7, int(primary_font.size * 0.10))
    english_gap = max(2, int(english_font.size * 0.08))
    shadow_offset = max(1, int(primary_font.size * 0.028))
    padding = max(12, int(primary_font.size * 0.14)) + stroke_width * 3 + shadow_offset * 2

    content_width = max(
        [text_width(line, primary_font) for line in primary_lines]
        + [text_width(line, english_font) for line in english_lines]
    )
    primary_height = sum(text_height(line, primary_font) for line in primary_lines)
    primary_height += primary_gap * (len(primary_lines) - 1)
    english_height = sum(text_height(line, english_font) for line in english_lines)
    english_height += english_gap * (len(english_lines) - 1)
    block_width = content_width + padding * 2
    block_height = primary_height + bilingual_gap + english_height + padding * 2

    glow = Image.new("RGBA", (block_width, block_height), (0, 0, 0, 0))
    text_layer = Image.new("RGBA", glow.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    text_draw = ImageDraw.Draw(text_layer)
    y = padding

    for line in primary_lines:
        draw_lyric_line(
            glow_draw=glow_draw,
            text_draw=text_draw,
            position=(padding, y),
            text=line,
            font=primary_font,
            color=(242, 242, 242),
            opacity=opacity,
            stroke_width=stroke_width,
            shadow_offset=shadow_offset,
            style=style,
        )
        y += text_height(line, primary_font) + primary_gap

    y += bilingual_gap - primary_gap
    english_shadow_offset = max(1, int(english_font.size * 0.04))
    for line in english_lines:
        draw_lyric_line(
            glow_draw=glow_draw,
            text_draw=text_draw,
            position=(padding, y),
            text=line,
            font=english_font,
            color=english_color,
            opacity=opacity,
            stroke_width=max(0, stroke_width - 1),
            shadow_offset=english_shadow_offset,
            style=style,
        )
        y += text_height(line, english_font) + english_gap

    block = glow.filter(ImageFilter.GaussianBlur(radius=style["glow_radius"]))
    block.alpha_composite(text_layer)
    return block


def draw_lyric_line(
    *,
    glow_draw: ImageDraw.ImageDraw,
    text_draw: ImageDraw.ImageDraw,
    position: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    color: tuple[int, int, int],
    opacity: int,
    stroke_width: int,
    shadow_offset: int,
    style: dict[str, float],
) -> None:
    x, y = position
    glow_alpha = int(opacity * style["glow"])
    shadow_alpha = int(opacity * style["shadow"])
    glow_draw.text(
        (x, y),
        text,
        font=font,
        fill=(*color, glow_alpha),
        stroke_width=stroke_width,
        stroke_fill=(*color, glow_alpha),
    )
    text_draw.text(
        (x + shadow_offset, y + shadow_offset),
        text,
        font=font,
        fill=(0, 0, 0, shadow_alpha),
        stroke_width=stroke_width,
        stroke_fill=(0, 0, 0, shadow_alpha),
    )
    text_draw.text(
        (x, y),
        text,
        font=font,
        fill=(*color, opacity),
        stroke_width=stroke_width,
        stroke_fill=(0, 0, 0, int(opacity * 0.42)),
    )


def apply_perspective(image: Image.Image, skew: float) -> Image.Image:
    if abs(skew) < 0.001:
        return image

    width, height = image.size
    extra_width = int(width * abs(skew)) + 6
    output_size = (width + extra_width, height)
    x_offset = extra_width if skew < 0 else 0
    matrix = (1, skew, x_offset, 0, 1, 0)
    return image.transform(output_size, Image.AFFINE, matrix, resample=Image.BICUBIC)


def apply_directional_motion_blur(image: Image.Image, distance: int) -> Image.Image:
    output = Image.new("RGBA", (image.width + distance, image.height), (0, 0, 0, 0))
    samples = max(3, min(9, distance + 1))

    for index in range(samples):
        offset = int(round(index * distance / max(1, samples - 1)))
        sample = image.copy()
        sample_alpha = sample.getchannel("A").point(lambda value: int(value * 0.32 / samples))
        sample.putalpha(sample_alpha)
        output.alpha_composite(sample, (offset, 0))

    output.alpha_composite(image, (distance, 0))
    return output


def build_cue_positions(
    *,
    cues: list[LyricCue],
    background_video: Optional[Path],
    width: int,
    height: int,
    default_x: float,
    default_y: float,
) -> dict[int, tuple[float, float]]:
    if not background_video:
        return {}

    try:
        from moviepy.editor import VideoFileClip
    except ModuleNotFoundError:
        return {}

    clip = None
    try:
        clip = VideoFileClip(str(background_video), audio=False)
        scale = max(width / clip.w, height / clip.h)
        clip = clip.resize(scale)
        clip = clip.crop(x_center=clip.w / 2, y_center=clip.h / 2, width=width, height=height)
        positions: dict[int, tuple[float, float]] = {}

        for index, cue in enumerate(cues):
            sample_time = max(0.0, cue.start - 0.08)
            if clip.duration:
                sample_time = sample_time % clip.duration
            frame = clip.get_frame(sample_time)
            positions[index] = choose_lyric_position(frame, width, height, default_x, default_y)

        return positions
    except Exception:
        return {}
    finally:
        if clip is not None:
            clip.close()


def choose_lyric_position(
    frame: np.ndarray, width: int, height: int, default_x: float, default_y: float
) -> tuple[float, float]:
    gray = np.asarray(frame, dtype=np.float32).mean(axis=2)
    candidates: list[tuple[float, float]] = []
    for dx in (-0.015, 0.0, 0.015, 0.03):
        for dy in (-0.035, -0.015, 0.0, 0.015, 0.035):
            x = clamp(default_x + dx, 0.06, 0.14)
            y = clamp(default_y + dy, 0.18, 0.30)
            candidates.append((x, y))

    roi_w = int(width * 0.42)
    roi_h = int(height * 0.18)
    best = (default_x, default_y)
    best_score = float("inf")

    for x_ratio, y_ratio in candidates:
        x = int(width * x_ratio)
        y = int(height * y_ratio)
        roi = gray[y : min(height, y + roi_h), x : min(width, x + roi_w)]
        if roi.size == 0:
            continue
        mean_light = float(roi.mean())
        bright_penalty = float((roi > 205).mean()) * 255
        vanishing_penalty = vanishing_point_overlap_penalty(x, y, roi_w, roi_h, width, height)
        score = mean_light + bright_penalty * 1.4 + vanishing_penalty
        if score < best_score:
            best_score = score
            best = (x_ratio, y_ratio)

    return best


def vanishing_point_overlap_penalty(
    x: int, y: int, roi_w: int, roi_h: int, width: int, height: int
) -> float:
    roi_left = x
    roi_right = x + roi_w
    roi_top = y
    roi_bottom = y + roi_h
    zone_left = int(width * 0.38)
    zone_right = int(width * 0.64)
    zone_top = int(height * 0.23)
    zone_bottom = int(height * 0.56)

    overlaps = not (
        roi_right < zone_left
        or roi_left > zone_right
        or roi_bottom < zone_top
        or roi_top > zone_bottom
    )
    return 160.0 if overlaps else 0.0


def find_active_cue(cues: list[LyricCue], t: float) -> Optional[tuple[int, LyricCue]]:
    for index, cue in enumerate(cues):
        if cue.start <= t < cue.end:
            return index, cue
    return None


def get_animation_style(name: str) -> dict[str, float]:
    if name not in ANIMATION_STYLES:
        raise ValueError(f"Unsupported animation style: {name}")
    return ANIMATION_STYLES[name]


def resolve_font_path(font: str) -> Path:
    font_path = Path(font)
    if font_path.exists():
        return font_path

    windows_font_dir = Path("C:/Windows/Fonts")
    preferred = [
        "Anton",
        "Impact",
        "Arial Black",
        "Montserrat ExtraBold",
        "Montserrat-ExtraBold",
    ]
    candidates = {
        "auto": preferred + ["Microsoft YaHei"],
        "anton": ["Anton"],
        "impact": ["impact.ttf", "Impact"],
        "arial black": ["ariblk.ttf", "Arial Black"],
        "montserrat extrabold": ["Montserrat-ExtraBold", "Montserrat ExtraBold"],
        "microsoft yahei": ["msyhbd.ttc", "msyh.ttc"],
        "simhei": ["simhei.ttf"],
        "simsun": ["simsun.ttc"],
    }
    names = candidates.get(font.lower(), [font])

    for name in names:
        candidate = windows_font_dir / name
        if candidate.exists():
            return candidate
        for found in windows_font_dir.glob("*"):
            lower_name = name.lower().replace(" ", "")
            lower_file = found.stem.lower().replace(" ", "").replace("-", "")
            if lower_name.replace("-", "") in lower_file and found.suffix.lower() in {".ttf", ".otf", ".ttc"}:
                return found

    for fallback_name in ("impact.ttf", "ariblk.ttf", "msyhbd.ttc", "msyh.ttc"):
        fallback = windows_font_dir / fallback_name
        if fallback.exists():
            return fallback

    raise FileNotFoundError(
        f"Font not found: {font}. Use --font with a Windows font file path, "
        'for example "C:\\Windows\\Fonts\\msyh.ttc".'
    )


def resolve_cjk_font_path() -> Path:
    windows_font_dir = Path("C:/Windows/Fonts")
    for name in ("msyhbd.ttc", "msyh.ttc", "simhei.ttf", "simsun.ttc"):
        candidate = windows_font_dir / name
        if candidate.exists():
            return candidate
    return resolve_font_path("auto")


def contains_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def normalize_lyric_text(text: str) -> str:
    return " ".join(text.strip().upper().split())


def normalize_english_display_text(text: str, uppercase: bool) -> str:
    normalized = " ".join(text.strip().split())
    return normalized.upper() if uppercase else normalized


def parse_hex_color(value: str) -> tuple[int, int, int]:
    cleaned = value.strip().lstrip("#")
    if len(cleaned) != 6:
        raise ValueError(f"Invalid hex color: {value}")
    return (
        int(cleaned[0:2], 16),
        int(cleaned[2:4], 16),
        int(cleaned[4:6], 16),
    )


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    count_wrapped = wrap_text_by_character_budget(text, max_units=14.0)
    lines: list[str] = []

    for candidate in count_wrapped:
        if text_width(candidate, font) <= max_width:
            lines.append(candidate)
            continue
        lines.extend(wrap_overwide_text(candidate, font, max_width))

    return lines or [" "]


def wrap_text_by_character_budget(text: str, max_units: float) -> list[str]:
    words = text.split(" ")
    if len(words) > 1:
        lines: list[str] = []
        current = ""
        for word in words:
            trial = word if not current else f"{current} {word}"
            if current and text_units(trial) > max_units:
                lines.append(current)
                current = word
            else:
                current = trial
        if current:
            lines.append(current)
        return split_long_units(lines, max_units)

    return split_long_units([text], max_units)


def split_long_units(lines: list[str], max_units: float) -> list[str]:
    output: list[str] = []
    for line in lines:
        current = ""
        current_units = 0.0
        for char in line:
            units = character_units(char)
            if current and current_units + units > max_units:
                output.append(current)
                current = char
                current_units = units
            else:
                current += char
                current_units += units
        if current:
            output.append(current)
    return output


def text_units(text: str) -> float:
    return sum(character_units(char) for char in text)


def character_units(char: str) -> float:
    if "\u4e00" <= char <= "\u9fff":
        return 1.55
    if char.isspace():
        return 0.6
    return 1.0


def wrap_overwide_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for char in text:
        trial = current + char
        if current and text_width(trial, font) > max_width:
            lines.append(current)
            current = char
        else:
            current = trial

    if current:
        lines.append(current)

    return lines


def text_width(text: str, font: ImageFont.FreeTypeFont) -> int:
    box = font.getbbox(text)
    return box[2] - box[0]


def text_height(text: str, font: ImageFont.FreeTypeFont) -> int:
    box = font.getbbox(text)
    return box[3] - box[1]


def normalized_progress(value: float) -> float:
    return min(1.0, max(0.0, value))


def lyric_push_motion(
    progress: float, zoom_start: float, zoom_end: float, start_x: float, start_y: float
) -> dict[str, object]:
    p = normalized_progress(progress)
    if p < 0.18:
        local = ease_out_cubic(p / 0.18)
        return {
            "scale": lerp(zoom_start, max(0.35, zoom_start), local),
            "opacity": lerp(0.0, 1.0, local),
            "x": lerp(start_x, 0.36, local),
            "y": lerp(start_y, 0.38, local),
            "depth": local * 0.25,
            "anchor_x": lerp(0.50, 0.38, local),
            "anchor_y": lerp(0.50, 0.38, local),
        }

    if p < 0.64:
        local = ease_out_cubic((p - 0.18) / 0.46)
        return {
            "scale": lerp(max(0.35, zoom_start), 1.2, local),
            "opacity": 1.0,
            "x": lerp(0.36, 0.18, local),
            "y": lerp(0.38, 0.30, local),
            "depth": lerp(0.25, 0.78, local),
            "anchor_x": lerp(0.38, 0.0, local),
            "anchor_y": lerp(0.38, 0.0, local),
        }

    local = ease_out_cubic((p - 0.64) / 0.36)
    return {
        "scale": lerp(1.2, zoom_end, local),
        "opacity": lerp(1.0, 0.0, local),
        "x": lerp(0.18, -0.28, local),
        "y": lerp(0.30, 0.10, local),
        "depth": lerp(0.78, 1.0, local),
        "anchor_x": 0.0,
        "anchor_y": 0.0,
    }


def clamp(value: float, minimum: float, maximum: float) -> float:
    return min(maximum, max(minimum, value))


def staged_push_progress(progress: float, hold_near: float) -> float:
    far_end = 0.10
    near_start = max(far_end + 0.01, 1.0 - hold_near)
    if progress <= far_end:
        return 0.0
    if progress >= near_start:
        return 1.0
    return normalized_progress((progress - far_end) / (near_start - far_end))


def ease_out_cubic(value: float) -> float:
    return 1 - math.pow(1 - value, 3)


def lerp(start: float, end: float, amount: float) -> float:
    return start + (end - start) * amount
