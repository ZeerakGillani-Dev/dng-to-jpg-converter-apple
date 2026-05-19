"""
DNG → JPG Converter
Convert iPhone ProRAW / DNG photos to JPG — GUI or terminal.

Requirements (install once):
    pip install rawpy Pillow

Usage:
    python dng_to_jpg_converter.py                     # launch GUI
    python dng_to_jpg_converter.py photo.dng            # convert one file
    python dng_to_jpg_converter.py *.dng -q 90          # batch, quality 90
    python dng_to_jpg_converter.py ./photos -o ./jpgs   # folder in, folder out
"""

import glob
import os
import sys
import threading
from pathlib import Path

# ── Dependency check ──────────────────────────────────────────────────────────
try:
    import rawpy
    from PIL import Image
except ImportError:
    import subprocess
    print("Installing required packages: rawpy, Pillow ...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "rawpy", "Pillow"])
    import rawpy
    from PIL import Image

# tkinter is only needed for GUI mode — import lazily
_tk_available = False
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    _tk_available = True
except ImportError:
    pass


# ══════════════════════════════════════════════════════════════════════════════
#  CORE CONVERSION  — extracts iPhone's embedded preview (keeps Smart HDR etc.)
# ══════════════════════════════════════════════════════════════════════════════

import io

def convert_one(src_path: str, dst_path: str, quality: int = 95):
    """
    Convert a single DNG to JPG.

    Strategy:
      1. Try extracting the embedded JPEG preview the iPhone bakes in.
         This preserves all computational photography (Deep Fusion, Smart HDR,
         Night Mode tone-mapping, etc.) and is the "real" photo.
      2. Fall back to rawpy post-processing only if no preview exists
         (rare — mainly non-iPhone DNG files).
    """
    with rawpy.imread(src_path) as raw:
        try:
            thumb = raw.extract_thumb()
            if thumb.format == rawpy.ThumbFormat.JPEG:
                # Embedded JPEG — decode, optionally re-save at chosen quality
                img = Image.open(io.BytesIO(thumb.data))
                img = img.convert("RGB")          # strip alpha if present
            elif thumb.format == rawpy.ThumbFormat.BITMAP:
                img = Image.fromarray(thumb.data)
            else:
                raise rawpy.LibRawNoThumbnailError
        except (rawpy.LibRawNoThumbnailError, rawpy.LibRawError):
            # No embedded preview → full raw develop
            rgb = raw.postprocess(
                use_camera_wb=True,
                no_auto_bright=False,
                output_bps=8,
                half_size=False,
            )
            img = Image.fromarray(rgb)

    # Apply EXIF orientation (iPhones store rotation as a tag, not in pixels)
    from PIL import ImageOps
    img = ImageOps.exif_transpose(img)

    img.save(dst_path, "JPEG", quality=quality, subsampling=0)


# ══════════════════════════════════════════════════════════════════════════════
#  CLI MODE
# ══════════════════════════════════════════════════════════════════════════════

def cli_convert(inputs, output_dir=None, quality=95):
    """Convert DNG files from the command line (no GUI needed)."""

    # Gather all .dng files (expand globs for Windows where the shell doesn't)
    files: list[str] = []
    for raw in inputs:
        expanded = glob.glob(raw, recursive=True)
        if not expanded:
            expanded = [raw]          # not a glob, treat as literal path
        for item in expanded:
            p = Path(item)
            if p.is_dir():
                files.extend(sorted(str(f) for f in p.rglob("*") if f.suffix.lower() == ".dng"))
            elif p.suffix.lower() == ".dng" and p.exists():
                files.append(str(p))
            elif not p.exists():
                print(f"  [!] File not found: {p}")
            else:
                print(f"  [!] Skipping (not a .dng): {p}")

    if not files:
        print("  [X] No .dng files found.")
        sys.exit(1)

    print()
    print("  +======================================+")
    print("  |       DNG -> JPG  Converter          |")
    print("  +======================================+")
    print(f"\n  Files:   {len(files)}")
    print(f"  Quality: {quality}%")
    print(f"  Output:  {output_dir or 'same as source'}\n")
    print("  ----------------------------------------")

    success, errors = 0, []
    for i, fpath in enumerate(files, 1):
        name = os.path.basename(fpath)
        out_dir = output_dir or os.path.dirname(fpath) or "."
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, Path(fpath).stem + ".jpg")

        try:
            convert_one(fpath, out_path, quality)
            print(f"  [OK]  [{i}/{len(files)}] {name}  ->  {out_path}")
            success += 1
        except Exception as exc:
            print(f"  [FAIL] [{i}/{len(files)}] {name}  ->  {exc}")
            errors.append(name)

    print("  ----------------------------------------")
    print(f"  Done: {success}/{len(files)} converted", end="")
    if errors:
        print(f"  ({len(errors)} failed)")
    else:
        print("  All good!")
    print()


# ══════════════════════════════════════════════════════════════════════════════
#  GUI MODE
# ══════════════════════════════════════════════════════════════════════════════

