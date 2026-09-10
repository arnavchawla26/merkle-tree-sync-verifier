import copy

from merkletree.diff import DiffStats, diff_trees
from merkletree.tree import build_dir_node, build_file_node


def _leaf(name, content):
    return build_file_node(name, content.encode("utf-8"))


def _wide_tree(depth, branching, leaf_content_fn):
    """Build a tree of the given depth with `branching` children per level.

    leaf_content_fn(path_tuple) -> bytes, so callers can make exactly one
    leaf differ between two trees built from two different content
    functions.
    """

    def _build(path):
        if len(path) == depth:
            return _leaf("leaf", leaf_content_fn(path).decode("utf-8"))
        children = {}
        for i in range(branching):
            name = f"n{i}"
            child_path = path + (i,)
            if len(child_path) == depth:
                children[name] = _leaf(name, leaf_content_fn(child_path).decode("utf-8"))
            else:
                children[name] = _build(child_path)
        return build_dir_node("dir" if path else "root", children)

    return _build(())


def test_diff_identical_trees_is_empty_and_skips_root():
    a = _wide_tree(3, 4, lambda p: f"content-{p}".encode())
    b = _wide_tree(3, 4, lambda p: f"content-{p}".encode())
    stats = DiffStats()

    entries = diff_trees(a, b, stats=stats)

    assert entries == []
    assert stats.subtrees_skipped == 1  # the whole tree was pruned at the root
    assert stats.dirs_compared == 0


def test_diff_detects_single_deep_change_and_reports_exact_path():
    def content_fn(path):
        return f"content-{path}".encode()

    a = _wide_tree(3, 5, content_fn)

    changed_path = (2, 3, 1)

    def content_fn_modified(path):
        if path == changed_path:
            return b"MODIFIED"
        return content_fn(path)

    b = _wide_tree(3, 5, content_fn_modified)

    entries = diff_trees(a, b)

    assert len(entries) == 1
    assert entries[0].change == "modified"
    assert entries[0].path == "n2/n3/n1"


def test_diff_is_log_depth_not_linear_in_tree_size():
    """The whole point of hashing the tree: diffing two large trees that
    differ in exactly one leaf must not visit every node.
    """

    def content_fn(path):
        return f"content-{path}".encode()

    depth, branching = 4, 6
    a = _wide_tree(depth, branching, content_fn)
    total_nodes = a.node_count()

    changed_path = (1, 2, 3, 4)

    def content_fn_modified(path):
        return b"MODIFIED" if path == changed_path else content_fn(path)

    b = _wide_tree(depth, branching, content_fn_modified)

    stats = DiffStats()
    entries = diff_trees(a, b, stats=stats)

    assert len(entries) == 1
    # Only the `depth` directories on the path to the change were opened --
    # everywhere else was pruned by a single hash comparison.
    assert stats.dirs_compared == depth
    assert total_nodes > 1000  # sanity: this tree really is big
    assert stats.dirs_compared < total_nodes / 50  # nowhere close to linear


def test_diff_detects_added_and_removed_paths():
    a = build_dir_node("root", {"a.txt": _leaf("a.txt", "x")})
    b = build_dir_node(
        "root", {"a.txt": _leaf("a.txt", "x"), "b.txt": _leaf("b.txt", "y")}
    )

    added = diff_trees(a, b)
    assert [(e.path, e.change) for e in added] == [("b.txt", "added")]

    removed = diff_trees(b, a)
    assert [(e.path, e.change) for e in removed] == [("b.txt", "removed")]


def test_diff_detects_type_changed_file_to_dir():
    a = build_dir_node("root", {"x": _leaf("x", "content")})
    b = build_dir_node("root", {"x": build_dir_node("x", {"y": _leaf("y", "z")})})

    entries = diff_trees(a, b)
    assert len(entries) == 1
    assert entries[0].change == "type_changed"
    assert entries[0].path == "x"


def test_diff_one_side_none_reports_everything_under_the_other():
    tree = build_dir_node(
        "root",
        {
            "a.txt": _leaf("a.txt", "1"),
            "sub": build_dir_node("sub", {"b.txt": _leaf("b.txt", "2")}),
        },
    )

    added = diff_trees(None, tree)
    assert sorted((e.path, e.change) for e in added) == [
        ("a.txt", "added"),
        ("sub/b.txt", "added"),
    ]

    removed = diff_trees(tree, None)
    assert sorted((e.path, e.change) for e in removed) == [
        ("a.txt", "removed"),
        ("sub/b.txt", "removed"),
    ]


def test_diff_both_none_is_empty():
    assert diff_trees(None, None) == []


def test_diff_does_not_mutate_inputs():
    a = _wide_tree(2, 3, lambda p: f"c{p}".encode())
    b_source = _wide_tree(2, 3, lambda p: f"c{p}".encode())
    b = copy.deepcopy(b_source)
    diff_trees(a, b)
    # structural equality with the untouched copy, proving diff_trees is read-only
    assert b.to_dict() == b_source.to_dict()
