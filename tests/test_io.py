"""Private serialized artifacts have deterministic UTF-8 bytes on every platform."""

import json

import pytest

from closed_review import io
from closed_review.receipts import installed_identity


@pytest.mark.parametrize("value", ["원문\nSecond line.\n", "원문\r\nSecond line.\r\n"])
def test_atomic_text_preserves_supplied_bytes_without_platform_translation(tmp_path, value):
    target = tmp_path / "text.txt"
    io.atomic_write_text(target, value)
    assert target.read_bytes() == value.encode("utf-8")


@pytest.mark.parametrize("kind", ["text", "json"])
def test_atomic_serialization_explicitly_chooses_utf8_and_lf(tmp_path, monkeypatch, kind):
    original = io.os.fdopen
    observed = []

    def fdopen(fd, mode, **kwargs):
        observed.append(kwargs)
        return original(fd, mode, **kwargs)

    monkeypatch.setattr(io.os, "fdopen", fdopen)
    target = tmp_path / "artifact"
    if kind == "json":
        io.atomic_write_json(target, {"source": "원문", "lines": "a\nb"})
        assert json.loads(target.read_bytes()) == {"source": "원문", "lines": "a\nb"}
    else:
        io.atomic_write_text(target, "원문\nSecond line.\n")
    assert observed == [{"encoding": "utf-8", "newline": "\n"}]
    assert b"\r\n" not in target.read_bytes()


def test_independent_sums_file_hash_matches_the_installed_identity(tmp_path):
    identity = installed_identity()
    target = tmp_path / "trusted.sums"
    io.atomic_write_text(target, identity["sums"])
    assert io.sha256_file(target) == identity["sums_sha256"]
