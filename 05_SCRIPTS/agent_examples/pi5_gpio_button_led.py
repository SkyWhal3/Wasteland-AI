# EXAMPLE (CPython, on the Raspberry Pi itself): button press lights an LED.
#
# IMPORTANT PI 5 FACT: the old RPi.GPIO library DOES NOT WORK on the Pi 5
# (new GPIO hardware, RP1 chip). Use gpiozero — it's preinstalled on
# Raspberry Pi OS, drives the Pi 5 correctly through libgpiod, and the
# code is shorter anyway. If an internet tutorial says `import RPi.GPIO`,
# it's a pre-2024 tutorial.
#
# Wiring: LED + resistor (330R) from BCM17 (physical pin 11) to ground;
# button from BCM2 (physical pin 3) to ground — gpiozero enables the
# internal pull-up for you.

from gpiozero import LED, Button
from signal import pause

led = LED(17)          # BCM numbering, not physical pin numbers
button = Button(2)     # pull-up enabled by default; pressed = pin to ground

button.when_pressed = led.on
button.when_released = led.off

print("Press the button (Ctrl-C to quit)")
pause()                # sleep forever; the callbacks do the work
