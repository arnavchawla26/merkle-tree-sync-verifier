# merkle-tree-sync-verifier

A from-scratch Merkle tree over a real directory tree (or a dataset's shard
layout): build it, diff two trees in **log-depth time** instead of hashing
everything twice, and verify a local or replicated copy against a trusted
manifest — finding exactly which files changed without a full re-scan.

## Why a tree, not a flat hash list

Hashing every file and comparing lists works, but it's O(n) in the number of
files even when only one file changed. This project instead builds a
**content-addressed tree**, git-object style: every file is a leaf hashed
from its bytes, and every directory's hash is a pure function of its
children's `(name, is_dir, hash)` triples. Two subtrees with equal hashes are
*guaranteed* identical (barring a hash collision) — so diffing two trees can
skip an entire matching subtree the instant their root hashes match, instead
of walking into it. For a tree of depth `d` with `k` changed leaves, that
makes diffing roughly `O(k · d)` instead of `O(total files)`.

## What it does

- **`hashing.py`** — SHA-256 with git-inspired framing (`blob <len>\0<content>`
  for files, `tree <len>\0<entries>` for directories) so a file's hash and a
  directory's hash can never collide by construction, and directory hashing
  is independent of filesystem listing order.
- **`tree.py`** — `build_tree()` walks a real directory into an in-memory
  `MerkleNode` tree (files, subdirectories, and symlinks — a symlink is
  hashed by its target string, never followed off the tree). Serializes to/
  from JSON for saving as a manifest.
- **`diff.py`** — `diff_trees()` recursively compares two trees, pruning any
  subtree whose hash already matches. Reports `added` / `removed` /
  `modified` / `type_changed` per path. A `DiffStats` counter lets tests (and
  callers) verify the pruning actually happens, not just trust the docstring.
- **`verify.py`** — `verify_directory()` rebuilds a directory's tree and
  diffs it against a previously saved trusted manifest, so a replica or
  downloaded copy can be checked against a known-good root hash and told
  exactly what's wrong, not just "mismatch."
- **`cli.py`** — a `merkletree` command: `hash`, `diff`, `verify`.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Usage

```bash
# Hash a directory and save a manifest (the "trusted signature")
merkletree hash ./mydata -o manifest.json

# Diff two directories, or two saved manifests, or one of each
merkletree diff ./mydata ./mydata-copy
merkletree diff manifest-v1.json manifest-v2.json

# Verify a local/replicated directory against a trusted manifest
merkletree verify ./mydata-replica manifest.json
```

Example:

```
$ merkletree hash ./mydata -o manifest.json
root hash: 4464289649c25f09d69d8428e9f8ce883c13089b5d815da1e0a8723db5e9bd0d
manifest written to manifest.json (2 nodes, 1 files)

$ merkletree verify ./mydata-replica manifest.json
MISMATCH: local=a60662891f4034d920fee81e4ad6b849cb2de2f9d7b822669861d8da91c31802 trusted=4464289649c25f09d69d8428e9f8ce883c13089b5d815da1e0a8723db5e9bd0d
1 differing path(s):
  added        sub/b.txt
```

`diff` and `verify` exit `0` when there are no differences and `1` when
there are, so both are safe to use in scripts/CI as a pass/fail check.

## Tech stack

Python 3.9+, standard library only (`hashlib`, `argparse`, `json`, `os`) —
no runtime dependencies. `pytest` + `pyflakes` for dev/test.

## Tests

```bash
pytest        # 42 tests
pyflakes merkletree tests
```

Coverage: hash determinism and order-independence, tree building (structure,
ignore patterns, symlinks, empty dirs, JSON round-trip), diffing (identical
trees, added/removed/modified/type-changed, both-sides-None), verification
against a saved manifest (unchanged / modified / added+removed / scattered
multi-file changes / moved-directory / missing-manifest), and CLI end-to-end
smoke tests for all three subcommands including exit codes.

The diff module's log-depth claim is tested directly, not just asserted in
prose: `test_diff_is_log_depth_not_linear_in_tree_size` builds a tree with
1,555 nodes (depth 4, branching factor 6), changes exactly one leaf, and
asserts the diff only opens the 4 directories on the path to that leaf —
everywhere else is pruned by a single hash comparison, confirmed via a
`DiffStats` counter rather than trusting the implementation.

## A real bug this caught

`_all_paths()` (used when one side of a diff is entirely missing, e.g.
comparing against `None`) originally fell back to `path or node.name` for
*every* node, not just leaves. That meant a top-level directory's own name
leaked into every reported path — `diff_trees(None, tree)` on a tree whose
root was named `"root"` reported `root/a.txt` instead of `a.txt`, breaking
the invariant (used everywhere else in `diff_trees`) that the tree root's own
name never appears in a reported path, only its children's names do. Caught
by `test_diff_one_side_none_reports_everything_under_the_other` asserting the
exact expected path set — not just "diff returns something."

## Current status

v1 shipped and complete: hashing, tree building (incl. symlinks and ignore
patterns), log-depth diffing, manifest-based verification, and a 3-command
CLI, all covered by 42 passing tests. Possible future extensions (not yet
built): a `--jobs N` parallel hasher for very large trees, content-defined
chunking for large individual files (so a one-byte change inside a huge file
doesn't re-transfer the whole blob — see the companion
[rolling-hash-delta-sync](https://github.com/arnavchawla26/rolling-hash-delta-sync)
project for that piece), and a `sync` subcommand that actually copies the
changed paths rather than only reporting them.

## License

MIT
