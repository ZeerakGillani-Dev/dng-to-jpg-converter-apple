"""
DNG → JPG Converter  +  JPG Bulk Resizer
Convert iPhone ProRAW / DNG photos to JPG, and shrink JPGs under a size limit.

Requirements (install once):
    pip install rawpy Pillow

Usage:
    python dng_to_jpg_converter.py                            # launch GUI
    python dng_to_jpg_converter.py photo.dng                   # convert one DNG
    python dng_to_jpg_converter.py *.dng -q 90                 # batch DNG convert
    python dng_to_jpg_converter.py resize ./photos             # shrink JPGs to < 2 MB
    python dng_to_jpg_converter.py resize ./photos -m 1        # shrink to < 1 MB
"""

import glob
import io
import os
import sys
import threading
from pathlib import Path

# ── Dependency check ──────────────────────────────────────────────────────────
try:
    import rawpy
    from PIL import Image, ImageOps
except ImportError:
    import subprocess
    print("Installing required packages: rawpy, Pillow ...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "rawpy", "Pillow"])
    import rawpy
    from PIL import Image, ImageOps

# tkinter — only needed for GUI mode
_tk_available = False
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    _tk_available = True
except ImportError:
    pass


# ══════════════════════════════════════════════════════════════════════════════
#  CORE: DNG → JPG
# ══════════════════════════════════════════════════════════════════════════════

def convert_one(src_path: str, dst_path: str, quality: int = 95):
    """Convert a single DNG to JPG, extracting iPhone's embedded preview."""
    with rawpy.imread(src_path) as raw:
        try:
            thumb = raw.extract_thumb()
            if thumb.format == rawpy.ThumbFormat.JPEG:
                img = Image.open(io.BytesIO(thumb.data)).convert("RGB")
            elif thumb.format == rawpy.ThumbFormat.BITMAP:
                img = Image.fromarray(thumb.data)
            else:
                raise rawpy.LibRawNoThumbnailError
        except (rawpy.LibRawNoThumbnailError, rawpy.LibRawError):
            rgb = raw.postprocess(use_camera_wb=True, no_auto_bright=False, output_bps=8)
            img = Image.fromarray(rgb)

    img = ImageOps.exif_transpose(img)
    img.save(dst_path, "JPEG", quality=quality, subsampling=0)


# ══════════════════════════════════════════════════════════════════════════════
#  CORE: RESIZE JPG TO FIT UNDER A SIZE LIMIT
# ══════════════════════════════════════════════════════════════════════════════

def _jpg_size(img, quality):
    """Return the byte size of img if saved as JPEG at the given quality."""
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality, subsampling=0)
    return buf.tell()


def resize_one(src_path: str, dst_path: str, max_bytes: int = 2 * 1024 * 1024):
    """
    Re-save a JPG so it's under max_bytes.

    Strategy (preserves as much quality as possible):
      1. Open the image and fix EXIF orientation.
      2. Try quality 95 → if already small enough, done.
      3. Binary-search quality (30–95) to find the highest quality under limit.
      4. If quality 30 is still too big, scale the image down in 10% steps
         and repeat the quality search.

    Returns (final_size_bytes, was_resized_bool).
    """
    img = Image.open(src_path).convert("RGB")
    img = ImageOps.exif_transpose(img)

    src_size = os.path.getsize(src_path)
    if src_size <= max_bytes:
        # Already under limit — just copy (or re-save to fix orientation)
        img.save(dst_path, "JPEG", quality=95, subsampling=0)
        final = os.path.getsize(dst_path)
        return final, False

    def best_quality(image, lo=30, hi=95):
        """Binary-search the highest quality that fits under max_bytes."""
        # Quick check: even lowest quality too big?
        if _jpg_size(image, lo) > max_bytes:
            return None
        # Quick check: highest quality already fits?
        if _jpg_size(image, hi) <= max_bytes:
            return hi
        best = lo
        while lo <= hi:
            mid = (lo + hi) // 2
            if _jpg_size(image, mid) <= max_bytes:
                best = mid
                lo = mid + 1
            else:
                hi = mid - 1
        return best

    # Try without resizing first
    q = best_quality(img)
    if q is not None:
        img.save(dst_path, "JPEG", quality=q, subsampling=0)
        return os.path.getsize(dst_path), True

    # Scale down until it fits
    w, h = img.size
    for scale in [0.90, 0.80, 0.70, 0.60, 0.50, 0.40, 0.30, 0.20]:
        new_w, new_h = int(w * scale), int(h * scale)
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        q = best_quality(resized)
        if q is not None:
            resized.save(dst_path, "JPEG", quality=q, subsampling=0)
            return os.path.getsize(dst_path), True

    # Last resort: tiny image at minimum quality
    resized = img.resize((int(w * 0.15), int(h * 0.15)), Image.LANCZOS)
    resized.save(dst_path, "JPEG", quality=30, subsampling=0)
    return os.path.getsize(dst_path), True


