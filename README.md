# MovToMp4 - iPhone .MOV → Android .MP4 Converter

A modern desktop app that converts iPhone videos (HEVC/H.265 **or** H.264 in a
`.MOV` container) into universally compatible **MP4** files using the **H.264
(AVC)** video codec and **AAC** audio - the combination that plays on virtually
every Android device.

Built with **Python + PySide6 (Qt)** and powered by **FFmpeg**.

![queue → convert → done](https://img.shields.io/badge/Python-3.9%2B-blue) ![Qt](https://img.shields.io/badge/GUI-PySide6-41cd52) ![engine](https://img.shields.io/badge/engine-FFmpeg-007808)

---

## Features

- 🎞️ **HEVC & H.264 input** - handles both iPhone recording formats.
- 📱 **Android-safe output** - H.264 High profile, `yuv420p` 8-bit, AAC stereo,
  `+faststart` for instant playback and progressive streaming.
- 🔍 **Automatic codec detection** - unsupported codecs are flagged and skipped
  with a clear warning instead of failing silently.
- 🧭 **Orientation preserved** - FFmpeg auto-rotates so portrait videos stay
  upright on Android; other metadata (creation time, GPS) is copied.
- 🖱️ **Drag & drop** - drop files *or* whole folders (scanned recursively).
- 📦 **Batch conversion** - queue as many files as you like.
- 🎚️ **Quality presets** - High Quality / Balanced / Small File Size.
- 📐 **Estimated output size** - shown per file, updates with the preset.
- 📊 **Live progress** - per-file and overall progress bars.
- 🧵 **Never freezes** - conversions run on a background thread.
- 🗂️ **Choose output** - a `converted/` subfolder next to each original, or a
  single folder you pick.
- 🧱 **Handles huge files** - FFmpeg streams data, so 10 GB+ inputs are fine.
- 📝 **Logging & error handling** - rotating log file + in-app log panel.
- 🚀 **Standalone build** - package to a single executable with PyInstaller.

---

## Project structure

```
iphone video/
├── run.py                     # Dev entry point (python run.py)
├── build.py                   # One-command PyInstaller build
├── MovToMp4.spec              # PyInstaller spec (bundles bin/)
├── requirements.txt
├── README.md
├── scripts/
│   └── download_ffmpeg.py     # Fetch a static FFmpeg into bin/
├── bin/                       # (created) bundled ffmpeg + ffprobe
└── movconv/                   # Application package
    ├── app.py                 # QApplication bootstrap
    ├── __main__.py            # python -m movconv
    ├── core/                  # Conversion engine (no Qt dependencies)
    │   ├── ffmpeg_locator.py  # Find ffmpeg/ffprobe
    │   ├── probe.py           # ffprobe → MediaInfo
    │   ├── presets.py         # Quality presets
    │   ├── estimator.py       # Size/duration estimation + formatting
    │   └── converter.py       # Build & run FFmpeg, parse progress
    ├── gui/                   # PySide6 user interface
    │   ├── main_window.py     # Main window & queue
    │   ├── drop_area.py       # Drag-and-drop widget
    │   ├── worker.py          # QThread conversion worker
    │   └── styles.py          # Dark theme (QSS)
    └── utils/
        ├── logging_config.py  # Logging setup
        └── resources.py       # Path handling (source & PyInstaller)
```

The `core/` package is intentionally free of any Qt imports, so the conversion
engine can be reused from a CLI, tests, or a server without a GUI.

---

## Installation

### 1. Prerequisites
- **Python 3.9+**
- **FFmpeg** (`ffmpeg` + `ffprobe`) - see below.

### 2. Get the code & dependencies
```bash
cd "iphone video"
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Get FFmpeg (choose one)
**Option A - bundled (recommended):**
```bash
python scripts/download_ffmpeg.py
```
Downloads a static build into `bin/`. The app finds it automatically and it
gets bundled into standalone builds.

**Option B - system install:**
- **Windows:** `winget install Gyan.FFmpeg` (or download from ffmpeg.org)
- **macOS:** `brew install ffmpeg`
- **Linux:** `sudo apt install ffmpeg` (or your distro's package)

Make sure `ffmpeg` and `ffprobe` are on your `PATH`.

**Option C — custom location:** set `MOVCONV_FFMPEG_DIR` to the folder that
contains `ffmpeg`/`ffprobe`.

### 4. Run
```bash
python run.py
```

---

## How FFmpeg is integrated

FFmpeg is located at runtime in this order (`movconv/core/ffmpeg_locator.py`):

1. `MOVCONV_FFMPEG_DIR` environment variable.
2. The bundled `bin/` folder (also works inside a PyInstaller bundle).
3. The system `PATH`.

Each conversion runs a command equivalent to:

```bash
ffmpeg -y -hide_banner -loglevel error -i INPUT.mov \
  [-vf scale=-2:1080]            # only for "Small File Size"
  -c:v libx264 -preset PRESET -crf CRF \
  -pix_fmt yuv420p -profile:v high -level 4.2 \
  -c:a aac -b:a 192k -ac 2 \
  -map_metadata 0 -movflags +faststart \
  -progress pipe:1 -nostats \
  OUTPUT.mp4
```

Progress is parsed from the machine-readable `-progress pipe:1` stream and
converted to a percentage using the duration reported by `ffprobe`.

### Quality presets

| Preset            | CRF | x264 preset | Audio   | Notes                       |
|-------------------|-----|-------------|---------|-----------------------------|
| High Quality      | 18  | slow        | 256 kbps| Near-lossless, largest      |
| Balanced (default)| 22  | medium      | 192 kbps| Recommended                 |
| Small File Size   | 27  | medium      | 128 kbps| Downscaled to 1080p         |

---

## Building a standalone executable

```bash
python scripts/download_ffmpeg.py   # so FFmpeg is bundled into the app
python build.py                     # wraps PyInstaller + MovToMp4.spec
```

The executable appears in `dist/`:

- **Windows:** `dist/MovToMp4.exe`
- **macOS:** `dist/MovToMp4` (see note below)
- **Linux:** `dist/MovToMp4`

> Builds are **not** cross-platform — build on each target OS.

### Platform notes
- **Windows:** produces a windowed `.exe` (no console). To add an icon, drop an
  `.ico` file in `assets/` and uncomment the `icon=` line in `MovToMp4.spec`.
- **macOS:** to get a `.app` bundle, add `app = BUNDLE(exe, name='MovToMp4.app',
  ...)` to the spec, or run PyInstaller with `--windowed`. You may need to
  ad-hoc code-sign: `codesign --deep -s - dist/MovToMp4.app`.
- **Linux:** the resulting binary is dynamically linked against common system
  libraries; build on the oldest distro you intend to support for best
  portability. Qt may require `libxcb`/`xcb-cursor` packages on minimal systems.

---

## Troubleshooting

| Problem | Fix |
|--------|-----|
| "FFmpeg was not found" banner | Run `python scripts/download_ffmpeg.py` or install FFmpeg on PATH, then click **Re-check FFmpeg**. |
| A file shows **Unsupported ⚠** | Its video codec isn't H.264/HEVC. Re-export it or convert manually. |
| Output won't play on an old device | Use the **Balanced** or **Small** preset (High profile can be too demanding for very old hardware). |
| Where are the logs? | Windows `%LOCALAPPDATA%\MovToMp4\movtomp4.log`, macOS `~/Library/Application Support/MovToMp4/`, Linux `~/.local/share/MovToMp4/`. |

---

## License

Provided as-is for personal and commercial use. FFmpeg is a separate project
distributed under its own (LGPL/GPL) license — see https://ffmpeg.org/legal.html.
