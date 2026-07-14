"""The main application window: file queue, presets, output, progress."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from movconv import __app_name__, __version__
from movconv.core import converter
from movconv.core.estimator import estimate_output_size, human_duration, human_size
from movconv.core.ffmpeg_locator import FFmpegNotFound, FFmpegTools, locate_ffmpeg
from movconv.core.presets import DEFAULT_PRESET_KEY, PRESET_ORDER, PRESETS, get_preset
from movconv.core.probe import MediaInfo, ProbeError, probe
from movconv.gui.drop_area import DropArea
from movconv.gui.styles import STYLESHEET
from movconv.gui.worker import ConversionWorker, Job

log = logging.getLogger(__name__)

# Table columns.
COL_FILE, COL_CODEC, COL_RES, COL_DURATION, COL_EST, COL_PROGRESS = range(6)
COLUMN_TITLES = ["File", "Codec", "Resolution", "Duration", "Est. size", "Progress"]

CONVERTED_SUBFOLDER = "converted"


@dataclass
class RowItem:
    """Backing model for one table row."""

    info: MediaInfo
    progress: QProgressBar
    status: str = "Ready"
    output_path: Path | None = None


class MainWindow(QMainWindow):
    def __init__(self, tools: FFmpegTools | None) -> None:
        super().__init__()
        self._tools = tools
        self._rows: list[RowItem] = []
        self._thread: QThread | None = None
        self._worker: ConversionWorker | None = None
        self._converting = False

        self.setWindowTitle(f"{__app_name__} - iPhone MOV to Android MP4")
        # A low hard minimum; a scroll area (below) guarantees everything stays
        # reachable even on very short / heavily-scaled screens.
        self.setMinimumSize(760, 420)

        root = QWidget()
        root.setObjectName("Root")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(8)

        outer.addLayout(self._build_header())
        self._banner = self._build_banner()
        outer.addWidget(self._banner)
        self._drop = DropArea()
        self._drop.filesDropped.connect(self.add_files)
        outer.addWidget(self._drop)
        outer.addWidget(self._build_queue_group(), stretch=1)
        outer.addWidget(self._build_options_group())
        outer.addLayout(self._build_action_row())
        outer.addWidget(self._build_progress_row())
        outer.addWidget(self._build_log())

        # Wrap everything in a scroll area so the window can be shorter than the
        # content without anything ever falling off-screen.
        scroll = QScrollArea()
        scroll.setObjectName("RootScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(root)
        self.setCentralWidget(scroll)

        self.setStyleSheet(STYLESHEET)
        self._refresh_banner()
        self._update_buttons()
        # Open at a comfortable size, clamped to the available screen.
        self._size_to_screen(preferred_w=1040, preferred_h=720)

    # ------------------------------------------------------------------ UI
    def _build_header(self) -> QVBoxLayout:
        box = QVBoxLayout()
        title = QLabel("iPhone → Android Video Converter")
        title.setObjectName("Title")
        subtitle = QLabel(
            "Convert HEVC/H.264 .MOV files to universally playable H.264 .MP4"
        )
        subtitle.setObjectName("Subtitle")
        box.addWidget(title)
        box.addWidget(subtitle)
        return box

    def _build_banner(self) -> QWidget:
        banner = QWidget()
        lay = QHBoxLayout(banner)
        lay.setContentsMargins(12, 10, 12, 10)
        self._banner_label = QLabel()
        self._banner_label.setWordWrap(True)
        recheck = QPushButton("Re-check FFmpeg")
        recheck.clicked.connect(self._recheck_ffmpeg)
        lay.addWidget(self._banner_label, stretch=1)
        lay.addWidget(recheck)
        banner.setStyleSheet(
            "background:#3a2326;border:1px solid #e5484d;border-radius:10px;"
        )
        return banner

    def _build_queue_group(self) -> QGroupBox:
        group = QGroupBox("Conversion queue")
        lay = QVBoxLayout(group)

        self._table = QTableWidget(0, len(COLUMN_TITLES))
        self._table.setHorizontalHeaderLabels(COLUMN_TITLES)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.setMinimumHeight(90)
        self._table.verticalHeader().setDefaultSectionSize(34)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(COL_FILE, QHeaderView.Stretch)
        for col in (COL_CODEC, COL_RES, COL_DURATION, COL_EST):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(COL_PROGRESS, QHeaderView.Fixed)
        self._table.setColumnWidth(COL_PROGRESS, 170)
        lay.addWidget(self._table)

        row = QHBoxLayout()
        self._btn_add = QPushButton("Add Files…")
        self._btn_add.clicked.connect(self._choose_files)
        self._btn_remove = QPushButton("Remove Selected")
        self._btn_remove.clicked.connect(self._remove_selected)
        self._btn_clear = QPushButton("Clear All")
        self._btn_clear.clicked.connect(self._clear_all)
        row.addWidget(self._btn_add)
        row.addWidget(self._btn_remove)
        row.addWidget(self._btn_clear)
        row.addStretch(1)
        self._count_label = QLabel("0 files")
        self._count_label.setProperty("dim", True)
        row.addWidget(self._count_label)
        lay.addLayout(row)
        return group

    def _build_options_group(self) -> QGroupBox:
        group = QGroupBox("Output options")
        lay = QVBoxLayout(group)

        # Preset row.
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Quality preset:"))
        self._preset_combo = QComboBox()
        for key in PRESET_ORDER:
            p = PRESETS[key]
            self._preset_combo.addItem(f"{p.label}", userData=key)
        self._preset_combo.setCurrentIndex(PRESET_ORDER.index(DEFAULT_PRESET_KEY))
        self._preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        self._preset_combo.setMinimumWidth(170)
        preset_row.addWidget(self._preset_combo)
        self._preset_desc = QLabel(get_preset(DEFAULT_PRESET_KEY).description)
        self._preset_desc.setProperty("dim", True)
        # Single line; give up width (elide) instead of forcing the window
        # wider or wrapping to a second line.
        self._preset_desc.setSizePolicy(
            QSizePolicy.Ignored, QSizePolicy.Preferred
        )
        preset_row.addWidget(self._preset_desc, stretch=1)
        lay.addLayout(preset_row)

        # Output folder row.
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("Output folder:"))
        self._out_edit = QLineEdit()
        self._out_edit.setPlaceholderText("Choose where converted files are saved…")
        out_row.addWidget(self._out_edit, stretch=1)
        self._btn_browse = QPushButton("Browse…")
        self._btn_browse.clicked.connect(self._choose_output_dir)
        out_row.addWidget(self._btn_browse)
        lay.addLayout(out_row)

        self._subfolder_check = QCheckBox(
            "Save into a 'converted' subfolder next to each original file"
        )
        self._subfolder_check.setChecked(True)
        self._subfolder_check.toggled.connect(self._on_subfolder_toggled)
        lay.addWidget(self._subfolder_check)
        self._on_subfolder_toggled(True)
        return group

    def _build_action_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self._btn_start = QPushButton("Start Conversion")
        self._btn_start.setObjectName("Primary")
        self._btn_start.clicked.connect(self._start)
        self._btn_cancel = QPushButton("Cancel")
        self._btn_cancel.setObjectName("Danger")
        self._btn_cancel.clicked.connect(self._cancel)
        row.addStretch(1)
        row.addWidget(self._btn_cancel)
        row.addWidget(self._btn_start)
        return row

    def _build_progress_row(self) -> QWidget:
        wrap = QWidget()
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        self._overall_bar = QProgressBar()
        self._overall_bar.setValue(0)
        self._status_label = QLabel("Idle")
        self._status_label.setProperty("dim", True)
        lay.addWidget(self._overall_bar)
        lay.addWidget(self._status_label)
        return wrap

    def _build_log(self) -> QWidget:
        wrap = QWidget()
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        label = QLabel("Activity log")
        label.setProperty("dim", True)
        self._log_view = QPlainTextEdit()
        self._log_view.setObjectName("Log")
        self._log_view.setReadOnly(True)
        self._log_view.setFixedHeight(62)
        lay.addWidget(label)
        lay.addWidget(self._log_view)
        return wrap

    # -------------------------------------------------------------- helpers
    def _size_to_screen(self, preferred_w: int, preferred_h: int) -> None:
        """Resize to the preferred size, clamped to ~92% of the usable screen."""
        screen = QApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            preferred_w = min(preferred_w, int(avail.width() * 0.92))
            preferred_h = min(preferred_h, int(avail.height() * 0.92))
        # Respect the window's hard minimum.
        preferred_w = max(preferred_w, self.minimumWidth())
        preferred_h = max(preferred_h, self.minimumHeight())
        self.resize(preferred_w, preferred_h)

    def _log(self, text: str) -> None:
        self._log_view.appendPlainText(text)
        log.info(text)

    def _refresh_banner(self) -> None:
        available = self._tools is not None
        self._banner.setVisible(not available)
        if not available:
            self._banner_label.setText(
                "FFmpeg was not found. Run  python scripts/download_ffmpeg.py  "
                "or install FFmpeg and add it to your PATH, then click "
                "“Re-check FFmpeg”."
            )

    def _recheck_ffmpeg(self) -> None:
        try:
            self._tools = locate_ffmpeg()
            self._log(f"FFmpeg found: {self._tools.version}")
        except FFmpegNotFound as exc:
            QMessageBox.warning(self, "FFmpeg still missing", str(exc))
        self._refresh_banner()
        self._update_buttons()

    def _current_preset_key(self) -> str:
        return self._preset_combo.currentData()

    # --------------------------------------------------------------- files
    def _choose_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select videos to convert",
            str(Path.home()),
            "Videos (*.mov *.MOV *.mp4 *.MP4 *.m4v *.qt);;All files (*.*)",
        )
        if files:
            self.add_files(files)

    def add_files(self, paths: list[str]) -> None:
        if self._converting:
            return
        if self._tools is None:
            # We can still probe using ffprobe only if we have it; without tools
            # we cannot, so prompt the user first.
            QMessageBox.warning(
                self, "FFmpeg required",
                "FFmpeg/ffprobe must be available before adding files.",
            )
            return

        existing = {r.info.path for r in self._rows}
        added = 0
        self.setCursor(Qt.WaitCursor)
        try:
            for raw in paths:
                path = Path(raw).resolve()
                if path in existing:
                    continue
                try:
                    info = probe(path, self._tools.ffprobe)
                except ProbeError as exc:
                    self._log(f"Skipped {path.name}: {exc}")
                    continue
                self._append_row(info)
                existing.add(path)
                added += 1
        finally:
            self.unsetCursor()

        if added:
            self._log(f"Added {added} file(s).")
            if not self._out_edit.text() and self._rows:
                # Seed a sensible default output folder.
                first_parent = self._rows[0].info.path.parent
                self._out_edit.setText(str(first_parent / CONVERTED_SUBFOLDER))
        self._update_counts()
        self._update_buttons()

    def _append_row(self, info: MediaInfo) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)

        name_item = QTableWidgetItem(info.path.name)
        name_item.setToolTip(str(info.path))

        codec = info.video_codec.upper() or "?"
        if not info.supported:
            codec += " ⚠"
        codec_item = QTableWidgetItem(codec)
        if not info.supported:
            codec_item.setToolTip("Unsupported codec - conversion may be skipped.")

        res_item = QTableWidgetItem(f"{info.display_width}×{info.display_height}")
        dur_item = QTableWidgetItem(human_duration(info.duration))

        bar = QProgressBar()
        bar.setValue(0)
        bar.setTextVisible(True)
        bar.setFormat("Ready")
        # Wrap the bar so it has breathing room inside the cell.
        bar_cell = QWidget()
        cell_lay = QHBoxLayout(bar_cell)
        cell_lay.setContentsMargins(8, 7, 8, 7)
        cell_lay.addWidget(bar)

        self._table.setItem(row, COL_FILE, name_item)
        self._table.setItem(row, COL_CODEC, codec_item)
        self._table.setItem(row, COL_RES, res_item)
        self._table.setItem(row, COL_DURATION, dur_item)
        self._table.setItem(row, COL_EST, QTableWidgetItem("-"))
        self._table.setCellWidget(row, COL_PROGRESS, bar_cell)

        self._rows.append(RowItem(info=info, progress=bar))
        self._update_estimate(row)

    def _update_estimate(self, row: int) -> None:
        item = self._rows[row]
        preset = get_preset(self._current_preset_key())
        size = estimate_output_size(item.info, preset)
        est_item = self._table.item(row, COL_EST)
        if est_item is not None:
            est_item.setText(f"≈ {human_size(size)}" if size else "-")

    def _remove_selected(self) -> None:
        if self._converting:
            return
        rows = sorted({idx.row() for idx in self._table.selectedIndexes()}, reverse=True)
        for row in rows:
            self._table.removeRow(row)
            del self._rows[row]
        self._update_counts()
        self._update_buttons()

    def _clear_all(self) -> None:
        if self._converting:
            return
        self._table.setRowCount(0)
        self._rows.clear()
        self._update_counts()
        self._update_buttons()

    def _update_counts(self) -> None:
        n = len(self._rows)
        self._count_label.setText(f"{n} file{'s' if n != 1 else ''}")

    # ------------------------------------------------------------- options
    def _on_preset_changed(self) -> None:
        preset = get_preset(self._current_preset_key())
        self._preset_desc.setText(preset.description)
        for row in range(len(self._rows)):
            self._update_estimate(row)

    def _on_subfolder_toggled(self, checked: bool) -> None:
        self._out_edit.setEnabled(not checked)
        self._btn_browse.setEnabled(not checked)

    def _choose_output_dir(self) -> None:
        start = self._out_edit.text() or str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "Choose output folder", start)
        if folder:
            self._out_edit.setText(folder)

    def _resolve_output_dir(self, info: MediaInfo) -> Path:
        if self._subfolder_check.isChecked():
            return info.path.parent / CONVERTED_SUBFOLDER
        return Path(self._out_edit.text())

    # ------------------------------------------------------------- convert
    def _update_buttons(self) -> None:
        has_files = bool(self._rows)
        ready = has_files and self._tools is not None and not self._converting
        self._btn_start.setEnabled(ready)
        self._btn_cancel.setEnabled(self._converting)
        for btn in (self._btn_add, self._btn_remove, self._btn_clear,
                    self._preset_combo, self._subfolder_check):
            btn.setEnabled(not self._converting)
        editing = not self._converting and not self._subfolder_check.isChecked()
        self._out_edit.setEnabled(editing)
        self._btn_browse.setEnabled(editing)

    def _start(self) -> None:
        if self._converting or self._tools is None or not self._rows:
            return

        if not self._subfolder_check.isChecked() and not self._out_edit.text().strip():
            QMessageBox.warning(self, "No output folder",
                                "Please choose an output folder first.")
            return

        preset = get_preset(self._current_preset_key())
        jobs: list[Job] = []
        used: set[Path] = set()
        skipped = 0
        for item in self._rows:
            if not item.info.supported:
                skipped += 1
                item.progress.setFormat("Unsupported")
                self._set_bar_state(item.progress, "failed")
                continue
            out_dir = self._resolve_output_dir(item.info)
            out_path = converter.unique_output_path(out_dir, item.info.path.stem)
            # Guard against two inputs mapping to the same output this run.
            while out_path in used:
                out_path = converter.unique_output_path(out_dir, item.info.path.stem)
            used.add(out_path)
            item.output_path = out_path
            jobs.append(Job(info=item.info, preset=preset, output_path=out_path))

        if not jobs:
            QMessageBox.information(
                self, "Nothing to convert",
                "None of the queued files use a supported codec.",
            )
            return
        if skipped:
            self._log(f"{skipped} unsupported file(s) will be skipped.")

        # Reset progress on the jobs we are about to run.
        for item in self._rows:
            if item.output_path is not None:
                item.progress.setValue(0)
                item.progress.setFormat("Waiting…")
                self._set_bar_state(item.progress, "normal")

        self._converting = True
        self._overall_bar.setValue(0)
        self._status_label.setText(f"Converting {len(jobs)} file(s)…")
        self._update_buttons()
        self._start_worker(jobs)

    def _start_worker(self, jobs: list[Job]) -> None:
        self._thread = QThread(self)
        self._worker = ConversionWorker(self._tools.ffmpeg, jobs)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.job_started.connect(self._on_job_started)
        self._worker.job_progress.connect(self._on_job_progress)
        self._worker.job_finished.connect(self._on_job_finished)
        self._worker.job_failed.connect(self._on_job_failed)
        self._worker.overall_progress.connect(
            lambda pct: self._overall_bar.setValue(int(pct))
        )
        self._worker.message.connect(self._log)
        self._worker.finished.connect(self._on_all_finished)
        self._thread.start()

    # Map worker rows (index into jobs) back to table rows. Because we skip
    # unsupported files, we look up by matching output_path.
    def _row_for_job(self, job_row: int) -> RowItem | None:
        convertible = [r for r in self._rows if r.output_path is not None]
        if 0 <= job_row < len(convertible):
            return convertible[job_row]
        return None

    def _on_job_started(self, job_row: int, name: str) -> None:
        item = self._row_for_job(job_row)
        if item:
            item.progress.setFormat("Converting… %p%")

    def _on_job_progress(self, job_row: int, pct: float) -> None:
        item = self._row_for_job(job_row)
        if item:
            item.progress.setValue(int(pct))

    def _on_job_finished(self, job_row: int, out_path: str) -> None:
        item = self._row_for_job(job_row)
        if item:
            item.progress.setValue(100)
            item.progress.setFormat("Done")
            self._set_bar_state(item.progress, "done")

    def _on_job_failed(self, job_row: int, message: str) -> None:
        item = self._row_for_job(job_row)
        if item:
            item.progress.setFormat("Failed")
            item.progress.setToolTip(message)
            self._set_bar_state(item.progress, "failed")

    def _on_all_finished(self, completed: int, failed: int) -> None:
        self._converting = False
        self._status_label.setText(
            f"Finished - {completed} converted, {failed} failed."
        )
        self._update_buttons()
        self._teardown_thread()

        if completed and not failed:
            self._offer_open_folder(completed)
        elif failed:
            QMessageBox.warning(
                self, "Completed with errors",
                f"{completed} file(s) converted, {failed} failed.\n"
                "See the log panel for details.",
            )

    def _offer_open_folder(self, completed: int) -> None:
        first = next((r for r in self._rows if r.output_path), None)
        if not first or not first.output_path:
            return
        folder = first.output_path.parent
        resp = QMessageBox.question(
            self, "Conversion complete",
            f"Successfully converted {completed} file(s).\n\nOpen the output folder?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if resp == QMessageBox.Yes:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _cancel(self) -> None:
        if self._worker is not None:
            self._btn_cancel.setEnabled(False)
            self._status_label.setText("Cancelling…")
            self._worker.cancel()

    def _teardown_thread(self) -> None:
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(5000)
            self._thread = None
        self._worker = None

    @staticmethod
    def _set_bar_state(bar: QProgressBar, state: str) -> None:
        bar.setProperty("state", state)
        bar.style().unpolish(bar)
        bar.style().polish(bar)

    # --------------------------------------------------------------- close
    def closeEvent(self, event) -> None:  # noqa: N802
        if self._converting:
            resp = QMessageBox.question(
                self, "Quit while converting?",
                "A conversion is in progress. Cancel it and quit?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if resp != QMessageBox.Yes:
                event.ignore()
                return
            if self._worker is not None:
                self._worker.cancel()
            self._teardown_thread()
        event.accept()
