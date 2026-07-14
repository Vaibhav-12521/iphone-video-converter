"""Inspect a media file with ffprobe and expose the details we care about."""
from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from movconv.core.ffmpeg_locator import SUBPROCESS_FLAGS

log = logging.getLogger(__name__)

# Video codecs we know how to handle well.  Anything else is reported as
# "unsupported" so the UI can warn the user before attempting a conversion.
SUPPORTED_VIDEO_CODECS = {"h264", "hevc", "h265"}


class ProbeError(RuntimeError):
    """Raised when ffprobe fails or returns something unusable."""


@dataclass
class MediaInfo:
    """A normalised, GUI-friendly summary of a media file."""

    path: Path
    size_bytes: int
    duration: float          # seconds
    video_codec: str         # e.g. "hevc", "h264"
    width: int
    height: int
    rotation: int            # degrees, normalised to 0/90/180/270
    fps: float
    video_bitrate: int       # bits/sec (0 if unknown)
    audio_codec: str         # e.g. "aac", "pcm_s16le", "" if none
    audio_bitrate: int       # bits/sec (0 if unknown)
    has_audio: bool

    @property
    def supported(self) -> bool:
        """True when the video codec is one we explicitly support."""
        return self.video_codec in SUPPORTED_VIDEO_CODECS

    @property
    def display_width(self) -> int:
        """Width as it appears after rotation is applied."""
        return self.height if self.rotation in (90, 270) else self.width

    @property
    def display_height(self) -> int:
        return self.width if self.rotation in (90, 270) else self.height


def _to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _parse_fps(rate: str | None) -> float:
    """Parse an ffprobe frame-rate fraction such as ``"30000/1001"``."""
    if not rate or rate == "0/0":
        return 0.0
    if "/" in rate:
        num, _, den = rate.partition("/")
        den_f = _to_float(den, 0.0)
        return _to_float(num) / den_f if den_f else 0.0
    return _to_float(rate)


def _parse_rotation(video_stream: dict) -> int:
    """Extract rotation from either the legacy ``rotate`` tag or a Display Matrix.

    Normalises the result to one of 0/90/180/270 degrees.
    """
    rotation = 0

    tags = video_stream.get("tags") or {}
    if "rotate" in tags:
        rotation = _to_int(tags.get("rotate"), 0)

    for side in video_stream.get("side_data_list", []) or []:
        if "rotation" in side:
            # Display-matrix rotation is typically negative (e.g. -90).
            rotation = _to_int(side.get("rotation"), rotation)
            break

    rotation %= 360
    # Snap to the nearest 90-degree step.
    return min((0, 90, 180, 270), key=lambda r: abs(r - rotation)) % 360


def probe(path: str | Path, ffprobe: str) -> MediaInfo:
    """Run ffprobe on *path* and return a :class:`MediaInfo`."""
    path = Path(path)
    cmd = [
        ffprobe,
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    log.debug("Probing: %s", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            creationflags=SUBPROCESS_FLAGS,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ProbeError(f"ffprobe failed to start for {path.name}: {exc}") from exc

    if result.returncode != 0:
        raise ProbeError(
            f"ffprobe could not read {path.name}: {result.stderr.strip() or 'unknown error'}"
        )

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ProbeError(f"ffprobe returned invalid JSON for {path.name}") from exc

    fmt = data.get("format", {})
    streams = data.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    if video_stream is None:
        raise ProbeError(f"{path.name} contains no video stream.")

    # Duration can live on the format or the stream; prefer whichever is present.
    duration = _to_float(fmt.get("duration")) or _to_float(video_stream.get("duration"))

    try:
        size_bytes = _to_int(fmt.get("size")) or path.stat().st_size
    except OSError:
        size_bytes = _to_int(fmt.get("size"))

    return MediaInfo(
        path=path,
        size_bytes=size_bytes,
        duration=duration,
        video_codec=(video_stream.get("codec_name") or "").lower(),
        width=_to_int(video_stream.get("width")),
        height=_to_int(video_stream.get("height")),
        rotation=_parse_rotation(video_stream),
        fps=_parse_fps(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate")),
        video_bitrate=_to_int(video_stream.get("bit_rate")),
        audio_codec=(audio_stream.get("codec_name") or "").lower() if audio_stream else "",
        audio_bitrate=_to_int(audio_stream.get("bit_rate")) if audio_stream else 0,
        has_audio=audio_stream is not None,
    )
