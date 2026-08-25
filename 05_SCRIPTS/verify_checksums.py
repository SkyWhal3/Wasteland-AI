#!/usr/bin/env python3
"""
verify_checksums.py — fingerprint the archive so bit rot can't hide.

Two modes:

  BUILD an index (first time, and after you add files):
      python verify_checksums.py build /path/to/ARCHIVE --index checksums.csv

  CHECK against the index (yearly, or via cron):
      python verify_checksums.py check /path/to/ARCHIVE --index checksums.csv

Why this matters: on multi-terabyte cold storage, a flipped bit is silent.
The file still opens. The model weight is still "there." You find out it's
corrupt the day you need it. A checksum index turns that silent failure
into a loud one, years earlier.

Pure standard library — no pip installs needed. Safe: this script only
READS your archive; it never modifies or deletes anything.
"""

import argparse
import csv
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

CHUNK = 4 * 1024 * 1024  # read files 4 MB at a time (fine for a Pi's RAM)


def sha256_of(path: Path) -> str:
    """Hash one file without loading it all into memory."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(CHUNK)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def walk_files(root: Path):
    """Every regular file under root, as paths relative to root, sorted
    so the index is stable and diffs are readable."""
    for p in sorted(root.rglob("*")):
        if p.is_file() and not p.is_symlink():
            yield p.relative_to(root)


def build(root: Path, index: Path) -> int:
    rows = []
    total = 0
    print(f"Indexing {root} ... (large archives take a while — that's normal)")
    for rel in walk_files(root):
        full = root / rel
        try:
            digest = sha256_of(full)
        except OSError as e:
            print(f"  SKIP (unreadable): {rel}  [{e}]", file=sys.stderr)
            continue
        size = full.stat().st_size
        rows.append([str(rel), size, digest])
        total += 1
        if total % 100 == 0:
            print(f"  ...{total} files")

    with open(index, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["# built", datetime.now(timezone.utc).isoformat(), ""])
        w.writerow(["path", "bytes", "sha256"])
        w.writerows(rows)

    print(f"Done. {total} files indexed -> {index}")
    print("Keep a copy of the index ON A DIFFERENT DRIVE than the archive.")
    return 0


def check(root: Path, index: Path) -> int:
    if not index.exists():
        print(f"ERROR: index not found: {index}", file=sys.stderr)
        return 2

    expected = {}
    with open(index, newline="", encoding="utf-8") as f:
        for row in csv.reader(f):
            if not row or row[0].startswith("#") or row[0] == "path":
                continue
            expected[row[0]] = (int(row[1]), row[2])

    ok = missing = mismatched = new = 0
    seen = set()

    for rel in walk_files(root):
        key = str(rel)
        seen.add(key)
        if key not in expected:
            new += 1  # fine — just not indexed yet
            continue
        exp_size, exp_hash = expected[key]
        full = root / rel
        if full.stat().st_size != exp_size or sha256_of(full) != exp_hash:
            print(f"MISMATCH: {key}")
            mismatched += 1
        else:
            ok += 1

    for key in expected:
        if key not in seen:
            print(f"MISSING:  {key}")
            missing += 1

    print("-" * 50)
    print(f"OK: {ok}   MISMATCH: {mismatched}   MISSING: {missing}   "
          f"NEW (unindexed): {new}")
    if mismatched or missing:
        print("Action: restore the flagged files from another copy, "
              "then re-run 'build' to refresh the index.")
        return 1
    print("Archive verified clean.")
    if new:
        print(f"Note: {new} new files aren't in the index yet — "
              "run 'build' to include them.")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["build", "check"])
    ap.add_argument("root", type=Path, help="archive root directory")
    ap.add_argument("--index", type=Path, default=Path("checksums.csv"),
                    help="index CSV path (default: checksums.csv)")
    args = ap.parse_args()

    if not args.root.is_dir():
        print(f"ERROR: not a directory: {args.root}", file=sys.stderr)
        sys.exit(2)

    sys.exit(build(args.root, args.index) if args.mode == "build"
             else check(args.root, args.index))


if __name__ == "__main__":
    main()
