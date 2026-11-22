"""Archive readers shared by the T-TARX-01-CR suites."""

import tarfile


def members(path):
    with tarfile.open(path, "r:*") as tar:
        return tar.getmembers()


def names(path):
    return [m.name.rstrip("/") for m in members(path)]
