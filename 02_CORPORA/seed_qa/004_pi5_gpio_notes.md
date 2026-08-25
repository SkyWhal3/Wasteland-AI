---
question: Why doesn't my GPIO code work on the Raspberry Pi 5? What changed?
answer_model: claude-fable-5
date: 2026-08-25
domain: code
serve_via: rag
human_verified: false
sources: [05_SCRIPTS/agent_examples/pi5_gpio_button_led.py]
---

The Pi 5 moved GPIO to a new I/O chip (RP1), which broke the library most
old tutorials use.

**The rules on a Pi 5:**

1. **`RPi.GPIO` DOES NOT WORK.** Any tutorial with `import RPi.GPIO as GPIO`
   is pre-Pi 5. It fails with "Cannot determine SOC peripheral base address."
2. **Use `gpiozero`** (preinstalled on Raspberry Pi OS) — it picks a working
   backend (lgpio/libgpiod) automatically and the API is simpler anyway.
   Example: `05_SCRIPTS/agent_examples/pi5_gpio_button_led.py`.
3. Lower-level needs (precise timing, chips gpiozero doesn't cover): use
   `lgpio` or `gpiod` directly. For hardware PWM/SPI/I2C, enable the
   peripheral in `sudo raspi-config` → Interface Options first.
4. **Numbering is BCM ("GPIO17"), not physical pin numbers.** GPIO17 is
   physical pin 11. Pinout reference: run `pinout` in a terminal — it ships
   with the OS and works offline.
5. **All GPIO is 3.3 V.** 5 V into a GPIO pin kills that pin or the Pi.
   Level-shift anything 5 V (relay boards are the classic trap — check if
   the IN pin is opto-isolated or straight to the coil driver).
6. The manifest keeps the Pi's GPIO free by design (§3: bottom-mount NVMe,
   USB radio dongle) — the supervisor MCU (§4), not the Pi, is what
   ultimately owns power-control pins.
