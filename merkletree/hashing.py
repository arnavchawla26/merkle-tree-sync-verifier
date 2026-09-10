"""Content-addressed hashing primitives for the Merkle tree.

Uses SHA-256 throughout, with a git-inspired framing (a type tag plus an
explicit length prefix ahead of the content) so a file's blob hash can never
be produced by hashing the same bytes some other way -- a directory's tree
body and a file's raw content are hashed under disjoint headers, so a
maliciously (or accidentally) crafted file can't be mistaken for a tree
object, and vice versa.
"""
from __future__ import annotations

import hashlib
from typing import List, Tuple

HASH_ALGO = "sha256"


def hash_bytes(data: bytes) -> str:
    """Return the hex digest of ``data`` under the chosen hash algorithm."""
    return hashlib.new(HASH_ALGO, data).hexdigest()


def blob_hash(content: bytes) -> str:
    """Hash a file's contents (or a symlink target) as a Merkle leaf.

    Framed as ``blob <length>\\0<content>``, so the empty file and the
    string b"" of some unrelated origin can never collide with a
    differently-framed hash of the same bytes.
    """
    header = f"blob {len(content)}\0".encode("utf-8")
    return hash_bytes(header + content)


def _tree_entry_line(name: str, is_dir: bool, entry_hash: str) -> str:
    """Canonical single-line encoding of one child entry in a tree body."""
    kind = "tree" if is_dir else "blob"
    return f"{kind} {entry_hash} {name}\n"


def tree_hash(entries: List[Tuple[str, bool, str]]) -> str:
    """Hash a directory node from its children.

    ``entries`` is a list of ``(name, is_dir, hash)`` triples. Entries are
    sorted by name before hashing, which is what makes the resulting hash a
    pure function of tree *content* rather than of filesystem iteration
    order (``os.listdir`` order is unspecified and must never leak into the
    hash, or two byte-identical directories built in different orders would
    hash differently).
    """
    body = "".join(
        _tree_entry_line(name, is_dir, h)
        for name, is_dir, h in sorted(entries, key=lambda e: e[0])
    ).encode("utf-8")
    header = f"tree {len(body)}\0".encode("utf-8")
    return hash_bytes(header + body)
