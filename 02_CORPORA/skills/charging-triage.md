---
name: charging-triage
description: >
  Fires when the battery is not charging, is charging slowly, or the state of
  charge does not match what the sun should have delivered. Covers controller
  error and charge-state codes, cold-weather BMS cutoff, snow, and why a
  voltage reading lies on lithium.
fires_on: [not charging, wont charge, will not charge, no charge current,
           battery is low, soc dropping, mppt error, err 33, charge state,
           bulk absorption float, low temp cutoff, bms cutoff, not making power]
ask_first:
  - "What does the controller itself report — the charge state and any error
     code? power_monitor.py decodes both; read them before guessing."
  - "Battery temperature. Below freezing, a correctly functioning BMS will
     REFUSE charge. That is the number one December cause."
  - "Is there snow, shade, or dust on the array right now?"
  - "Measured PV open-circuit voltage at the controller's input."
open_these:
  - power_log.csv   (the trend matters more than any single reading)
  - 02_CORPORA/datasheets/power/<controller>_manual.pdf   (its own code table)
  - 02_CORPORA/datasheets/power/<battery>_manual.pdf   (BMS temperature limits)
never_generate:
  - charge voltages, absorption or float setpoints, or temperature limits
  - fuse ratings
fence: retrieval_only   # charge parameters are a fenced domain
radio: ultra            # mesh replies from this skill: one packet, always
radio_payload: "CHARGE: read controller code first (power_monitor decodes). Below 0C lithium BMS REFUSES charge - by design. Then: snow/shade, battery fuse, wiggle connections."
human_verified: false
---

## Read the controller before you theorise

The controller already knows. `power_monitor.py` translates its charge-state
and error codes into words, so start there rather than with a hypothesis.

The one worth recognising on sight is **PV input voltage too high** — that is
the string-configuration error that destroys controllers, and if you are seeing
it, disconnect the array and go re-run the cold-Voc arithmetic in
`solar-commissioning` before anything else.

## The December answer, checked second

**A lithium BMS refuses charge below freezing.** It is not broken; it is
protecting the cells, because charging lithium below 0 °C plates lithium metal
onto the anode and permanently damages the pack.

This is the cruel one: it bites on exactly the cold, brilliantly clear mornings
when your array is producing best. The system looks healthy, the sun is
blazing, and the bank takes nothing.

- A **self-heating** pack warms itself first, then accepts charge — and it
  draws real power to do it, which is why that draw is a budgeted line item.
- A **cutoff-only** pack simply waits for the day to warm up.

Which one you have, and at what temperature it acts, is in the battery's
manual. Retrieve it; do not accept a remembered threshold.

## Then the boring physical causes, in order of frequency

1. **Snow, frost, or dust on the panels.** A dusting is enough. At winter tilt
   most snow sheds itself, but not always and not immediately.
2. **Shade.** A single shaded panel in a series string drags the whole string
   down, which is one of the arguments for parallel.
3. **A blown battery-side fuse.** The controller sees no battery, so it does
   nothing, and often reports very little.
4. **Connections.** Meter across each joint under load. Voltage that appears
   and disappears when you wiggle something is your answer.
5. **PV voltage below the wake threshold.** A controller needs PV voltage some
   margin above battery voltage before it starts. In dim light or heavy
   overcast the array may genuinely be below that line — that is physics, not
   a fault.

## Why the state of charge looks wrong

**A voltage reading on LiFePO4 is nearly useless.** The chemistry sits flat
around 13.2 V through most of its usable range, so the same reading covers 80
percent and 30 percent. Worse, voltage reads high while charging and sags under
load, so it only means anything at rest.

That is why the band logic holds its last verdict while current is flowing, and
reports UNKNOWN rather than guessing. If you want real state of charge, the
answer is a **shunt-based monitor** that counts amp-hours in and out. Until
then, treat the band as a rough traffic light and the trend in `power_log.csv`
as the real information.

## Expectation check

Before declaring a fault: what *should* today have produced? A tilted array in
midwinter with three hours of usable sun does not deliver its nameplate. Run
the arithmetic from BUILD_GUIDE, remembering that plane-of-array and horizontal
irradiance figures differ by roughly a factor of two in December — mixing them
up has convinced more than one person their perfectly healthy array was broken.
