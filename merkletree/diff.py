"""Log-depth diffing between two Merkle trees.

The key property: if two subtrees have equal hashes, their entire content is
identical (barring a hash collision), so the diff never has to recurse into
an unchanged subtree -- it just skips it. For a tree of depth ``d`` with
``k`` changed leaves scattered across it, diff work is roughly O(k * d), not
O(total nodes). That pruning is the entire point of hashing the tree
bottom-up in the first place: it's what makes verifying a huge replica after
a small edit cheap instead of requiring a full re-scan and comparison.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .tree import MerkleNode


@dataclass
class DiffEntry:
    path: str
    change: str  # "added" | "removed" | "modified" | "type_changed"

    def __str__(self) -> str:
        return f"{self.change:12s} {self.path}"


class DiffStats:
    """Counts how many directory nodes ``diff_trees`` actually opened.

    Exists so tests (and curious callers) can verify the pruning behaviour
    directly instead of just trusting the module docstring.
    """

    def __init__(self) -> None:
        self.dirs_compared = 0
        self.subtrees_skipped = 0


def diff_trees(
    a: Optional[MerkleNode],
    b: Optional[MerkleNode],
    path: str = "",
    stats: Optional[DiffStats] = None,
) -> List[DiffEntry]:
    """Diff two Merkle trees rooted at ``a`` (old/trusted) and ``b`` (new/local).

    Returns every path that differs between the two trees, relative to the
    tree root. Either ``a`` or ``b`` may be ``None`` (meaning "does not
    exist at this path"), which naturally produces "added"/"removed"
    entries for everything under the side that does exist.
    """
    if stats is None:
        stats = DiffStats()

    if a is None and b is None:
        return []
    if a is None:
        return _all_paths(b, path, "added")
    if b is None:
        return _all_paths(a, path, "removed")

    if a.hash == b.hash:
        # Identical subtree -- this is the pruning step that makes the
        # overall diff log-depth rather than linear in the number of nodes.
        stats.subtrees_skipped += 1
        return []

    if a.is_dir != b.is_dir:
        return [DiffEntry(path or a.name, "type_changed")]

    if not a.is_dir:
        return [DiffEntry(path or a.name, "modified")]

    stats.dirs_compared += 1
    results: List[DiffEntry] = []
    names = sorted(set(a.children) | set(b.children))
    for name in names:
        child_path = f"{path}/{name}" if path else name
        results.extend(diff_trees(a.children.get(name), b.children.get(name), child_path, stats))
    return results


def _all_paths(node: MerkleNode, path: str, change: str) -> List[DiffEntry]:
    """List every leaf under ``node`` as its own added/removed DiffEntry.

    ``path`` is the path already accumulated by the caller (empty at the
    tree root) -- it deliberately never folds in ``node.name`` for a
    directory, matching diff_trees' own convention that the root's name is
    not part of any reported path, only its children's names are.
    """
    if not node.is_dir:
        return [DiffEntry(path or node.name, change)]
    results: List[DiffEntry] = []
    for name, child in sorted(node.children.items()):
        child_path = f"{path}/{name}" if path else name
        results.extend(_all_paths(child, child_path, change))
    return results
