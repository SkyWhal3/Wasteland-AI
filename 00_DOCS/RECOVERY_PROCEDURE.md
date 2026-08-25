# RECOVERY PROCEDURE — rebuild the stack from the faraday drive

**Status: SKELETON — untested. An untested backup is a rumor (manifest §14
step 12). Fill in the blanks during the first air-gapped recovery drill,
then re-run the drill yearly (§15).**

## What you are holding
The 4 TB rugged USB drive contains: small models + core ZIMs + toolchain +
layers 0/3 (inventory + datasheets) + these scripts + this procedure.

## Order of restoration (each step useful alone)

1. **A computer.** Any x86_64 or Pi 4/5. If nothing boots: `03_SOFTWARE/os_images/`
   has Raspberry Pi OS + `rpi-imager` + a Debian ISO. Flash from any working
   machine. TODO: record which images + versions are actually on the drive.
2. **Kiwix first.** `kiwix-tools` static binary + `wikipedia_en_all_mini` +
   `wikem` = the library, on anything, in minutes. TODO: exact launch line.
3. **Checksums.** `python verify_checksums.py check <drive_root> --index ...`
   — know NOW if the drive rotted, not when you need a file. TODO: where the
   index copy lives (must be a different drive than the archive!).
4. **Scripts.** `05_SCRIPTS/` + `make_skeleton.py` to rebuild the tree;
   requirements install from the offline wheel cache in `03_SOFTWARE/python/`.
   TODO: verify the wheel cache covers pyserial/meshtastic/requests for the
   target Python version.
5. **Models.** Ollama or llama.cpp from `01_MODELS/runtimes/RUNTIME_<date>/`
   — use the frozen combination, not whatever's newest. TODO: record the
   known-good launch flags per snapshot.
6. **Power telemetry + radio** last — they need the physical cables anyway.

## Drill log

| Date | Machine | Time to Kiwix | Time to model | Gaps found |
|---|---|---|---|---|
| (never run) | | | | |
