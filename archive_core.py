# -*- coding: utf-8 -*-
"""
archive_core.py — SZip-এর আর্কাইভ লজিক (GUI থেকে আলাদা)
Archive logic for SZip, kept separate from the GUI.
Copyright (c) 2026 Md. Sonet Mia (SONET). All rights reserved.

শুধু Python standard library ব্যবহার করা হয়েছে যেখানে সম্ভব:
  ZIP  -> zipfile, TAR/GZ/BZ2/XZ -> tarfile
ঐচ্ছিক (না থাকলে সুন্দরভাবে বার্তা দিয়ে বন্ধ হবে, ক্র্যাশ করবে না):
  7Z   -> py7zr,   RAR (শুধু খোলা) -> rarfile + UnRAR বাইনারি

সতর্কতা / Honest limits:
  * RAR বানানো (create) দেওয়া হয় না — RAR ফরম্যাট প্রোপ্রাইটারি।
  * AES-এনক্রিপ্ট করা ZIP খোলা যায় না — Python-এর zipfile শুধু
    পুরনো ZipCrypto পাসওয়ার্ড বোঝে।
  * ফাইল বের করার সময় path traversal (../) আটকানো হয় — ফাইল
    কখনো গন্তব্য ফোল্ডারের বাইরে যাবে না।
"""

import os
import shutil
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime

# ---------------------------------------------------------------------------
# ঐচ্ছিক নির্ভরতা (optional dependencies) — না থাকলেও বাকি সব চলবে
# ---------------------------------------------------------------------------
try:
    import py7zr  # type: ignore
    HAS_PY7ZR = True
except ImportError:  # pragma: no cover
    py7zr = None
    HAS_PY7ZR = False

try:
    import rarfile  # type: ignore
    HAS_RARFILE = True
except ImportError:  # pragma: no cover
    rarfile = None
    HAS_RARFILE = False


# ---------------------------------------------------------------------------
# ধ্রুবক (constants)
# ---------------------------------------------------------------------------
READ_EXTENSIONS = (".zip", ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2",
                   ".tar.xz", ".txz", ".7z", ".rar")

# তৈরির জন্য সমর্থিত ফরম্যাট: key = ফাইলের এক্সটেনশন
CREATE_FORMATS = {
    ".zip": "zip",
    ".7z": "7z",
    ".tar": "tar",
    ".tar.gz": "tar.gz",
    ".tgz": "tar.gz",
    ".tar.bz2": "tar.bz2",
    ".tbz2": "tar.bz2",
    ".tar.xz": "tar.xz",
    ".txz": "tar.xz",
}

EXECUTABLE_EXTS = {".exe", ".bat", ".cmd", ".msi", ".scr", ".com", ".ps1", ".vbs"}


@dataclass
class ArchiveEntry:
    """আর্কাইভের ভেতরের একটি ফাইল বা ফোল্ডারের তথ্য / one member."""
    name: str            # আর্কাইভের ভেতরের পুরো পথ, ফোল্ডার হলে শেষে '/'
    is_dir: bool
    size: int = 0        # আনকমপ্রেসড সাইজ (বাইট)
    modified: object = None  # datetime বা None


class ArchiveError(Exception):
    """আর্কাইভ সংক্রান্ত সব ভুলের জন্য একটাই exception।"""
    pass


# ---------------------------------------------------------------------------
# ছোট সাহায্যকারী (helpers)
# ---------------------------------------------------------------------------
def format_size(n):
    """বাইটকে মানুষের পড়ার মতো করে দেখানো / human-readable size."""
    n = int(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} TB"


def file_type_label(name, is_dir):
    """নাম দেখে টাইপের লেবেল / type label from file name."""
    if is_dir:
        return "ফোল্ডার (Folder)"
    ext = os.path.splitext(name)[1].lower()
    return ext[1:].upper() + " ফাইল" if ext else "ফাইল (File)"


def detect_format(path):
    """ফাইলের এক্সটেনশন দেখে ফরম্যাট চেনা / detect format from extension."""
    low = path.lower()
    if low.endswith(".tar.gz") or low.endswith(".tgz"):
        return "tar.gz"
    if low.endswith(".tar.bz2") or low.endswith(".tbz2"):
        return "tar.bz2"
    if low.endswith(".tar.xz") or low.endswith(".txz"):
        return "tar.xz"
    if low.endswith(".zip"):
        return "zip"
    if low.endswith(".tar"):
        return "tar"
    if low.endswith(".7z"):
        return "7z"
    if low.endswith(".rar"):
        return "rar"
    return None


