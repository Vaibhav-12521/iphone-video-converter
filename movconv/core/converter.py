"""The FFmpeg conversion engine: build commands, run them, report progress.

Design notes
------------
* We always re-encode video to **H.264 (libx264)** and audio to **AAC**, in an
  MP4 container with ``+faststart`` so playback can begin before the whole file
  downloads - the combination that plays on essentially every Android device.
* ``-pix_fmt yuv420p`` guarantees 8-bit 4:2:0 output; iPhone HEVC is often
  10-bit, which many Android decoders reject.
* FFmpeg auto-rotates by default, so the output is physically upright and needs
  no rotation metadata.  Other metadata (creation time, GPS, ...) is copied with
  ``-map_metadata 0``.
* Progress is read from ``-progress pipe:1`` (machine-readable key=value lines)
  and converted to a percentage using the known duration.
"""
from __future__ import annotations

import logging
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from movconv.core.ffmpeg_locator import SUBPROCESS_FLAGS
from movconv.core.presets import Preset
from movconv.core.probe import MediaInfo

log = logging.getLogger(__name__)

ProgressCallback = Callable[[float], None]  # receives 0..100
ProcCallback = Callable[[subprocess.Popen], None]


class ConversionError(RuntimeError):
    """Raised when FFmpeg exits with a non-zero status."""


class ConversionCancelled(RuntimeError):
    """Raised when a conversion is cancelled by the user."""


class UnsupportedCodecError(RuntimeError):
    """Raised when the input video codec is not one we support."""


def build_command(
    ffmpeg: str,
    info: MediaInfo,
    preset: Preset,
    output_path: Path,
) -> list[str]:
    """Assemble the full FFmpeg argument list for one conversion."""
    cmd: list[str] = [
        ffmpeg,
        "-y",                    # overwrite (we already resolved a unique name)
        "-hide_banner",
        "-loglevel", "error",    # keep stderr for real errors only
        "-i", str(info.path),
    ]

    # Optional downscale (only ever shrinks, never upscales). ``-2`` keeps the
    # dimension even, which H.264 requires.
    if preset.max_height and info.display_height > preset.max_height:
        cmd += ["-vf", f"scale=-2:{preset.max_height}"]

    # Video: H.264 with the chosen quality/speed and universally safe options.
    cmd += [
        "-c:v", "libx264",
        "-preset", preset.x264_preset,
        "-crf", str(preset.crf),
        "-pix_fmt", "yuv420p",
        "-profile:v", "high",
        "-level", "4.2",
    ]

    # Audio: AAC, or "no audio" if the source has none.
    if info.has_audio:
        cmd += ["-c:a", "aac", "-b:a", f"{preset.audio_bitrate_k}k", "-ac", "2"]
    else:
        cmd += ["-an"]

    # Container / metadata / streaming.
    cmd += [
        "-map_metadata", "0",
        "-movflags", "+faststart",
        # Machine-readable progress on stdout; suppress the human stats line.
        "-progress", "pipe:1",
        "-nostats",
        str(output_path),
    ]
    return cmd


def _emit_progress(line: str, duration: float, on_progress: ProgressCallback) -> None:
    """Translate one ``key=value`` progress line into a percentage callback."""
    if duration <= 0:
        return
    if line.startswith("out_time_us=") or line.startswith("out_time_ms="):
        # NB: some FFmpeg builds mislabel microseconds as "ms"; both are µs here.
        raw = line.split("=", 1)[1].strip()
        if raw.isdigit():
            seconds = int(raw) / 1_000_000
            pct = max(0.0, min(99.9, seconds / duration * 100.0))
            on_progress(pct)
    elif line.strip() == "progress=end":
        on_progress(100.0)


def convert(
    ffmpeg: str,
    info: MediaInfo,
    preset: Preset,
    output_path: Path,
    on_progress: ProgressCallback | None = None,
    cancel_event: threading.Event | None = None,
    on_proc: ProcCallback | None = None,
    *,
    allow_unsupported: bool = False,
) -> None:
    """Convert a single file, blocking until done.

    Raises :class:`UnsupportedCodecError`, :class:`ConversionCancelled` or
    :class:`ConversionError` on the corresponding failure.
    """
    if not info.supported and not allow_unsupported:
        raise UnsupportedCodecError(
            f"'{info.video_codec or 'unknown'}' is not a supported input codec."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = build_command(ffmpeg, info, preset, output_path)
    log.info("Converting %s -> %s [%s]", info.path.name, output_path.name, preset.key)
    log.debug("FFmpeg cmd: %s", " ".join(cmd))

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            creationflags=SUBPROCESS_FLAGS,
        )
    except OSError as exc:
        raise ConversionError(f"Could not start FFmpeg: {exc}") from exc

    if on_proc:
        on_proc(proc)

    # Drain stderr on a background thread so a full pipe can never dead-lock us.
    stderr_tail: list[str] = []

    def _drain_stderr() -> None:
        assert proc.stderr is not None
        for err_line in proc.stderr:
            stderr_tail.append(err_line)
            del stderr_tail[:-40]  # keep only the last 40 lines

    err_thread = threading.Thread(target=_drain_stderr, daemon=True)
    err_thread.start()

    cancelled = False
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            if cancel_event is not None and cancel_event.is_set():
                cancelled = True
                break
            if on_progress is not None:
                _emit_progress(line, info.duration, on_progress)
    finally:
        if cancelled:
            _terminate(proc)
        proc.wait()
        err_thread.join(timeout=2)

    if cancelled:
        _cleanup_partial(output_path)
        raise ConversionCancelled(f"Cancelled: {info.path.name}")

    if proc.returncode != 0:
        _cleanup_partial(output_path)
        detail = "".join(stderr_tail).strip() or f"exit code {proc.returncode}"
        raise ConversionError(f"FFmpeg failed for {info.path.name}:\n{detail}")

    log.info("Done: %s", output_path)


def _terminate(proc: subprocess.Popen) -> None:
    """Politely stop FFmpeg, escalating to kill if it ignores us."""
    try:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    except Exception:  # pragma: no cover
        log.exception("Error terminating FFmpeg process")


def _cleanup_partial(output_path: Path) -> None:
    """Remove a half-written output file after failure/cancellation."""
    try:
        if output_path.exists():
            output_path.unlink()
    except OSError:  # pragma: no cover
        log.warning("Could not remove partial file %s", output_path)


def unique_output_path(directory: Path, stem: str, suffix: str = ".mp4") -> Path:
    """Return a non-colliding path like ``name.mp4`` / ``name (1).mp4``."""
    directory.mkdir(parents=True, exist_ok=True)
    candidate = directory / f"{stem}{suffix}"
    counter = 1
    while candidate.exists():
        candidate = directory / f"{stem} ({counter}){suffix}"
        counter += 1
    return candidate
