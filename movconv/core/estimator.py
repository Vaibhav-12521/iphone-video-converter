"""Rough output-size estimation and byte-size formatting helpers.

Because CRF encoding produces a variable bitrate, the true output size is only
known after encoding.  We approximate it from resolution, frame rate and a
per-preset bits-per-pixel constant so the UI can show a ballpark figure.
"""
from __future__ import annotations

from movconv.core.presets import Preset
from movconv.core.probe import MediaInfo


def _target_dimensions(info: MediaInfo, preset: Preset) -> tuple[int, int]:
    """Output dimensions after any preset downscaling (aspect preserved)."""
    w, h = info.display_width, info.display_height
    if preset.max_height and h > preset.max_height and h > 0:
        scale = preset.max_height / h
        w = max(2, round(w * scale))
        h = preset.max_height
    return w, h


def estimate_output_size(info: MediaInfo, preset: Preset) -> int:
    """Estimated output size in bytes (returns 0 if inputs are unknown)."""
    if info.duration <= 0:
        return 0

    w, h = _target_dimensions(info, preset)
    fps = info.fps if info.fps > 0 else 30.0

    video_bps = w * h * fps * preset.est_bits_per_pixel
    audio_bps = preset.audio_bitrate_k * 1000 if info.has_audio else 0

    total_bits = (video_bps + audio_bps) * info.duration
    return int(total_bits / 8)


def human_size(num_bytes: float) -> str:
    """Format a byte count as a human-readable string (e.g. '1.4 GB')."""
    if num_bytes <= 0:
        return "-"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            precision = 0 if unit == "B" else 1
            return f"{size:.{precision}f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def human_duration(seconds: float) -> str:
    """Format seconds as ``H:MM:SS`` or ``M:SS``."""
    if seconds <= 0:
        return "-"
    total = int(round(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
