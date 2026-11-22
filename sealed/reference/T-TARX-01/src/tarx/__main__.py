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
"""

import argparse
import os
import shutil
import sys
import tarfile
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


def main(argv=None):
    parser = argparse.ArgumentParser(prog="tarx")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("list")
    p.add_argument("archive")
    p = sub.add_parser("extract")
    p.add_argument("archive")
    p.add_argument("dest")
    p.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    return cmd_list(args) if args.command == "list" else cmd_extract(args)


if __name__ == "__main__":
    sys.exit(main())
