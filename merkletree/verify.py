"""Verify a directory (or replica) against a trusted Merkle manifest."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List, Optional

from .diff import DiffEntry, DiffStats, diff_trees
from .tree import MerkleNode, build_tree


@dataclass
class VerifyResult:
    ok: bool
    local_root_hash: str
    trusted_root_hash: str
    differences: List[DiffEntry]
    stats: DiffStats

    def summary(self) -> str:
        if self.ok:
            return f"OK: root hash matches ({self.local_root_hash})"
        lines = [
            f"MISMATCH: local={self.local_root_hash} trusted={self.trusted_root_hash}",
            f"{len(self.differences)} differing path(s):",
        ]
        lines.extend(f"  {d}" for d in self.differences)
        return "\n".join(lines)


def save_manifest(node: MerkleNode, manifest_path: str) -> None:
    """Write a full, re-loadable Merkle tree to disk as JSON.

    This is the "signature"/trusted reference: unlike a bare root hash, it
    carries every subtree hash, so a later verify_directory() call can say
    exactly *which* paths changed instead of only "match" / "no match".
    """
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(node.to_dict(), f, indent=2, sort_keys=True)
        f.write("\n")


def load_manifest(manifest_path: str) -> MerkleNode:
    with open(manifest_path, "r", encoding="utf-8") as f:
        return MerkleNode.from_dict(json.load(f))


def verify_directory(
    directory: str,
    manifest_path: str,
    ignore: Optional[List[str]] = None,
) -> VerifyResult:
    """Rebuild the Merkle tree for ``directory`` and compare it against a
    previously saved trusted manifest.

    This always has to hash the full local directory -- there is no way to
    know whether a file changed without reading it at least once. The
    log-depth saving from ``diff_trees`` applies to *comparing two already
    built trees*, which is exactly what happens right after that: walking
    from the two root hashes down to find exactly where they differ is
    pruned at every matching subtree, so the more of the replica that is
    still correct, the cheaper the walk that finds what isn't.
    """
    trusted = load_manifest(manifest_path)
    local = build_tree(directory, ignore=ignore, root_name=trusted.name)
    stats = DiffStats()
    differences = diff_trees(trusted, local, stats=stats)
    return VerifyResult(
        ok=(local.hash == trusted.hash),
        local_root_hash=local.hash,
        trusted_root_hash=trusted.hash,
        differences=differences,
        stats=stats,
    )