def _fmt_size(b):
    """Human-readable file size."""
    if b < 1024:
        return f"{b} B"
    elif b < 1024 * 1024:
        return f"{b / 1024:.0f} KB"
    else:
        return f"{b / (1024 * 1024):.1f} MB"


# ══════════════════════════════════════════════════════════════════════════════
#  CLI: DNG CONVERT
# ══════════════════════════════════════════════════════════════════════════════

def cli_convert(inputs, output_dir=None, quality=95):
    files: list[str] = []
    for raw_arg in inputs:
        expanded = glob.glob(raw_arg, recursive=True)
        if not expanded:
            expanded = [raw_arg]
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
#  CLI: RESIZE JPGs
# ══════════════════════════════════════════════════════════════════════════════

def cli_resize(inputs, output_dir=None, max_mb=2.0):
    max_bytes = int(max_mb * 1024 * 1024)
    jpg_exts = {".jpg", ".jpeg"}

    files: list[str] = []
    for raw_arg in inputs:
        expanded = glob.glob(raw_arg, recursive=True)
        if not expanded:
            expanded = [raw_arg]
        for item in expanded:
            p = Path(item)
            if p.is_dir():
                files.extend(sorted(str(f) for f in p.rglob("*") if f.suffix.lower() in jpg_exts))
            elif p.suffix.lower() in jpg_exts and p.exists():
                files.append(str(p))
            elif not p.exists():
                print(f"  [!] File not found: {p}")

    if not files:
        print("  [X] No .jpg files found.")
        sys.exit(1)

    print()
    print("  +======================================+")
    print("  |       JPG  Bulk  Resizer             |")
    print("  +======================================+")
    print(f"\n  Files:    {len(files)}")
    print(f"  Max size: {max_mb} MB")
    print(f"  Output:   {output_dir or 'overwrite in place'}\n")
    print("  ----------------------------------------")

    success, skipped, errors = 0, 0, []
    for i, fpath in enumerate(files, 1):
        name = os.path.basename(fpath)
        out_dir = output_dir or os.path.dirname(fpath) or "."
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, os.path.basename(fpath))
        try:
            before = os.path.getsize(fpath)
            after, changed = resize_one(fpath, out_path, max_bytes)
            if changed:
                print(f"  [OK]  [{i}/{len(files)}] {name}  {_fmt_size(before)} -> {_fmt_size(after)}")
                success += 1
            else:
                print(f"  [--]  [{i}/{len(files)}] {name}  {_fmt_size(before)} (already under limit)")
                skipped += 1
        except Exception as exc:
            print(f"  [FAIL] [{i}/{len(files)}] {name}  ->  {exc}")
            errors.append(name)

    print("  ----------------------------------------")
    print(f"  Resized: {success}  |  Skipped: {skipped}  |  Failed: {len(errors)}")
    print()


# ══════════════════════════════════════════════════════════════════════════════
#  GUI
# ══════════════════════════════════════════════════════════════════════════════