def is_supported_archive(path):
    """এই ফাইলটা খোলা যাবে কি না / can this file be opened?"""
    return detect_format(path) is not None


def _pwd_bytes(password):
    """পাসওয়ার্ড str হলে bytes-এ বদলানো (zipfile-এর জন্য)।"""
    if password is None:
        return None
    if isinstance(password, bytes):
        return password
    return str(password).encode("utf-8")


def _safe_join(dest, member):
    """Path traversal থেকে বাঁচা: member যেন dest-এর ভেতরেই থাকে।"""
    dest_abs = os.path.abspath(dest)
    target = os.path.abspath(os.path.join(dest_abs, member))
    if os.path.commonpath([dest_abs, target]) != dest_abs:
        raise ArchiveError(f"অনিরাপদ পথ (unsafe path) আটকানো হয়েছে: {member}")
    return target


def _is_aes_zip_info(info):
    """ZipInfo-তে AES এনক্রিপশনের extra field (0x9901) আছে কি না।"""
    extra = info.extra or b""
    i = 0
    while i + 4 <= len(extra):
        header_id = int.from_bytes(extra[i:i + 2], "little")
        size = int.from_bytes(extra[i + 2:i + 4], "little")
        if header_id == 0x9901:
            return True
        i += 4 + size
    return False


def zip_needs_password(path):
    """ZIP-এ এনক্রিপ্ট করা ফাইল আছে কি না / is any member encrypted?"""
    try:
        with zipfile.ZipFile(path) as zf:
            return any(info.flag_bits & 0x1 for info in zf.infolist())
    except Exception:
        return False


def zip_has_aes(path):
    """ZIP-এ AES-এনক্রিপ্ট করা ফাইল আছে কি না (খোলা যাবে না)।"""
    try:
        with zipfile.ZipFile(path) as zf:
            return any(_is_aes_zip_info(info) for info in zf.infolist())
    except Exception:
        return False


# ---------------------------------------------------------------------------
# তালিকা (listing)
# ---------------------------------------------------------------------------
def list_archive(path, password=None):
    """আর্কাইভের সব এন্ট্রির তালিকা / list all members of an archive."""
    fmt = detect_format(path)
    if fmt is None:
        raise ArchiveError(f"অসমর্থিত ফরম্যাট (unsupported format): {path}")
    if fmt == "zip":
        return _list_zip(path)
    if fmt in ("tar", "tar.gz", "tar.bz2", "tar.xz"):
        return _list_tar(path)
    if fmt == "7z":
        return _list_7z(path, password)
    if fmt == "rar":
        return _list_rar(path, password)
    raise ArchiveError(f"অসমর্থিত ফরম্যাট (unsupported format): {fmt}")


def _list_zip(path):
    entries = []
    try:
        with zipfile.ZipFile(path) as zf:
            for info in zf.infolist():
                entries.append(ArchiveEntry(
                    name=info.filename,
                    is_dir=info.is_dir(),
                    size=info.file_size,
                    modified=datetime(*info.date_time),
                ))
    except zipfile.BadZipFile:
        raise ArchiveError("ফাইলটি বৈধ ZIP নয় (not a valid ZIP file)।")
    return entries


def _list_tar(path):
    entries = []
    try:
        with tarfile.open(path, "r:*") as tf:
            for m in tf.getmembers():
                entries.append(ArchiveEntry(
                    name=m.name + ("/" if m.isdir() and not m.name.endswith("/") else ""),
                    is_dir=m.isdir(),
                    size=m.size,
                    modified=datetime.fromtimestamp(m.mtime) if m.mtime else None,
                ))
    except tarfile.TarError as exc:
        raise ArchiveError(f"TAR ফাইল খোলা যায়নি: {exc}")
    return entries


def _list_7z(path, password=None):
    if not HAS_PY7ZR:
        raise ArchiveError(
            "7Z খুলতে py7zr লাগবে — pip install py7zr দিয়ে ইনস্টল করুন "
            "(7z support needs py7zr: pip install py7zr)।")
    try:
        with py7zr.SevenZipFile(path, mode="r", password=password) as z:
            entries = []
            for info in z.list():
                # py7zr সংস্করণভেদে ফিল্ডের নাম বদলায় (1.x-এ creationtime)
                modified = getattr(info, "lastwritetime", None)
                if modified is None:
                    modified = getattr(info, "creationtime", None)
                entries.append(ArchiveEntry(
                    name=info.filename + ("/" if info.is_directory and not info.filename.endswith("/") else ""),
                    is_dir=info.is_directory,
                    size=info.uncompressed or 0,
                    modified=modified,
                ))
            return entries
    except Exception as exc:
        raise ArchiveError(f"7Z ফাইল খোলা যায়নি: {exc}")


