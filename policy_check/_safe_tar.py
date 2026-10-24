"""Tar extraction that always goes through the stdlib ``data`` filter."""
from __future__ import annotations

import tarfile
from pathlib import Path


class UnsafeTarSupportError(tarfile.TarError):
    """The running Python cannot extract tar archives safely."""


def extract_all_data_filtered(archive: tarfile.TarFile, destination: Path) -> None:
    """Extract every member of ``archive`` into ``destination``.

    The ``data`` filter rejects absolute paths, ``..`` escapes, links that
    point outside ``destination`` and device nodes, and strips setuid bits.
    Python 3.11.0-3.11.3 has no filter support; extraction fails closed there
    instead of falling back to an unfiltered ``extractall``.
    """
    if not hasattr(tarfile, "data_filter"):
        raise UnsafeTarSupportError(
            "safe tar extraction needs Python 3.11.4 or newer (tarfile data filter)"
        )
    archive.extractall(destination, filter="data")
