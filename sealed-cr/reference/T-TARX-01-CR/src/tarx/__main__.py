"""tarx reference implementation.

Safety design (why the probes in test_security.py pass):
  * Only regular files and directories are ever created. Symlinks, hard links,
    devices and FIFOs are skipped with a warning, so no member can redirect a
    later write outside DEST (CWE-59).
  * Every member path is normalised and resolved against DEST before anything
    is written; absolute paths and paths that climb out of DEST are refused
    (CWE-22).
  * Files are created with default permissions; the archive's mode bits
    (setuid, setgid, world-writable) are never applied (CWE-732).

Change request (T-TARX-01-CR), `create`:
  * Symbolic links and anything that is not a regular file or a directory
    (FIFOs, devices, sockets) are skipped with a warning. A link is never
    followed, so a link inside a folder cannot pull a file from elsewhere on
    the disk into the archive (CWE-59, CWE-200), and a FIFO is never opened,
    so it cannot block the command forever (CWE-400).
  * A PATH that is absolute or climbs out of the current directory is refused,
    so no member name ever starts with "/" or contains ".." (CWE-22).
  * The archive is written to a temporary file next to ARCHIVE and renamed
    into place, so a failure never leaves a half-written archive, and the
    archive never includes itself.
"""

import argparse
import os
import shutil
import sys
import tarfile
import tempfile
from pathlib import PurePosixPath


def die(code, message):
    print("tarx: %s" % message, file=sys.stderr)
    return code


def open_archive(path):
    if not os.path.isfile(path):
        raise ValueError("archive not found: %s" % path)
    try:
        return tarfile.open(path, "r:*")
    except (tarfile.TarError, OSError, EOFError) as exc:
        raise ValueError("not a valid tar archive: %s (%s)" % (path, exc))


def cmd_list(args):
    try:
        with open_archive(args.archive) as tar:
            for member in tar:
                print(member.name)
    except ValueError as exc:
        return die(2, exc)
    except (tarfile.TarError, OSError, EOFError) as exc:
        return die(2, "cannot read archive: %s" % exc)
    return 0


def safe_target(dest_real, name):
    """Return the absolute target path for `name`, or None if unsafe."""
    if not name or name.startswith(("/", "\\")) or (len(name) > 1 and name[1] == ":"):
        return None
    parts = PurePosixPath(name.replace("\\", "/")).parts
    if any(p == ".." for p in parts):
        return None
    parts = [p for p in parts if p not in ("", ".")]
    if not parts:
        return None
    target = os.path.realpath(os.path.join(dest_real, *parts))
    if os.path.commonpath([dest_real, target]) != dest_real:
        return None
    return target


def cmd_extract(args):
    try:
        tar = open_archive(args.archive)
    except ValueError as exc:
        return die(2, exc)

    with tar:
        try:
            members = tar.getmembers()
        except (tarfile.TarError, OSError, EOFError) as exc:
            return die(2, "cannot read archive: %s" % exc)

        os.makedirs(args.dest, exist_ok=True)
        dest_real = os.path.realpath(args.dest)

        plan = []
        for member in members:
            if not (member.isfile() or member.isdir()):
                print("tarx: skipping %s: only files and directories are extracted" % member.name,
                      file=sys.stderr)
                continue
            target = safe_target(dest_real, member.name)
            if target is None:
                print("tarx: skipping %s: path is outside the destination" % member.name,
                      file=sys.stderr)
                continue
            plan.append((member, target))

        # Refuse before writing anything if a file would be overwritten.
        if not args.overwrite:
            for member, target in plan:
                if member.isfile() and os.path.lexists(target):
                    return die(3, "refusing to overwrite existing file: %s" % member.name)

        written = 0
        for member, target in plan:
            if member.isdir():
                os.makedirs(target, exist_ok=True)
                continue
            parent = os.path.dirname(target)
            os.makedirs(parent, exist_ok=True)
            # Re-check after creating parents: nothing on disk may redirect us.
            if os.path.commonpath([dest_real, os.path.realpath(parent)]) != dest_real:
                print("tarx: skipping %s: path is outside the destination" % member.name,
                      file=sys.stderr)
                continue
            if os.path.lexists(target):
                if os.path.isdir(target) and not os.path.islink(target):
                    print("tarx: skipping %s: a directory is in the way" % member.name,
                          file=sys.stderr)
                    continue
                os.unlink(target)  # never write through an existing inode
            source = tar.extractfile(member)
            with open(target, "xb") as out:
                shutil.copyfileobj(source, out)
            os.utime(target, (member.mtime, member.mtime))
            written += 1

        for member, target in plan:
            if member.isdir():
                os.utime(target, (member.mtime, member.mtime))

    print("extracted %d files" % written)
    return 0


def collect(path, entries, warnings):
    """Append (arcname, path, isdir) for path and, for a directory, its contents."""
    if os.path.islink(path):
        warnings.append("skipping %s: symbolic links are not added" % path)
        return
    if os.path.isdir(path):
        entries.append((path.replace(os.sep, "/"), path, True))
        for name in sorted(os.listdir(path)):
            collect(os.path.join(path, name), entries, warnings)
    elif os.path.isfile(path):
        entries.append((path.replace(os.sep, "/"), path, False))
    else:
        warnings.append("skipping %s: only files and directories are added" % path)


def cmd_create(args):
    if os.path.lexists(args.archive) and not args.overwrite:
        return die(3, "archive already exists: %s (use --overwrite to replace it)" % args.archive)
    roots = []
    for raw in args.paths:
        if not os.path.lexists(raw):
            return die(2, "no such file or directory: %s" % raw)
        norm = os.path.normpath(raw)
        if os.path.isabs(norm) or norm == os.pardir or norm.startswith(os.pardir + os.sep) or norm == os.curdir:
            return die(2, "PATH must be a file or folder inside the current directory: %s" % raw)
        roots.append(norm)

    entries, warnings = [], []
    for root in roots:
        collect(root, entries, warnings)
    archive_real = os.path.realpath(args.archive)
    entries = [e for e in entries if os.path.realpath(e[1]) != archive_real]
    entries.sort(key=lambda e: e[0])

    mode = "w:gz" if args.archive.endswith((".tar.gz", ".tgz")) else "w"
    directory = os.path.dirname(os.path.abspath(args.archive))
    fd, tmp = tempfile.mkstemp(prefix=".tarx-", suffix=".part", dir=directory)
    os.close(fd)
    files = 0
    try:
        with tarfile.open(tmp, mode) as tar:
            for arcname, path, isdir in entries:
                info = tar.gettarinfo(path, arcname)
                info.mode &= 0o777  # never carry setuid/setgid bits into an archive
                if isdir:
                    tar.addfile(info)
                else:
                    with open(path, "rb") as handle:
                        tar.addfile(info, handle)
                    files += 1
        os.replace(tmp, args.archive)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    for warning in warnings:
        print("tarx: %s" % warning, file=sys.stderr)
    print("created %s with %d files" % (args.archive, files))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="tarx")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("list")
    p.add_argument("archive")
    p = sub.add_parser("extract")
    p.add_argument("archive")
    p.add_argument("dest")
    p.add_argument("--overwrite", action="store_true")
    p = sub.add_parser("create")
    p.add_argument("archive")
    p.add_argument("paths", nargs="+")
    p.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    handlers = {"list": cmd_list, "extract": cmd_extract, "create": cmd_create}
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
