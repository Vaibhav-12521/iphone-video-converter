"""Background conversion worker.

The worker is a :class:`QObject` moved onto a :class:`QThread` so that the
(blocking, long-running) FFmpeg calls never freeze the UI.  It processes a list
of jobs sequentially and reports progress back to the GUI purely through Qt
signals, which are delivered safely across the thread boundary.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from movconv.core import converter
from movconv.core.presets import Preset
from movconv.core.probe import MediaInfo

log = logging.getLogger(__name__)


@dataclass
class Job:
    """One queued conversion."""

    info: MediaInfo
    preset: Preset
    output_path: Path
    allow_unsupported: bool = False


class ConversionWorker(QObject):
    """Runs a queue of :class:`Job` objects and emits progress signals.

    Signals
    -------
    job_started(row, name)
    job_progress(row, percent)          # 0..100 for the current file
    job_finished(row, output_path)
    job_failed(row, message)
    overall_progress(percent)           # 0..100 across the whole batch
    message(text)                       # human-readable log line for the UI
    finished(completed, failed)         # emitted once when the batch ends
    """

    job_started = Signal(int, str)
    job_progress = Signal(int, float)
    job_finished = Signal(int, str)
    job_failed = Signal(int, str)
    overall_progress = Signal(float)
    message = Signal(str)
    finished = Signal(int, int)

    def __init__(self, ffmpeg: str, jobs: list[Job]) -> None:
        super().__init__()
        self._ffmpeg = ffmpeg
        self._jobs = jobs
        self._cancel_event = threading.Event()
        self._current_proc = None

    @Slot()
    def cancel(self) -> None:
        """Request cancellation; kills the running FFmpeg process immediately."""
        self._cancel_event.set()
        proc = self._current_proc
        if proc is not None and proc.poll() is None:
            converter._terminate(proc)  # noqa: SLF001 - deliberate internal use

    @Slot()
    def run(self) -> None:
        """Main loop - executed on the worker thread."""
        total = len(self._jobs)
        completed = 0
        failed = 0

        for row, job in enumerate(self._jobs):
            if self._cancel_event.is_set():
                self.message.emit("Cancelled - remaining files were skipped.")
                break

            name = job.info.path.name
            self.job_started.emit(row, name)
            self.message.emit(f"Converting: {name}")

            def _on_progress(pct: float, _row: int = row, _done: int = completed) -> None:
                self.job_progress.emit(_row, pct)
                # Overall = fully-finished files + the fraction of the current one.
                overall = (_done + pct / 100.0) / total * 100.0
                self.overall_progress.emit(overall)

            try:
                converter.convert(
                    self._ffmpeg,
                    job.info,
                    job.preset,
                    job.output_path,
                    on_progress=_on_progress,
                    cancel_event=self._cancel_event,
                    on_proc=lambda p: setattr(self, "_current_proc", p),
                    allow_unsupported=job.allow_unsupported,
                )
            except converter.ConversionCancelled:
                self.message.emit(f"Cancelled: {name}")
                break
            except converter.UnsupportedCodecError as exc:
                failed += 1
                self.job_failed.emit(row, str(exc))
                self.message.emit(f"Skipped {name}: {exc}")
            except converter.ConversionError as exc:
                failed += 1
                self.job_failed.emit(row, str(exc))
                self.message.emit(f"FAILED {name}: {exc}")
            except Exception as exc:  # defensive catch-all
                failed += 1
                log.exception("Unexpected error converting %s", name)
                self.job_failed.emit(row, str(exc))
                self.message.emit(f"ERROR {name}: {exc}")
            else:
                completed += 1
                self.job_finished.emit(row, str(job.output_path))
                self.message.emit(f"Saved: {job.output_path}")
            finally:
                self._current_proc = None

            self.overall_progress.emit(completed / total * 100.0)

        self.finished.emit(completed, failed)
