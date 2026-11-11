# -*- coding: utf-8 -*-
"""
tests/test_core.py — archive_core.py-এর স্বয়ংক্রিয় পরীক্ষা (GUI ছাড়া)
Automated tests for archive_core.py (no GUI needed).

চালানো:  python tests/test_core.py        (py7zr থাকলে 7Z-ও পরীক্ষা হবে)
           python3 tests/test_core.py       (py7zr ছাড়া — 7Z অংশ skip হবে)
"""
import hashlib
import os
import shutil
import sys
import tarfile
import zipfile

# Windows কনসোল (cp1252) বাংলা ছাপতে পারে না বলে পরীক্ষা ভেঙে যেত —
# তাই শুরুতেই stdout/stderr UTF-8 করে নেওয়া হয়। GitHub Actions-এ
# এটা না থাকলে UnicodeEncodeError-এ "Run core tests" ধাপটি ফেল করত।
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from archive_core import (  # noqa: E402
    ArchiveError, add_to_archive, archive_info, create_archive,
    delete_from_archive, detect_format, extract_all, extract_selected,
    format_size, list_archive, list_children, test_archive,
    HAS_PY7ZR, HAS_RARFILE,
)

BASE = "/tmp/sweet-test"
SRC = os.path.join(BASE, "src")
FAILED = []
PASSED = [0]


