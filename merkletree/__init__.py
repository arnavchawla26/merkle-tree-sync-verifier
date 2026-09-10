"""merkle-tree-sync-verifier: content-addressed directory integrity & sync verification.

Build a Merkle tree over a directory (or dataset shard set), diff two trees
in log-depth time by pruning subtrees whose hashes already match, and verify
a local or replicated copy against a trusted root hash / manifest.
"""

from .diff import DiffEntry, DiffStats, diff_trees
from .hashing import blob_hash, hash_bytes, tree_hash
from .tree import MerkleNode, build_tree
from .verify import VerifyResult, load_manifest, save_manifest, verify_directory

__version__ = "0.1.0"

__all__ = [
    "DiffEntry",
    "DiffStats",
    "diff_trees",
    "blob_hash",
    "hash_bytes",
    "tree_hash",
    "MerkleNode",
    "build_tree",
    "VerifyResult",
    "load_manifest",
    "save_manifest",
    "verify_directory",
    "__version__",
]
