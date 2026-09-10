"""Command-line interface for merkle-tree-sync-verifier."""
from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from .diff import diff_trees
from .tree import build_tree
from .verify import load_manifest, save_manifest, verify_directory


def _load_side(path: str):
    """A CLI diff argument may be a saved manifest (.json) or a live directory."""
    if path.endswith(".json"):
        return load_manifest(path)
    return build_tree(path)


def cmd_hash(args: argparse.Namespace) -> int:
    node = build_tree(args.directory, ignore=args.ignore)
    if args.output:
        save_manifest(node, args.output)
        print(f"root hash: {node.hash}")
        print(f"manifest written to {args.output} ({node.node_count()} nodes, {node.leaf_count()} files)")
    else:
        print(node.hash)
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    a = _load_side(args.a)
    b = _load_side(args.b)
    entries = diff_trees(a, b)
    if not entries:
        print("no differences")
        return 0
    for entry in entries:
        print(entry)
    return 1


def cmd_verify(args: argparse.Namespace) -> int:
    result = verify_directory(args.directory, args.manifest, ignore=args.ignore)
    print(result.summary())
    return 0 if result.ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="merkletree", description="Merkle-tree directory integrity & sync verification"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_hash = sub.add_parser("hash", help="hash a directory and optionally save a manifest")
    p_hash.add_argument("directory")
    p_hash.add_argument("-o", "--output", help="write full manifest JSON to this path")
    p_hash.add_argument("--ignore", nargs="*", help="additional basenames to ignore")
    p_hash.set_defaults(func=cmd_hash)

    p_diff = sub.add_parser(
        "diff", help="diff two directories or saved manifests (.json), log-depth if both are manifests"
    )
    p_diff.add_argument("a", help="directory path, or a .json manifest saved by 'hash -o'")
    p_diff.add_argument("b", help="directory path, or a .json manifest saved by 'hash -o'")
    p_diff.set_defaults(func=cmd_diff)

    p_verify = sub.add_parser("verify", help="verify a directory against a trusted manifest")
    p_verify.add_argument("directory")
    p_verify.add_argument("manifest")
    p_verify.add_argument("--ignore", nargs="*", help="additional basenames to ignore")
    p_verify.set_defaults(func=cmd_verify)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
