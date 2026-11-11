# -*- coding: utf-8 -*-
"""
main.py — SZip (WinRAR-এর মতো আর্কাইভ ম্যানেজার, নিজস্ব ব্র্যান্ডিং)
SZip — a WinRAR-like archive manager with our own branding.
Copyright (c) 2026 Md. Sonet Mia (SONET). All rights reserved.

শুধু tkinter/ttk (Python standard library) দিয়ে GUI বানানো — বাড়তি
কোনো GUI লাইব্রেরি লাগে না, তাই PyInstaller-এ এক ফাইলের exe বানানো সহজ।

ভাষা (Language): ডিফল্ট ইংরেজি; Options মেনু থেকে বাংলায় বদলানো যায়,
পছন্দ ~/.szip_settings.json-এ সংরক্ষিত হয়।

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
VERSION = "1.1.0"
AUTHOR = "Md. Sonet Mia"
ORG = "SONET"
COPYRIGHT = "Copyright \u00a9 2026 Md. Sonet Mia"
RECENT_FILE = os.path.join(os.path.expanduser("~"), ".sweet_archiver_recent.json")
SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".szip_settings.json")
MAX_RECENT = 10

# Drag-drop: tkinterdnd2 থাকলে চলবে, না থাকলে File > Open দিয়েই চলবে।
# (Drag-drop is optional — File > Open always works.)
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD  # type: ignore
    HAS_DND = True
except ImportError:
    HAS_DND = False


# ---------------------------------------------------------------------------
# ভাষা (Language strings — 'en' ডিফল্ট, 'bn' বাংলায় বদলানো যায়)
# 'bn'-এর লেখা আগের সংস্করণের হুবহু বাংলা (ইংরেজি বন্ধনীসহ)।
# ---------------------------------------------------------------------------
STRINGS = {
    "en": {
        "menu_file": "File",
        "menu_open": "Open…\tCtrl+O",
        "menu_recent": "Recent",
        "menu_new_archive": "New Archive…",
        "menu_extract_here": "Extract Here",
        "menu_extract_to": "Extract To…",
        "menu_close_archive": "Close Archive",
        "menu_exit": "Exit",
        "menu_commands": "Commands",
        "menu_add_files": "Add Files…",
        "menu_add_folder": "Add Folder…",
        "menu_extract_selected": "Extract Selected",
        "menu_view": "View",
        "menu_delete": "Delete — ZIP only",
        "menu_test": "Test Archive",
        "menu_info": "Archive Info",
        "menu_tools": "Tools",
        "menu_tools_test": "Test Archive",
        "menu_tools_info": "Archive Info",
        "menu_options": "Options",
        "opt_open_after": "Open folder after extract",
        "menu_help": "Help",
        "menu_howto": "How to Use",
        "menu_about": "About",
        "tb_add": "＋ Add",
        "tb_extract": "⇩ Extract To",
        "tb_test": "✓ Test",
        "tb_view": "👁 View",
        "tb_delete": "🗑 Delete",
        "tb_find": "🔍 Find",
        "tb_info": "ℹ Info",
        "pb_back": "← Back",
        "pb_up": "↑ Up",
        "pb_archive_label": "Archive:",
        "pb_no_archive": "No archive open",
        "pb_find_label": "Find:",
        "col_check": "✓",
        "col_name": "Name",
        "col_size": "Size",
        "col_type": "Type",
        "col_modified": "Modified",
        "type_folder": "Folder",
        "type_file": "File",
        "type_ext_file": "{ext} file",
        "status_zero_files": "0 files",
        "status_ready": "Ready",
        "status_credit": "SZip by Md. Sonet Mia",
        "status_items": "{shown} items ({total} files)",
        "status_total_size": "Total size: {size}",
        "status_inside": " — Inside: /{folder}",
        "status_opened": "Opened: {name}",
        "status_extracted": "{n} files extracted",
        "prog_starting": "Starting…",
        "prog_wait_title": "Please wait",
        "prog_wait_msg": "Please wait until the task is finished.",
        "prog_running": "Working… {name}",
        "prog_extracting": "Extracting…",
        "prog_adding": "Adding…",
        "prog_creating": "Creating…",
        "prog_deleting": "Deleting…",
        "ft_all_archives": "All archives",
        "ft_zip": "ZIP archive",
        "ft_tar": "TAR archive",
        "ft_7z": "7Z archive",
        "ft_rar": "RAR archive",
        "ft_all_files": "All files",
        "ft_targz": "TAR.GZ archive",
        "dlg_open_archive": "Open Archive",
        "dlg_extract_to": "Extract to…",
        "dlg_add_files": "Add Files",
        "dlg_add_folder": "Add Folder",
        "dlg_new_archive": "Create New Archive",
        "dlg_choose_files": "Which files should be added?",
        "dlg_choose_folder": "Or choose a folder",
        "err_not_found": "File not found",
        "err_unsupported_fmt": "Unsupported format",
        "msg_unsupported_fmt": "This format cannot be opened. Use ZIP / 7Z / TAR / RAR.",
        "warn_py7zr_missing": "py7zr missing",
        "msg_py7zr_open": "py7zr is needed to open 7Z files. Install it: pip install py7zr",
        "warn_rar_missing": "RAR support missing",
        "msg_rar_missing": "Opening RAR needs rarfile and UnRAR.\nInstall rarfile with pip and install UnRAR.",
        "warn_aes": "AES-encrypted",
        "msg_aes_open": "This ZIP is AES-encrypted — file names are visible, but files cannot be extracted. (AES-encrypted ZIP cannot be extracted.)",
        "msg_aes_blocked": "This ZIP is AES-encrypted — it cannot be extracted.",
        "ask_password_title": "Password",
        "ask_password_prompt": "Enter the archive password:",
        "err_cannot_open": "Cannot open",
        "err_extract_failed": "Extraction failed",
        "info_done": "Done",
        "msg_extracted_to": "{n} files extracted.\n{dest}",
        "warn_no_archive": "No archive",
        "msg_open_first": "Open an archive first.",
        "warn_nothing_selected": "Nothing selected",
        "msg_select_files": "Tick the checkboxes or select files first.",
        "msg_select_one": "Select a file first.",
        "err_rar_add": "Cannot add to RAR",
        "msg_rar_add": "Files cannot be added to a RAR archive (RAR is read-only).",
        "err_py7zr": "py7zr missing",
        "msg_py7zr_add": "py7zr is needed to add files to 7Z.",
        "msg_py7zr_create": "py7zr is needed to create 7Z: pip install py7zr",
        "err_add_failed": "Add failed",
        "msg_added": "Files added.",
        "err_create_failed": "Create failed",
        "msg_created": "Archive created:\n{path}",
        "warn_nothing_chosen": "Nothing selected",
        "msg_nothing_chosen": "No file or folder was selected.",
        "err_zip_only": "ZIP only",
        "msg_zip_only_delete": "Deleting works only in ZIP archives. For other formats, create a new archive.",
        "ask_delete_title": "Delete?",
        "ask_delete_msg": "{n} items will be deleted from the archive.",
        "err_delete_failed": "Delete failed",
        "msg_deleted": "{n} items deleted.",
        "info_folder": "Folder",
        "msg_folder_view": "Double-click a folder to open it.",
        "warn_exe": "Warning",
        "msg_exe_warn": "This is an executable file ({ext}).\nRunning files from unknown sources can be dangerous.\n\nOpen anyway?",
        "err_cannot_view": "Cannot view",
        "err_view_failed": "Cannot open",
        "msg_view_failed": "The file could not be extracted.",
        "title_test": "Test",
        "err_info": "Could not get info",
        "title_info": "Archive Info",
        "info_file": "File: {v}",
        "info_format": "Format: {v}",
        "info_file_count": "Files: {n}",
        "info_folder_count": "Folders: {n}",
        "info_total_size": "Total size: {v}",
        "info_disk_size": "Size on disk: {v}",
        "info_encrypted": "Encrypted: {v}",
        "info_aes": "AES encryption: {v}",
        "yes": "Yes",
        "no": "No",
        "aes_yes": "Yes (cannot open)",
        "warn_unsupported_file": "Unsupported file",
        "msg_unsupported_file": "This file cannot be opened: {path}",
        "recent_empty": "(Empty)",
        "recent_clear": "Clear list",
        "help_title": "How to Use",
        "help_text": "1. Open an archive with File > Open (or drag and drop the file).\n2. Double-click a folder to enter it; use ↑ to go up.\n3. Tick the ✓ column to select files, then click Extract.\n4. New archive: File > New Archive.\n5. You can create ZIP / 7Z / TAR / TAR.GZ; RAR can only be opened.\n6. A password is asked for password-protected ZIP files; AES-encrypted ZIP files cannot be extracted.",
        "about_title": "About",
        "about_text": "{app} {version}\n\nA WinRAR-style archive manager with its own branding.\nOffline, portable — your files are never uploaded anywhere.\n\nZIP / 7Z / TAR / TAR.GZ / RAR (open only)\nBuilt with Python + tkinter.\n\nDeveloped by {author}\nFounder — {org}, Tangail, Bangladesh\n{copyright}\nhttps://mdsonetmia.vercel.app\nhttps://github.com/mdsonetmia05-cloud/SZip",
    },
    "bn": {
        "menu_file": "ফাইল (File)",
        "menu_open": "খুলুন… (Open…)\tCtrl+O",
        "menu_recent": "সাম্প্রতিক (Recent)",
        "menu_new_archive": "নতুন আর্কাইভ বানান… (New Archive…)",
        "menu_extract_here": "এখানেই বের করুন (Extract Here)",
        "menu_extract_to": "ফোল্ডার বেছে বের করুন… (Extract To…)",
        "menu_close_archive": "আর্কাইভ বন্ধ করুন (Close Archive)",
        "menu_exit": "বন্ধ করুন (Exit)",
        "menu_commands": "কমান্ড (Commands)",
        "menu_add_files": "ফাইল যোগ করুন… (Add Files…)",
        "menu_add_folder": "ফোল্ডার যোগ করুন… (Add Folder…)",
        "menu_extract_selected": "বাছা ফাইল বের করুন (Extract Selected)",
        "menu_view": "দেখুন (View)",
        "menu_delete": "মুছুন (Delete — ZIP only)",
        "menu_test": "পরীক্ষা করুন (Test Archive)",
        "menu_info": "তথ্য (Archive Info)",
        "menu_tools": "টুলস (Tools)",
        "menu_tools_test": "আর্কাইভ পরীক্ষা (Test Archive)",
        "menu_tools_info": "আর্কাইভের তথ্য (Archive Info)",
        "menu_options": "অপশন (Options)",
        "opt_open_after": "Extract শেষে ফোল্ডার খুলুন (Open folder after extract)",
        "menu_help": "সাহায্য (Help)",
        "menu_howto": "কীভাবে ব্যবহার করবেন (How to Use)",
        "menu_about": "সম্পর্কে (About)",
        "tb_add": "＋ যোগ করুন (Add)",
        "tb_extract": "⇩ এক্সট্রাক্ট (Extract To)",
        "tb_test": "✓ পরীক্ষা (Test)",
        "tb_view": "👁 দেখুন (View)",
        "tb_delete": "🗑 মুছুন (Delete)",
        "tb_find": "🔍 খুঁজুন (Find)",
        "tb_info": "ℹ তথ্য (Info)",
        "pb_back": "← পেছনে (Back)",
        "pb_up": "↑ উপরে (Up)",
        "pb_archive_label": "আর্কাইভ (Archive):",
        "pb_no_archive": "কোনো আর্কাইভ খোলা হয়নি (No archive open)",
        "pb_find_label": "খুঁজুন (Find):",
        "col_check": "✓",
        "col_name": "নাম (Name)",
        "col_size": "সাইজ (Size)",
        "col_type": "ধরন (Type)",
        "col_modified": "পরিবর্তন (Modified)",
        "type_folder": "ফোল্ডার (Folder)",
        "type_file": "ফাইল (File)",
        "type_ext_file": "{ext} ফাইল",
        "status_zero_files": "0টি ফাইল",
        "status_ready": "প্রস্তুত (Ready)",
        "status_credit": "SZip by Md. Sonet Mia",
        "status_items": "{shown}টি আইটেম (মোট {total}টি ফাইল)",
        "status_total_size": "মোট সাইজ: {size}",
        "status_inside": " — ভেতরে: /{folder}",
        "status_opened": "খোলা হয়েছে: {name}",
        "status_extracted": "{n}টি ফাইল বের হয়েছে",
        "prog_starting": "শুরু হচ্ছে… (Starting…)",
        "prog_wait_title": "অপেক্ষা করুন (Please wait)",
        "prog_wait_msg": "কাজ শেষ না হওয়া পর্যন্ত অপেক্ষা করুন।",
        "prog_running": "চলছে… {name}",
        "prog_extracting": "বের করা হচ্ছে… (Extracting…)",
        "prog_adding": "যোগ করা হচ্ছে… (Adding…)",
        "prog_creating": "বানানো হচ্ছে… (Creating…)",
        "prog_deleting": "মোছা হচ্ছে… (Deleting…)",
        "ft_all_archives": "সব আর্কাইভ (All archives)",
        "ft_zip": "ZIP আর্কাইভ",
        "ft_tar": "TAR আর্কাইভ",
        "ft_7z": "7Z আর্কাইভ",
        "ft_rar": "RAR আর্কাইভ",
        "ft_all_files": "সব ফাইল (All files)",
        "ft_targz": "TAR.GZ আর্কাইভ",
        "dlg_open_archive": "আর্কাইভ খুলুন (Open Archive)",
        "dlg_extract_to": "কোথায় বের করবেন? (Extract to…)",
        "dlg_add_files": "ফাইল বেছে নিন (Add Files)",
        "dlg_add_folder": "ফোল্ডার বেছে নিন (Add Folder)",
        "dlg_new_archive": "নতুন আর্কাইভ বানান (Create New Archive)",
        "dlg_choose_files": "কোন ফাইলগুলো ঢোকাবেন?",
        "dlg_choose_folder": "অথবা একটি ফোল্ডার বেছে নিন",
        "err_not_found": "ফাইল পাওয়া যায়নি (File not found)",
        "err_unsupported_fmt": "অসমর্থিত ফরম্যাট (Unsupported format)",
        "msg_unsupported_fmt": "এই ফরম্যাট খোলা যায় না। ZIP / 7Z / TAR / RAR দিন।",
        "warn_py7zr_missing": "py7zr নেই (py7zr missing)",
        "msg_py7zr_open": "7Z খুলতে py7zr লাগবে। ইনস্টল করুন: pip install py7zr",
        "warn_rar_missing": "RAR সমর্থন নেই (RAR support missing)",
        "msg_rar_missing": "RAR খুলতে rarfile আর UnRAR লাগবে।\npip install rarfile করুন এবং UnRAR ইনস্টল করুন।",
        "warn_aes": "AES এনক্রিপশন (AES-encrypted)",
        "msg_aes_open": "এই ZIP-এ AES এনক্রিপশন আছে — নাম দেখা যাবে, কিন্তু ফাইল বের করা যাবে না। (AES-encrypted ZIP cannot be extracted.)",
        "msg_aes_blocked": "এই ZIP AES-এ এনক্রিপ্ট করা — বের করা যাবে না।",
        "ask_password_title": "পাসওয়ার্ড (Password)",
        "ask_password_prompt": "আর্কাইভের পাসওয়ার্ড দিন:",
        "err_cannot_open": "খোলা যায়নি (Cannot open)",
        "err_extract_failed": "বের করা যায়নি (Extraction failed)",
        "info_done": "সম্পন্ন (Done)",
        "msg_extracted_to": "{n}টি ফাইল বের হয়েছে।\n{dest}",
        "warn_no_archive": "আর্কাইভ নেই (No archive)",
        "msg_open_first": "আগে একটি আর্কাইভ খুলুন।",
        "warn_nothing_selected": "কিছু বাছা হয়নি (Nothing selected)",
        "msg_select_files": "টিক দিন বা ফাইল সিলেক্ট করুন।",
        "msg_select_one": "একটি ফাইল বেছে নিন।",
        "err_rar_add": "RAR-এ যোগ করা যায় না",
        "msg_rar_add": "RAR আর্কাইভে ফাইল যোগ করা যায় না (RAR is read-only)।",
        "err_py7zr": "py7zr নেই",
        "msg_py7zr_add": "7Z-এ যোগ করতে py7zr লাগবে।",
        "msg_py7zr_create": "7Z বানাতে py7zr লাগবে: pip install py7zr",
        "err_add_failed": "যোগ করা যায়নি (Add failed)",
        "msg_added": "ফাইল যোগ হয়েছে।",
        "err_create_failed": "বানানো যায়নি (Create failed)",
        "msg_created": "আর্কাইভ বানানো হয়েছে:\n{path}",
        "warn_nothing_chosen": "কিছু বাছা হয়নি",
        "msg_nothing_chosen": "কোনো ফাইল/ফোল্ডার বাছা হয়নি।",
        "err_zip_only": "শুধু ZIP-এ চলে (ZIP only)",
        "msg_zip_only_delete": "মোছা শুধু ZIP আর্কাইভে চলে। অন্য ফরম্যাটে নতুন করে বানাতে হবে।",
        "ask_delete_title": "মুছবেন? (Delete?)",
        "ask_delete_msg": "{n}টি আইটেম আর্কাইভ থেকে মুছে ফেলা হবে।",
        "err_delete_failed": "মোছা যায়নি (Delete failed)",
        "msg_deleted": "{n}টি আইটেম মোছা হয়েছে।",
        "info_folder": "ফোল্ডার (Folder)",
        "msg_folder_view": "ফোল্ডার দেখতে ডাবল-ক্লিক করে ভেতরে যান।",
        "warn_exe": "সতর্কতা (Warning)",
        "msg_exe_warn": "এটি একটি এক্সিকিউটেবল ফাইল ({ext})।\nঅপরিচিত উৎসের ফাইল চালানো বিপজ্জনক হতে পারে।\n\nতবু খুলবেন? (Open anyway?)",
        "err_cannot_view": "খোলা যায়নি (Cannot view)",
        "err_view_failed": "খোলা যায়নি",
        "msg_view_failed": "ফাইলটি বের করা যায়নি।",
        "title_test": "পরীক্ষা (Test)",
        "err_info": "তথ্য পাওয়া যায়নি",
        "title_info": "আর্কাইভের তথ্য (Archive Info)",
        "info_file": "ফাইল: {v}",
        "info_format": "ফরম্যাট: {v}",
        "info_file_count": "ফাইল সংখ্যা: {n}টি",
        "info_folder_count": "ফোল্ডার সংখ্যা: {n}টি",
        "info_total_size": "মোট সাইজ: {v}",
        "info_disk_size": "ডিস্কে সাইজ: {v}",
        "info_encrypted": "এনক্রিপ্ট করা: {v}",
        "info_aes": "AES এনক্রিপশন: {v}",
        "yes": "হ্যাঁ",
        "no": "না",
        "aes_yes": "হ্যাঁ (খোলা যাবে না)",
        "warn_unsupported_file": "অসমর্থিত ফাইল (Unsupported file)",
        "msg_unsupported_file": "এই ফাইল খোলা যায় না: {path}",
        "recent_empty": "(খালি — Empty)",
        "recent_clear": "তালিকা মুছুন (Clear list)",
        "help_title": "কীভাবে ব্যবহার করবেন (How to Use)",
        "help_text": "১. File > Open দিয়ে আর্কাইভ খুলুন (অথবা ফাইলটা টেনে ছাড়ুন)।\n২. ফোল্ডারে ঢুকতে ডাবল-ক্লিক করুন, উপরে যেতে ↑ চাপুন।\n৩. ✓ কলামে ক্লিক করে ফাইল টিক দিন, তারপর Extract চাপুন।\n৪. নতুন আর্কাইভ: File > নতুন আর্কাইভ বানান।\n৫. ZIP / 7Z / TAR / TAR.GZ বানানো যায়; RAR শুধু খোলা যায়।\n৬. পাসওয়ার্ড দেওয়া ZIP খুলতে পাসওয়ার্ড চাওয়া হবে; AES-এনক্রিপ্ট করা ZIP খোলা যায় না।",
        "about_title": "সম্পর্কে (About)",
        "about_text": "{app} {version}\n\nWinRAR-এর মতো আর্কাইভ ম্যানেজার — নিজস্ব ব্র্যান্ডিং।\nঅফলাইন, পোর্টেবল, ফাইল কোথাও আপলোড হয় না।\n\nZIP / 7Z / TAR / TAR.GZ / RAR (শুধু খোলা)\nPython + tkinter দিয়ে বানানো।\n\nDeveloped by {author}\nFounder — {org}, Tangail, Bangladesh\n{copyright}\nhttps://mdsonetmia.vercel.app\nhttps://github.com/mdsonetmia05-cloud/SZip",
    },
}


def _load_language():
    """সংরক্ষিত ভাষা পড়া — না থাকলে ডিফল্ট 'en'।"""
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        lang = data.get("language", "en") if isinstance(data, dict) else "en"
        return lang if lang in ("en", "bn") else "en"
    except Exception:
        return "en"


def _save_language(lang):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump({"language": lang}, f, ensure_ascii=False)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# প্রোগ্রেস ডায়ালগ (progress dialog — কাজ চলার সময় দেখায়)
# ---------------------------------------------------------------------------
class ProgressDialog(tk.Toplevel):
    """Extract/Add চলার সময় প্রোগ্রেস বার দেখানো উইন্ডো।"""

    def __init__(self, parent, title, t):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.result_queue = queue.Queue()
        self._cancelled = False
        self._t = t

        self.label = ttk.Label(self, text=self._t("prog_starting"), wraplength=420)
        self.label.pack(padx=20, pady=(16, 6), anchor="w")
        self.bar = ttk.Progressbar(self, length=420, mode="determinate")
        self.bar.pack(padx=20, pady=6)
        self.count_label = ttk.Label(self, text="")
        self.count_label.pack(padx=20, pady=(0, 16), anchor="w")
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        # কাজ থামানো যায় না মাঝপথে — শুধু উইন্ডো লুকানো হয় না, অপেক্ষা করতে হয়।
        messagebox.showinfo(self._t("prog_wait_title"),
                            self._t("prog_wait_msg"))

    def update_progress(self, done, total, name):
        self.bar["maximum"] = max(total, 1)
        self.bar["value"] = done
        self.count_label.config(text=f"{done} / {total} — {name}")
        self.label.config(text=self._t("prog_running", name=name))
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

        self.lang = _load_language()
        self.archive_path = None       # খোলা আর্কাইভের পুরো পথ
        self.current_folder = ""       # আর্কাইভের ভেতরের বর্তমান ফোল্ডার
        self.history = []              # পেছনে যাওয়ার ইতিহাস (Back)
        self.entries = []              # পুরো আর্কাইভের এন্ট্রি
        self.checked = set()           # টিক দেওয়া আইটেম (পুরো নাম)
        self.open_after_extract = tk.BooleanVar(value=True)
        self.lang_var = tk.StringVar(value=self.lang)
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

    # -- ভাষা (language) -------------------------------------------------------
    def _t(self, key, **kwargs):
        text = STRINGS.get(self.lang, STRINGS["en"]).get(key)
        if text is None:
            text = STRINGS["en"].get(key, key)
        return text.format(**kwargs) if kwargs else text

    def set_language(self, lang):
        """ভাষা বদলানো — সাথে সাথে পুরো UI-তে কার্যকর হয়, রিস্টার্ট লাগে না।"""
        if lang not in ("en", "bn"):
            return
        self.lang = lang
        self.lang_var.set(lang)
        _save_language(lang)
        self._apply_language()

    def _apply_language(self):
        self._build_menu()
        self._refresh_recent_menu()
        for key, btn in self.toolbar_buttons.items():
            btn.config(text=self._t(key))
        self.back_btn.config(text=self._t("pb_back"))
        self.up_btn.config(text=self._t("pb_up"))
        self.archive_lbl.config(text=self._t("pb_archive_label"))
        self.find_lbl.config(text=self._t("pb_find_label"))
        for col in ("check", "name", "size", "type", "modified"):
            self.tree.heading(col, text=self._t("col_" + col))
        if not self.archive_path:
            self.path_var.set(self._t("pb_no_archive"))
            self.status_count.config(text=self._t("status_zero_files"))
            self.status_size.config(text="")
            self.status_msg.config(text=self._t("status_ready"))
        self.refresh_list()

    def _open_filetypes(self):
        return [
            (self._t("ft_all_archives"), "*.zip *.tar *.tar.gz *.tgz *.tar.bz2 *.tar.xz *.7z *.rar"),
            (self._t("ft_zip"), "*.zip"),
            (self._t("ft_tar"), "*.tar *.tar.gz *.tgz *.tar.bz2 *.tar.xz"),
            (self._t("ft_7z"), "*.7z"),
            (self._t("ft_rar"), "*.rar"),
            (self._t("ft_all_files"), "*.*"),
        ]

    def _save_filetypes(self):
        return [
            (self._t("ft_zip"), "*.zip"),
            (self._t("ft_7z"), "*.7z"),
            (self._t("ft_tar"), "*.tar"),
            (self._t("ft_targz"), "*.tar.gz"),
        ]

    def _type_label(self, name, is_dir):
        """নাম দেখে টাইপের লেবেল — বর্তমান ভাষায়।"""
        if is_dir:
            return self._t("type_folder")
        ext = os.path.splitext(name)[1].lower()
        if ext:
            return self._t("type_ext_file", ext=ext[1:].upper())
        return self._t("type_file")

    # -- মেনু বার ------------------------------------------------------------
    def _build_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        self.menubar = menubar

        # ফাইল (File)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label=self._t("menu_open"),
                              command=self.open_archive)
        self.recent_menu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(label=self._t("menu_recent"), menu=self.recent_menu)
        file_menu.add_separator()
        file_menu.add_command(label=self._t("menu_new_archive"),
                              command=self.create_new_archive)
        file_menu.add_separator()
        file_menu.add_command(label=self._t("menu_extract_here"),
                              command=self.extract_here)
        file_menu.add_command(label=self._t("menu_extract_to"),
                              command=self.extract_to)
        file_menu.add_separator()
        file_menu.add_command(label=self._t("menu_close_archive"),
                              command=self.close_archive)
        file_menu.add_command(label=self._t("menu_exit"), command=self.root.quit)
        menubar.add_cascade(label=self._t("menu_file"), menu=file_menu)

        # কমান্ড (Commands)
        cmd_menu = tk.Menu(menubar, tearoff=0)
        cmd_menu.add_command(label=self._t("menu_add_files"),
                             command=self.add_files)
        cmd_menu.add_command(label=self._t("menu_add_folder"),
                             command=self.add_folder)
        cmd_menu.add_separator()
        cmd_menu.add_command(label=self._t("menu_extract_selected"),
                             command=self.extract_selected_action)
        cmd_menu.add_command(label=self._t("menu_view"), command=self.view_selected)
        cmd_menu.add_command(label=self._t("menu_delete"),
                             command=self.delete_selected)
        cmd_menu.add_separator()
        cmd_menu.add_command(label=self._t("menu_test"),
                             command=self.test_archive_action)
        cmd_menu.add_command(label=self._t("menu_info"), command=self.show_info)
        menubar.add_cascade(label=self._t("menu_commands"), menu=cmd_menu)

        # টুলস (Tools)
        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label=self._t("menu_tools_test"),
                               command=self.test_archive_action)
        tools_menu.add_command(label=self._t("menu_tools_info"), command=self.show_info)
        menubar.add_cascade(label=self._t("menu_tools"), menu=tools_menu)

        # অপশন (Options)
        opt_menu = tk.Menu(menubar, tearoff=0)
        opt_menu.add_checkbutton(
            label=self._t("opt_open_after"),
            variable=self.open_after_extract)
        opt_menu.add_separator()
        opt_menu.add_radiobutton(label="English (default)",
                                 variable=self.lang_var, value="en",
                                 command=lambda: self.set_language("en"))
        opt_menu.add_radiobutton(label="বাংলা (Bengali)",
                                 variable=self.lang_var, value="bn",
                                 command=lambda: self.set_language("bn"))
        menubar.add_cascade(label=self._t("menu_options"), menu=opt_menu)

        # সাহায্য (Help)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label=self._t("menu_howto"),
                              command=self.show_help)
        help_menu.add_command(label=self._t("menu_about"), command=self.show_about)
        menubar.add_cascade(label=self._t("menu_help"), menu=help_menu)

    # -- টুলবার ---------------------------------------------------------------
    def _build_toolbar(self):
        bar = ttk.Frame(self.root)
        bar.pack(fill="x", padx=6, pady=(6, 0))
        buttons = [
            ("tb_add", self.add_files),
            ("tb_extract", self.extract_to),
            ("tb_test", self.test_archive_action),
            ("tb_view", self.view_selected),
            ("tb_delete", self.delete_selected),
            ("tb_find", self._focus_search),
            ("tb_info", self.show_info),
        ]
        self.toolbar_buttons = {}
        for key, cmd in buttons:
            btn = ttk.Button(bar, text=self._t(key), command=cmd)
            btn.pack(side="left", padx=2)
            self.toolbar_buttons[key] = btn

    # -- পথ বার (archive path + ভেতরের ফোল্ডার নেভিগেশন) -----------------------
    def _build_pathbar(self):
        row = ttk.Frame(self.root)
        row.pack(fill="x", padx=6, pady=6)
        self.back_btn = ttk.Button(row, text=self._t("pb_back"), command=self.go_back)
        self.back_btn.pack(side="left", padx=2)
        self.up_btn = ttk.Button(row, text=self._t("pb_up"), command=self.go_up)
        self.up_btn.pack(side="left", padx=2)
        self.archive_lbl = ttk.Label(row, text=self._t("pb_archive_label"))
        self.archive_lbl.pack(side="left", padx=(8, 2))
        self.path_var = tk.StringVar(value=self._t("pb_no_archive"))
        path_entry = ttk.Entry(row, textvariable=self.path_var, state="readonly")
        path_entry.pack(side="left", fill="x", expand=True, padx=2)
        self.find_lbl = ttk.Label(row, text=self._t("pb_find_label"))
        self.find_lbl.pack(side="left", padx=(8, 2))
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
        widths = {"check": 36, "name": 420, "size": 100, "type": 140, "modified": 170}
        for col in columns:
            self.tree.heading(col, text=self._t("col_" + col),
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
        self.status_count = ttk.Label(bar, text=self._t("status_zero_files"))
        self.status_count.pack(side="left", padx=8, pady=3)
        self.status_size = ttk.Label(bar, text="")
        self.status_size.pack(side="left", padx=8, pady=3)
        self.status_msg = ttk.Label(bar, text=self._t("status_ready"))
        self.status_msg.pack(side="right", padx=8, pady=3)
        self.status_credit = ttk.Label(bar, text=self._t("status_credit"))
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
            messagebox.showwarning(self._t("warn_unsupported_file"),
                                   self._t("msg_unsupported_file", path=path))

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
            self.recent_menu.add_command(label=self._t("recent_empty"), state="disabled")
            return
        for p in self.recent:
            self.recent_menu.add_command(
                label=p, command=lambda path=p: self.open_archive(path))
        self.recent_menu.add_separator()
        self.recent_menu.add_command(label=self._t("recent_clear"),
                                     command=self._clear_recent)

    def _clear_recent(self):
        self.recent = []
        self._save_recent()
        self._refresh_recent_menu()

    # -- আর্কাইভ খোলা / নেভিগেশন -------------------------------------------------
    def open_archive(self, path=None):
        if path is None:
            path = filedialog.askopenfilename(title=self._t("dlg_open_archive"),
                                              filetypes=self._open_filetypes())
            if not path:
                return
        if not os.path.isfile(path):
            messagebox.showerror(self._t("err_not_found"), path)
            return
        if not is_supported_archive(path):
            messagebox.showerror(self._t("err_unsupported_fmt"),
                                 self._t("msg_unsupported_fmt"))
            return
        fmt = detect_format(path)
        if fmt == "7z" and not HAS_PY7ZR:
            messagebox.showwarning(
                self._t("warn_py7zr_missing"),
                self._t("msg_py7zr_open"))
            return
        if fmt == "rar" and not HAS_RARFILE:
            messagebox.showwarning(
                self._t("warn_rar_missing"),
                self._t("msg_rar_missing"))
            return
        self.archive_path = path
        self.current_folder = ""
        self.history = []
        self.checked = set()
        self._add_recent(path)
        self.path_var.set(path)
        if zip_has_aes(path):
            messagebox.showwarning(
                self._t("warn_aes"),
                self._t("msg_aes_open"))
        self.refresh_list()
        self.status_msg.config(text=self._t("status_opened", name=os.path.basename(path)))

    def close_archive(self):
        self.archive_path = None
        self.current_folder = ""
        self.history = []
        self.entries = []
        self.checked = set()
        self.path_var.set(self._t("pb_no_archive"))
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
            self.status_count.config(text=self._t("status_zero_files"))
            self.status_size.config(text="")
            return
        try:
            self.entries = list_archive(self.archive_path)
        except ArchiveError as exc:
            messagebox.showerror(self._t("err_cannot_open"), str(exc))
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
                self._type_label(e.name, e.is_dir), modified))
        files = [e for e in self.entries if not e.is_dir]
        self.status_count.config(
            text=self._t("status_items", shown=len(children), total=len(files)))
        self.status_size.config(
            text=self._t("status_total_size", size=format_size(sum(e.size for e in files))))
        folder_text = self._t("status_inside", folder=self.current_folder) if self.current_folder else ""
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
                self._t("warn_aes"),
                self._t("msg_aes_blocked"))
            return False
        if zip_needs_password(self.archive_path):
            pwd = simpledialog.askstring(
                self._t("ask_password_title"), self._t("ask_password_prompt"),
                show="*")
            if pwd is None:
                return False
            return pwd
        return None

    # -- থ্রেডে কাজ চালানো (threaded work + progress) ---------------------------------
    def _run_with_progress(self, title, func, on_done):
        dialog = ProgressDialog(self.root, title, self._t)
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
        title = self._t("prog_extracting")
        if names is None:
            func = lambda progress: extract_all(
                self.archive_path, dest, password=pwd, progress=progress)
        else:
            func = lambda progress: extract_selected(
                self.archive_path, names, dest, password=pwd, progress=progress)

        def on_done(count, error):
            if error:
                messagebox.showerror(self._t("err_extract_failed"), error)
                return
            self.status_msg.config(text=self._t("status_extracted", n=count))
            messagebox.showinfo(self._t("info_done"),
                                self._t("msg_extracted_to", n=count, dest=dest))
            if self.open_after_extract.get():
                self._open_folder(dest)

        self._run_with_progress(title, func, on_done)

    def extract_here(self):
        if not self.archive_path:
            messagebox.showwarning(self._t("warn_no_archive"), self._t("msg_open_first"))
            return
        dest = os.path.dirname(os.path.abspath(self.archive_path))
        self._do_extract(None, dest, here=True)

    def extract_to(self):
        if not self.archive_path:
            messagebox.showwarning(self._t("warn_no_archive"), self._t("msg_open_first"))
            return
        dest = filedialog.askdirectory(title=self._t("dlg_extract_to"))
        if not dest:
            return
        self._do_extract(None, dest)

    def extract_selected_action(self):
        if not self.archive_path:
            messagebox.showwarning(self._t("warn_no_archive"), self._t("msg_open_first"))
            return
        names = self._selected_names()
        if not names:
            messagebox.showwarning(self._t("warn_nothing_selected"),
                                   self._t("msg_select_files"))
            return
        dest = filedialog.askdirectory(title=self._t("dlg_extract_to"))
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
            messagebox.showerror(self._t("err_rar_add"),
                                 self._t("msg_rar_add"))
            return
        if fmt == "7z" and not HAS_PY7ZR:
            messagebox.showerror(self._t("err_py7zr"), self._t("msg_py7zr_add"))
            return
        title = self._t("prog_adding")

        def func(progress):
            return add_to_archive(self.archive_path, sources, progress=progress)

        def on_done(_value, error):
            if error:
                messagebox.showerror(self._t("err_add_failed"), error)
                return
            messagebox.showinfo(self._t("info_done"), self._t("msg_added"))
            self.refresh_list()

        self._run_with_progress(title, func, on_done)

    def add_files(self):
        files = filedialog.askopenfilenames(title=self._t("dlg_add_files"))
        if files:
            self._add_sources(list(files))

    def add_folder(self):
        folder = filedialog.askdirectory(title=self._t("dlg_add_folder"))
        if folder:
            self._add_sources([folder])

    def create_new_archive(self, prefill_sources=None):
        path = filedialog.asksaveasfilename(
            title=self._t("dlg_new_archive"),
            filetypes=self._save_filetypes(), defaultextension=".zip")
        if not path:
            return
        sources = prefill_sources
        if sources is None:
            files = filedialog.askopenfilenames(title=self._t("dlg_choose_files"))
            sources = list(files)
            if not sources:
                folder = filedialog.askdirectory(title=self._t("dlg_choose_folder"))
                if folder:
                    sources = [folder]
        if not sources:
            messagebox.showwarning(self._t("warn_nothing_chosen"),
                                   self._t("msg_nothing_chosen"))
            return
        fmt = detect_format(path)
        if fmt == "7z" and not HAS_PY7ZR:
            messagebox.showerror(self._t("err_py7zr"), self._t("msg_py7zr_create"))
            return
        title = self._t("prog_creating")

        def func(progress):
            return create_archive(path, sources, fmt=fmt, progress=progress)

        def on_done(_value, error):
            if error:
                messagebox.showerror(self._t("err_create_failed"), error)
                return
            messagebox.showinfo(self._t("info_done"),
                                self._t("msg_created", path=path))
            self.open_archive(path)

        self._run_with_progress(title, func, on_done)

    # -- Delete / View / Test / Info ------------------------------------------------------
    def delete_selected(self):
        if not self.archive_path:
            messagebox.showwarning(self._t("warn_no_archive"), self._t("msg_open_first"))
            return
        if detect_format(self.archive_path) != "zip":
            messagebox.showerror(
                self._t("err_zip_only"),
                self._t("msg_zip_only_delete"))
            return
        names = self._selected_names()
        if not names:
            messagebox.showwarning(self._t("warn_nothing_selected"),
                                   self._t("msg_select_files"))
            return
        if not messagebox.askyesno(self._t("ask_delete_title"),
                                   self._t("ask_delete_msg", n=len(names))):
            return

        def func(progress):
            return delete_from_archive(self.archive_path, names, progress=progress)

        def on_done(count, error):
            if error:
                messagebox.showerror(self._t("err_delete_failed"), error)
                return
            messagebox.showinfo(self._t("info_done"),
                                self._t("msg_deleted", n=count))
            self.checked.discard(names[0]) if names else None
            self.checked = {c for c in self.checked if c not in set(names)}
            self.refresh_list()

        self._run_with_progress(self._t("prog_deleting"), func, on_done)

    def view_selected(self):
        if not self.archive_path:
            messagebox.showwarning(self._t("warn_no_archive"), self._t("msg_open_first"))
            return
        names = self._selected_names()
        if not names:
            messagebox.showwarning(self._t("warn_nothing_selected"),
                                   self._t("msg_select_one"))
            return
        name = names[0]
        entry = next((e for e in self.entries if e.name.rstrip("/") == name.rstrip("/")), None)
        if entry is not None and entry.is_dir:
            messagebox.showinfo(self._t("info_folder"), self._t("msg_folder_view"))
            return
        ext = os.path.splitext(name)[1].lower()
        if ext in EXECUTABLE_EXTS:
            if not messagebox.askyesno(
                    self._t("warn_exe"),
                    self._t("msg_exe_warn", ext=ext)):
                return
        pwd = self._ask_password_if_needed()
        if pwd is False:
            return
        tmpdir = tempfile.mkdtemp(prefix="sweet_archiver_view_")
        try:
            extract_selected(self.archive_path, [name], tmpdir, password=pwd)
        except ArchiveError as exc:
            messagebox.showerror(self._t("err_cannot_view"), str(exc))
            return
        target = os.path.join(tmpdir, name)
        if not os.path.exists(target):
            messagebox.showerror(self._t("err_view_failed"), self._t("msg_view_failed"))
            return
        self._open_file(target)

    def test_archive_action(self):
        if not self.archive_path:
            messagebox.showwarning(self._t("warn_no_archive"), self._t("msg_open_first"))
            return
        pwd = None
        if detect_format(self.archive_path) == "zip" and zip_needs_password(self.archive_path):
            pwd = self._ask_password_if_needed()
            if pwd is False:
                return
        ok, bad, msg = test_archive(self.archive_path, password=pwd)
        if ok:
            messagebox.showinfo(self._t("title_test"), f"✓ {msg}")
        else:
            messagebox.showerror(self._t("title_test"), f"✗ {msg}\n{bad}")

    def show_info(self):
        if not self.archive_path:
            messagebox.showwarning(self._t("warn_no_archive"), self._t("msg_open_first"))
            return
        try:
            info = archive_info(self.archive_path)
        except ArchiveError as exc:
            messagebox.showerror(self._t("err_info"), str(exc))
            return
        text = (
            self._t("info_file", v=info['path']) + "\n"
            + self._t("info_format", v=info['format']) + "\n"
            + self._t("info_file_count", n=info['file_count']) + "\n"
            + self._t("info_folder_count", n=info['folder_count']) + "\n"
            + self._t("info_total_size", v=info['total_size_text']) + "\n"
            + self._t("info_disk_size", v=info['disk_size_text']) + "\n"
            + self._t("info_encrypted",
                      v=self._t("yes") if info['encrypted'] else self._t("no")) + "\n"
            + self._t("info_aes",
                      v=self._t("aes_yes") if info['aes_encrypted'] else self._t("no"))
        )
        messagebox.showinfo(self._t("title_info"), text)

    # -- সাহায্য / সম্পর্কে ------------------------------------------------------------------
    def show_help(self):
        messagebox.showinfo(
            self._t("help_title"),
            self._t("help_text"))

    def show_about(self):
        messagebox.showinfo(
            self._t("about_title"),
            self._t("about_text", app=APP_NAME, version=VERSION,
                    author=AUTHOR, org=ORG, copyright=COPYRIGHT))

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
