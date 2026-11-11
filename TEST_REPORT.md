# SZip — TEST REPORT (পরীক্ষার রিপোর্ট)

> নোট: পরীক্ষাগুলো চালানো হয়েছিল আগের নাম "Sweet Archiver"-এ; পরে শুধু নামের লেখা বদলে "SZip" করা হয়েছে, আর নাম বদলের পর সিস্টেম পাইথনে আবার চালিয়ে ৩৩/৩৩ পাস পাওয়া গেছে।

**তারিখ:** ২০২৬-১১-১১
**পরিবেশ:** Linux VM, Python 3.12.3
**পরীক্ষা করা হয়েছে:** `archive_core.py`-এর ফাংশনগুলো (GUI ছাড়া) + GUI স্মোক টেস্ট (Xvfb)

## নমুনা ডেটা

`/tmp/sweet-test/src/`-এ ৭টি ফাইল, নেস্টেড ফোল্ডার সহ:
`readme.txt`, `docs/guide.txt`, `docs/notes.md`, `docs/sub/deep.txt`,
`images/logo.png`, `images/photos/pic1.jpg`, `data/report.csv`
(মোট ৯৭৮ বাইট)। সব extract যাচাই করা হয়েছে SHA-256 মিলিয়ে।

## চালানো কমান্ড (exact commands)

```bash
# ১. py7zr-সহ টেস্ট পরিবেশ (সিস্টেম Python-এ py7zr ছিল না)
python3 -m venv /tmp/sweet-test-venv
/tmp/sweet-test-venv/bin/pip install -q py7zr   # py7zr 1.1.4 ইনস্টল হয়েছে

# ২. কম্পাইল যাচাই
cd ~/workspace/zip-extractor
python3 -m py_compile main.py archive_core.py
/tmp/sweet-test-venv/bin/python -m py_compile main.py archive_core.py

# ৩. মূল টেস্ট (py7zr-সহ)
cd ~/workspace/zip-extractor
/tmp/sweet-test-venv/bin/python tests/test_core.py

# ৪. সিস্টেম Python-এ টেস্ট (py7zr ছাড়া — graceful degradation যাচাই)
python3 tests/test_core.py

# ৫. GUI স্মোক টেস্ট (Xvfb-তে, আসল উইন্ডো খুলে)
/tmp/gui_smoke.py  (ভেতরে: Tk() + SweetArchiverApp, gui.zip খোলা, docs/-এ ঢোকা)
xvfb-run -a python3 /tmp/gui_smoke.py

# ৬. GUI ইমপোর্ট যাচাই
python3 -c "import main; print('main.py import OK (tkinter available)')"
```

## ফলাফল

### A. মূল টেস্ট — venv Python (py7zr 1.1.4): **৩৯টি PASS, ০টি FAIL**

