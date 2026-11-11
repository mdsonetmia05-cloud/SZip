# GUI language smoke test for SZip v1.1.0 (English default, Bengali switchable)
# Run: HOME=/tmp/szip-gui-home xvfb-run -a python3 /tmp/gui_lang_smoke.py
import os
import shutil
import sys
import tkinter as tk

sys.path.insert(0, "/home/hatch/workspace/zip-extractor")
import main
from archive_core import create_archive

HOME = os.path.expanduser("~")
print("HOME:", HOME)
print("settings file:", main.SETTINGS_FILE,
      "exists before start:", os.path.exists(main.SETTINGS_FILE))

PASSED = [0]
FAILED = []


def check(name, cond, detail=""):
    if cond:
        PASSED[0] += 1
        print(f"  PASS: {name}" + (f" — {detail}" if detail else ""))
    else:
        FAILED.append(name)
        print(f"  FAIL: {name}" + (f" — {detail}" if detail else ""))


def menu_label(menu, index):
    return menu.entryconfigure(index)["label"][-1]


def submenu(menubar, index):
    return menubar.nametowidget(menubar.entryconfigure(index)["menu"][-1])


# --- sample archive ---
base = "/tmp/szip-lang-test"
shutil.rmtree(base, ignore_errors=True)
src = os.path.join(base, "src")
os.makedirs(os.path.join(src, "docs"))
for rel, content in [("readme.txt", "hello"),
                     ("docs/guide.txt", "guide " * 20),
                     ("data.csv", "a,b\n1,2\n")]:
    p = os.path.join(src, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").write(content)
zip_path = os.path.join(base, "sample.zip")
create_archive(zip_path, [os.path.join(src, n) for n in sorted(os.listdir(src))],
               fmt="zip")
print("sample zip:", zip_path)

root = tk.Tk()
app = main.SZipApp(root)
root.update()

# --- 1. Default language is English (no settings file existed) ---
check("default lang is en", app.lang == "en", f"lang={app.lang}")
check("lang_var is en", app.lang_var.get() == "en")
check("menu cascade 0 is File", menu_label(app.menubar, 1) == "File",
      repr(menu_label(app.menubar, 1)))
check("File menu first item is Open",
      menu_label(submenu(app.menubar, 1), 0) == "Open…\tCtrl+O",
      repr(menu_label(submenu(app.menubar, 1), 0)))
check("Options cascade is Options", menu_label(app.menubar, 4) == "Options",
      repr(menu_label(app.menubar, 4)))
check("Help cascade is Help", menu_label(app.menubar, 5) == "Help")
check("toolbar Add is English",
      app.toolbar_buttons["tb_add"].cget("text") == "＋ Add",
      repr(app.toolbar_buttons["tb_add"].cget("text")))
check("toolbar Extract is English",
      app.toolbar_buttons["tb_extract"].cget("text") == "⇩ Extract To")
check("tree heading Name is English",
      app.tree.heading("name", "text") == "Name")
check("tree heading Modified is English",
      app.tree.heading("modified", "text") == "Modified")
check("status Ready is English",
      app.status_msg.cget("text") == "Ready",
      repr(app.status_msg.cget("text")))
check("status count is English",
      app.status_count.cget("text") == "0 files",
      repr(app.status_count.cget("text")))
check("path var is English",
      app.path_var.get() == "No archive open", repr(app.path_var.get()))
check("back button is English",
      app.back_btn.cget("text") == "← Back")
check("About text is English",
      "A WinRAR-style archive manager" in
      app._t("about_text", app=main.APP_NAME, version=main.VERSION,
              author=main.AUTHOR, org=main.ORG, copyright=main.COPYRIGHT))
check("About keeps author line",
      "Developed by Md. Sonet Mia" in
      app._t("about_text", app=main.APP_NAME, version=main.VERSION,
              author=main.AUTHOR, org=main.ORG, copyright=main.COPYRIGHT))

# --- 2. Open archive in English ---
app.open_archive(zip_path)
root.update()
check("status count English with archive",
      app.status_count.cget("text") == "3 items (3 files)",
      repr(app.status_count.cget("text")))
check("status opened English",
      app.status_msg.cget("text") == "Opened: sample.zip",
      repr(app.status_msg.cget("text")))
check("tree rows are files",
      app.tree.heading("type", "text") == "Type")
check("type label English",
      app._type_label("readme.txt", False) == "TXT file" and
      app._type_label("docs", True) == "Folder",
      repr(app._type_label("readme.txt", False)))

# --- 3. Switch to Bengali via Options menu (radiobutton) ---
opt_menu = submenu(app.menubar, 4)
# find the Bengali radio item index by label
bn_idx = None
for i in range(opt_menu.index("end") + 1):
    try:
        if opt_menu.entryconfigure(i).get("label", (None,)*5)[-1] == "বাংলা (Bengali)":
            bn_idx = i
            break
    except Exception:
        pass
check("Bengali radio item exists in Options menu", bn_idx is not None)
opt_menu.invoke(bn_idx)
root.update()
check("lang is bn after switch", app.lang == "bn", f"lang={app.lang}")
check("settings file saved as bn",
      open(main.SETTINGS_FILE, encoding="utf-8").read().strip() ==
      '{"language": "bn"}',
      open(main.SETTINGS_FILE, encoding="utf-8").read())
check("menu cascade 0 is Bengali File",
      menu_label(app.menubar, 1) == "ফাইল (File)",
      repr(menu_label(app.menubar, 1)))
check("File menu first item is Bengali Open",
      menu_label(submenu(app.menubar, 1), 0) ==
      "খুলুন… (Open…)\tCtrl+O")
check("toolbar Add is Bengali",
      app.toolbar_buttons["tb_add"].cget("text") == "＋ যোগ করুন (Add)",
      repr(app.toolbar_buttons["tb_add"].cget("text")))
check("tree heading Name is Bengali",
      app.tree.heading("name", "text") == "নাম (Name)")
check("status count is Bengali with archive",
      app.status_count.cget("text") == "3টি আইটেম (মোট 3টি ফাইল)",
      repr(app.status_count.cget("text")))
# NOTE: _apply_language() calls refresh_list(), which (as in v1.0.0) replaces
# the transient "Opened: ..." text with the archive format. So after the
# switch the status shows the format, not the "Opened" message.
check("status msg shows format after Bengali switch",
      app.status_msg.cget("text") == "zip",
      repr(app.status_msg.cget("text")))
check("type label Bengali",
      app._type_label("readme.txt", False) == "TXT ফাইল" and
      app._type_label("docs", True) == "ফোল্ডার (Folder)")
check("About text is Bengali",
      "WinRAR-এর মতো আর্কাইভ ম্যানেজার" in
      app._t("about_text", app=main.APP_NAME, version=main.VERSION,
              author=main.AUTHOR, org=main.ORG, copyright=main.COPYRIGHT))
check("About keeps author line in Bengali mode",
      "Developed by Md. Sonet Mia" in
      app._t("about_text", app=main.APP_NAME, version=main.VERSION,
              author=main.AUTHOR, org=main.ORG, copyright=main.COPYRIGHT))
check("Help text is Bengali",
      "File > Open দিয়ে আর্কাইভ খুলুন" in app._t("help_text"))

# --- 4. Switch back to English ---
en_idx = None
for i in range(opt_menu.index("end") + 1):
    try:
        if opt_menu.entryconfigure(i).get("label", (None,)*5)[-1] == "English (default)":
            en_idx = i
            break
    except Exception:
        pass
# menubar was rebuilt on the bn switch, so re-fetch the Options submenu
opt_menu = submenu(app.menubar, 4)
for i in range(opt_menu.index("end") + 1):
    try:
        if opt_menu.entryconfigure(i).get("label", (None,)*5)[-1] == "English (default)":
            en_idx = i
            break
    except Exception:
        pass
check("English radio item exists in Options menu", en_idx is not None)
opt_menu.invoke(en_idx)
root.update()
check("lang is en after switch back", app.lang == "en", f"lang={app.lang}")
check("settings file saved as en",
      open(main.SETTINGS_FILE, encoding="utf-8").read().strip() ==
      '{"language": "en"}')
check("menu cascade 0 is File again",
      menu_label(app.menubar, 1) == "File",
      repr(menu_label(app.menubar, 1)))
check("toolbar Add is English again",
      app.toolbar_buttons["tb_add"].cget("text") == "＋ Add")
check("tree heading Name is English again",
      app.tree.heading("name", "text") == "Name")
check("status count is English again",
      app.status_count.cget("text") == "3 items (3 files)",
      repr(app.status_count.cget("text")))
check("recent menu still works after rebuilds",
      app.recent_menu.index("end") is not None)

print()
print(f"ফলাফল: {PASSED[0]}টি PASS, {len(FAILED)}টি FAIL")
if FAILED:
    print("ব্যর্থ: " + ", ".join(FAILED))
    root.destroy()
    sys.exit(1)
print("GUI ভাষা পরীক্ষা পাস করেছে।")
root.destroy()
sys.exit(0)
