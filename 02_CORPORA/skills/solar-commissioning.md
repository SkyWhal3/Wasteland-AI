---
name: solar-commissioning
description: >
  Fires when someone is wiring or first powering a solar array — series vs
  parallel, panel-to-controller order, polarity checks, fuse and breaker
  placement, MPPT vs PWM selection, or "I just bought panels, now what."
fires_on: [wire my panels, hook up panels, series or parallel, mc4, mppt,
           pwm, charge controller, commission, first power up, combiner,
           y branch, string my panels]
ask_first:
  - "Panel model, and the Voc / Vmp / Isc numbers off the label on its back —
     not from memory, not from the sales listing. Every number below depends
     on these."
  - "How many panels, and is your bank 12 V or 24 V?"
  - "Controller model and its ABSOLUTE MAXIMUM PV INPUT VOLTAGE."
  - "Coldest temperature the array will ever see with sun on it."
open_these:
  - 02_CORPORA/reference_tables/WIRING_DIAGRAMS_SOLAR.md   (diagrams + cold-Voc math)
  - 00_DOCS/BUILD_GUIDE.md   (panels/controllers, the fake-MPPT box, 12V/24V table)
  - 02_CORPORA/datasheets/power/<controller>_manual.pdf
never_generate:
  - wire gauge, fuse ratings, or breaker sizes
  - a string configuration for a panel whose datasheet has not been read
  - cold-Voc results from memory (run the formula, show the arithmetic)
fence: retrieval_only   # sizing is a fenced domain (electrical_sizing)
human_verified: false
---

## The one number that decides everything

**Cold open-circuit voltage versus the controller's absolute maximum.** Cold
panels make *more* voltage, and the worst case is a clear freezing dawn: panel
at ambient, sun just hit it, no load on it.

Exceeding the controller's **wattage** is harmless clipping. Exceeding its
**voltage** is a dead controller, and it is not a warranty claim.

Run the formula in WIRING_DIAGRAMS_SOLAR.md using the temperature coefficient
from your own datasheet, keep the result under **80 percent** of the
controller's maximum, and show the arithmetic to another human before landing
any wires.

## Order of operations — the sequence is not arbitrary

1. **Array disconnected while wiring**: breaker open, or panels covered or
   face-down. MC4 connectors pulled apart under load arc and pit their
   contacts, and a pitted connector is a future hot spot.
2. **Battery to controller FIRST.** The controller reads battery voltage at
   power-up to auto-detect 12 V versus 24 V. Connecting PV first can make it
   guess wrong and then apply the wrong charge profile to your bank.
3. **Meter on the PV leads before landing them.** Is the voltage what your
   arithmetic predicted? Is the polarity correct? Reversed polarity is the most
   common first-build mistake, and some controllers do not forgive it.
4. Close the PV disconnect.
5. Teardown is the reverse: **PV off first, battery last.**

## Series or parallel

Series adds volts, parallel adds amps, and it is the same energy either way —
you are choosing *which number gets large*. The cold-Voc ceiling above usually
makes the decision for you.

Worked examples, including the four-panels-in-one-string layout that appears in
half the tutorials online and kills 100 V controllers, are drawn in
WIRING_DIAGRAMS_SOLAR.md. Do not scale those diagrams in your head at midnight;
re-run the numbers for your actual panel.

**Never mix panel models or orientations on one controller.** A mismatched
panel drags the whole array off its maximum power point, and you lose more than
the extra panel contributed. Different panels mean a second controller.

## MPPT versus PWM

A PWM controller effectively clamps the panel down to battery voltage, throwing
away everything between Vmp and the battery. That is acceptable when the
panel's Vmp already sits near battery voltage, and wasteful otherwise. MPPT
converts the surplus voltage into extra current instead — that is where the
20 to 30 percent comes from.

**Verify that a cheap "MPPT" is really MPPT** before trusting it. See the
fake-MPPT box in BUILD_GUIDE. A twenty-dollar unit advertising 100 A is a PWM
controller in a costume, and it will quietly underperform for years without
ever announcing itself.

## Protection

The **battery-side fuse is the safety device** — it is the thing that stops a
shorted controller from welding itself to the bank. The **PV-side breaker is a
service disconnect**, not protection. String fuses are unnecessary with two
parallel strings and required at three or more, rated per the panel label's
maximum series fuse.

Actual ratings and gauges come from the ampacity tables, not from this file and
not from a language model. That is a fenced domain: retrieve the table, show
the table.
