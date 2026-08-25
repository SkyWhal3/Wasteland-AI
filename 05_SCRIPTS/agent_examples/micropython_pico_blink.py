# EXAMPLE (MicroPython, Raspberry Pi Pico / Pico W / Pico 2)
# Blink the onboard LED forever — the "hello world" that proves the board,
# the firmware, and your copy process all work.
#
# This runs ON THE PICO, not on the Pi 5. Save it to the board as main.py
# (see 02_CORPORA/seed_qa/002_flash_micropython_pico.md) and it runs at
# every power-on.

from machine import Pin
import time

# "LED" works on every modern MicroPython build: a plain Pico maps it to
# GP25, a Pico W routes it to the WiFi chip's LED. On very old firmware,
# use Pin(25, Pin.OUT) instead.
led = Pin("LED", Pin.OUT)

while True:
    led.toggle()
    time.sleep(0.5)      # seconds: 0.5 on / 0.5 off = 1 blink per second