| # | পরীক্ষা | ফলাফল |
|---|---|---|
| 1 | ZIP বানানো (৯০৮ B) | PASS |
| 2 | TAR.GZ বানানো | PASS |
| 3 | TAR.GZ stdlib দিয়ে cross-check (৭ ফাইল) | PASS |
| 4 | ZIP stdlib দিয়ে cross-check (৭ ফাইল) | PASS |
| 5 | ZIP তালিকা: ৭টি ফাইল | PASS |
| 6 | ZIP রুটে ৪টি আইটেম (readme, docs, images, data) | PASS |
| 7 | docs/ ফোল্ডারে ৩টি আইটেম | PASS |
| 8 | TAR.GZ তালিকা: ৭টি ফাইল | PASS |
| 9 | ZIP সব বের করা: ৭টি | PASS |
| 10 | প্রোগ্রেস কলব্যাক: শেষে 7/7 | PASS |
| 11 | ZIP extract-all: SHA-256 হুবহু মিলেছে | PASS |
| 12 | TAR.GZ সব বের করা: ৭টি | PASS |
| 13 | TAR.GZ extract-all: SHA-256 হুবহু মিলেছে | PASS |
| 14 | ZIP বাছা বের করা: ৩টি (guide + logo + pic1) | PASS |
| 15 | বাছা extract-এ readme.txt আসেনি | PASS |
| 16 | বাছা extract-এ pic1.jpg এসেছে | PASS |
| 17 | ZIP-এ ফাইল যোগ: ৭ → ৮টি | PASS |
| 18 | যোগ করা ফাইল বের করা যায় | PASS |
| 19 | ZIP থেকে ফাইল মোছা: ১টি | PASS |
| 20 | মোছার পর আবার ৭টি ফাইল | PASS |
| 21 | ZIP থেকে ফোল্ডার মোছা: docs/ গেলে ৪টি ফাইল | PASS |
| 22 | TAR থেকে মোছা বাধা পায় (ZIP only) | PASS |
| 23 | ZIP পরীক্ষা (test): OK | PASS |
| 24 | TAR.GZ পরীক্ষা (test): OK | PASS |
| 25 | নষ্ট ZIP (অর্ধেক কাটা) পরীক্ষা: OK নয় — ধরা পড়েছে | PASS |
| 26 | archive_info: TAR.GZ, ৭ ফাইল | PASS |
| 27 | RAR (rarfile নেই): সৎ বার্তা দেয় | PASS |
| 28 | RAR বানানো বন্ধ (proprietary) | PASS |
| 29 | path traversal (`../evil.txt`) আটকানো হয় | PASS |
| 30 | evil.txt বাইরে কোথাও তৈরি হয়নি | PASS |
| 31 | পাসওয়ার্ড ZIP সঠিক পাসওয়ার্ডে খোলে (`zip -P` দিয়ে বানানো) | PASS |
| 32 | ভুল পাসওয়ার্ডে বাধা পায় | PASS |
| 33 | 7Z বানানো হয়েছে | PASS |
| 34 | 7Z তালিকা: ৭টি ফাইল | PASS |
| 35 | 7Z সব বের করা: ৭টি, SHA-256 মিলেছে | PASS |
| 36 | 7Z বাছা বের করা: ১টি | PASS |
| 37 | 7Z পরীক্ষা (test): OK | PASS |
| 38 | 7Z-এ ফাইল যোগ (rebuild পথ): ৭ → ৮টি | PASS |
| 39 | (উপরের ১১ নম্বর সহ) সব extract SHA-256 যাচাই | PASS |

### B. সিস্টেম Python (py7zr/rarfile নেই): **৩৩টি PASS, ০টি FAIL**

৭Z-এর ৬টি পরীক্ষা skip হয়েছে, তার বদলে যাচাই হয়েছে: py7zr ছাড়া 7Z খুলতে
গেলে সৎ বার্তা আসে (`7Z খুলতে py7zr লাগবে — pip install py7zr`)। বাকি সব
ZIP/TAR/পাসওয়ার্ড/RAR-সীমা/path-traversal পরীক্ষা পাস করেছে।

### C. GUI স্মোক টেস্ট (Xvfb): **PASS**

- `Tk()` + `SweetArchiverApp` খুলেছে, `gui.zip` খুলে ট্রি-তে রুটে ৫টি আইটেম দেখিয়েছে
- `docs/`-এ ঢুকে ৩টি আইটেম দেখিয়েছে, স্ট্যাটাস বারে "৫টি আইটেম (মোট ৮টি ফাইল) | মোট সাইজ: 998 B"
- চেকবক্স সেট/সিলেকশন কাজ করেছে
- `main.py` ইমপোর্ট হয় (tkinter পাওয়া গেছে)

### D. কম্পাইল: **PASS**

`python3 -m py_compile main.py archive_core.py` — সিস্টেম Python ও venv দুটোতেই OK।

## পরীক্ষায় ধরা পড়া বাগ ও ফিক্স

- **বাগ:** py7zr 1.1.4-এ `FileInfo`-তে `lastwritetime` অ্যাট্রিবিউট নেই (আছে `creationtime`) —
  প্রথম রানে 7Z তালিকা `AttributeError` দিয়ে ভেঙেছিল (তখন ৩২টি PASS-এর পর থেমে যায়)।
- **ফিক্স:** `archive_core.py`-এর `_list_7z`-এ `getattr(info, "lastwritetime", None)` →
  না থাকলে `getattr(info, "creationtime", None)` — দুই সংস্করণেই চলে। ফিক্সের পর ৩৯/৩৯ PASS।

