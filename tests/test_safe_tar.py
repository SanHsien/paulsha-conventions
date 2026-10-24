import io
import tarfile

import pytest

from policy_check import _safe_tar
from policy_check._safe_tar import UnsafeTarSupportError, extract_all_data_filtered


def _archive(entries):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for info, payload in entries:
            tar.addfile(info, io.BytesIO(payload) if payload is not None else None)
    buffer.seek(0)
    return tarfile.open(fileobj=buffer, mode="r:")


def _file(name, payload=b"ok"):
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    return info, payload


def test_extracts_regular_members(tmp_path):
    dest = tmp_path / "dest"
    dest.mkdir()
    with _archive([_file("a/b.txt", b"hello")]) as tar:
        extract_all_data_filtered(tar, dest)
    assert (dest / "a" / "b.txt").read_bytes() == b"hello"


def test_parent_traversal_is_rejected_and_writes_nothing(tmp_path):
    dest = tmp_path / "dest"
    dest.mkdir()
    with _archive([_file("../escape.txt")]) as tar:
        with pytest.raises(tarfile.TarError):
            extract_all_data_filtered(tar, dest)
    assert not (tmp_path / "escape.txt").exists()


def test_absolute_member_is_not_written_outside_destination(tmp_path):
    dest = tmp_path / "dest"
    dest.mkdir()
    outside = tmp_path / "abs.txt"
    with _archive([_file(str(outside))]) as tar:
        try:
            extract_all_data_filtered(tar, dest)
        except tarfile.TarError:
            pass  # newer Pythons raise, older ones strip the leading slash
    assert not outside.exists()


def test_symlink_escaping_destination_is_rejected(tmp_path):
    dest = tmp_path / "dest"
    dest.mkdir()
    link = tarfile.TarInfo("link")
    link.type = tarfile.SYMTYPE
    link.linkname = "../outside"
    with _archive([(link, None)]) as tar:
        with pytest.raises(tarfile.TarError):
            extract_all_data_filtered(tar, dest)
    assert not (dest / "link").exists()


def test_fails_closed_without_data_filter(tmp_path, monkeypatch):
    dest = tmp_path / "dest"
    dest.mkdir()
    monkeypatch.delattr(_safe_tar.tarfile, "data_filter", raising=False)
    with _archive([_file("a.txt")]) as tar:
        with pytest.raises(UnsafeTarSupportError):
            extract_all_data_filtered(tar, dest)
    assert not (dest / "a.txt").exists()
