from merkletree.hashing import blob_hash, hash_bytes, tree_hash


def test_hash_bytes_deterministic():
    assert hash_bytes(b"hello") == hash_bytes(b"hello")


def test_hash_bytes_sensitive_to_content():
    assert hash_bytes(b"hello") != hash_bytes(b"hellp")


def test_blob_hash_deterministic_and_content_sensitive():
    assert blob_hash(b"abc") == blob_hash(b"abc")
    assert blob_hash(b"abc") != blob_hash(b"abd")
    assert blob_hash(b"") != blob_hash(b"\x00")


def test_blob_hash_is_not_a_bare_sha256():
    # The framing header (`blob <len>\0`) must actually participate in the
    # hash, otherwise blob_hash would just be hash_bytes in a trenchcoat and
    # every "does this framing matter" argument in the docstring is false.
    raw = b"some content"
    assert blob_hash(raw) != hash_bytes(raw)


def test_tree_hash_order_independent():
    entries_a = [("b.txt", False, "hash-b"), ("a.txt", False, "hash-a")]
    entries_b = [("a.txt", False, "hash-a"), ("b.txt", False, "hash-b")]
    assert tree_hash(entries_a) == tree_hash(entries_b)


def test_tree_hash_sensitive_to_membership_and_names():
    base = [("a.txt", False, "hash-a"), ("b.txt", False, "hash-b")]
    missing_one = [("a.txt", False, "hash-a")]
    renamed = [("a.txt", False, "hash-a"), ("c.txt", False, "hash-b")]
    assert tree_hash(base) != tree_hash(missing_one)
    assert tree_hash(base) != tree_hash(renamed)


def test_tree_hash_sensitive_to_is_dir_flag():
    as_file = [("x", False, "deadbeef")]
    as_dir = [("x", True, "deadbeef")]
    assert tree_hash(as_file) != tree_hash(as_dir)


def test_tree_hash_empty_is_stable_and_distinct_from_empty_blob():
    assert tree_hash([]) == tree_hash([])
    assert tree_hash([]) != blob_hash(b"")
