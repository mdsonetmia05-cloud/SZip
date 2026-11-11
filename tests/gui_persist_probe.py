import json, os, sys, tkinter as tk
sys.path.insert(0, "/home/hatch/workspace/zip-extractor")
import main
home = os.path.expanduser("~")
# 1. persisted Bengali setting -> app starts in Bengali
with open(os.path.join(home, ".szip_settings.json"), "w", encoding="utf-8") as f:
    json.dump({"language": "bn"}, f)
root = tk.Tk(); app = main.SZipApp(root); root.update()
print("persisted bn -> lang:", app.lang, "| menu0:", app.menubar.entryconfigure(1)["label"][-1],
      "| status:", app.status_msg.cget("text"))
assert app.lang == "bn" and app.status_msg.cget("text") == "প্রস্তুত (Ready)"
# ProgressDialog uses current language
d = main.ProgressDialog(root, app._t("prog_extracting"), app._t)
root.update()
print("progress label (bn):", d.label.cget("text"))
assert d.label.cget("text") == "শুরু হচ্ছে… (Starting…)"
d.destroy()
# 2. corrupt settings file -> default en
with open(os.path.join(home, ".szip_settings.json"), "w", encoding="utf-8") as f:
    f.write("{not json")
app2 = main.SZipApp(tk.Toplevel(root)); root.update()
print("corrupt settings -> lang:", app2.lang)
assert app2.lang == "en"
# 3. invalid language value -> default en
with open(os.path.join(home, ".szip_settings.json"), "w", encoding="utf-8") as f:
    json.dump({"language": "xx"}, f)
print("invalid lang ->", main._load_language())
assert main._load_language() == "en"
root.destroy()
print("PERSISTENCE PROBE: ALL PASS")