BG           = "#1a1a2e"
BG_CARD      = "#16213e"
BG_INPUT     = "#0f3460"
ACCENT       = "#e94560"
ACCENT_HOVER = "#ff6b81"
TEXT         = "#eaeaea"
TEXT_DIM     = "#8a8a9a"
FONT_TITLE   = ("Segoe UI", 22, "bold")
FONT_BODY    = ("Segoe UI", 11)
FONT_SMALL   = ("Segoe UI", 9)
FONT_BTN     = ("Segoe UI", 11, "bold")


def launch_gui():
    """Build and run the tkinter GUI."""

    class DNGConverter(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title("DNG -> JPG Converter")
            self.configure(bg=BG)
            self.resizable(False, False)
            self.geometry("680x720")
            self.files: list[str] = []
            self.output_dir = ""
            self.quality = tk.IntVar(value=95)
            self.converting = False
            self._build_ui()
            self._centre_window()

        def _build_ui(self):
            header = tk.Frame(self, bg=BG)
            header.pack(fill="x", padx=28, pady=(24, 0))
            tk.Label(header, text="DNG -> JPG", font=FONT_TITLE, bg=BG, fg=ACCENT).pack(side="left")
            tk.Label(header, text="iPhone Raw Photo Converter", font=("Segoe UI", 10), bg=BG, fg=TEXT_DIM).pack(side="left", padx=(12, 0), pady=(8, 0))

            card1 = self._card("Step 1: Select DNG Files")
            btn_frame = tk.Frame(card1, bg=BG_CARD)
            btn_frame.pack(fill="x", pady=(4, 0))
            self._accent_btn(btn_frame, "Browse Files...", self._browse_files).pack(side="left")
            self._accent_btn(btn_frame, "Browse Folder...", self._browse_folder).pack(side="left", padx=(10, 0))
            self.file_label = tk.Label(card1, text="No files selected", font=FONT_SMALL, bg=BG_CARD, fg=TEXT_DIM, anchor="w")
            self.file_label.pack(fill="x", pady=(8, 0))
            list_frame = tk.Frame(card1, bg=BG_INPUT, bd=0, highlightthickness=1, highlightbackground="#2a2a4a")
            list_frame.pack(fill="both", expand=True, pady=(8, 0))
            self.file_listbox = tk.Listbox(list_frame, bg=BG_INPUT, fg=TEXT, font=FONT_SMALL, selectbackground=ACCENT, selectforeground="white", bd=0, highlightthickness=0, height=6)
            scroll = tk.Scrollbar(list_frame, command=self.file_listbox.yview)
            self.file_listbox.config(yscrollcommand=scroll.set)
            self.file_listbox.pack(side="left", fill="both", expand=True, padx=4, pady=4)
            scroll.pack(side="right", fill="y")

            card2 = self._card("Step 2: Output Settings")
            row1 = tk.Frame(card2, bg=BG_CARD)
            row1.pack(fill="x", pady=(4, 0))
            self._accent_btn(row1, "Output Folder...", self._browse_output).pack(side="left")
            self.out_label = tk.Label(row1, text="Same as source", font=FONT_SMALL, bg=BG_CARD, fg=TEXT_DIM, anchor="w")
            self.out_label.pack(side="left", padx=(12, 0))
            q_frame = tk.Frame(card2, bg=BG_CARD)
            q_frame.pack(fill="x", pady=(12, 0))
            tk.Label(q_frame, text="JPG Quality:", font=FONT_BODY, bg=BG_CARD, fg=TEXT).pack(side="left")
            self.q_val_label = tk.Label(q_frame, text="95%", font=("Segoe UI", 11, "bold"), bg=BG_CARD, fg=ACCENT, width=4)
            self.q_val_label.pack(side="right")
            style = ttk.Style()
            style.theme_use("default")
            style.configure("Accent.Horizontal.TScale", troughcolor=BG_INPUT, background=ACCENT, sliderthickness=18)
            self.slider = ttk.Scale(q_frame, from_=50, to=100, variable=self.quality, orient="horizontal", style="Accent.Horizontal.TScale", command=self._update_quality_label)
            self.slider.pack(side="left", fill="x", expand=True, padx=(12, 8))

            card3 = self._card("Step 3: Convert", pad_bottom=16)
            style.configure("TProgressbar", troughcolor=BG_INPUT, background=ACCENT, thickness=10)
            self.progress = ttk.Progressbar(card3, mode="determinate", length=400)
            self.progress.pack(fill="x", pady=(4, 8))
            self.status_label = tk.Label(card3, text="Ready", font=FONT_SMALL, bg=BG_CARD, fg=TEXT_DIM, anchor="w")
            self.status_label.pack(fill="x")
            self.convert_btn = self._accent_btn(card3, "Convert All", self._start_convert, big=True)
            self.convert_btn.pack(pady=(10, 0))

        def _card(self, title, pad_bottom=4):
            wrapper = tk.Frame(self, bg=BG)
            wrapper.pack(fill="x", padx=28, pady=(16, pad_bottom))
            tk.Label(wrapper, text=title, font=("Segoe UI", 12, "bold"), bg=BG, fg=TEXT).pack(anchor="w", pady=(0, 6))
            card = tk.Frame(wrapper, bg=BG_CARD, bd=0, highlightthickness=1, highlightbackground="#2a2a4a")
            card.pack(fill="both", expand=True, ipady=10, ipadx=14)
            return card

        def _accent_btn(self, parent, text, command, big=False):
            btn = tk.Button(parent, text=text, font=FONT_BTN if big else FONT_BODY, bg=ACCENT, fg="white", activebackground=ACCENT_HOVER, activeforeground="white", bd=0, cursor="hand2", padx=18 if big else 12, pady=8 if big else 4, command=command)
            btn.bind("<Enter>", lambda e: btn.config(bg=ACCENT_HOVER))
            btn.bind("<Leave>", lambda e: btn.config(bg=ACCENT))
            return btn

        def _centre_window(self):
            self.update_idletasks()
            w, h = self.winfo_width(), self.winfo_height()
            x = (self.winfo_screenwidth() - w) // 2
            y = (self.winfo_screenheight() - h) // 2
            self.geometry(f"+{x}+{y}")

        def _update_quality_label(self, _=None):
            self.q_val_label.config(text=f"{self.quality.get()}%")

        def _browse_files(self):
            paths = filedialog.askopenfilenames(title="Select DNG files", filetypes=[("DNG files", "*.dng *.DNG"), ("All files", "*.*")])
            if paths:
                self.files = list(paths)
                self._refresh_file_list()

        def _browse_folder(self):
            folder = filedialog.askdirectory(title="Select folder with DNG files")
            if folder:
                found = sorted(str(p) for p in Path(folder).rglob("*") if p.suffix.lower() == ".dng")
                if not found:
                    messagebox.showinfo("No DNG files", "No .dng files found in that folder.")
                    return
                self.files = found
                self._refresh_file_list()

        def _browse_output(self):
            folder = filedialog.askdirectory(title="Select output folder")
            if folder:
                self.output_dir = folder
                self.out_label.config(text=folder)

        def _refresh_file_list(self):
            self.file_listbox.delete(0, "end")
            for f in self.files:
                self.file_listbox.insert("end", f"  {os.path.basename(f)}")
            n = len(self.files)
            self.file_label.config(text=f"{n} file{'s' if n != 1 else ''} selected")

        def _start_convert(self):
            if self.converting:
                return
            if not self.files:
                messagebox.showwarning("No files", "Please select DNG files first.")
                return
            self.converting = True
            self.convert_btn.config(state="disabled", bg=TEXT_DIM)
            threading.Thread(target=self._convert_worker, daemon=True).start()

        def _convert_worker(self):
            total = len(self.files)
            success, errors = 0, []
            for i, path in enumerate(self.files, 1):
                name = os.path.basename(path)
                self._set_status(f"Converting {i}/{total}: {name}")
                self.progress["value"] = (i - 1) / total * 100
                try:
                    out_dir = self.output_dir or os.path.dirname(path)
                    out_path = os.path.join(out_dir, Path(path).stem + ".jpg")
                    convert_one(path, out_path, self.quality.get())
                    success += 1
                except Exception as exc:
                    errors.append(f"{name}: {exc}")
            self.progress["value"] = 100
            self._set_status(f"Done: {success}/{total} converted")
            self.converting = False
            self.convert_btn.config(state="normal", bg=ACCENT)
            if errors:
                messagebox.showwarning("Some files failed", "\n".join(errors[:15]) + ("\n..." if len(errors) > 15 else ""))
            else:
                messagebox.showinfo("Success", f"All {success} file(s) converted to JPG!")

        def _set_status(self, text):
            self.after(0, lambda: self.status_label.config(text=text))
            self.after(0, self.update_idletasks)

    app = DNGConverter()
    app.mainloop()


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="DNG -> JPG Converter  |  iPhone ProRAW / DNG photos to JPG",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python dng_to_jpg_converter.py                          Open the GUI
  python dng_to_jpg_converter.py IMG_0042.dng             Convert one file
  python dng_to_jpg_converter.py *.dng                    Convert all DNG in current dir
  python dng_to_jpg_converter.py *.dng -q 85              Batch convert at 85%% quality
  python dng_to_jpg_converter.py ./DCIM -o ./converted    Folder in -> folder out
  python dng_to_jpg_converter.py ./DCIM -o ./out -q 90    Folder + custom quality + output
        """,
    )
    parser.add_argument("files", nargs="*", help="DNG files or folders to convert (omit to open GUI)")
    parser.add_argument("-o", "--output", default=None, help="Output directory (default: same as source)")
    parser.add_argument("-q", "--quality", type=int, default=95, help="JPG quality 50-100 (default: 95)")

    args = parser.parse_args()

    if args.files:
        cli_convert(args.files, args.output, args.quality)
    else:
        if not _tk_available:
            print("  [X] GUI needs tkinter (comes with Python on Windows).")
            print("      Use CLI mode:  python dng_to_jpg_converter.py photo.dng")
            print("      Run with --help for all options.")
            sys.exit(1)
        launch_gui()