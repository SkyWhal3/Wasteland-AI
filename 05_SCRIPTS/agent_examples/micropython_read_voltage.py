# EXAMPLE (MicroPython, Raspberry Pi Pico): read a DC voltage via a divider.
#
# *** THE PICO'S ADC PINS DIE ABOVE 3.3 V. NEVER CONNECT A BATTERY DIRECTLY. ***
#
# A resistor divider scales the voltage down first. With 100k on top and
# 20k on the bottom, 19.8 V at the battery becomes 3.3 V at the pin — good
# for a 12 V system with headroom. Recalculate for YOUR resistors; measure
# them with a multimeter (5% resistors give ~5% wrong voltage until you
# calibrate CAL against a known-good meter).
#
#   battery + ---[ R_TOP ]---+---[ R_BOTTOM ]--- ground
#                            |
#                        ADC pin (GP26)

from machine import ADC
import time

adc = ADC(26)                   # GP26 = ADC0 (physical pin 31)
R_TOP = 100_000                 # ohms, battery side
R_BOTTOM = 20_000               # ohms, ground side
DIVIDER = (R_TOP + R_BOTTOM) / R_BOTTOM     # = 6.0 with the values above
VREF = 3.3
CAL = 1.000                     # nudge after comparing with a real meter

while True:
    raw = adc.read_u16()                    # 0..65535
    v_pin = raw / 65535 * VREF              # volts at the ADC pin
    v_batt = v_pin * DIVIDER * CAL          # volts at the battery
    print("{:.2f} V".format(v_batt))
    time.sleep(1)