## যা পরীক্ষা করা হয়নি (সত্যিটা)

- **আসল RAR ফাইল খোলা:** এই VM-এ `rarfile`/`UnRAR`/নমুনা RAR কিছুই নেই — শুধু
  "সৎ বার্তা দেয়" পথটা পরীক্ষা হয়েছে। আসল RAR Mark-এর PC-তে UnRAR থাকলে যাচাই করতে হবে।
- **AES-এনক্রিপ্ট করা ZIP:** নমুনা ফাইল ছিল না, তাই শুধু কোডে detection আছে —
  আসল AES ZIP দিয়ে যাচাই হয়নি।
- **Windows .exe:** ইচ্ছে করেই বানানো হয়নি — Linux-এ PyInstaller দিয়ে Windows exe
  বানানো যায় না। `build.bat` Mark-এর Windows PC-তে (বা GitHub Actions Windows
  runner-এ) চালাতে হবে।
- **WinRAR ইনস্টলার চালানো হয়নি:** `workspace/user/files/winrar-x64-723.exe`
  Windows-only ফাইল — শুধু রেফারেন্স হিসেবে রাখা হয়েছে, একবারও চালানো/ইনস্টল করা হয়নি।
- **GUI চোখে দেখা:** Linux Xvfb-তে শুধু স্মোক টেস্ট হয়েছে; আসল Windows-এ চেহারা
  Mark-কে নিজে দেখে জানাতে হবে।

---

# v1.1.0 — ডিফল্ট ইংরেজি UI, বাংলা বদলানো যায় (২০২৬-১১-১১)

**পরিবর্তন:** `main.py`-এ `STRINGS` টেবিল যোগ করা হয়েছে (`en`/`bn`, ১৪১টি করে কি) —
মেনু, টুলবার, পথ বার, Treeview হেডিং, স্ট্যাটাস বার, সার্চ, সব বোতাম ও ডায়ালগ
(Help/About/Info/প্রম্পট/কনফার্মেশন/এরর) এখন দুই ভাষায়। ডিফল্ট **ইংরেজি**;
Options মেনুতে `English (default)` / `বাংলা (Bengali)` রেডিও — চাপলেই সাথে সাথে
পুরো UI বদলে যায় (রিস্টার্ট লাগে না), পছন্দ `~/.szip_settings.json`-এ থাকে।
VERSION 1.1.0; `version.txt`-ও 1.1.0 (CompanyName ও LegalCopyright আগের মতোই)।
About-এর লেখক লাইন (Developed by Md. Sonet Mia, Founder — SONET,
Copyright © 2026 Md. Sonet Mia, ওয়েবসাইট ও GitHub লিংক) দুই ভাষাতেই একই।

**`archive_core.py` বদলানো হয়নি — ইচ্ছে করে।** এর বার্তাগুলো (যেমন
"অসমর্থিত ফরম্যাট (unsupported format)") ইতিমধ্যে ইংরেজি বন্ধনীসহ, আর
পরীক্ষাগুলো বার্তার কি-ওয়ার্ডের ওপর নির্ভর করে (যেমন "RAR", "ZIP", "py7zr",
"unsafe") — ভাষা বদলে আবার Windows বিল্ড ভাঙার ঝুঁকি নেওয়া হয়নি। তাই কোর
এরর বার্তা (যেমন আর্কাইভ খুলতে না পারলে দেখানো বার্তা) এখনো বাংলায়, ইংরেজি
বন্ধনীসহ। GUI-এর নিজের সব লেখা ইংরেজি-ডিফল্ট।

## চালানো কমান্ড (exact commands)

