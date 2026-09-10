"""In-memory Merkle tree over a directory tree."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional

from .hashing import blob_hash, tree_hash

DEFAULT_IGNORE = {".git", "__pycache__", ".pytest_cache", ".DS_Store", "node_modules", ".venv"}


@dataclass
class MerkleNode:
    name: str
    is_dir: bool
    hash: str
    size: int = 0  # file size in bytes; unused (0) for directories
    children: Dict[str, "MerkleNode"] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d: dict = {"name": self.name, "is_dir": self.is_dir, "hash": self.hash}
        if self.is_dir:
            d["children"] = {name: child.to_dict() for name, child in self.children.items()}
        else:
            d["size"] = self.size
        return d

    @staticmethod
    def from_dict(d: dict) -> "MerkleNode":
        if d["is_dir"]:
            children = {
                name: MerkleNode.from_dict(c) for name, c in d.get("children", {}).items()
            }
            return MerkleNode(name=d["name"], is_dir=True, hash=d["hash"], children=children)
        return MerkleNode(name=d["name"], is_dir=False, hash=d["hash"], size=d.get("size", 0))

    def node_count(self) -> int:
        """Total number of nodes (files + directories) in this subtree."""
        if not self.is_dir:
            return 1
        return 1 + sum(child.node_count() for child in self.children.values())

    def leaf_count(self) -> int:
        """Number of files (leaves) in this subtree."""
        if not self.is_dir:
            return 1
        return sum(child.leaf_count() for child in self.children.values())


def build_file_node(name: str, content: bytes) -> MerkleNode:
    return MerkleNode(name=name, is_dir=False, hash=blob_hash(content), size=len(content))


def build_dir_node(name: str, children: Dict[str, MerkleNode]) -> MerkleNode:
    entries = [(child.name, child.is_dir, child.hash) for child in children.values()]
    return MerkleNode(name=name, is_dir=True, hash=tree_hash(entries), children=dict(children))


def build_tree(
    root_path: str,
    ignore: Optional[Iterable[str]] = None,
    root_name: Optional[str] = None,
) -> MerkleNode:
    """Recursively hash a real directory on disk into a MerkleNode tree.

    ``ignore`` is a set of basenames to skip anywhere in the tree (defaults
    to DEFAULT_IGNORE). Files are read and hashed bottom-up; each
    directory's hash is a pure function of its children's ``(name, is_dir,
    hash)`` triples, so a change anywhere below propagates predictably up to
    the root, and an unchanged subtree hashes identically no matter when or
    where it is rebuilt.

    ``root_name`` overrides the label used for the top node (it never enters
    the hash of anything -- names only affect the hash of a *parent*
    directory's entry line -- so verifying a directory under a different
    local path than it was originally hashed under still works, as long as
    ``root_name`` matches what the manifest was built with).
    """
    ignore_set = set(DEFAULT_IGNORE if ignore is None else ignore)
    root_path = os.path.abspath(root_path)
    if not os.path.isdir(root_path):
        raise NotADirectoryError(root_path)

    def _walk(path: str, name: str) -> MerkleNode:
        entries = sorted(os.listdir(path))
        children: Dict[str, MerkleNode] = {}
        for entry in entries:
            if entry in ignore_set:
                continue
            full = os.path.join(path, entry)
            if os.path.islink(full):
                # Symlinks are hashed as blobs of their target string, so a
                # changed link target is detected like any other change,
                # without the walk ever following the link off the tree.
                target = os.readlink(full)
                children[entry] = MerkleNode(
                    name=entry,
                    is_dir=False,
                    hash=blob_hash(target.encode("utf-8")),
                    size=len(target),
                )
            elif os.path.isdir(full):
                children[entry] = _walk(full, entry)
            elif os.path.isfile(full):
                with open(full, "rb") as f:
                    content = f.read()
                children[entry] = build_file_node(entry, content)
            # other special files (sockets, devices, fifos...) are skipped

        return build_dir_node(name, children)

    return _walk(root_path, root_name or os.path.basename(root_path) or root_path)
