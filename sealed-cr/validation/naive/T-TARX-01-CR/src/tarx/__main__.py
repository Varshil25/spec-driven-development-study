"""Naive variant of the T-TARX-01-CR reference: create opens the archive with
dereference=True and calls tar.add(path) on each PATH as given."""


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


def cmd_create(args):
    # Naive first draft: tarfile does the walking, links are followed.
    if os.path.exists(args.archive) and not args.overwrite:
        return die(3, "archive already exists: %s" % args.archive)
    for path in args.paths:
        if not os.path.exists(path):
            return die(2, "no such file or directory: %s" % path)
    mode = "w:gz" if args.archive.endswith((".tar.gz", ".tgz")) else "w"
    files = 0
    with tarfile.open(args.archive, mode, dereference=True) as tar:
        for path in args.paths:
            tar.add(path)
    with tarfile.open(args.archive, "r:*") as tar:
        files = sum(1 for m in tar.getmembers() if m.isfile())
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
