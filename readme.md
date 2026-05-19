# DNG → JPG Converter + JPG Bulk Resizer

A lightweight Windows tool for converting iPhone ProRAW (`.dng`) photos to `.jpg`, and for batch-shrinking JPGs under a file size limit.

---

## Quick Start

### Requirements

- **Python 3.9+** — [download here](https://www.python.org/downloads/) (check "Add Python to PATH" during install)
- Two packages installed automatically on first run: `rawpy`, `Pillow`

### Option A: Double-click

Double-click **RUN_CONVERTER.bat** — installs dependencies and opens the GUI.

### Option B: Terminal

```powershell
pip install rawpy Pillow
python dng_to_jpg_converter.py
```

---

## Features

### 1. DNG → JPG Conversion

Extracts the iPhone's embedded processed preview (preserving Smart HDR, Deep Fusion, Night Mode, etc.) and saves it as a standard JPEG with correct orientation.

### 2. JPG Bulk Resizer

Select a folder of JPGs and shrink them all under a target size (default 2 MB). The tool finds the highest possible quality that fits, only scaling dimensions down as a last resort.

---

## GUI Usage

Run with no arguments to open the graphical interface:

```
python dng_to_jpg_converter.py
```

Two tabs at the top:

- **DNG → JPG** — browse for DNG files/folder, set quality, convert
- **Resize JPGs** — browse for JPG files/folder, set max file size (0.5–10 MB), resize

---

## CLI Usage

### Convert DNG files

```powershell
python dng_to_jpg_converter.py IMG_0042.dng             # one file
python dng_to_jpg_converter.py *.dng                     # all in current dir
python dng_to_jpg_converter.py *.dng -q 85               # custom quality
python dng_to_jpg_converter.py C:\Photos\DCIM -o ./out   # folder in, folder out
```

| Flag | Description | Default |
|------|-------------|---------|
| `-o`, `--output` | Output directory | Same as source |
| `-q`, `--quality` | JPEG quality (50–100) | 95 |

### Resize JPG files

```powershell
python dng_to_jpg_converter.py resize ./photos           # shrink to < 2 MB
python dng_to_jpg_converter.py resize ./photos -m 1      # shrink to < 1 MB
python dng_to_jpg_converter.py resize *.jpg -o ./small   # output to separate folder
```

| Flag | Description | Default |
|------|-------------|---------|
| `-o`, `--output` | Output directory | Overwrites in place |
| `-m`, `--max-mb` | Max file size in MB | 2.0 |

### Show help

```
python dng_to_jpg_converter.py --help
```

---

## How It Works

### DNG Conversion

iPhone ProRAW `.dng` files embed a full-resolution JPEG preview with all computational photography applied. The tool extracts that preview, applies EXIF orientation, and re-saves at your chosen quality.

For non-iPhone DNG files (cameras, Adobe DNG), it falls back to raw processing with camera white balance.

### JPG Resizing

For each image over the size limit:

1. Binary-searches JPEG quality (30–95) to find the highest quality that fits.
2. If even quality 30 is too large, scales the image down in steps (90%, 80%, 70%…) and repeats the quality search.
3. Images already under the limit are copied as-is.

---

## File Structure

```
dng_to_jpg_converter.py   # Main script — GUI + CLI
RUN_CONVERTER.bat          # Windows launcher
README.md                  # This file
```

---

## Troubleshooting

**`*.dng` or `*.jpg` matches nothing on PowerShell**
The script handles glob expansion internally. Make sure you're running from the folder that contains the files, or pass a folder path instead.

**Images look washed out**
You may have an older version that used raw processing. Re-download the latest script.

**Images are rotated**
Same — older versions didn't apply EXIF orientation. Current version fixes this.

**`rawpy` fails to install**
Try: `pip install rawpy --only-binary :all:`

---

## License

MIT — do whatever you want with it.