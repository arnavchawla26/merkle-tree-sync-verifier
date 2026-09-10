import os

import pytest

from merkletree.tree import DEFAULT_IGNORE, MerkleNode, build_dir_node, build_file_node, build_tree


def _write(path, content=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


def test_build_tree_basic_structure(tmp_path):
    _write(tmp_path / "a.txt", "hello")
    _write(tmp_path / "sub" / "b.txt", "world")

    root = build_tree(str(tmp_path))

    assert root.is_dir
    assert set(root.children) == {"a.txt", "sub"}
    assert root.children["a.txt"].is_dir is False
    assert root.children["a.txt"].size == 5
    assert root.children["sub"].is_dir is True
    assert set(root.children["sub"].children) == {"b.txt"}
    assert root.node_count() == 4  # root, a.txt, sub, sub/b.txt
    assert root.leaf_count() == 2


def test_build_tree_is_deterministic_across_rebuilds(tmp_path):
    _write(tmp_path / "a.txt", "hello")
    _write(tmp_path / "sub" / "b.txt", "world")

    root1 = build_tree(str(tmp_path))
    root2 = build_tree(str(tmp_path))
    assert root1.hash == root2.hash


def test_build_tree_hash_independent_of_listdir_order(tmp_path, monkeypatch):
    _write(tmp_path / "a.txt", "hello")
    _write(tmp_path / "z.txt", "world")

    root_normal = build_tree(str(tmp_path))

    real_listdir = os.listdir

    def reversed_listdir(path):
        return list(reversed(real_listdir(path)))

    monkeypatch.setattr(os, "listdir", reversed_listdir)
    root_reversed = build_tree(str(tmp_path))

    assert root_normal.hash == root_reversed.hash


def test_build_tree_detects_content_change(tmp_path):
    f = tmp_path / "a.txt"
    _write(f, "hello")
    before = build_tree(str(tmp_path))

    _write(f, "hello!")
    after = build_tree(str(tmp_path))

    assert before.hash != after.hash


def test_build_tree_unrelated_sibling_unaffected_at_leaf_level(tmp_path):
    _write(tmp_path / "a.txt", "hello")
    _write(tmp_path / "b.txt", "world")
    root = build_tree(str(tmp_path))

    _write(tmp_path / "a.txt", "hello!")
    root2 = build_tree(str(tmp_path))

    # b.txt's own leaf hash must be untouched by a.txt changing, even though
    # the directory (root) hash necessarily changes.
    assert root.children["b.txt"].hash == root2.children["b.txt"].hash
    assert root.hash != root2.hash


def test_build_tree_ignores_default_and_custom_patterns(tmp_path):
    _write(tmp_path / "keep.txt", "x")
    _write(tmp_path / ".git" / "HEAD", "ref: refs/heads/main")
    _write(tmp_path / "__pycache__" / "x.pyc", "junk")
    _write(tmp_path / "secrets.env", "TOKEN=abc")

    root = build_tree(str(tmp_path), ignore={"secrets.env", *DEFAULT_IGNORE})

    assert set(root.children) == {"keep.txt"}


def test_build_tree_raises_on_non_directory(tmp_path):
    f = tmp_path / "not_a_dir.txt"
    _write(f, "x")
    with pytest.raises(NotADirectoryError):
        build_tree(str(f))


def test_build_tree_handles_symlinks_as_leaves(tmp_path):
    target = tmp_path / "real.txt"
    _write(target, "content")
    link = tmp_path / "link.txt"
    os.symlink(target, link)

    root = build_tree(str(tmp_path))
    assert root.children["link.txt"].is_dir is False
    # The symlink is hashed by its target *string*, not by following it, so
    # it must not equal the hash of the file it points at.
    assert root.children["link.txt"].hash != root.children["real.txt"].hash


def test_build_tree_empty_directory(tmp_path):
    root = build_tree(str(tmp_path))
    assert root.is_dir
    assert root.children == {}
    assert root.node_count() == 1
    assert root.leaf_count() == 0


def test_to_dict_from_dict_round_trip_preserves_hash(tmp_path):
    _write(tmp_path / "a.txt", "hello")
    _write(tmp_path / "sub" / "b.txt", "world")
    root = build_tree(str(tmp_path))

    restored = MerkleNode.from_dict(root.to_dict())

    assert restored.hash == root.hash
    assert restored.node_count() == root.node_count()
    assert restored.children["sub"].children["b.txt"].hash == root.children["sub"].children["b.txt"].hash


def test_build_file_node_and_build_dir_node_agree_with_build_tree(tmp_path):
    _write(tmp_path / "a.txt", "hello")
    from_disk = build_tree(str(tmp_path))

    manual_file = build_file_node("a.txt", b"hello")
    manual_root = build_dir_node(from_disk.name, {"a.txt": manual_file})

    assert manual_root.hash == from_disk.hash
