---
name: node-dark-triage
description: >
  Fires when the knowledge node is dead or unreachable — no lights, no WiFi
  access point, no SSH, will not boot, boot loop, or the Pi is running but
  nothing answers. Working backwards from "nothing is happening."
fires_on: [node is down, node is dark, wont boot, will not boot, no lights,
           cant ssh, no wifi, boot loop, kiwix is down, nothing responds,
           unreachable, undervolt, red light, wont turn on]
ask_first:
  - "Is ANY light on anywhere — the Pi, the controller, the router? That one
     answer splits this into a power problem or a computer problem."
  - "Battery voltage measured AT THE TERMINALS with a meter. Not an app, not a
     panel gauge."
  - "When did it last work, and what changed in between? New load, weather,
     someone touching wiring, an update."
open_these:
  - power_log.csv and latest.json   (the last thing the monitor saw before silence)
  - 00_DOCS/SECURITY.md   (only if it answers but refuses logins)
never_generate: [fuse ratings, wire gauges]
fence: none
radio: ultra            # mesh replies from this skill: one packet, always
radio_payload: "NODE DARK: any light anywhere? NO=power: check band in power_log (BLACK=designed shutdown), volts AT battery terminals, fuses, wiggle joints. YES=computer: PSU quality, SD card, service status."
human_verified: false
---

## Split it with one question: power, or computer?

**No lights anywhere → power.** See below.
**Lights but no service → computer.** See below.

Do not start typing diagnostic commands at a machine that has no volts.

## Power

1. **It may have shut down on purpose.** If the bank reached the BLACK band,
   that is the design working, not a fault. Check the last rows of
   power_log.csv for the band before it went quiet.
2. **Measure at the battery terminals.** LiFePO4 sits nearly flat around
   13.2 V for most of its discharge and then falls off a cliff, so a voltage
   that "looks fine" can be nearly empty. And a BMS that has disconnected reads
   near zero at its output while the cells themselves are healthy.
3. **Fuses and breakers, in order**: battery-side fuse, then distribution, then
   the load's own fuse. A fuse that blew had a reason. Find the reason before
   fitting a new one, and never fit a larger one to make the problem go away.
4. **Connections.** Off-grid DC failures are overwhelmingly corroded or loose
   terminals rather than dead components. Wiggle-test with the meter attached
   and watch for the voltage flickering.
5. Snow on the array, or a controller sitting in an error state — that is
   charging-triage, not this skill.

## Computer

1. **Power supply first.** A Pi 5 wants a genuine 27 W USB-C supply. A marginal
   supply does not announce itself as a power problem — it shows up as random
   reboots, refusal to boot, or USB devices vanishing. If the system is
   reachable at all, check the kernel log for undervoltage warnings.
2. **Boot loop?** The hardware watchdog may be doing precisely its job:
   rebooting a machine that keeps hanging. That means the hang is the real
   fault, and it is usually storage.
3. **Storage.** SD cards fail more than anything else on a Pi, and they fail by
   going read-only or corrupting the filesystem rather than dying outright.
   This is exactly why the build puts the OS on NVMe. If it is running from SD,
   suspect the card early.
4. **Running but not serving?** Then it is a service, not the box. Check the
   status of each unit and read the last fifty journal lines for it. A service
   that vanished after a reboot is usually one that was started but never
   enabled, or one whose working directory no longer exists.
5. **Answers but refuses logins** — that is SECURITY.md, not a fault.

## Before you walk away

Write what it was and what fixed it into 00_DOCS/BUILD_LOG.md with the date.
The second occurrence will be at three in the morning in February, and that log
is the only thing that will remember.
