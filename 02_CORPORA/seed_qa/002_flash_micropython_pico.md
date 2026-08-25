---
question: How do I get MicroPython onto a Raspberry Pi Pico and make my code run at power-on?
answer_model: claude-fable-5
date: 2026-08-25
domain: code
serve_via: rag
human_verified: false
sources: [03_SOFTWARE/firmware/ (archived .uf2 files), 05_SCRIPTS/agent_examples/micropython_pico_blink.py]
---

**One-time: install the MicroPython firmware**

1. Hold the white **BOOTSEL** button on the Pico while plugging its USB into
   the Pi/PC. Keep holding until a drive called **RPI-RP2** appears.
2. Copy the MicroPython **.uf2** file onto that drive (archived offline in
   `03_SOFTWARE/firmware/` — one per board: pico, pico_w, pico2). The drive
   ejects itself; the Pico reboots as a MicroPython machine.

**Run code on it**

- Interactive: `mpremote` (pip-installed, archived in the wheel cache):
  - `mpremote`             → REPL on the board (Ctrl-X to exit)
  - `mpremote run blink.py`→ run a local file without copying it
- Or Thonny (GUI): bottom-right interpreter selector → "MicroPython
  (Raspberry Pi Pico)".

**Make it run at every power-on**

Copy the script to the board's filesystem **as `main.py`**:

    mpremote cp blink.py :main.py

MicroPython auto-runs `boot.py` then `main.py` from its internal flash on
power-up. To stop a runaway main.py: connect with `mpremote`, press Ctrl-C
to interrupt it, then `mpremote rm :main.py`.

**Gotchas**
- A Pico showing up as RPI-RP2 every time = firmware never got flashed, or
  the .uf2 is for the wrong board variant (pico vs pico_w vs pico2).
- `import machine` failing on the Pi itself is normal — MicroPython code
  runs on the microcontroller, not on Linux.
