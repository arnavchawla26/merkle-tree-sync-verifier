import os

import pytest

from merkletree.tree import build_tree
from merkletree.verify import load_manifest, save_manifest, verify_directory


def _write(path, content=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


def _make_source(base):
    _write(base / "README.md", "hello")
    _write(base / "src" / "main.py", "print('hi')")
    _write(base / "src" / "util.py", "def f(): pass")
    return base


def test_verify_unchanged_directory_is_ok(tmp_path):
    src = _make_source(tmp_path / "src_dir")
    manifest = tmp_path / "manifest.json"
    save_manifest(build_tree(str(src)), str(manifest))

    result = verify_directory(str(src), str(manifest))

    assert result.ok is True
    assert result.differences == []
    assert result.local_root_hash == result.trusted_root_hash


def test_verify_detects_modified_file(tmp_path):
    src = _make_source(tmp_path / "src_dir")
    manifest = tmp_path / "manifest.json"
    save_manifest(build_tree(str(src)), str(manifest))

    _write(src / "src" / "main.py", "print('modified!')")

    result = verify_directory(str(src), str(manifest))

    assert result.ok is False
    assert len(result.differences) == 1
    assert result.differences[0].change == "modified"
    assert result.differences[0].path == "src/main.py"


def test_verify_detects_added_and_removed_files(tmp_path):
    src = _make_source(tmp_path / "src_dir")
    manifest = tmp_path / "manifest.json"
    save_manifest(build_tree(str(src)), str(manifest))

    os.remove(src / "src" / "util.py")
    _write(src / "src" / "new_module.py", "x = 1")

    result = verify_directory(str(src), str(manifest))

    changes = {(d.path, d.change) for d in result.differences}
    assert ("src/util.py", "removed") in changes
    assert ("src/new_module.py", "added") in changes
    assert result.ok is False


def test_verify_reports_multiple_scattered_changes_independently(tmp_path):
    src = _make_source(tmp_path / "src_dir")
    manifest = tmp_path / "manifest.json"
    save_manifest(build_tree(str(src)), str(manifest))

    _write(src / "README.md", "changed readme")
    _write(src / "src" / "util.py", "def f(): return 42")

    result = verify_directory(str(src), str(manifest))

    changes = {(d.path, d.change) for d in result.differences}
    assert changes == {("README.md", "modified"), ("src/util.py", "modified")}
    # main.py was untouched, so it must not appear as a difference.
    assert not any(d.path == "src/main.py" for d in result.differences)


def test_manifest_round_trip_preserves_root_name_and_hash(tmp_path):
    src = _make_source(tmp_path / "src_dir")
    original = build_tree(str(src))
    manifest = tmp_path / "manifest.json"
    save_manifest(original, str(manifest))

    loaded = load_manifest(str(manifest))
    assert loaded.hash == original.hash
    assert loaded.name == original.name


def test_verify_works_when_directory_was_moved(tmp_path):
    """A manifest built for one directory should still verify a byte-identical
    copy living at a different local path, as long as the top-level name matches
    (build_tree's root_name is derived from the directory's own basename by
    default, so callers must rename or copy under the same leaf dirname --
    this test copies to a same-named directory under a different parent)."""
    src = _make_source(tmp_path / "original_name")
    manifest = tmp_path / "manifest.json"
    save_manifest(build_tree(str(src)), str(manifest))

    import shutil

    other_parent = tmp_path / "elsewhere"
    other_parent.mkdir()
    copy_path = other_parent / "original_name"
    shutil.copytree(src, copy_path)

    result = verify_directory(str(copy_path), str(manifest))
    assert result.ok is True


def test_verify_raises_for_missing_manifest(tmp_path):
    src = _make_source(tmp_path / "src_dir")
    with pytest.raises(FileNotFoundError):
        verify_directory(str(src), str(tmp_path / "does_not_exist.json"))
