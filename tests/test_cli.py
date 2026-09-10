import json
import os

import pytest

from merkletree.cli import main


def _write(path, content=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


def _make_source(base):
    _write(base / "a.txt", "hello")
    _write(base / "sub" / "b.txt", "world")
    return base


def test_cli_hash_prints_root_hash(tmp_path, capsys):
    src = _make_source(tmp_path / "src")
    rc = main(["hash", str(src)])
    out = capsys.readouterr().out.strip()

    assert rc == 0
    assert len(out) == 64  # sha256 hex digest length
    int(out, 16)  # must be valid hex


def test_cli_hash_writes_manifest(tmp_path, capsys):
    src = _make_source(tmp_path / "src")
    manifest = tmp_path / "manifest.json"

    rc = main(["hash", str(src), "-o", str(manifest)])
    out = capsys.readouterr().out

    assert rc == 0
    assert manifest.exists()
    assert "root hash" in out
    data = json.loads(manifest.read_text())
    assert data["is_dir"] is True
    assert "a.txt" in data["children"]


def test_cli_diff_two_directories_no_changes(tmp_path, capsys):
    src_a = _make_source(tmp_path / "a")
    src_b = _make_source(tmp_path / "b")

    rc = main(["diff", str(src_a), str(src_b)])
    out = capsys.readouterr().out

    assert rc == 0
    assert "no differences" in out


def test_cli_diff_two_directories_reports_changes(tmp_path, capsys):
    src_a = _make_source(tmp_path / "a")
    src_b = _make_source(tmp_path / "b")
    _write(src_b / "a.txt", "hello, changed")

    rc = main(["diff", str(src_a), str(src_b)])
    out = capsys.readouterr().out

    assert rc == 1
    assert "modified" in out
    assert "a.txt" in out


def test_cli_diff_using_saved_manifests(tmp_path, capsys):
    src = _make_source(tmp_path / "src")
    manifest_a = tmp_path / "a.json"
    main(["hash", str(src), "-o", str(manifest_a)])
    capsys.readouterr()

    _write(src / "a.txt", "hello, changed")
    manifest_b = tmp_path / "b.json"
    main(["hash", str(src), "-o", str(manifest_b)])
    capsys.readouterr()

    rc = main(["diff", str(manifest_a), str(manifest_b)])
    out = capsys.readouterr().out

    assert rc == 1
    assert "a.txt" in out


def test_cli_verify_ok(tmp_path, capsys):
    src = _make_source(tmp_path / "src")
    manifest = tmp_path / "manifest.json"
    main(["hash", str(src), "-o", str(manifest)])
    capsys.readouterr()

    rc = main(["verify", str(src), str(manifest)])
    out = capsys.readouterr().out

    assert rc == 0
    assert "OK" in out


def test_cli_verify_mismatch(tmp_path, capsys):
    src = _make_source(tmp_path / "src")
    manifest = tmp_path / "manifest.json"
    main(["hash", str(src), "-o", str(manifest)])
    capsys.readouterr()

    _write(src / "sub" / "b.txt", "tampered")

    rc = main(["verify", str(src), str(manifest)])
    out = capsys.readouterr().out

    assert rc == 1
    assert "MISMATCH" in out
    assert "sub/b.txt" in out


def test_cli_no_command_exits_nonzero(capsys):
    with pytest.raises(SystemExit):
        main([])