def _list_rar(path, password=None):
    if not HAS_RARFILE:
        raise ArchiveError(
            "RAR খুলতে rarfile আর UnRAR লাগবে — pip install rarfile করুন "
            "এবং UnRAR বাইনারি ইনস্টল করুন (RAR needs rarfile + UnRAR)।")
    try:
        with rarfile.RarFile(path) as rf:
            entries = []
            for info in rf.infolist():
                entries.append(ArchiveEntry(
                    name=info.filename + ("/" if info.isdir() and not info.filename.endswith("/") else ""),
                    is_dir=info.isdir(),
                    size=info.file_size,
                    modified=datetime(*info.date_time) if info.date_time else None,
                ))
            return entries
    except rarfile.RarCannotExec as exc:
        raise ArchiveError(
            "UnRAR বাইনারি পাওয়া যায়নি — RAR খুলতে UnRAR ইনস্টল করুন। "
            f"(UnRAR binary not found: {exc})")
    except Exception as exc:
        raise ArchiveError(f"RAR ফাইল খোলা যায়নি: {exc}")


def list_children(entries, folder):
    """কোনো ফোল্ডারের সরাসরি ভেতরের জিনিসগুলো / immediate children of a folder.

    folder = "" মানে রুট। ফোল্ডারগুলো একসাথে গুছিয়ে দেখানো হয়।
    """
    folder = (folder or "").strip("/")
    prefix = folder + "/" if folder else ""
    children = {}
    for e in entries:
        if not e.name.startswith(prefix):
            continue
        rest = e.name[len(prefix):].strip("/")
        if not rest:
            continue
        first = rest.split("/")[0]
        is_sub = "/" in rest
        key = prefix + first + ("/" if is_sub or e.is_dir else "")
        if key in children:
            if children[key].is_dir:
                children[key].size += e.size
            continue
        if is_sub:
            children[key] = ArchiveEntry(name=key, is_dir=True,
                                         size=e.size if not e.is_dir else 0,
                                         modified=e.modified)
        else:
            children[key] = e
    return sorted(children.values(), key=lambda x: (not x.is_dir, x.name.lower()))


# ---------------------------------------------------------------------------
# বের করা (extraction)
# ---------------------------------------------------------------------------
def _expand_names(entries, names):
    """বাছা নামগুলোকে আসল সদস্য-নামে ভাঙা — ফোল্ডার বাছলে তার ভেতরের সব ফাইল।"""
    wanted = set()
    for name in names:
        name = name.rstrip("/")
        for e in entries:
            if e.name.rstrip("/") == name or e.name.startswith(name + "/"):
                if not e.is_dir:
                    wanted.add(e.name)
    return sorted(wanted)


def extract_all(path, dest, password=None, progress=None):
    """সব ফাইল বের করা / extract everything. Returns: বের করা ফাইলের সংখ্যা।"""
    entries = list_archive(path, password=password)
    files = [e.name for e in entries if not e.is_dir]
    return _extract_members(path, files, dest, password=password, progress=progress)


def extract_selected(path, names, dest, password=None, progress=None):
    """শুধু বাছা ফাইল বের করা / extract only the selected members."""
    entries = list_archive(path, password=password)
    files = _expand_names(entries, names)
    if not files:
        raise ArchiveError("বের করার মতো কোনো ফাইল বাছা হয়নি (nothing selected)।")
    return _extract_members(path, files, dest, password=password, progress=progress)


def _extract_members(path, files, dest, password=None, progress=None):
    fmt = detect_format(path)
    os.makedirs(dest, exist_ok=True)
    total = len(files)
    if fmt == "zip":
        return _extract_zip(path, files, dest, password, progress, total)
    if fmt in ("tar", "tar.gz", "tar.bz2", "tar.xz"):
        return _extract_tar(path, files, dest, progress, total)
    if fmt == "7z":
        return _extract_7z(path, files, dest, password, progress, total)
    if fmt == "rar":
        return _extract_rar(path, files, dest, password, progress, total)
    raise ArchiveError(f"অসমর্থিত ফরম্যাট (unsupported format): {fmt}")


