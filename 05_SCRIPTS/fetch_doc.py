#!/usr/bin/env python3
"""
fetch_doc.py — download a document into the archive, and REFUSE to save a
broken one.

    python fetch_doc.py <url> <destination.pdf>
    python fetch_doc.py --list urls.txt        # one "url<TAB>dest" per line

WHY THIS EXISTS — an actual incident, 2026-08-25:

Three generator manuals downloaded from a manufacturer CDN came back at
exactly 8 MiB, 8 MiB, and 4 MiB. Powers of two are never a coincidence in a
file size. The CDN was truncating automated requests, the download reported
success, and every file began with a valid %PDF header.

Had those been saved and indexed, the archive would have held three corrupt
manuals **with perfectly valid checksums** — because a checksum only proves a
file has not changed since you hashed it. It says nothing about whether the
file was whole when it arrived. The corruption would have surfaced years
later, on the day somebody needed page 41 with no internet to re-download it.

So this script validates before it writes:
  1. HTTP status must be OK
  2. Byte count must match Content-Length when the server provides one
  3. PDFs must start with %PDF *and* end with the %%EOF trailer
  4. Nothing is written to the archive until all of the above pass

A refused download is a good outcome. It tells you to find a mirror, or to
open a browser, instead of quietly poisoning the archive.

Pure standard library.
"""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request

# A User-Agent alone is not enough everywhere: stacks.cdc.gov returns 403
# to any request that omits an Accept header (found 2026-09-01). These are
# headers every ordinary HTTP client sends; the UA still says archival.
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) archival/1.0",
      "Accept": "application/pdf,application/octet-stream,*/*",
      "Accept-Language": "en-US,en;q=0.9"}
CHUNK = 65536
RETRIES = 3
TAIL = 2048          # how far from the end to look for the PDF trailer


def looks_complete(data: bytes, dest: str) -> tuple[bool, str]:
    """Format-aware integrity check. Extend this as you add formats."""
    if dest.lower().endswith(".pdf"):
        if not data.startswith(b"%PDF"):
            return False, "not a PDF (no %PDF header — probably an error page)"
        if b"%%EOF" not in data[-TAIL:]:
            return False, "PDF has no %%EOF trailer — TRUNCATED"
    if len(data) < 1024:
        return False, f"suspiciously small ({len(data)} bytes)"
    return True, ""


def fetch(url: str, dest: str, retries: int = RETRIES) -> bool:
    """Download url to dest, or write nothing and explain why."""
    name = os.path.basename(dest)
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=180) as r:
                expected = int(r.headers.get("Content-Length") or 0)
                buf = bytearray()
                while True:
                    chunk = r.read(CHUNK)
                    if not chunk:
                        break
                    buf += chunk
            data = bytes(buf)
        except urllib.error.HTTPError as e:
            print(f"  attempt {attempt}: HTTP {e.code}")
            if e.code in (403, 404):
                break          # not transient — retrying will not help
            continue
        except Exception as e:
            print(f"  attempt {attempt}: {type(e).__name__}: {e}")
            continue

        if expected and len(data) != expected:
            print(f"  attempt {attempt}: got {len(data):,} of {expected:,} bytes — short")
            continue

        ok, why = looks_complete(data, dest)
        if not ok:
            print(f"  attempt {attempt}: {why}")
            continue

        os.makedirs(os.path.dirname(os.path.abspath(dest)) or ".", exist_ok=True)
        with open(dest, "wb") as f:
            f.write(data)
        print(f"OK    {name}  {len(data):,} bytes")
        return True

    print(f"FAIL  {name}  — nothing written. Try a mirror, or fetch it in a\n"
          f"      browser. Some CDNs (Intel, Generac) refuse or truncate\n"
          f"      automated requests on purpose.")
    return False


def main() -> None:
    args = sys.argv[1:]
    if len(args) == 2 and args[0] == "--list":
        jobs = []
        with open(args[1], encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    url, _, dest = line.partition("\t")
                    jobs.append((url.strip(), dest.strip()))
    elif len(args) == 2:
        jobs = [(args[0], args[1])]
    else:
        print(__doc__.strip().split("\n\n")[1])
        sys.exit(1)

    good = sum(1 for url, dest in jobs if fetch(url, dest))
    print(f"\n{good}/{len(jobs)} saved.")
    if good < len(jobs):
        print("Refused downloads are a FEATURE — a truncated manual that "
              "indexes as good is worse than no manual at all.")
    sys.exit(0 if good == len(jobs) else 1)


if __name__ == "__main__":
    main()
