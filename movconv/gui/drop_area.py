"""A drag-and-drop target that accepts video files and folders."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

# File extensions we accept when dropped.
VIDEO_EXTENSIONS = {".mov", ".mp4", ".m4v", ".qt"}


class DropArea(QFrame):
    """A compact dashed panel; emits :attr:`filesDropped` with file paths."""

    filesDropped = Signal(list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("DropArea")
        self.setAcceptDrops(True)
        self.setFixedHeight(72)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(22, 8, 22, 8)
        layout.setSpacing(14)

        icon = QLabel("\U0001F4E5")  # inbox tray emoji
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("font-size: 26px;")

        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        headline = QLabel("Drag & drop videos here")
        headline.setObjectName("DropHeadline")
        hint = QLabel("Drop .MOV files or a folder - or use “Add Files…” below")
        hint.setObjectName("DropHint")
        text_box.addWidget(headline)
        text_box.addWidget(hint)

        layout.addWidget(icon)
        layout.addLayout(text_box)
        layout.addStretch(1)

    # -- drag events -----------------------------------------------------
    def _set_active(self, active: bool) -> None:
        self.setProperty("dragActive", active)
        # Re-polish so the property-based stylesheet updates immediately.
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._set_active(True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self._set_active(False)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        self._set_active(False)
        paths: list[str] = []
        for url in event.mimeData().urls():
            if not url.isLocalFile():
                continue
            p = Path(url.toLocalFile())
            if p.is_dir():
                paths.extend(str(f) for f in self._scan_folder(p))
            elif p.suffix.lower() in VIDEO_EXTENSIONS:
                paths.append(str(p))
        if paths:
            self.filesDropped.emit(paths)
        event.acceptProposedAction()

    @staticmethod
    def _scan_folder(folder: Path) -> list[Path]:
        """Recursively collect supported video files inside *folder*."""
        found: list[Path] = []
        for ext in VIDEO_EXTENSIONS:
            found.extend(folder.rglob(f"*{ext}"))
            found.extend(folder.rglob(f"*{ext.upper()}"))
        # De-duplicate (case-insensitive globs can overlap) and sort.
        return sorted({f.resolve() for f in found if f.is_file()})
