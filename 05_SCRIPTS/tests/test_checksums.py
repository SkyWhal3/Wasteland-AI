"""End-to-end test: verify_checksums.py build/check/corrupt/missing.

Run from anywhere:  python 05_SCRIPTS/tests/test_checksums.py
Uses a throwaway temp directory; touches nothing in the repo.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = str(Path(__file__).resolve().parents[1] / "verify_checksums.py")


def run(*args):
    return subprocess.run([sys.executable, SCRIPT, *args],
                          capture_output=True, text=True)


with tempfile.TemporaryDirectory() as td:
    S = Path(td) / "archive"
    (S / "sub").mkdir(parents=True)
    (S / "a.txt").write_text("alpha")
    (S / "sub" / "b.bin").write_bytes(b"\x00" * 1000)
    idx = S / "checksums.csv"      # index INSIDE the root: tests self-skip too

    # build
    r = run("build", str(S), "--index", str(idx))
    assert r.returncode == 0, r.stdout + r.stderr
    text = idx.read_text()
    assert "sub/b.bin" in text and "sub\\b.bin" not in text, \
        "want posix keys:\n" + text
    assert "checksums.csv" not in text, "index must not index itself:\n" + text

    # clean check
    r = run("check", str(S), "--index", str(idx))
    assert r.returncode == 0 and "verified clean" in r.stdout, r.stdout

    # same-size corruption -> MISMATCH, exit 1
    (S / "sub" / "b.bin").write_bytes(b"\x00" * 999 + b"\x01")
    r = run("check", str(S), "--index", str(idx))
    assert r.returncode == 1 and "MISMATCH: sub/b.bin" in r.stdout, r.stdout

    # deleted file -> MISSING, exit 1
    (S / "a.txt").unlink()
    r = run("check", str(S), "--index", str(idx))
    assert r.returncode == 1 and "MISSING:  a.txt" in r.stdout, r.stdout

print("verify_checksums: ALL TESTS PASS")
