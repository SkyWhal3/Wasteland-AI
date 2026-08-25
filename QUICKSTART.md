# QUICKSTART — three on-ramps

Pick your commitment level. Levels 1 and 2 work on **any computer** —
Windows, Mac, Linux — tonight, with no special hardware. Python 3.9+.

---

## Level 1 — Five minutes, no hardware: prove the code is real

From the repo root (cloned, or the unzipped release):

**Linux / macOS / Raspberry Pi:**
```bash
cd 05_SCRIPTS
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python safety_router.py --test
python safety_router.py "how much varget for a 168gr .308 load?"
python verify_checksums.py build ../00_DOCS --index demo.csv
python verify_checksums.py check ../00_DOCS --index demo.csv
python power_monitor.py --list-ports
python power_monitor.py --demo        # fake sun, real band logic (Ctrl-C stops)
python lora_oracle.py --demo          # the mesh bot at your keyboard
```

**Windows (PowerShell):**
```powershell
cd 05_SCRIPTS
py -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python safety_router.py --test
python safety_router.py "how much varget for a 168gr .308 load?"
python verify_checksums.py build ..\00_DOCS --index demo.csv
python verify_checksums.py check ..\00_DOCS --index demo.csv
python power_monitor.py --list-ports
python power_monitor.py --demo        # fake sun, real band logic (Ctrl-C stops)
python lora_oracle.py --demo          # the mesh bot at your keyboard
```
> If `Activate.ps1` is blocked: `Set-ExecutionPolicy -Scope Process Bypass`
> (affects this one window only), then activate again.

Want more proof? The full test suite runs anywhere too (same as CI):
```bash
python tests/test_vedirect.py
python tests/test_checksums.py
python tests/test_smoke.py
```

**What you just saw:**
- `--test` — the safety contract executing: 14 canonical questions routed,
  dangerous ones provably fenced away from the AI. This is the audit.
- The router refusing to let a **reloading** question near a language model.
- A real bit-rot index built over the docs folder, then verified. Point the
  same two commands at terabytes and that's the archive's immune system.
- Every serial port on your machine, enumerated — the VE.Direct solar cable
  and the Meshtastic radio will show up right there when they arrive.
- `--demo` on the monitor: a fake sun rises and sets so you can watch the
  GREEN/YELLOW/RED/BLACK band logic think — synthetic data, labeled DEMO
  everywhere it lands.
- `--demo` on the oracle: the mesh bot with your keyboard standing in for
  the radio — same code, same 200-char cap. **They chain:** run the monitor
  demo in one terminal, the oracle demo in another, type `?power` — that's
  the whole Tier-0 loop with zero hardware.

---

## Level 2 — One evening, any computer: the actual library

This is the demo that sells the whole idea: **Wikipedia and an ER manual on
your machine, no internet required once downloaded.**

1. **Get kiwix-serve** (a single small binary):
   https://download.kiwix.org/release/kiwix-tools/ — grab the archive for
   your OS (Windows/macOS/Linux x86_64, and `armhf`/`aarch64` for the Pi),
   extract it anywhere.
2. **Get a ZIM file** (the compressed library format). Start small:
   search for **`wikem`** (~1 GB, emergency medicine) at
   https://library.kiwix.org or browse https://download.kiwix.org/zim/ —
   use the torrent links if you can, it's the polite way.
3. **Serve it:**
   ```bash
   kiwix-serve --port 8080 wikem_en_all_maxi_2025-XX.zim
   ```
   (Windows: `kiwix-serve.exe --port 8080 wikem_...zim` — same thing.)
4. Open **http://localhost:8080** and look up: `dehydration`, `tourniquet`,
   `hypothermia`. That's retrieval — verbatim, cited, zero hallucination.
5. Note the **book name** kiwix shows (e.g. `wikem_en_all_maxi`) — that
   exact string is what goes in `KIWIX_BOOK` in `lora_oracle.py` later.

6. **Bonus — the full Oracle pipeline, no radio:** with kiwix still
   running, `python 05_SCRIPTS/lora_oracle.py --demo`, then type
   `?med tourniquet`. That is the exact code the radio path runs — it even
   figures out your server's real book name by itself (URL names are
   filename stems like `wikem_en_all_maxi_2026-07`; the script probes,
   discovers, and logs what it picked).

Then go back for `wikipedia_en_all_mini` (~5–6 GB) and feel the size of
what fits on a fingernail of storage. The full shopping list with all
sources: [MANIFEST.md §8](00_DOCS/MANIFEST.md).

---

## Level 3 — The real build: Pi + solar + radio

**Minimum viable node:** Raspberry Pi 5 (8 GB) + active cooler + an NVMe
(or just a big SD to start) + `wikipedia_en_all_mini` (~5 GB) + `wikem`
(~0.4 GB) + the Hesperian PDFs. That's the survival core, complete.
Everything else in this project is capability stacked on top of it.

The step-by-step lives in [05_SCRIPTS/README.md](05_SCRIPTS/README.md)
(venv, watchdog, systemd units) and the build order in
[MANIFEST.md §14](00_DOCS/MANIFEST.md) — each step useful on its own:

1. Library on the Pi first (Level 2, on the Pi — one evening, ~8 W).
2. Solar telemetry when the VE.Direct cable lands (`power_monitor.py`).
3. Radio + Oracle last (`lora_oracle.py`) — and run the
   [SECURITY.md](00_DOCS/SECURITY.md) checklist **before** the node lives
   on a real mesh. Set `AUTHORIZED_SENDERS`.

---

## Filing a bug worth fixing

"It didn't work" is a mood, not a bug report. Include:

- OS + Python version (`python --version`)
- The script, the exact command, and the **full traceback**
- For `?med` problems: your kiwix-tools version and the book name it serves
- For serial problems: the `--list-ports` output

You are the test fleet. Break it honestly and you're a contributor.