def _extract_zip(path, files, dest, password, progress, total):
    pwd = _pwd_bytes(password)
    if zip_has_aes(path) and files:
        # AES চেক: শুধু এনক্রিপ্ট করা ফাইল থাকলেই বাধা
        with zipfile.ZipFile(path) as zf:
            aes_names = {i.filename for i in zf.infolist() if _is_aes_zip_info(i)}
        if aes_names & set(files):
            raise ArchiveError(
                "এই ZIP-এ AES এনক্রিপশন আছে — Python-এর zipfile তা খুলতে পারে না। "
                "(AES-encrypted ZIP is not supported by Python's zipfile.)")
    done = 0
    try:
        with zipfile.ZipFile(path) as zf:
            for name in files:
                _safe_join(dest, name)  # traversal চেক
                try:
                    zf.extract(name, path=dest, pwd=pwd)
                except RuntimeError as exc:
                    # ভুল/অনুপস্থিত পাসওয়ার্ডে zipfile RuntimeError দেয়
                    raise ArchiveError(
                        f"পাসওয়ার্ড ভুল বা দেওয়া হয়নি: {name} ({exc})")
                done += 1
                if progress:
                    progress(done, total, name)
    except zipfile.BadZipFile:
        raise ArchiveError("ফাইলটি বৈধ ZIP নয় (not a valid ZIP file)।")
    return done


def _extract_tar(path, files, dest, progress, total):
    wanted = set(files)
    done = 0
    try:
        with tarfile.open(path, "r:*") as tf:
            for m in tf.getmembers():
                if m.name not in wanted:
                    continue
                _safe_join(dest, m.name)  # traversal চেক
                tf.extract(m, path=dest, filter="data")  # নিরাপদ extract
                done += 1
                if progress:
                    progress(done, total, m.name)
    except tarfile.TarError as exc:
        raise ArchiveError(f"TAR বের করা যায়নি: {exc}")
    return done


def _extract_7z(path, files, dest, password, progress, total):
    if not HAS_PY7ZR:
        raise ArchiveError("7Z বের করতে py7zr লাগবে (pip install py7zr)।")
    try:
        with py7zr.SevenZipFile(path, mode="r", password=password) as z:
            if len(files) == len(z.getnames()):
                z.extractall(path=dest)
                done = len(files)
            else:
                z.extract(targets=files, path=dest)
                done = len(files)
            if progress:
                for i, name in enumerate(files, 1):
                    progress(i, total, name)
        return done
    except Exception as exc:
        raise ArchiveError(f"7Z বের করা যায়নি: {exc}")


def _extract_rar(path, files, dest, password, progress, total):
    if not HAS_RARFILE:
        raise ArchiveError("RAR বের করতে rarfile + UnRAR লাগবে।")
    try:
        with rarfile.RarFile(path) as rf:
            rf.extractall(path=dest, members=files, pwd=password)
            if progress:
                for i, name in enumerate(files, 1):
                    progress(i, total, name)
        return total
    except rarfile.RarCannotExec as exc:
        raise ArchiveError(f"UnRAR বাইনারি পাওয়া যায়নি: {exc}")
    except Exception as exc:
        raise ArchiveError(f"RAR বের করা যায়নি: {exc}")


# ---------------------------------------------------------------------------
# বানানো / যোগ করা (creation / adding)
# ---------------------------------------------------------------------------
def _write_sources_to_zip(zf, sources, progress=None, total=0, done=0):
    """ফাইল/ফোল্ডারের তালিকা ZIP-এ লেখা / write sources into an open ZipFile."""
    for src in sources:
        src = os.path.abspath(src)
        base = os.path.basename(src.rstrip(os.sep)) or src
        if os.path.isfile(src):
            zf.write(src, arcname=base)
            done += 1
            if progress:
                progress(done, total, base)
        elif os.path.isdir(src):
            for root, _dirs, filenames in os.walk(src):
                for fn in filenames:
                    full = os.path.join(root, fn)
                    arc = os.path.join(base, os.path.relpath(full, src))
                    zf.write(full, arcname=arc)
                    done += 1
                    if progress:
                        progress(done, total, arc)
        else:
            raise ArchiveError(f"ফাইল/ফোল্ডার পাওয়া যায়নি: {src}")
    return done


