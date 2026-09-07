"""Safety checks for the consent-gated external SQLite fetch target."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import fetch_source


def _result(returncode: int = 0) -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode)


def test_fetch_installs_only_a_checksum_verified_source(monkeypatch, tmp_path):
    target = tmp_path / "source" / "world.sqlite"
    content = b"verified sqlite fixture"
    source = fetch_source.SourceFetch("test", "https://example.invalid/source", hashlib.sha256(content).hexdigest())
    monkeypatch.setattr(fetch_source, "FETCHES", {"test": source})
    monkeypatch.setattr(
        fetch_source,
        "load_pack",
        lambda _dataset: SimpleNamespace(source=SimpleNamespace(path=target)),
    )

    def runner(command, **_kwargs):
        if command[0] == "curl":
            target_path = next(path for path in command if path.endswith("source.download"))
            Path(target_path).write_bytes(content)
        return _result()

    assert fetch_source.fetch_source("test", runner=runner) == target
    assert target.read_bytes() == content


def test_fetch_does_not_install_a_checksum_mismatch(monkeypatch, tmp_path):
    target = tmp_path / "source" / "world.sqlite"
    source = fetch_source.SourceFetch("test", "https://example.invalid/source", "0" * 64)
    monkeypatch.setattr(fetch_source, "FETCHES", {"test": source})
    monkeypatch.setattr(
        fetch_source,
        "load_pack",
        lambda _dataset: SimpleNamespace(source=SimpleNamespace(path=target)),
    )

    def runner(command, **_kwargs):
        if command[0] == "curl":
            target_path = next(path for path in command if path.endswith("source.download"))
            Path(target_path).write_bytes(b"wrong")
        return _result()

    with pytest.raises(fetch_source.SourceFetchError, match="Checksum mismatch"):
        fetch_source.fetch_source("test", runner=runner)
    assert not target.exists()


def test_archive_fetch_extracts_and_verifies_only_the_documented_member(monkeypatch, tmp_path):
    target = tmp_path / "source" / "schools.sqlite"
    content = b"verified school sqlite fixture"
    member = "minidev/schools.sqlite"
    source = fetch_source.SourceFetch(
        "test",
        "https://example.invalid/archive.zip",
        hashlib.sha256(content).hexdigest(),
        archive_member=member,
    )
    monkeypatch.setattr(fetch_source, "FETCHES", {"test": source})
    monkeypatch.setattr(
        fetch_source,
        "load_pack",
        lambda _dataset: SimpleNamespace(source=SimpleNamespace(path=target)),
    )

    def runner(command, **kwargs):
        if command[0] == "curl":
            archive = next(path for path in command if path.endswith("source.download"))
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr(member, content)
        elif command[0] == "unzip":
            with zipfile.ZipFile(command[2]) as archive:
                kwargs["stdout"].write(archive.read(command[3]))
        return _result()

    assert fetch_source.fetch_source("test", runner=runner) == target
    assert target.read_bytes() == content
