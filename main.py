# -*- coding: utf-8 -*-
"""
main.py — SZip (WinRAR-এর মতো আর্কাইভ ম্যানেজার, নিজস্ব ব্র্যান্ডিং)
SZip — a WinRAR-like archive manager with our own branding.
Copyright (c) 2026 Md. Sonet Mia (SONET). All rights reserved.

শুধু tkinter/ttk (Python standard library) দিয়ে GUI বানানো — বাড়তি
কোনো GUI লাইব্রেরি লাগে না, তাই PyInstaller-এ এক ফাইলের exe বানানো সহজ।

সুরক্ষা (Safety):
  * বের করা .exe/.bat-জাতীয় ফাইল নিজে থেকে চালানো হয় না — View করলে
    আগে ব্যবহারকারীকে জিজ্ঞেস করা হয়, তারপর OS-এর ডিফল্ট অ্যাপে খোলে।
  * RAR বানানো যায় না, শুধু খোলা যায় (প্রোপ্রাইটারি ফরম্যাট)।
  * AES-এনক্রিপ্ট করা ZIP খোলা যায় না — সত্যিটা বার্তায় জানানো হয়।

চালানো:  python main.py
exe বানানো (Windows PC-তে):  build.bat
"""

import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from archive_core import (
    ArchiveError,
    add_to_archive,
    archive_info,
    create_archive,
    delete_from_archive,
    detect_format,
    EXECUTABLE_EXTS,
    extract_all,
    extract_selected,
    file_type_label,
    format_size,
    HAS_PY7ZR,
    HAS_RARFILE,
    is_supported_archive,
    list_archive,
    list_children,
    test_archive,
    zip_has_aes,
    zip_needs_password,
)

APP_NAME = "SZip"
VERSION = "1.0.0"
AUTHOR = "Md. Sonet Mia"
ORG = "SONET"
COPYRIGHT = "Copyright \u00a9 2026 Md. Sonet Mia"
RECENT_FILE = os.path.join(os.path.expanduser("~"), ".sweet_archiver_recent.json")
MAX_RECENT = 10

# Drag-drop: tkinterdnd2 থাকলে চলবে, না থাকলে File > Open দিয়েই চলবে।
# (Drag-drop is optional — File > Open always works.)
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD  # type: ignore
    HAS_DND = True
except ImportError:
    HAS_DND = False


OPEN_FILETYPES = [
    ("সব আর্কাইভ (All archives)", "*.zip *.tar *.tar.gz *.tgz *.tar.bz2 *.tar.xz *.7z *.rar"),
    ("ZIP আর্কাইভ", "*.zip"),
    ("TAR আর্কাইভ", "*.tar *.tar.gz *.tgz *.tar.bz2 *.tar.xz"),
    ("7Z আর্কাইভ", "*.7z"),
    ("RAR আর্কাইভ", "*.rar"),
    ("সব ফাইল (All files)", "*.*"),
]

SAVE_FILETYPES = [
    ("ZIP আর্কাইভ", "*.zip"),
    ("7Z আর্কাইভ", "*.7z"),
    ("TAR আর্কাইভ", "*.tar"),
    ("TAR.GZ আর্কাইভ", "*.tar.gz"),
]


# ---------------------------------------------------------------------------
# প্রোগ্রেস ডায়ালগ (progress dialog — কাজ চলার সময় দেখায়)
# ---------------------------------------------------------------------------
class ProgressDialog(tk.Toplevel):
    """Extract/Add চলার সময় প্রোগ্রেস বার দেখানো উইন্ডো।"""

    def __init__(self, parent, title):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.result_queue = queue.Queue()
        self._cancelled = False

        self.label = ttk.Label(self, text="শুরু হচ্ছে… (Starting…)", wraplength=420)
        self.label.pack(padx=20, pady=(16, 6), anchor="w")
        self.bar = ttk.Progressbar(self, length=420, mode="determinate")
        self.bar.pack(padx=20, pady=6)
        self.count_label = ttk.Label(self, text="")
        self.count_label.pack(padx=20, pady=(0, 16), anchor="w")
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        # কাজ থামানো যায় না মাঝপথে — শুধু উইন্ডো লুকানো হয় না, অপেক্ষা করতে হয়।
        messagebox.showinfo("অপেক্ষা করুন (Please wait)",
                            "কাজ শেষ না হওয়া পর্যন্ত অপেক্ষা করুন।")

    def update_progress(self, done, total, name):
        self.bar["maximum"] = max(total, 1)
        self.bar["value"] = done
        self.count_label.config(text=f"{done} / {total} — {name}")
        self.label.config(text=f"চলছে… {name}")
        self.update_idletasks()