def _count_files(sources):
    total = 0
    for src in sources:
        if os.path.isfile(src):
            total += 1
        elif os.path.isdir(src):
            total += sum(len(fns) for _r, _d, fns in os.walk(src))
    return total


def create_archive(archive_path, sources, fmt=None, password=None, progress=None):
    """নতুন আর্কাইভ বানানো / create a new archive from files/folders.

    fmt না দিলে এক্সটেনশন দেখে ঠিক হবে। RAR বানানো যাবে না —
    ইচ্ছে করে দেওয়া হয়নি (RAR creation is proprietary)।
    """
    if fmt is None:
        fmt = detect_format(archive_path)
    if fmt is None:
        raise ArchiveError("এক্সটেনশন দেখে ফরম্যাট বোঝা যায়নি — .zip/.7z/.tar/.tar.gz দিন।")
    if fmt == "rar":
        raise ArchiveError(
            "RAR বানানো যায় না — RAR প্রোপ্রাইটারি ফরম্যাট, শুধু খোলা যায়। "
            "(RAR creation is not supported.)")
    total = _count_files(sources)
    if fmt == "zip":
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
            _write_sources_to_zip(zf, sources, progress, total)
        return archive_path
    if fmt in ("tar", "tar.gz", "tar.bz2", "tar.xz"):
        mode = {"tar": "w", "tar.gz": "w:gz",
                "tar.bz2": "w:bz2", "tar.xz": "w:xz"}[fmt]
        done = 0
        with tarfile.open(archive_path, mode) as tf:
            for src in sources:
                tf.add(src, arcname=os.path.basename(src.rstrip(os.sep)))
                done += _count_files([src])
                if progress:
                    progress(done, total, os.path.basename(src))
        return archive_path
    if fmt == "7z":
        if not HAS_PY7ZR:
            raise ArchiveError("7Z বানাতে py7zr লাগবে (pip install py7zr)।")
        with py7zr.SevenZipFile(archive_path, mode="w", password=password) as z:
            for src in sources:
                z.writeall(src, arcname=os.path.basename(src.rstrip(os.sep)))
        if progress:
            progress(total, total, os.path.basename(archive_path))
        return archive_path
    raise ArchiveError(f"এই ফরম্যাটে বানানো যায় না: {fmt}")


def add_to_archive(archive_path, sources, password=None, progress=None):
    """আগের আর্কাইভে ফাইল যোগ করা / add files to an existing (or new) archive.

    ZIP-এ সরাসরি append করা যায়। TAR/7Z-এ পুরনোটা temp-এ বের করে
    নতুন করে বানানো হয় (ফরম্যাটের সীমা)।
    """
    fmt = detect_format(archive_path)
    if fmt is None:
        raise ArchiveError("অসমর্থিত ফরম্যাট (unsupported format)।")
    if fmt == "rar":
        raise ArchiveError("RAR-এ ফাইল যোগ করা যায় না (RAR is read-only here)।")
    if not os.path.exists(archive_path):
        return create_archive(archive_path, sources, fmt=fmt,
                              password=password, progress=progress)
    if fmt == "zip":
        total = _count_files(sources)
        with zipfile.ZipFile(archive_path, "a", zipfile.ZIP_DEFLATED) as zf:
            _write_sources_to_zip(zf, sources, progress, total)
        return archive_path
    # TAR / 7Z: পুরনো + নতুন একসাথে নতুন করে বানানো
    with tempfile.TemporaryDirectory() as tmp:
        old_dir = os.path.join(tmp, "old")
        os.makedirs(old_dir)
        extract_all(archive_path, old_dir, password=password)
        old_items = [os.path.join(old_dir, n) for n in os.listdir(old_dir)]
        new_path = archive_path + ".tmp"
        create_archive(new_path, old_items + [os.path.abspath(s) for s in sources],
                       fmt=fmt, password=password, progress=progress)
        os.replace(new_path, archive_path)
    return archive_path


