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

Portability: index paths are stored with forward slashes, so an index BUILT
on the Windows drive array CHECKS cleanly on the Pi (and vice versa) after
you copy the archive over. A read error during check (failing sector,
yanked cable) is REPORTED and counted — it does not kill a 10-hour scan,
because an unreadable file is exactly the kind of rot we're hunting.

Pure standard library — no pip installs needed. Safe: this script only
READS your archive; it never modifies or deletes anything (the index file
itself is the one thing it writes, atomically).
"""

import argparse
import csv
import hashlib
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

CHUNK = 4 * 1024 * 1024   # read files 4 MB at a time (fine for a Pi's RAM)
PROGRESS_EVERY = 200      # heartbeat so long scans don't look hung


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


def walk_files(root: Path, skip_rel: set):
    """Every regular file under root, as PORTABLE (forward-slash) relative
    path strings, sorted so the index is stable and diffs are readable.
    `skip_rel` lets us exclude the index file itself when it lives inside
    the archive — otherwise every check flags the index as changed."""
    for p in sorted(root.rglob("*")):
        if p.is_file() and not p.is_symlink():
            rel = p.relative_to(root).as_posix()
            if rel in skip_rel:
                continue
            yield rel


def index_skip_set(root: Path, index: Path) -> set:
    """If the index (or its temp file) is inside the archive, exclude it."""
    skip = set()
    try:
        root_res = root.resolve()
        for candidate in (index, index.with_suffix(index.suffix + ".tmp")):
            res = candidate.resolve()
            if res.is_relative_to(root_res):
                skip.add(res.relative_to(root_res).as_posix())
    except OSError:
        pass
    return skip


def build(root: Path, index: Path) -> int:
    if index.exists():
        print(f"NOTE: overwriting existing index {index}. If you haven't run "
              f"'check' first, corrupted files get blessed as the new truth.")
    rows = []
    total = 0
    skip = index_skip_set(root, index)
    print(f"Indexing {root} ... (large archives take a while — that's normal)")
    for rel in walk_files(root, skip):
        full = root / rel
        try:
            digest = sha256_of(full)
            size = full.stat().st_size
        except OSError as e:
            print(f"  SKIP (unreadable): {rel}  [{e}]", file=sys.stderr)
            continue
        rows.append([rel, size, digest])
        total += 1
        if total % PROGRESS_EVERY == 0:
            print(f"  ...{total} files")

    # Write to a temp file, then atomically replace: a crash or Ctrl-C
    # mid-write can't destroy the previous index.
    tmp = index.with_suffix(index.suffix + ".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["# built", datetime.now(timezone.utc).isoformat(), ""])
        w.writerow(["path", "bytes", "sha256"])
        w.writerows(rows)
    os.replace(tmp, index)

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
            if len(row) < 3 or row[0].startswith("#") or row[0] == "path":
                continue
            # tolerate an index built by an older version on Windows
            key = row[0].replace("\\", "/")
            try:
                expected[key] = (int(row[1]), row[2])
            except ValueError:
                print(f"  SKIP (bad index row): {row}", file=sys.stderr)

    ok = missing = mismatched = read_errors = new = scanned = 0
    seen = set()
    skip = index_skip_set(root, index)

    for rel in walk_files(root, skip):
        seen.add(rel)
        scanned += 1
        if scanned % PROGRESS_EVERY == 0:
            print(f"  ...{scanned} files checked")
        if rel not in expected:
            new += 1  # fine — just not indexed yet
            continue
        exp_size, exp_hash = expected[rel]
        full = root / rel
        try:
            if full.stat().st_size != exp_size or sha256_of(full) != exp_hash:
                print(f"MISMATCH: {rel}")
                mismatched += 1
            else:
                ok += 1
        except OSError as e:
            # An unreadable file IS the failure we're scanning for.
            # Report it and keep going — don't lose the rest of the scan.
            print(f"READ ERROR: {rel}  [{e}]")
            read_errors += 1

    for key in expected:
        if key not in seen:
            print(f"MISSING:  {key}")
            missing += 1

    print("-" * 50)
    print(f"OK: {ok}   MISMATCH: {mismatched}   MISSING: {missing}   "
          f"READ ERRORS: {read_errors}   NEW (unindexed): {new}")
    if mismatched or missing or read_errors:
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
