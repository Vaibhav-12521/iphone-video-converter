"""Quality presets that map user-friendly choices to encoder settings.

We encode with libx264 using constant-rate-factor (CRF) mode, which targets a
perceptual quality level rather than a fixed bitrate.  Lower CRF = higher
quality and larger files.  Each preset also carries an approximate
bits-per-pixel figure used purely to *estimate* the output size in the UI
(CRF output size cannot be known exactly in advance).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Preset:
    key: str
    label: str
    description: str
    crf: int                 # libx264 quality (lower = better)
    x264_preset: str         # encoding speed/efficiency trade-off
    audio_bitrate_k: int     # AAC audio bitrate in kbps
    est_bits_per_pixel: float  # for size estimation only
    max_height: int | None = None  # optional downscale ceiling (keeps aspect)


# Ordered from best quality to smallest file.
HIGH = Preset(
    key="high",
    label="High Quality",
    description="Near-lossless - largest files.",
    crf=18,
    x264_preset="slow",
    audio_bitrate_k=256,
    est_bits_per_pixel=0.10,
    max_height=None,
)

BALANCED = Preset(
    key="balanced",
    label="Balanced",
    description="Great quality, sensible size - recommended.",
    crf=22,
    x264_preset="medium",
    audio_bitrate_k=192,
    est_bits_per_pixel=0.065,
    max_height=None,
)

SMALL = Preset(
    key="small",
    label="Small File Size",
    description="Smallest files, downscaled to 1080p.",
    crf=27,
    x264_preset="medium",
    audio_bitrate_k=128,
    est_bits_per_pixel=0.04,
    max_height=1080,
)

PRESETS: dict[str, Preset] = {p.key: p for p in (HIGH, BALANCED, SMALL)}
PRESET_ORDER: list[str] = ["high", "balanced", "small"]
DEFAULT_PRESET_KEY = "balanced"


def get_preset(key: str) -> Preset:
    return PRESETS.get(key, BALANCED)
