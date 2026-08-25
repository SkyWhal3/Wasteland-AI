#!/usr/bin/env python3
"""
make_skeleton.py — create the manifest §13 folder tree.

The public repo ships only docs + code (see .gitignore), so a fresh clone
doesn't include the data folders. Run this once after cloning to build
them. Idempotent: existing folders are left exactly as they are.

    python make_skeleton.py            # builds the tree in the repo root
    python make_skeleton.py D:\\SOMEWHERE\\ELSE
"""

import sys
from pathlib import Path

DIRS = [
    "00_DOCS",
    "00_INVENTORY/photos",
    "01_MODELS/tier0_small",
    "01_MODELS/tier1_workhorse",
    "01_MODELS/embeddings",
    "01_MODELS/speech",
    "01_MODELS/runtimes",
    "02_CORPORA/kiwix_zim",
    "02_CORPORA/datasheets/radio",
    "02_CORPORA/datasheets/power",
    "02_CORPORA/datasheets/vehicle",
    "02_CORPORA/datasheets/components",
    "02_CORPORA/reference_tables",
    "02_CORPORA/pdfs/medical",
    "02_CORPORA/pdfs/technical",
    "02_CORPORA/pdfs/personal",
    "02_CORPORA/bootstrap",
    "02_CORPORA/maps",
    "02_CORPORA/seed_qa",
    "03_SOFTWARE/runtimes",
    "03_SOFTWARE/docker_images",
    "03_SOFTWARE/python",
    "03_SOFTWARE/drivers",
    "03_SOFTWARE/os_images",
    "03_SOFTWARE/apt_mirror",
    "03_SOFTWARE/firmware",
    "04_CONFIG/modelfiles",
    "04_CONFIG/systemd",
    "04_CONFIG/dotfiles",
    "04_CONFIG/meshtastic",
    "04_CONFIG/supervisor",
    "05_SCRIPTS/agent_examples",
    "06_MONUMENT",
]


def main():
    # default root = the repo root (parent of the folder this script is in)
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else \
        Path(__file__).resolve().parent.parent
    made = existed = 0
    for d in DIRS:
        p = root / d
        if p.is_dir():
            existed += 1
        else:
            p.mkdir(parents=True, exist_ok=True)
            made += 1
    print(f"{root}: created {made} folder(s), {existed} already existed.")
    print("Reminder: 01_MODELS / 02_CORPORA / 04_CONFIG / 06_MONUMENT are "
          "git-ignored on purpose. Keep them that way.")


if __name__ == "__main__":
    main()
