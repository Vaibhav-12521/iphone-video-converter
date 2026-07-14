"""Application entry point: wire up logging, FFmpeg, and the Qt window."""
from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from movconv import __app_name__, __version__
from movconv.core.ffmpeg_locator import FFmpegNotFound, locate_ffmpeg
from movconv.gui.main_window import MainWindow
from movconv.utils.logging_config import setup_logging

log = logging.getLogger(__name__)


def main() -> int:
    setup_logging()
    log.info("Starting %s v%s", __app_name__, __version__)

    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setApplicationDisplayName(f"{__app_name__} {__version__}")

    # Try to locate FFmpeg up front. If it is missing we still open the window
    # (with a warning banner) so the user can fix it and click "Re-check".
    tools = None
    try:
        tools = locate_ffmpeg()
    except FFmpegNotFound as exc:
        log.warning("FFmpeg not found at startup: %s", exc)
        QMessageBox.warning(None, "FFmpeg not found", str(exc))
    except Exception:  # pragma: no cover
        log.exception("Unexpected error while locating FFmpeg")

    try:
        window = MainWindow(tools)
        window.show()
        return app.exec()
    except Exception:  # pragma: no cover
        log.exception("Fatal error")
        QMessageBox.critical(
            None, "Fatal error",
            "An unexpected error occurred. See the log file for details.",
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