def delete_from_archive(path, names, progress=None):
    """আর্কাইভ থেকে ফাইল মোছা — শুধু ZIP-এ চলে / delete members (ZIP only)."""
    if detect_format(path) != "zip":
        raise ArchiveError(
            "মোছা শুধু ZIP আর্কাইভে চলে (delete works only for ZIP)। "
            "অন্য ফরম্যাটে নতুন করে বানাতে হবে।")
    entries = list_archive(path)
    remove = set()
    for name in names:
        name = name.rstrip("/")
        for e in entries:
            if e.name.rstrip("/") == name or e.name.startswith(name + "/"):
                remove.add(e.name)
    if not remove:
        raise ArchiveError("মোছার মতো কিছু পাওয়া যায়নি।")
    total = len(remove)
    done = 0
    # Temp ফাইল আর্কাইভের ফোল্ডারেই বানানো হয় — Windows-এ os.replace
    # অন্য ড্রাইভে কাজ করে না (WinError 17), তাই সিস্টেম temp (C:) থেকে
    # অন্য ড্রাইভের (D:) আর্কাইভে replace করলে ভেঙে যেত। আসল ব্যবহারেও
    # একই বাগ হতো, তাই এটা শুধু পরীক্ষার ফিক্স নয়।
    target_dir = os.path.dirname(os.path.abspath(path))
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".zip", dir=target_dir)
    os.close(tmp_fd)
    try:
        with zipfile.ZipFile(path, "r") as zin, \
                zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                if item.filename in remove:
                    done += 1
                    if progress:
                        progress(done, total, item.filename)
                    continue
                zout.writestr(item, zin.read(item.filename))
        try:
            os.replace(tmp_path, path)
        except OSError:
            # Cross-device fallback (যেমন Windows-এ অন্য ড্রাইভ)।
            shutil.move(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
    return len(remove)


# ---------------------------------------------------------------------------
# পরীক্ষা ও তথ্য (test / info)
# ---------------------------------------------------------------------------
def test_archive(path, password=None):
    """আর্কাইভ ঠিক আছে কি না পরীক্ষা / test integrity.

    Returns: (ok: bool, bad_files: list[str], message: str)
    """
    fmt = detect_format(path)
    if fmt is None:
        return False, [], "অসমর্থিত ফরম্যাট (unsupported format)।"
    try:
        if fmt == "zip":
            if zip_has_aes(path):
                return False, [], (
                    "এই ZIP-এ AES এনক্রিপশন আছে — পরীক্ষা করা যাবে না "
                    "(AES-encrypted ZIP cannot be tested here)।")
            with zipfile.ZipFile(path) as zf:
                bad = zf.testzip()
                if bad is not None:
                    return False, [bad], f"নষ্ট ফাইল পাওয়া গেছে: {bad}"
                if zip_needs_password(path) and password is None:
                    return False, [], "পাসওয়ার্ড লাগবে (password required)।"
                return True, [], "সব ফাইল ঠিক আছে (all files OK)।"
        if fmt in ("tar", "tar.gz", "tar.bz2", "tar.xz"):
            with tarfile.open(path, "r:*") as tf:
                for m in tf.getmembers():
                    if m.isfile():
                        f = tf.extractfile(m)
                        if f is not None:
                            while f.read(1024 * 1024):
                                pass
            return True, [], "সব ফাইল ঠিক আছে (all files OK)।"
        if fmt == "7z":
            if not HAS_PY7ZR:
                return False, [], "7Z পরীক্ষা করতে py7zr লাগবে (pip install py7zr)।"
            with tempfile.TemporaryDirectory() as tmp:
                extract_all(path, tmp, password=password)
            return True, [], "সব ফাইল ঠিক আছে (all files OK)।"
        if fmt == "rar":
            if not HAS_RARFILE:
                return False, [], "RAR পরীক্ষা করতে rarfile + UnRAR লাগবে।"
            with rarfile.RarFile(path) as rf:
                rf.testrar()
            return True, [], "সব ফাইল ঠিক আছে (all files OK)।"
    except Exception as exc:
        return False, [], f"পরীক্ষায় সমস্যা: {exc}"
    return False, [], "অজানা ফরম্যাট।"


def archive_info(path, password=None):
    """আর্কাইভের সারাংশ / summary info dict."""
    entries = list_archive(path, password=password)
    files = [e for e in entries if not e.is_dir]
    folders = [e for e in entries if e.is_dir]
    return {
        "path": path,
        "format": detect_format(path),
        "file_count": len(files),
        "folder_count": len(folders),
        "total_size": sum(e.size for e in files),
        "total_size_text": format_size(sum(e.size for e in files)),
        "disk_size": os.path.getsize(path),
        "disk_size_text": format_size(os.path.getsize(path)),
        "encrypted": zip_needs_password(path) if detect_format(path) == "zip" else False,
        "aes_encrypted": zip_has_aes(path) if detect_format(path) == "zip" else False,
    }