# ---------------------------------------------------------------------------
# মূল অ্যাপ (main application)
# ---------------------------------------------------------------------------
class SZipApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} {VERSION}")
        self.root.geometry("1000x620")
        self.root.minsize(760, 460)

        self.archive_path = None       # খোলা আর্কাইভের পুরো পথ
        self.current_folder = ""       # আর্কাইভের ভেতরের বর্তমান ফোল্ডার
        self.history = []              # পেছনে যাওয়ার ইতিহাস (Back)
        self.entries = []              # পুরো আর্কাইভের এন্ট্রি
        self.checked = set()           # টিক দেওয়া আইটেম (পুরো নাম)
        self.open_after_extract = tk.BooleanVar(value=True)
        self.recent = self._load_recent()

        self._build_menu()
        self._build_toolbar()
        self._build_pathbar()
        self._build_tree()
        self._build_statusbar()
        self._setup_drag_drop()
        self._refresh_recent_menu()
        self.refresh_list()
        self.root.bind("<Control-o>", lambda e: self.open_archive())

    # -- মেনু বার ------------------------------------------------------------
    def _build_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # ফাইল (File)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="খুলুন… (Open…)\tCtrl+O",
                              command=self.open_archive)
        self.recent_menu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(label="সাম্প্রতিক (Recent)", menu=self.recent_menu)
        file_menu.add_separator()
        file_menu.add_command(label="নতুন আর্কাইভ বানান… (New Archive…)",
                              command=self.create_new_archive)
        file_menu.add_separator()
        file_menu.add_command(label="এখানেই বের করুন (Extract Here)",
                              command=self.extract_here)
        file_menu.add_command(label="ফোল্ডার বেছে বের করুন… (Extract To…)",
                              command=self.extract_to)
        file_menu.add_separator()
        file_menu.add_command(label="আর্কাইভ বন্ধ করুন (Close Archive)",
                              command=self.close_archive)
        file_menu.add_command(label="বন্ধ করুন (Exit)", command=self.root.quit)
        menubar.add_cascade(label="ফাইল (File)", menu=file_menu)

        # কমান্ড (Commands)
        cmd_menu = tk.Menu(menubar, tearoff=0)
        cmd_menu.add_command(label="ফাইল যোগ করুন… (Add Files…)",
                             command=self.add_files)
        cmd_menu.add_command(label="ফোল্ডার যোগ করুন… (Add Folder…)",
                             command=self.add_folder)
        cmd_menu.add_separator()
        cmd_menu.add_command(label="বাছা ফাইল বের করুন (Extract Selected)",
                             command=self.extract_selected_action)
        cmd_menu.add_command(label="দেখুন (View)", command=self.view_selected)
        cmd_menu.add_command(label="মুছুন (Delete — ZIP only)",
                             command=self.delete_selected)
        cmd_menu.add_separator()
        cmd_menu.add_command(label="পরীক্ষা করুন (Test Archive)",
                             command=self.test_archive_action)
        cmd_menu.add_command(label="তথ্য (Archive Info)", command=self.show_info)
        menubar.add_cascade(label="কমান্ড (Commands)", menu=cmd_menu)

        # টুলস (Tools)
        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="আর্কাইভ পরীক্ষা (Test Archive)",
                               command=self.test_archive_action)
        tools_menu.add_command(label="আর্কাইভের তথ্য (Archive Info)",
                               command=self.show_info)
        menubar.add_cascade(label="টুলস (Tools)", menu=tools_menu)

        # অপশন (Options)
        opt_menu = tk.Menu(menubar, tearoff=0)
        opt_menu.add_checkbutton(
            label="Extract শেষে ফোল্ডার খুলুন (Open folder after extract)",
            variable=self.open_after_extract)
        menubar.add_cascade(label="অপশন (Options)", menu=opt_menu)

        # সাহায্য (Help)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="কীভাবে ব্যবহার করবেন (How to Use)",
                              command=self.show_help)
        help_menu.add_command(label="সম্পর্কে (About)", command=self.show_about)
        menubar.add_cascade(label="সাহায্য (Help)", menu=help_menu)

    # -- টুলবার ---------------------------------------------------------------
    def _build_toolbar(self):
        bar = ttk.Frame(self.root)
        bar.pack(fill="x", padx=6, pady=(6, 0))
        buttons = [
            ("＋ যোগ করুন (Add)", self.add_files),
            ("⇩ এক্সট্রাক্ট (Extract To)", self.extract_to),
            ("✓ পরীক্ষা (Test)", self.test_archive_action),
            ("👁 দেখুন (View)", self.view_selected),
            ("🗑 মুছুন (Delete)", self.delete_selected),
            ("🔍 খুঁজুন (Find)", self._focus_search),
            ("ℹ তথ্য (Info)", self.show_info),
        ]
        for text, cmd in buttons:
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=2)

    # -- পথ বার (archive path + ভেতরের ফোল্ডার নেভিগেশন) -----------------------
    def _build_pathbar(self):
        row = ttk.Frame(self.root)
        row.pack(fill="x", padx=6, pady=6)
        ttk.Button(row, text="← পেছনে (Back)", command=self.go_back).pack(side="left", padx=2)
        ttk.Button(row, text="↑ উপরে (Up)", command=self.go_up).pack(side="left", padx=2)
        ttk.Label(row, text="আর্কাইভ (Archive):").pack(side="left", padx=(8, 2))
        self.path_var = tk.StringVar(value="কোনো আর্কাইভ খোলা হয়নি (No archive open)")
        path_entry = ttk.Entry(row, textvariable=self.path_var, state="readonly")
        path_entry.pack(side="left", fill="x", expand=True, padx=2)
        ttk.Label(row, text="খুঁজুন (Find):").pack(side="left", padx=(8, 2))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.refresh_list())
        search = ttk.Entry(row, textvariable=self.search_var, width=18)
        search.pack(side="left", padx=2)
        self.search_entry = search

    def _focus_search(self):
        self.search_entry.focus_set()

    # -- ফাইলের তালিকা (Treeview) ----------------------------------------------
    def _build_tree(self):
        frame = ttk.Frame(self.root)
        frame.pack(fill="both", expand=True, padx=6, pady=2)
        columns = ("check", "name", "size", "type", "modified")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings",
                                 selectmode="extended")
        headings = {
            "check": "✓",
            "name": "নাম (Name)",
            "size": "সাইজ (Size)",
            "type": "ধরন (Type)",
            "modified": "পরিবর্তন (Modified)",
        }
        widths = {"check": 36, "name": 420, "size": 100, "type": 140, "modified": 170}
        for col in columns:
            self.tree.heading(col, text=headings[col],
                              command=lambda c=col: self._sort_by(c))
            self.tree.column(col, width=widths[col], stretch=(col == "name"))
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self.tree.bind("<Button-1>", self._on_click)
        self.tree.bind("<Double-1>", self._on_double_click)
        self._sort_reverse = False

    def _sort_by(self, col):
        self._sort_reverse = not self._sort_reverse
        self.refresh_list(sort_col=col, reverse=self._sort_reverse)

    # -- স্ট্যাটাস বার -----------------------------------------------------------
    def _build_statusbar(self):
        bar = ttk.Frame(self.root, relief="sunken")
        bar.pack(fill="x", side="bottom")
        self.status_count = ttk.Label(bar, text="0টি ফাইল")
        self.status_count.pack(side="left", padx=8, pady=3)
        self.status_size = ttk.Label(bar, text="")
        self.status_size.pack(side="left", padx=8, pady=3)
        self.status_msg = ttk.Label(bar, text="প্রস্তুত (Ready)")
        self.status_msg.pack(side="right", padx=8, pady=3)
        self.status_credit = ttk.Label(bar, text="SZip by Md. Sonet Mia")
        self.status_credit.pack(side="right", padx=8, pady=3)

    # -- Drag-drop (ঐচ্ছিক) ------------------------------------------------------
    def _setup_drag_drop(self):
        if not HAS_DND:
            return
        try:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind("<<Drop>>", self._on_drop)
        except Exception:
            pass

    def _on_drop(self, event):
        path = event.data.strip("{}").split("} {")[0].strip("{}")
        if os.path.isfile(path) and is_supported_archive(path):
            self.open_archive(path)
        elif os.path.isfile(path):
            messagebox.showwarning("অসমর্থিত ফাইল (Unsupported file)",
                                   f"এই ফাইল খোলা যায় না: {path}")

    # -- সাম্প্রতিক (recent) ------------------------------------------------------
    def _load_recent(self):
        try:
            with open(RECENT_FILE, encoding="utf-8") as f:
                data = json.load(f)
            return [p for p in data if isinstance(p, str)][:MAX_RECENT]
        except Exception:
            return []

    def _save_recent(self):
        try:
            with open(RECENT_FILE, "w", encoding="utf-8") as f:
                json.dump(self.recent, f, ensure_ascii=False)
        except Exception:
            pass

    def _add_recent(self, path):
        if path in self.recent:
            self.recent.remove(path)
        self.recent.insert(0, path)
        self.recent = self.recent[:MAX_RECENT]
        self._save_recent()
        self._refresh_recent_menu()

    def _refresh_recent_menu(self):
        self.recent_menu.delete(0, "end")
        if not self.recent:
            self.recent_menu.add_command(label="(খালি — Empty)", state="disabled")
            return
        for p in self.recent:
            self.recent_menu.add_command(
                label=p, command=lambda path=p: self.open_archive(path))
        self.recent_menu.add_separator()
        self.recent_menu.add_command(label="তালিকা মুছুন (Clear list)",
                                     command=self._clear_recent)

    def _clear_recent(self):
        self.recent = []
        self._save_recent()
        self._refresh_recent_menu()

    # -- আর্কাইভ খোলা / নেভিগেশন -------------------------------------------------
    def open_archive(self, path=None):
        if path is None:
            path = filedialog.askopenfilename(title="আর্কাইভ খুলুন (Open Archive)",
                                              filetypes=OPEN_FILETYPES)
            if not path:
                return
        if not os.path.isfile(path):
            messagebox.showerror("ফাইল পাওয়া যায়নি (File not found)", path)
            return
        if not is_supported_archive(path):
            messagebox.showerror("অসমর্থিত ফরম্যাট (Unsupported format)",
                                 "এই ফরম্যাট খোলা যায় না। ZIP / 7Z / TAR / RAR দিন।")
            return
        fmt = detect_format(path)
        if fmt == "7z" and not HAS_PY7ZR:
            messagebox.showwarning(
                "py7zr নেই (py7zr missing)",
                "7Z খুলতে py7zr লাগবে। ইনস্টল করুন: pip install py7zr")
            return
        if fmt == "rar" and not HAS_RARFILE:
            messagebox.showwarning(
                "RAR সমর্থন নেই (RAR support missing)",
                "RAR খুলতে rarfile আর UnRAR লাগবে।\n"
                "pip install rarfile করুন এবং UnRAR ইনস্টল করুন।")
            return
        self.archive_path = path
        self.current_folder = ""
        self.history = []
        self.checked = set()
        self._add_recent(path)
        self.path_var.set(path)
        if zip_has_aes(path):
            messagebox.showwarning(
                "AES এনক্রিপশন (AES-encrypted)",
                "এই ZIP-এ AES এনক্রিপশন আছে — নাম দেখা যাবে, কিন্তু ফাইল "
                "বের করা যাবে না। (AES-encrypted ZIP cannot be extracted.)")
        self.refresh_list()
        self.status_msg.config(text=f"খোলা হয়েছে: {os.path.basename(path)}")

    def close_archive(self):
        self.archive_path = None
        self.current_folder = ""
        self.history = []
        self.entries = []
        self.checked = set()
        self.path_var.set("কোনো আর্কাইভ খোলা হয়নি (No archive open)")
        self.refresh_list()

    def go_up(self):
        if not self.current_folder:
            return
        parent = "/".join(self.current_folder.strip("/").split("/")[:-1])
        self.history.append(self.current_folder)
        self.current_folder = parent
        self.refresh_list()

    def go_back(self):
        if self.history:
            self.current_folder = self.history.pop()
            self.refresh_list()

    def refresh_list(self, sort_col=None, reverse=False):
        for item in self.tree.get_children():
            self.tree.delete(item)
        if not self.archive_path:
            self.status_count.config(text="0টি ফাইল")
            self.status_size.config(text="")
            return
        try:
            self.entries = list_archive(self.archive_path)
        except ArchiveError as exc:
            messagebox.showerror("খোলা যায়নি (Cannot open)", str(exc))
            self.close_archive()
            return
        children = list_children(self.entries, self.current_folder)
        query = self.search_var.get().strip().lower()
        if query:
            children = [c for c in children if query in c.name.lower()]
        if sort_col == "size":
            children.sort(key=lambda e: e.size, reverse=reverse)
        elif sort_col == "modified":
            children.sort(key=lambda e: str(e.modified or ""), reverse=reverse)
        elif sort_col == "name":
            children.sort(key=lambda e: e.name.lower(), reverse=reverse)
        for e in children:
            display_name = e.name.rstrip("/").split("/")[-1]
            if e.is_dir:
                display_name += "/"
            modified = ""
            if e.modified is not None:
                try:
                    modified = e.modified.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    modified = str(e.modified)
            check = "☑" if e.name in self.checked else "☐"
            self.tree.insert("", "end", iid=e.name, values=(
                check, display_name,
                "" if e.is_dir else format_size(e.size),
                file_type_label(e.name, e.is_dir), modified))
        files = [e for e in self.entries if not e.is_dir]
        self.status_count.config(
            text=f"{len(children)}টি আইটেম (মোট {len(files)}টি ফাইল)")
        self.status_size.config(
            text=f"মোট সাইজ: {format_size(sum(e.size for e in files))}")
        folder_text = f" — ভেতরে: /{self.current_folder}" if self.current_folder else ""
        self.status_msg.config(text=f"{detect_format(self.archive_path) or ''}{folder_text}")

    # -- ক্লিক / ডাবল-ক্লিক ---------------------------------------------------------
    def _on_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        col = self.tree.identify_column(event.x)
        row = self.tree.identify_row(event.y)
        if not row or col != "#1":  # শুধু ✓ কলামে ক্লিক করলে টিক বদলায়
            return
        if row in self.checked:
            self.checked.discard(row)
            self.tree.set(row, "check", "☐")
        else:
            self.checked.add(row)
            self.tree.set(row, "check", "☑")

    def _on_double_click(self, event):
        row = self.tree.identify_row(event.y)
        if not row:
            return
        entry = next((e for e in self.entries if e.name == row), None)
        if entry is None:
            return
        if entry.is_dir:
            self.history.append(self.current_folder)
            self.current_folder = row.rstrip("/")
            self.refresh_list()
        else:
            self.view_selected()

    # -- বাছা আইটেম ------------------------------------------------------------------
    def _selected_names(self):
        """টিক দেওয়া আইটেম থাকলে সেগুলো, না থাকলে সিলেক্ট করা রো।"""
        if self.checked:
            return sorted(self.checked)
        return list(self.tree.selection())

    def _ask_password_if_needed(self):
        """এনক্রিপ্ট করা ZIP হলে পাসওয়ার্ড চাওয়া / ask password if needed."""
        if not self.archive_path or detect_format(self.archive_path) != "zip":
            return None
        if zip_has_aes(self.archive_path):
            messagebox.showerror(
                "AES এনক্রিপশন (AES-encrypted)",
                "এই ZIP AES-এ এনক্রিপ্ট করা — বের করা যাবে না।")
            return False
        if zip_needs_password(self.archive_path):
            pwd = simpledialog.askstring(
                "পাসওয়ার্ড (Password)", "আর্কাইভের পাসওয়ার্ড দিন:",
                show="*")
            if pwd is None:
                return False
            return pwd
        return None

    # -- থ্রেডে কাজ চালানো (threaded work + progress) ---------------------------------
    def _run_with_progress(self, title, func, on_done):
        dialog = ProgressDialog(self.root, title)
        result = {}

        def progress(done, total, name):
            dialog.result_queue.put(("progress", done, total, name))

        def worker():
            try:
                result["value"] = func(progress)
                dialog.result_queue.put(("done", None))
            except Exception as exc:  # noqa: BLE001 — বার্তায় দেখানো হবে
                dialog.result_queue.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

        def poll():
            try:
                while True:
                    kind, *data = dialog.result_queue.get_nowait()
                    if kind == "progress":
                        dialog.update_progress(*data)
                    elif kind == "done":
                        dialog.destroy()
                        on_done(result.get("value"), None)
                        return
                    elif kind == "error":
                        dialog.destroy()
                        on_done(None, data[0])
                        return
            except queue.Empty:
                pass
            self.root.after(100, poll)

        poll()

    # -- Extract -----------------------------------------------------------------------
    def _do_extract(self, names, dest, here=False):
        pwd = self._ask_password_if_needed()
        if pwd is False:
            return
        fmt = detect_format(self.archive_path)
        title = "বের করা হচ্ছে… (Extracting…)"
        if names is None:
            func = lambda progress: extract_all(
                self.archive_path, dest, password=pwd, progress=progress)
        else:
            func = lambda progress: extract_selected(
                self.archive_path, names, dest, password=pwd, progress=progress)

        def on_done(count, error):
            if error:
                messagebox.showerror("বের করা যায়নি (Extraction failed)", error)
                return
            self.status_msg.config(text=f"{count}টি ফাইল বের হয়েছে")
            messagebox.showinfo("সম্পন্ন (Done)", f"{count}টি ফাইল বের হয়েছে।\n{dest}")
            if self.open_after_extract.get():
                self._open_folder(dest)

        self._run_with_progress(title, func, on_done)

    def extract_here(self):
        if not self.archive_path:
            messagebox.showwarning("আর্কাইভ নেই (No archive)", "আগে একটি আর্কাইভ খুলুন।")
            return
        dest = os.path.dirname(os.path.abspath(self.archive_path))
        self._do_extract(None, dest, here=True)

    def extract_to(self):
        if not self.archive_path:
            messagebox.showwarning("আর্কাইভ নেই (No archive)", "আগে একটি আর্কাইভ খুলুন।")
            return
        dest = filedialog.askdirectory(title="কোথায় বের করবেন? (Extract to…)")
        if not dest:
            return
        self._do_extract(None, dest)

    def extract_selected_action(self):
        if not self.archive_path:
            messagebox.showwarning("আর্কাইভ নেই (No archive)", "আগে একটি আর্কাইভ খুলুন।")
            return
        names = self._selected_names()
        if not names:
            messagebox.showwarning("কিছু বাছা হয়নি (Nothing selected)",
                                   "টিক দিন বা ফাইল সিলেক্ট করুন।")
            return
        dest = filedialog.askdirectory(title="কোথায় বের করবেন? (Extract to…)")
        if not dest:
            return
        self._do_extract(names, dest)

    # -- Add / নতুন আর্কাইভ --------------------------------------------------------------
    def _add_sources(self, sources):
        if not sources:
            return
        if not self.archive_path:
            self.create_new_archive(prefill_sources=sources)
            return
        fmt = detect_format(self.archive_path)
        if fmt == "rar":
            messagebox.showerror("RAR-এ যোগ করা যায় না",
                                 "RAR আর্কাইভে ফাইল যোগ করা যায় না (RAR is read-only)।")
            return
        if fmt == "7z" and not HAS_PY7ZR:
            messagebox.showerror("py7zr নেই", "7Z-এ যোগ করতে py7zr লাগবে।")
            return
        title = "যোগ করা হচ্ছে… (Adding…)"

        def func(progress):
            return add_to_archive(self.archive_path, sources, progress=progress)

        def on_done(_value, error):
            if error:
                messagebox.showerror("যোগ করা যায়নি (Add failed)", error)
                return
            messagebox.showinfo("সম্পন্ন (Done)", "ফাইল যোগ হয়েছে।")
            self.refresh_list()

        self._run_with_progress(title, func, on_done)

    def add_files(self):
        files = filedialog.askopenfilenames(title="ফাইল বেছে নিন (Add Files)")
        if files:
            self._add_sources(list(files))

    def add_folder(self):
        folder = filedialog.askdirectory(title="ফোল্ডার বেছে নিন (Add Folder)")
        if folder:
            self._add_sources([folder])

    def create_new_archive(self, prefill_sources=None):
        path = filedialog.asksaveasfilename(
            title="নতুন আর্কাইভ বানান (Create New Archive)",
            filetypes=SAVE_FILETYPES, defaultextension=".zip")
        if not path:
            return
        sources = prefill_sources
        if sources is None:
            files = filedialog.askopenfilenames(title="কোন ফাইলগুলো ঢোকাবেন?")
            sources = list(files)
            if not sources:
                folder = filedialog.askdirectory(title="অথবা একটি ফোল্ডার বেছে নিন")
                if folder:
                    sources = [folder]
        if not sources:
            messagebox.showwarning("কিছু বাছা হয়নি", "কোনো ফাইল/ফোল্ডার বাছা হয়নি।")
            return
        fmt = detect_format(path)
        if fmt == "7z" and not HAS_PY7ZR:
            messagebox.showerror("py7zr নেই", "7Z বানাতে py7zr লাগবে: pip install py7zr")
            return
        title = "বানানো হচ্ছে… (Creating…)"

        def func(progress):
            return create_archive(path, sources, fmt=fmt, progress=progress)

        def on_done(_value, error):
            if error:
                messagebox.showerror("বানানো যায়নি (Create failed)", error)
                return
            messagebox.showinfo("সম্পন্ন (Done)", f"আর্কাইভ বানানো হয়েছে:\n{path}")
            self.open_archive(path)

        self._run_with_progress(title, func, on_done)

    # -- Delete / View / Test / Info ------------------------------------------------------
    def delete_selected(self):
        if not self.archive_path:
            messagebox.showwarning("আর্কাইভ নেই (No archive)", "আগে একটি আর্কাইভ খুলুন।")
            return
        if detect_format(self.archive_path) != "zip":
            messagebox.showerror(
                "শুধু ZIP-এ চলে (ZIP only)",
                "মোছা শুধু ZIP আর্কাইভে চলে। অন্য ফরম্যাটে নতুন করে বানাতে হবে।")
            return
        names = self._selected_names()
        if not names:
            messagebox.showwarning("কিছু বাছা হয়নি (Nothing selected)",
                                   "টিক দিন বা ফাইল সিলেক্ট করুন।")
            return
        if not messagebox.askyesno("মুছবেন? (Delete?)",
                                   f"{len(names)}টি আইটেম আর্কাইভ থেকে মুছে ফেলা হবে।"):
            return

        def func(progress):
            return delete_from_archive(self.archive_path, names, progress=progress)

        def on_done(count, error):
            if error:
                messagebox.showerror("মোছা যায়নি (Delete failed)", error)
                return
            messagebox.showinfo("সম্পন্ন (Done)", f"{count}টি আইটেম মোছা হয়েছে।")
            self.checked.discard(names[0]) if names else None
            self.checked = {c for c in self.checked if c not in set(names)}
            self.refresh_list()

        self._run_with_progress("মোছা হচ্ছে… (Deleting…)", func, on_done)

    def view_selected(self):
        if not self.archive_path:
            messagebox.showwarning("আর্কাইভ নেই (No archive)", "আগে একটি আর্কাইভ খুলুন।")
            return
        names = self._selected_names()
        if not names:
            messagebox.showwarning("কিছু বাছা হয়নি (Nothing selected)",
                                   "একটি ফাইল বেছে নিন।")
            return
        name = names[0]
        entry = next((e for e in self.entries if e.name.rstrip("/") == name.rstrip("/")), None)
        if entry is not None and entry.is_dir:
            messagebox.showinfo("ফোল্ডার (Folder)", "ফোল্ডার দেখতে ডাবল-ক্লিক করে ভেতরে যান।")
            return
        ext = os.path.splitext(name)[1].lower()
        if ext in EXECUTABLE_EXTS:
            if not messagebox.askyesno(
                    "সতর্কতা (Warning)",
                    f"এটি একটি এক্সিকিউটেবল ফাইল ({ext})।\n"
                    "অপরিচিত উৎসের ফাইল চালানো বিপজ্জনক হতে পারে।\n\n"
                    "তবু খুলবেন? (Open anyway?)"):
                return
        pwd = self._ask_password_if_needed()
        if pwd is False:
            return
        tmpdir = tempfile.mkdtemp(prefix="sweet_archiver_view_")
        try:
            extract_selected(self.archive_path, [name], tmpdir, password=pwd)
        except ArchiveError as exc:
            messagebox.showerror("খোলা যায়নি (Cannot view)", str(exc))
            return
        target = os.path.join(tmpdir, name)
        if not os.path.exists(target):
            messagebox.showerror("খোলা যায়নি", "ফাইলটি বের করা যায়নি।")
            return
        self._open_file(target)

    def test_archive_action(self):
        if not self.archive_path:
            messagebox.showwarning("আর্কাইভ নেই (No archive)", "আগে একটি আর্কাইভ খুলুন।")
            return
        pwd = None
        if detect_format(self.archive_path) == "zip" and zip_needs_password(self.archive_path):
            pwd = self._ask_password_if_needed()
            if pwd is False:
                return
        ok, bad, msg = test_archive(self.archive_path, password=pwd)
        if ok:
            messagebox.showinfo("পরীক্ষা (Test)", f"✓ {msg}")
        else:
            messagebox.showerror("পরীক্ষা (Test)", f"✗ {msg}\n{bad}")

    def show_info(self):
        if not self.archive_path:
            messagebox.showwarning("আর্কাইভ নেই (No archive)", "আগে একটি আর্কাইভ খুলুন।")
            return
        try:
            info = archive_info(self.archive_path)
        except ArchiveError as exc:
            messagebox.showerror("তথ্য পাওয়া যায়নি", str(exc))
            return
        text = (
            f"ফাইল: {info['path']}\n"
            f"ফরম্যাট: {info['format']}\n"
            f"ফাইল সংখ্যা: {info['file_count']}টি\n"
            f"ফোল্ডার সংখ্যা: {info['folder_count']}টি\n"
            f"মোট সাইজ: {info['total_size_text']}\n"
            f"ডিস্কে সাইজ: {info['disk_size_text']}\n"
            f"এনক্রিপ্ট করা: {'হ্যাঁ' if info['encrypted'] else 'না'}\n"
            f"AES এনক্রিপশন: {'হ্যাঁ (খোলা যাবে না)' if info['aes_encrypted'] else 'না'}"
        )
        messagebox.showinfo("আর্কাইভের তথ্য (Archive Info)", text)

    # -- সাহায্য / সম্পর্কে ------------------------------------------------------------------
    def show_help(self):
        messagebox.showinfo(
            "কীভাবে ব্যবহার করবেন (How to Use)",
            "১. File > Open দিয়ে আর্কাইভ খুলুন (অথবা ফাইলটা টেনে ছাড়ুন)।\n"
            "২. ফোল্ডারে ঢুকতে ডাবল-ক্লিক করুন, উপরে যেতে ↑ চাপুন।\n"
            "৩. ✓ কলামে ক্লিক করে ফাইল টিক দিন, তারপর Extract চাপুন।\n"
            "৪. নতুন আর্কাইভ: File > নতুন আর্কাইভ বানান।\n"
            "৫. ZIP / 7Z / TAR / TAR.GZ বানানো যায়; RAR শুধু খোলা যায়।\n"
            "৬. পাসওয়ার্ড দেওয়া ZIP খুলতে পাসওয়ার্ড চাওয়া হবে; "
            "AES-এনক্রিপ্ট করা ZIP খোলা যায় না।")

    def show_about(self):
        messagebox.showinfo(
            "সম্পর্কে (About)",
            f"{APP_NAME} {VERSION}\n\n"
            "WinRAR-এর মতো আর্কাইভ ম্যানেজার — নিজস্ব ব্র্যান্ডিং।\n"
            "অফলাইন, পোর্টেবল, ফাইল কোথাও আপলোড হয় না।\n\n"
            "ZIP / 7Z / TAR / TAR.GZ / RAR (শুধু খোলা)\n"
            "Python + tkinter দিয়ে বানানো।\n\n"
            f"Developed by {AUTHOR}\n"
            f"Founder — {ORG}, Tangail, Bangladesh\n"
            f"{COPYRIGHT}\n"
            "https://mdsonetmia.vercel.app\n"
            "https://github.com/mdsonetmia05-cloud/SZip")

    # -- OS-এ ফাইল/ফোল্ডার খোলা ---------------------------------------------------------------
    def _open_folder(self, path):
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # noqa: S606 — ব্যবহারকারীর বাছা ফোল্ডার
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception:
            pass

    def _open_file(self, path):
        self._open_folder(path)


def main():
    if HAS_DND:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    app = SZipApp(root)  # noqa: F841
    root.mainloop()


if __name__ == "__main__":
    main()