def check(name, cond, detail=""):
    if cond:
        PASSED[0] += 1
        print(f"  PASS: {name}" + (f" — {detail}" if detail else ""))
    else:
        FAILED.append(name)
        print(f"  FAIL: {name}" + (f" — {detail}" if detail else ""))


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def write(rel, content):
    p = os.path.join(SRC, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    mode = "wb" if isinstance(content, bytes) else "w"
    with open(p, mode) as f:
        f.write(content)
    return p


def make_sources():
    shutil.rmtree(BASE, ignore_errors=True)
    os.makedirs(SRC)
    write("readme.txt", "Hello SZip\nLine two.\n")
    write("docs/guide.txt", "User guide content " * 20)
    write("docs/notes.md", "# Notes\n- one\n- two\n")
    write("docs/sub/deep.txt", "deep nested file")
    write("images/logo.png", b"\x89PNG\r\n\x1a\n" + b"A" * 200)
    write("images/photos/pic1.jpg", b"\xff\xd8\xff\xe0" + b"B" * 300)
    write("data/report.csv", "name,value\na,1\nb,2\n")
    return [os.path.join(SRC, n) for n in sorted(os.listdir(SRC))]


def expected_files():
    out = {}
    for root, _dirs, files in os.walk(SRC):
        for fn in files:
            full = os.path.join(root, fn)
            out[os.path.relpath(full, SRC)] = sha(full)
    return out


def verify_extracted(dest, expected, label):
    ok = True
    for rel, digest in expected.items():
        p = os.path.join(dest, rel)
        if not os.path.isfile(p) or sha(p) != digest:
            ok = False
            print(f"     mismatch/missing: {rel}")
    check(f"{label}: সব ফাইলের বিষয়বস্তু হুবহু মিলেছে", ok,
          f"{len(expected)}টি ফাইল")


def main():
    print("== SZip — archive_core পরীক্ষা ==")
    print(f"py7zr: {HAS_PY7ZR}, rarfile: {HAS_RARFILE}, python: {sys.version.split()[0]}")
    sources = make_sources()
    expected = expected_files()
    print(f"নমুনা ফাইল: {len(expected)}টি, নেস্টেড ফোল্ডার সহ")

    zip_path = os.path.join(BASE, "sample.zip")
    tar_path = os.path.join(BASE, "sample.tar.gz")
    seven_path = os.path.join(BASE, "sample.7z")

    # --- 1. বানানো (create) ---
    create_archive(zip_path, sources)
    check("ZIP বানানো হয়েছে", os.path.isfile(zip_path) and os.path.getsize(zip_path) > 0,
          format_size(os.path.getsize(zip_path)))
    create_archive(tar_path, sources)
    check("TAR.GZ বানানো হয়েছে", os.path.isfile(tar_path))
    with tarfile.open(tar_path, "r:*") as tf:
        check("TAR.GZ stdlib দিয়ে যাচাই (cross-check)",
              len([m for m in tf.getmembers() if m.isfile()]) == 7)
    with zipfile.ZipFile(zip_path) as zf:
        check("ZIP stdlib দিয়ে যাচাই (cross-check)",
              len([i for i in zf.infolist() if not i.is_dir()]) == 7)

    # --- 2. তালিকা (list) ---
    z_entries = list_archive(zip_path)
    z_files = [e for e in z_entries if not e.is_dir]
    check("ZIP তালিকা: 7টি ফাইল", len(z_files) == 7, f"পাওয়া গেছে {len(z_files)}টি")
    root_children = list_children(z_entries, "")
    check("ZIP রুটে 4টি আইটেম (readme, docs, images, data)",
          len(root_children) == 4, [c.name for c in root_children])
    docs_children = list_children(z_entries, "docs")
    check("docs/ ফোল্ডারে 3টি আইটেম (guide, notes, sub)",
          len(docs_children) == 3, [c.name for c in docs_children])
    t_entries = list_archive(tar_path)
    check("TAR.GZ তালিকা: 7টি ফাইল",
          len([e for e in t_entries if not e.is_dir]) == 7)

    # --- 3. সব বের করা (extract all) ---
    dest = os.path.join(BASE, "out_zip_all")
    calls = []
    n = extract_all(zip_path, dest, progress=lambda d, t, name: calls.append((d, t)))
    check("ZIP সব বের করা: 7টি", n == 7)
    check("প্রোগ্রেস কলব্যাক: শেষে 7/7", calls and calls[-1] == (7, 7))
    verify_extracted(dest, expected, "ZIP extract-all")
    dest_t = os.path.join(BASE, "out_tar_all")
    check("TAR.GZ সব বের করা: 7টি", extract_all(tar_path, dest_t) == 7)
    verify_extracted(dest_t, expected, "TAR.GZ extract-all")

    # --- 4. বাছা ফাইল বের করা (extract selected) ---
    dest_s = os.path.join(BASE, "out_zip_sel")
    n = extract_selected(zip_path, ["docs/guide.txt", "images"], dest_s)
    check("ZIP বাছা বের করা: 3টি (guide + logo + pic1)", n == 3, f"পাওয়া গেছে {n}টি")
    check("বাছা extract-এ readme.txt আসেনি",
          not os.path.exists(os.path.join(dest_s, "readme.txt")))
    check("বাছা extract-এ pic1.jpg এসেছে",
          os.path.isfile(os.path.join(dest_s, "images/photos/pic1.jpg")))

    # --- 5. যোগ করা (add) + মোছা (delete, ZIP only) ---
    new_file = write("extra.txt", "new file added later")
    # extra.txt SRC-র ভেতরে বানানো হয়েছে — expected-এ ঢোকেনি, সেটাই ঠিক
    add_to_archive(zip_path, [new_file])
    after_add = [e for e in list_archive(zip_path) if not e.is_dir]
    check("ZIP-এ ফাইল যোগ: 7 -> 8টি", len(after_add) == 8, f"এখন {len(after_add)}টি")
    dest_add = os.path.join(BASE, "out_zip_add")
    extract_selected(zip_path, ["extra.txt"], dest_add)
    check("যোগ করা ফাইল বের করা যায়",
          open(os.path.join(dest_add, "extra.txt")).read() == "new file added later")
    deleted = delete_from_archive(zip_path, ["extra.txt"])
    check("ZIP থেকে ফাইল মোছা: 1টি", deleted == 1)
    check("মোছার পর আবার 7টি ফাইল",
          len([e for e in list_archive(zip_path) if not e.is_dir]) == 7)
    delete_from_archive(zip_path, ["docs"])
    check("ZIP থেকে ফোল্ডার মোছা: docs/ গেলে 4টি ফাইল থাকে",
          len([e for e in list_archive(zip_path) if not e.is_dir]) == 4)
    try:
        delete_from_archive(tar_path, ["readme.txt"])
        check("TAR থেকে মোছা বাধা পায় (ZIP only)", False, "বাধা পায়নি!")
    except ArchiveError as exc:
        check("TAR থেকে মোছা বাধা পায় (ZIP only)", "ZIP" in str(exc), str(exc))

    # --- 6. পরীক্ষা (integrity test) ---
    ok, bad, msg = test_archive(zip_path)
    check("ZIP পরীক্ষা: OK", ok, msg)
    ok, bad, msg = test_archive(tar_path)
    check("TAR.GZ পরীক্ষা: OK", ok, msg)
    bad_zip = os.path.join(BASE, "broken.zip")
    shutil.copy(zip_path, bad_zip)
    with open(bad_zip, "r+b") as f:  # ফাইল কেটে নষ্ট করা
        f.truncate(os.path.getsize(bad_zip) // 2)
    ok, bad, msg = test_archive(bad_zip)
    check("নষ্ট ZIP পরীক্ষা: OK নয় (সত্যি ধরা পড়েছে)", not ok, msg)

    # --- 7. তথ্য (info) ---
    info = archive_info(tar_path)
    check("archive_info: TAR.GZ, 7 ফাইল",
          info["format"] == "tar.gz" and info["file_count"] == 7, str(info))

    # --- 8. RAR: সৎ সীমা ---
    try:
        list_archive(os.path.join(BASE, "fake.rar"))
        check("RAR ছাড়া rarfile: সৎ বার্তা দেয়", False, "ভুল হয়নি!")
    except ArchiveError as exc:
        check("RAR ছাড়া rarfile: সৎ বার্তা দেয়",
              ("rarfile" in str(exc) or "UnRAR" in str(exc)), str(exc))
    try:
        create_archive(os.path.join(BASE, "x.rar"), sources)
        check("RAR বানানো বন্ধ (proprietary)", False, "বানিয়ে ফেলেছে!")
    except ArchiveError as exc:
        check("RAR বানানো বন্ধ (proprietary)", "RAR" in str(exc), str(exc))

    # --- 9. Path traversal সুরক্ষা ---
    evil_zip = os.path.join(BASE, "evil.zip")
    with zipfile.ZipFile(evil_zip, "w") as zf:
        zf.writestr("../evil.txt", "pwned")
        zf.writestr("good.txt", "ok")
    evil_dest = os.path.join(BASE, "out_evil")
    try:
        extract_all(evil_zip, evil_dest)
        check("path traversal আটকানো হয় (../)", False, "আটকায়নি!")
    except ArchiveError as exc:
        check("path traversal আটকানো হয় (../)", "unsafe" in str(exc).lower()
              or "অনিরাপদ" in str(exc), str(exc))
    check("evil.txt বাইরে কোথাও তৈরি হয়নি",
          not os.path.exists(os.path.join(BASE, "evil.txt"))
          and not os.path.exists("/tmp/evil.txt"))

    # --- 10. পাসওয়ার্ড ZIP (zip CLI থাকলে) ---
    if shutil.which("zip"):
        pw_src = os.path.join(BASE, "pw_src")
        os.makedirs(pw_src, exist_ok=True)
        with open(os.path.join(pw_src, "secret.txt"), "w") as f:
            f.write("top secret")
        pw_zip = os.path.join(BASE, "pw.zip")
        os.system(f"cd {pw_src} && zip -q -P s3cret {pw_zip} secret.txt")
        dest_pw = os.path.join(BASE, "out_pw")
        n = extract_all(pw_zip, dest_pw, password="s3cret")
        check("পাসওয়ার্ড ZIP সঠিক পাসওয়ার্ডে খোলে", n == 1
              and open(os.path.join(dest_pw, "secret.txt")).read() == "top secret")
        try:
            extract_all(pw_zip, os.path.join(BASE, "out_pw_wrong"), password="wrong")
            check("ভুল পাসওয়ার্ডে বাধা পায়", False, "খুলে গেছে!")
        except ArchiveError:
            check("ভুল পাসওয়ার্ডে বাধা পায়", True)
    else:
        print("  SKIP: পাসওয়ার্ড ZIP পরীক্ষা — 'zip' CLI নেই")

    # --- 11. 7Z (py7zr থাকলে) ---
    if HAS_PY7ZR:
        create_archive(seven_path, sources)
        check("7Z বানানো হয়েছে", os.path.isfile(seven_path))
        s_entries = list_archive(seven_path)
        check("7Z তালিকা: 7টি ফাইল",
              len([e for e in s_entries if not e.is_dir]) == 7)
        dest_7 = os.path.join(BASE, "out_7z_all")
        check("7Z সব বের করা: 7টি", extract_all(seven_path, dest_7) == 7)
        verify_extracted(dest_7, expected, "7Z extract-all")
        dest_7s = os.path.join(BASE, "out_7z_sel")
        check("7Z বাছা বের করা: 1টি",
              extract_selected(seven_path, ["data/report.csv"], dest_7s) == 1)
        ok, bad, msg = test_archive(seven_path)
        check("7Z পরীক্ষা: OK", ok, msg)
        check("7Z-এ ফাইল যোগ (rebuild পথ)",
              add_to_archive(seven_path, [new_file]) == seven_path
              and len([e for e in list_archive(seven_path) if not e.is_dir]) == 8)
    else:
        print("  SKIP: 7Z পরীক্ষা — py7zr ইনস্টল নেই")
        try:
            list_archive(seven_path if os.path.exists(seven_path) else os.path.join(BASE, "x.7z"))
            check("py7zr ছাড়া 7Z: সৎ বার্তা দেয়", False)
        except ArchiveError as exc:
            check("py7zr ছাড়া 7Z: সৎ বার্তা দেয়", "py7zr" in str(exc), str(exc))

    # --- ফলাফল ---
    print()
    print(f"ফলাফল: {PASSED[0]}টি PASS, {len(FAILED)}টি FAIL")
    if FAILED:
        print("ব্যর্থ: " + ", ".join(FAILED))
        sys.exit(1)
    print("সব পরীক্ষা পাস করেছে।")
    sys.exit(0)


if __name__ == "__main__":
    main()
