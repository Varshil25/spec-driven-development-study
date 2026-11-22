"""Archive builder shared by the T-TARX-01 suites."""

import io
import tarfile


def make_tar(path, members, compression=""):
    """Build an archive from member specs.

    Each spec is a dict: name, and one of
      data=bytes            regular file
      dir=True              directory
      symlink=target        symbolic link
      hardlink=target       hard link
    plus optional mode and mtime.
    """
    mode = "w:gz" if compression == "gz" else "w"
    with tarfile.open(path, mode) as tar:
        for spec in members:
            info = tarfile.TarInfo(spec["name"])
            info.mtime = spec.get("mtime", 1_600_000_000)
            if "dir" in spec:
                info.type = tarfile.DIRTYPE
                info.mode = spec.get("mode", 0o755)
                tar.addfile(info)
            elif "symlink" in spec:
                info.type = tarfile.SYMTYPE
                info.linkname = spec["symlink"]
                info.mode = 0o777
                tar.addfile(info)
            elif "hardlink" in spec:
                info.type = tarfile.LNKTYPE
                info.linkname = spec["hardlink"]
                info.mode = 0o644
                tar.addfile(info)
            else:
                data = spec["data"]
                info.size = len(data)
                info.mode = spec.get("mode", 0o644)
                tar.addfile(info, io.BytesIO(data))
    return path