```bash
cd ~/workspace/zip-extractor

# ১. কম্পাইল যাচাই
python3 -m py_compile main.py archive_core.py tests/test_core.py

# ২. মূল টেস্ট — venv Python (py7zr 1.1.4 + rarfile, UnRAR নেই = Actions runner-এর মতো)
#    (python3 -m venv /tmp/sweet-test-venv; pip install py7zr rarfile — আগেই করা ছিল)
/tmp/sweet-test-venv/bin/python tests/test_core.py

# ৩. সিস্টেম Python-এ টেস্ট (py7zr/rarfile নেই)
python3 tests/test_core.py

# ৪. GUI ভাষা স্মোক টেস্ট (Xvfb-তে, আসল উইন্ডো খুলে; tests/gui_lang_smoke.py)
rm -rf /tmp/szip-gui-home && mkdir -p /tmp/szip-gui-home
HOME=/tmp/szip-gui-home xvfb-run -a python3 tests/gui_lang_smoke.py

# ৫. পারসিস্টেন্স প্রব (সংরক্ষিত বাংলা সেটিংসে শুরু, নষ্ট সেটিংসে ডিফল্ট en;
#    tests/gui_persist_probe.py)
rm -rf /tmp/szip-gui-home2 && mkdir -p /tmp/szip-gui-home2
HOME=/tmp/szip-gui-home2 xvfb-run -a python3 tests/gui_persist_probe.py
```

## ফলাফল — v1.1.0

- **কম্পাইল: PASS** (`python3 -m py_compile main.py archive_core.py tests/test_core.py`)
- **মূল টেস্ট — venv (py7zr + rarfile): ৩৯টি PASS, ০টি FAIL**
- **সিস্টেম Python: ৩৩টি PASS, ০টি FAIL**
- **GUI ভাষা স্মোক টেস্ট (Xvfb): ৪১টি PASS, ০টি FAIL** — সেটিংস ফাইল না থাকলে
  ডিফল্ট ইংরেজি (মেনু File/Options/Help, টুলবার "＋ Add", হেডিং Name/Modified,
  স্ট্যাটাস "Ready", "0 files", "No archive open"); স্যাম্পল ZIP খুলে
  "3 items (3 files)" / "Opened: sample.zip"; Options মেনুর রেডিওতে বাংলায়
  বদল ("ফাইল (File)", "＋ যোগ করুন (Add)", "নাম (Name)",
  "3টি আইটেম (মোট 3টি ফাইল)"), `~/.szip_settings.json`-এ `{"language": "bn"}`
  সংরক্ষিত; আবার English-এ ফিরে গিয়ে সব আগের মতো, সেটিংস `{"language": "en"}`।
  About/Help-এর ইংরেজি ও বাংলা লেখা দুটোই যাচাই করা হয়েছে; লেখক লাইন দুই
  ভাষাতেই অপরিবর্তিত।
- **পারসিস্টেন্স প্রব: ALL PASS** — সংরক্ষিত `{"language": "bn"}` থাকলে অ্যাপ
  বাংলায় শুরু হয় ("ফাইল (File)", "প্রস্তুত (Ready)"); প্রোগ্রেস ডায়ালগের
  লেবেলও বাংলায়; নষ্ট সেটিংস ফাইল বা ভুল ভাষা (`"xx"`) থাকলে ডিফল্ট `en`।

## স্মোক টেস্টে পাওয়া একটি বিষয় (অ্যাপের বাগ নয়)

ভাষা বদলের সময় `_apply_language()` `refresh_list()` ডাকে, যা v1.0.0-এর মতোই
ক্ষণস্থায়ী "Opened: ..." স্ট্যাটাসটি আর্কাইভের ফরম্যাট ("zip") দিয়ে বদলে দেয় —
সর্ট/সার্চ/নেভিগেশনের পরও একই আচরণ হয়। পরীক্ষার প্রত্যাশা সেভাবেই ঠিক করা হয়েছে;
অ্যাপের আচরণে কিছু বদলানো হয়নি।

## যা পরীক্ষা করা হয়নি (সত্যিটা, v1.1.0)

- **আসল Windows-এ GUI:** শুধু Linux Xvfb-তে যাচাই হয়েছে; Windows-এ চেহারা ও
  ভাষা বদল Mark-কে নিজে দেখে জানাতে হবে।
- **Windows .exe:** ইচ্ছে করেই বানানো হয়নি — Linux-এ PyInstaller দিয়ে Windows
  exe বানানো যায় না। v1.1.0-এর exe আলাদাভাবে (GitHub Actions) বানাতে হবে।
- **archive_core.py-এর বার্তা:** ওপরে বলা কারণে ইচ্ছে করে বদলানো হয়নি।