BG           = "#1a1a2e"
BG_CARD      = "#16213e"
BG_INPUT     = "#0f3460"
ACCENT       = "#e94560"
ACCENT_HOVER = "#ff6b81"
ACCENT2      = "#0ea5e9"
ACCENT2_HOVER= "#38bdf8"
TEXT         = "#eaeaea"
TEXT_DIM     = "#8a8a9a"
FONT_TITLE   = ("Segoe UI", 20, "bold")
FONT_BODY    = ("Segoe UI", 11)
FONT_SMALL   = ("Segoe UI", 9)
FONT_BTN     = ("Segoe UI", 11, "bold")
FONT_TAB     = ("Segoe UI", 11, "bold")


def launch_gui():

    class App(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title("DNG -> JPG  |  Image Tools")
            self.configure(bg=BG)
            self.resizable(False, False)
            self.geometry("700x780")

            # Shared state
            self.files: list[str] = []
            self.output_dir = ""
            self.quality = tk.IntVar(value=95)
            self.converting = False
            self.mode = "dng"  # "dng" or "resize"
            self.max_mb = tk.DoubleVar(value=2.0)

            self._build_ui()
            self._centre_window()

        # ── UI ────────────────────────────────────────────────────────────
        def _build_ui(self):
            # Header
            header = tk.Frame(self, bg=BG)
            header.pack(fill="x", padx=28, pady=(20, 0))
            tk.Label(header, text="Image Tools", font=FONT_TITLE, bg=BG, fg=ACCENT).pack(side="left")

            # Tab bar
            tab_bar = tk.Frame(self, bg=BG)
            tab_bar.pack(fill="x", padx=28, pady=(14, 0))

            self.tab_dng = tk.Button(
                tab_bar, text="  DNG -> JPG  ", font=FONT_TAB,
                bg=ACCENT, fg="white", bd=0, padx=16, pady=6,
                cursor="hand2", command=lambda: self._switch_tab("dng")
            )
            self.tab_dng.pack(side="left")

            self.tab_resize = tk.Button(
                tab_bar, text="  Resize JPGs  ", font=FONT_TAB,
                bg=BG_CARD, fg=TEXT_DIM, bd=0, padx=16, pady=6,
                cursor="hand2", command=lambda: self._switch_tab("resize")
            )
            self.tab_resize.pack(side="left", padx=(4, 0))

            # Container for tab content
            self.tab_container = tk.Frame(self, bg=BG)
            self.tab_container.pack(fill="both", expand=True)

            self._build_dng_tab()
            self._build_resize_tab()
            self._switch_tab("dng")

        def _switch_tab(self, mode):
            self.mode = mode
            self.files = []
            self.output_dir = ""
            # Update tab button styles
            if mode == "dng":
                self.tab_dng.config(bg=ACCENT, fg="white")
                self.tab_resize.config(bg=BG_CARD, fg=TEXT_DIM)
                self.dng_frame.pack(fill="both", expand=True)
                self.resize_frame.pack_forget()
                self._refresh_file_list(self.dng_file_listbox, self.dng_file_label)
                self.dng_out_label.config(text="Same as source")
            else:
                self.tab_resize.config(bg=ACCENT2, fg="white")
                self.tab_dng.config(bg=BG_CARD, fg=TEXT_DIM)
                self.resize_frame.pack(fill="both", expand=True)
                self.dng_frame.pack_forget()
                self._refresh_file_list(self.resize_file_listbox, self.resize_file_label)
                self.resize_out_label.config(text="Overwrite in place")

        # ── DNG Tab ───────────────────────────────────────────────────────
        def _build_dng_tab(self):
            self.dng_frame = tk.Frame(self.tab_container, bg=BG)

            card1 = self._card(self.dng_frame, "Step 1: Select DNG Files")
            bf = tk.Frame(card1, bg=BG_CARD)
            bf.pack(fill="x", pady=(4, 0))
            self._accent_btn(bf, "Browse Files...", self._dng_browse_files).pack(side="left")
            self._accent_btn(bf, "Browse Folder...", self._dng_browse_folder).pack(side="left", padx=(10, 0))
            self.dng_file_label = tk.Label(card1, text="No files selected", font=FONT_SMALL, bg=BG_CARD, fg=TEXT_DIM, anchor="w")
            self.dng_file_label.pack(fill="x", pady=(8, 0))
            lf = tk.Frame(card1, bg=BG_INPUT, bd=0, highlightthickness=1, highlightbackground="#2a2a4a")
            lf.pack(fill="both", expand=True, pady=(8, 0))
            self.dng_file_listbox = tk.Listbox(lf, bg=BG_INPUT, fg=TEXT, font=FONT_SMALL, selectbackground=ACCENT, selectforeground="white", bd=0, highlightthickness=0, height=5)
            sc = tk.Scrollbar(lf, command=self.dng_file_listbox.yview)
            self.dng_file_listbox.config(yscrollcommand=sc.set)
            self.dng_file_listbox.pack(side="left", fill="both", expand=True, padx=4, pady=4)
            sc.pack(side="right", fill="y")

            card2 = self._card(self.dng_frame, "Step 2: Output Settings")
            r1 = tk.Frame(card2, bg=BG_CARD)
            r1.pack(fill="x", pady=(4, 0))
            self._accent_btn(r1, "Output Folder...", self._dng_browse_output).pack(side="left")
            self.dng_out_label = tk.Label(r1, text="Same as source", font=FONT_SMALL, bg=BG_CARD, fg=TEXT_DIM, anchor="w")
            self.dng_out_label.pack(side="left", padx=(12, 0))
            qf = tk.Frame(card2, bg=BG_CARD)
            qf.pack(fill="x", pady=(12, 0))
            tk.Label(qf, text="JPG Quality:", font=FONT_BODY, bg=BG_CARD, fg=TEXT).pack(side="left")
            self.q_val_label = tk.Label(qf, text="95%", font=("Segoe UI", 11, "bold"), bg=BG_CARD, fg=ACCENT, width=4)
            self.q_val_label.pack(side="right")
            style = ttk.Style()
            style.theme_use("default")
            style.configure("Accent.Horizontal.TScale", troughcolor=BG_INPUT, background=ACCENT, sliderthickness=18)
            ttk.Scale(qf, from_=50, to=100, variable=self.quality, orient="horizontal", style="Accent.Horizontal.TScale", command=self._update_q).pack(side="left", fill="x", expand=True, padx=(12, 8))

            card3 = self._card(self.dng_frame, "Step 3: Convert", pad_bottom=16)
            style.configure("TProgressbar", troughcolor=BG_INPUT, background=ACCENT, thickness=10)
            self.dng_progress = ttk.Progressbar(card3, mode="determinate", length=400)
            self.dng_progress.pack(fill="x", pady=(4, 8))
            self.dng_status = tk.Label(card3, text="Ready", font=FONT_SMALL, bg=BG_CARD, fg=TEXT_DIM, anchor="w")
            self.dng_status.pack(fill="x")
            self.dng_btn = self._accent_btn(card3, "Convert All", self._dng_start, big=True)
            self.dng_btn.pack(pady=(10, 0))

        # ── Resize Tab ────────────────────────────────────────────────────
        def _build_resize_tab(self):
            self.resize_frame = tk.Frame(self.tab_container, bg=BG)

            card1 = self._card(self.resize_frame, "Step 1: Select JPG Files")
            bf = tk.Frame(card1, bg=BG_CARD)
            bf.pack(fill="x", pady=(4, 0))
            self._accent_btn(bf, "Browse Files...", self._resize_browse_files, color=ACCENT2, hover=ACCENT2_HOVER).pack(side="left")
            self._accent_btn(bf, "Browse Folder...", self._resize_browse_folder, color=ACCENT2, hover=ACCENT2_HOVER).pack(side="left", padx=(10, 0))
            self.resize_file_label = tk.Label(card1, text="No files selected", font=FONT_SMALL, bg=BG_CARD, fg=TEXT_DIM, anchor="w")
            self.resize_file_label.pack(fill="x", pady=(8, 0))
            lf = tk.Frame(card1, bg=BG_INPUT, bd=0, highlightthickness=1, highlightbackground="#2a2a4a")
            lf.pack(fill="both", expand=True, pady=(8, 0))
            self.resize_file_listbox = tk.Listbox(lf, bg=BG_INPUT, fg=TEXT, font=FONT_SMALL, selectbackground=ACCENT2, selectforeground="white", bd=0, highlightthickness=0, height=5)
            sc = tk.Scrollbar(lf, command=self.resize_file_listbox.yview)
            self.resize_file_listbox.config(yscrollcommand=sc.set)
            self.resize_file_listbox.pack(side="left", fill="both", expand=True, padx=4, pady=4)
            sc.pack(side="right", fill="y")

            card2 = self._card(self.resize_frame, "Step 2: Settings")
            r1 = tk.Frame(card2, bg=BG_CARD)
            r1.pack(fill="x", pady=(4, 0))
            self._accent_btn(r1, "Output Folder...", self._resize_browse_output, color=ACCENT2, hover=ACCENT2_HOVER).pack(side="left")
            self.resize_out_label = tk.Label(r1, text="Overwrite in place", font=FONT_SMALL, bg=BG_CARD, fg=TEXT_DIM, anchor="w")
            self.resize_out_label.pack(side="left", padx=(12, 0))

            mf = tk.Frame(card2, bg=BG_CARD)
            mf.pack(fill="x", pady=(12, 0))
            tk.Label(mf, text="Max file size:", font=FONT_BODY, bg=BG_CARD, fg=TEXT).pack(side="left")
            self.mb_val_label = tk.Label(mf, text="2.0 MB", font=("Segoe UI", 11, "bold"), bg=BG_CARD, fg=ACCENT2, width=7)
            self.mb_val_label.pack(side="right")
            style = ttk.Style()
            style.configure("Blue.Horizontal.TScale", troughcolor=BG_INPUT, background=ACCENT2, sliderthickness=18)
            ttk.Scale(mf, from_=0.5, to=10.0, variable=self.max_mb, orient="horizontal", style="Blue.Horizontal.TScale", command=self._update_mb).pack(side="left", fill="x", expand=True, padx=(12, 8))

            card3 = self._card(self.resize_frame, "Step 3: Resize", pad_bottom=16)
            style.configure("Blue.Horizontal.TProgressbar", troughcolor=BG_INPUT, background=ACCENT2, thickness=10)
            self.resize_progress = ttk.Progressbar(card3, mode="determinate", length=400, style="Blue.Horizontal.TProgressbar")
            self.resize_progress.pack(fill="x", pady=(4, 8))
            self.resize_status = tk.Label(card3, text="Ready", font=FONT_SMALL, bg=BG_CARD, fg=TEXT_DIM, anchor="w")
            self.resize_status.pack(fill="x")
            self.resize_btn = self._accent_btn(card3, "Resize All", self._resize_start, big=True, color=ACCENT2, hover=ACCENT2_HOVER)
            self.resize_btn.pack(pady=(10, 0))

        # ── Shared helpers ────────────────────────────────────────────────
        def _card(self, parent, title, pad_bottom=4):
            wrapper = tk.Frame(parent, bg=BG)
            wrapper.pack(fill="x", padx=28, pady=(14, pad_bottom))
            tk.Label(wrapper, text=title, font=("Segoe UI", 12, "bold"), bg=BG, fg=TEXT).pack(anchor="w", pady=(0, 6))
            card = tk.Frame(wrapper, bg=BG_CARD, bd=0, highlightthickness=1, highlightbackground="#2a2a4a")
            card.pack(fill="both", expand=True, ipady=10, ipadx=14)
            return card

        def _accent_btn(self, parent, text, command, big=False, color=None, hover=None):
            c = color or ACCENT
            h = hover or ACCENT_HOVER
            btn = tk.Button(parent, text=text, font=FONT_BTN if big else FONT_BODY, bg=c, fg="white", activebackground=h, activeforeground="white", bd=0, cursor="hand2", padx=18 if big else 12, pady=8 if big else 4, command=command)
            btn.bind("<Enter>", lambda e, b=btn, hc=h: b.config(bg=hc))
            btn.bind("<Leave>", lambda e, b=btn, nc=c: b.config(bg=nc))
            return btn

        def _centre_window(self):
            self.update_idletasks()
            w, h = self.winfo_width(), self.winfo_height()
            x = (self.winfo_screenwidth() - w) // 2
            y = (self.winfo_screenheight() - h) // 2
            self.geometry(f"+{x}+{y}")

        def _update_q(self, _=None):
            self.q_val_label.config(text=f"{self.quality.get()}%")

        def _update_mb(self, _=None):
            self.mb_val_label.config(text=f"{self.max_mb.get():.1f} MB")

        def _refresh_file_list(self, listbox, label):
            listbox.delete(0, "end")
            for f in self.files:
                size = os.path.getsize(f) if os.path.exists(f) else 0
                listbox.insert("end", f"  {os.path.basename(f)}  ({_fmt_size(size)})")
            n = len(self.files)
            label.config(text=f"{n} file{'s' if n != 1 else ''} selected")

        # ── DNG actions ───────────────────────────────────────────────────
        def _dng_browse_files(self):
            paths = filedialog.askopenfilenames(title="Select DNG files", filetypes=[("DNG files", "*.dng *.DNG"), ("All files", "*.*")])
            if paths:
                self.files = list(paths)
                self._refresh_file_list(self.dng_file_listbox, self.dng_file_label)

        def _dng_browse_folder(self):
            folder = filedialog.askdirectory(title="Select folder with DNG files")
            if folder:
                found = sorted(str(p) for p in Path(folder).rglob("*") if p.suffix.lower() == ".dng")
                if not found:
                    messagebox.showinfo("No DNG files", "No .dng files found in that folder.")
                    return
                self.files = found
                self._refresh_file_list(self.dng_file_listbox, self.dng_file_label)

        def _dng_browse_output(self):
            folder = filedialog.askdirectory(title="Select output folder")
            if folder:
                self.output_dir = folder
                self.dng_out_label.config(text=folder)

        def _dng_start(self):
            if self.converting:
                return
            if not self.files:
                messagebox.showwarning("No files", "Please select DNG files first.")
                return
            self.converting = True
            self.dng_btn.config(state="disabled", bg=TEXT_DIM)
            threading.Thread(target=self._dng_worker, daemon=True).start()

        def _dng_worker(self):
            total = len(self.files)
            success, errors = 0, []
            for i, path in enumerate(self.files, 1):
                name = os.path.basename(path)
                self._set(self.dng_status, f"Converting {i}/{total}: {name}")
                self.dng_progress["value"] = (i - 1) / total * 100
                try:
                    out_dir = self.output_dir or os.path.dirname(path)
                    out_path = os.path.join(out_dir, Path(path).stem + ".jpg")
                    convert_one(path, out_path, self.quality.get())
                    success += 1
                except Exception as exc:
                    errors.append(f"{name}: {exc}")
            self.dng_progress["value"] = 100
            self._set(self.dng_status, f"Done: {success}/{total} converted")
            self.converting = False
            self.dng_btn.config(state="normal", bg=ACCENT)
            if errors:
                messagebox.showwarning("Some files failed", "\n".join(errors[:15]))
            else:
                messagebox.showinfo("Success", f"All {success} file(s) converted!")

        # ── Resize actions ────────────────────────────────────────────────
        def _resize_browse_files(self):
            paths = filedialog.askopenfilenames(title="Select JPG files", filetypes=[("JPG files", "*.jpg *.jpeg *.JPG *.JPEG"), ("All files", "*.*")])
            if paths:
                self.files = list(paths)
                self._refresh_file_list(self.resize_file_listbox, self.resize_file_label)

        def _resize_browse_folder(self):
            folder = filedialog.askdirectory(title="Select folder with JPG files")
            if folder:
                exts = {".jpg", ".jpeg"}
                found = sorted(str(p) for p in Path(folder).rglob("*") if p.suffix.lower() in exts)
                if not found:
                    messagebox.showinfo("No JPG files", "No .jpg files found in that folder.")
                    return
                self.files = found
                self._refresh_file_list(self.resize_file_listbox, self.resize_file_label)

        def _resize_browse_output(self):
            folder = filedialog.askdirectory(title="Select output folder (leave empty to overwrite)")
            if folder:
                self.output_dir = folder
                self.resize_out_label.config(text=folder)

        def _resize_start(self):
            if self.converting:
                return
            if not self.files:
                messagebox.showwarning("No files", "Please select JPG files first.")
                return
            self.converting = True
            self.resize_btn.config(state="disabled", bg=TEXT_DIM)
            threading.Thread(target=self._resize_worker, daemon=True).start()

        def _resize_worker(self):
            total = len(self.files)
            max_bytes = int(self.max_mb.get() * 1024 * 1024)
            success, skipped, errors = 0, 0, []
            for i, path in enumerate(self.files, 1):
                name = os.path.basename(path)
                self._set(self.resize_status, f"Resizing {i}/{total}: {name}")
                self.resize_progress["value"] = (i - 1) / total * 100
                try:
                    out_dir = self.output_dir or os.path.dirname(path)
                    out_path = os.path.join(out_dir, os.path.basename(path))
                    before = os.path.getsize(path)
                    after, changed = resize_one(path, out_path, max_bytes)
                    if changed:
                        success += 1
                    else:
                        skipped += 1
                except Exception as exc:
                    errors.append(f"{name}: {exc}")
            self.resize_progress["value"] = 100
            self._set(self.resize_status, f"Done: {success} resized, {skipped} skipped")
            self.converting = False
            self.resize_btn.config(state="normal", bg=ACCENT2)
            if errors:
                messagebox.showwarning("Some files failed", "\n".join(errors[:15]))
            else:
                messagebox.showinfo("Success", f"Resized: {success}  |  Already OK: {skipped}")

        def _set(self, label, text):
            self.after(0, lambda: label.config(text=text))
            self.after(0, self.update_idletasks)

    App().mainloop()


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Simple manual parsing to avoid argparse subcommand conflicts
    argv = sys.argv[1:]

    if not argv:
        # No args → GUI
        if not _tk_available:
            print("  [X] GUI needs tkinter.")
            print("      python dng_to_jpg_converter.py --help")
            sys.exit(1)
        launch_gui()
    elif argv[0] in ("-h", "--help"):
        print("""
DNG -> JPG Converter  +  JPG Bulk Resizer

USAGE:
  python dng_to_jpg_converter.py                             Open the GUI
  python dng_to_jpg_converter.py <files|folder> [options]    Convert DNG -> JPG
  python dng_to_jpg_converter.py resize <files|folder> [options]  Shrink JPGs

DNG CONVERT OPTIONS:
  -o, --output DIR       Output directory (default: same as source)
  -q, --quality 50-100   JPG quality (default: 95)

RESIZE OPTIONS:
  -o, --output DIR       Output directory (default: overwrite in place)
  -m, --max-mb NUM       Max file size in MB (default: 2.0)

EXAMPLES:
  python dng_to_jpg_converter.py IMG_0042.dng
  python dng_to_jpg_converter.py *.dng -q 85
  python dng_to_jpg_converter.py ./DCIM -o ./converted

  python dng_to_jpg_converter.py resize ./photos
  python dng_to_jpg_converter.py resize ./photos -m 1
  python dng_to_jpg_converter.py resize *.jpg -o ./small
        """)
    elif argv[0] == "resize":
        # Resize mode
        import argparse
        rp = argparse.ArgumentParser(prog="dng_to_jpg_converter.py resize")
        rp.add_argument("files", nargs="+", help="JPG files or folders")
        rp.add_argument("-o", "--output", default=None)
        rp.add_argument("-m", "--max-mb", type=float, default=2.0)
        args = rp.parse_args(argv[1:])
        cli_resize(args.files, args.output, args.max_mb)
    else:
        # DNG convert mode
        import argparse
        dp = argparse.ArgumentParser(prog="dng_to_jpg_converter.py")
        dp.add_argument("files", nargs="+", help="DNG files or folders")
        dp.add_argument("-o", "--output", default=None)
        dp.add_argument("-q", "--quality", type=int, default=95)
        args = dp.parse_args(argv)
        cli_convert(args.files, args.output, args.quality)