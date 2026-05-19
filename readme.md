# DNG → JPG Converter

A lightweight Windows tool for converting iPhone ProRAW (`.dng`) photos to `.jpg`. Works from the GUI or the command line.

iPhone ProRAW files are great for editing, but at 25–50 MB each they're impractical for sharing, uploading, or archiving. This tool extracts the iPhone's own processed preview — preserving Smart HDR, Deep Fusion, Night Mode, and all computational photography — and saves it as a standard JPEG.

---

## Quick Start

### Requirements

- **Python 3.9+** — [download here](https://www.python.org/downloads/) (check "Add Python to PATH" during install)
- Two packages installed automatically on first run: `rawpy`, `Pillow`

### Option A: Double-click

1. Put `dng_to_jpg_converter.py` and `RUN_CONVERTER.bat` in the same folder.
2. Double-click **RUN_CONVERTER.bat**. It installs dependencies and opens the GUI.

### Option B: Terminal

```powershell
pip install rawpy Pillow
python dng_to_jpg_converter.py IMG_0042.dng
```

---

## Usage

### GUI Mode

Run with no arguments to open the graphical interface:

```
python dng_to_jpg_converter.py
```

Three steps: browse for files → pick output folder and quality → hit Convert.

### CLI Mode

Pass files or folders as arguments:

```powershell
# Single file
python dng_to_jpg_converter.py IMG_0042.dng

# All DNG files in current directory
python dng_to_jpg_converter.py *.dng

# Entire folder (scans recursively)
python dng_to_jpg_converter.py C:\Users\You\DCIM

# Custom output folder + quality
python dng_to_jpg_converter.py *.dng -o ./converted -q 85
```

### CLI Options

| Flag | Description | Default |
|------|-------------|---------|
| `files` | DNG files, glob patterns, or folders | *(opens GUI if omitted)* |
| `-o`, `--output` | Output directory | Same as source file |
| `-q`, `--quality` | JPEG quality (50–100) | 95 |
| `-h`, `--help` | Show help and examples | |

---

## How It Works

iPhone ProRAW `.dng` files embed a full-resolution JPEG preview that includes all of the iPhone's computational photography processing. Rather than re-developing the raw sensor data (which loses Smart HDR, Deep Fusion, etc.), this tool:

1. **Extracts the embedded JPEG preview** from the DNG — this is the photo as the iPhone intended it.
2. **Applies EXIF orientation** so portrait/landscape rotation is correct.
3. **Re-saves at your chosen quality** as a standard `.jpg`.

If a DNG has no embedded preview (e.g. camera DNGs, Adobe DNGs), it falls back to full raw processing with camera white balance.

---

## File Structure

```
dng_to_jpg_converter.py   # Main script — GUI + CLI
RUN_CONVERTER.bat          # Windows launcher (installs deps, opens GUI)
```

---

## Troubleshooting

**`*.dng` converts 0 files or fails with I/O error**
PowerShell doesn't expand `*.dng` like bash. This is handled in the script, but make sure you're running from the folder that contains your DNG files, or pass the full path.

**Images look washed out or wrong colors**
You may be using an older version that used raw processing instead of preview extraction. Re-download and replace the script.

**Images are rotated sideways**
Same as above — older versions didn't apply EXIF orientation. The current version fixes this.

**`rawpy` fails to install**
On some systems you may need the Visual C++ Build Tools. Try:
```
pip install rawpy --only-binary :all:
```

---

## License

MIT — do whatever you want with it.