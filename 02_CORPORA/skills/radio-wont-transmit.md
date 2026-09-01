---
name: radio-wont-transmit
description: >
  Fires when a LoRa or Meshtastic node is silent, unreachable, not appearing on
  the mesh, not sending or receiving, or the Oracle never answers a direct
  message. Covers antenna, region and preset, channel and key mismatch, USB,
  and the point at which it becomes a hardware fault.
fires_on: [wont transmit, will not transmit, no signal, not sending, cant see
           my node, cannot see my node, mesh is down, oracle not replying,
           lora, meshtastic, sx1262, heltec, t-deck, no nodes, not connecting]
ask_first:
  - "Was the antenna attached every single time this board had power? A LoRa
     board keyed up without an antenna can damage its own output stage."
  - "Is the region set? A node ships with no region and will not transmit at
     all until you set one."
  - "What does the Meshtastic CLI report for node info, and what firmware
     version is on it?"
  - "Are both nodes on the same channel with the same key AND the same modem
     preset?"
open_these:
  - 02_CORPORA/datasheets/radio/<board>_schematic.pdf   (for the PA supply rail)
  - 02_CORPORA/datasheets/radio/sx1262_datasheet.pdf
  - 04_CONFIG/meshtastic/   (your own exported channel configuration)
  - 00_DOCS/SECURITY.md   (if it transmits but the Oracle ignores you)
never_generate: [pin numbers, register values, frequencies, duty-cycle limits]
fence: none   # but band and duty-cycle rules are retrieval-only
radio: ultra            # mesh replies from this skill: one packet, always
radio_payload: "RADIO SILENT: region set? (unset=mute, looks dead). Same channel+key+PRESET both ends? Data USB cable? Oracle answers DM only. NEVER power board w/o antenna."
human_verified: false
---

## Configuration before hardware — always

Ninety percent of "the radio is broken" is configuration, and the checks cost
nothing:

1. **Region unset.** A fresh node has no region and therefore no legal
   frequency plan, so it stays silent. This is the single most common cause and
   it looks exactly like dead hardware.
2. **Modem preset mismatch.** Two nodes on the same channel name and key but
   different presets are on different physical configurations. They cannot hear
   each other and neither reports an error.
3. **Channel key mismatch.** A mistyped pre-shared key produces silence, not a
   warning.
4. **Firmware age.** Encrypted direct messages need reasonably current
   firmware. If you are testing the Oracle over DM and the far node is old
   firmware, the DM path may not behave as expected.
5. **Charge-only USB cable.** A cable with no data lines looks identical to a
   good one and charges the board perfectly. If the CLI cannot see the node at
   all, swap the cable before suspecting anything else.

## If it transmits but the Oracle never answers

That is probably not a radio fault at all:

- Was it a **direct message**? The Oracle deliberately ignores channel traffic.
- Is your node number in `AUTHORIZED_SENDERS`? Denied senders get silence on
  purpose — no reply, no airtime, and a line in the local log. Check the log on
  the node.
- Are you inside the per-sender rate limit? A second question too soon is
  dropped silently.
- Is the Oracle process actually running on the node?

All of that is in SECURITY.md and the script's own README. Silence is a
designed behaviour in more places than people expect.

## Only now, hardware

- **Antenna.** Attached, correct band, correct connector. Note that SMA and
  RP-SMA look nearly identical and do not work together — WiFi antennas are the
  usual mistake. Some boards need a tiny u.FL pigtail and are easy to knock
  loose.
- **Coax and connectors.** A cheap thin cable and a long run can eat a large
  fraction of your output. Water in a connector does the same and is invisible.
- **Damaged output stage.** If this board was ever powered without an antenna,
  it may transmit weakly or not at all. This is the failure that cannot be
  fixed in software.
- **PA supply rail.** This is the manifest's own worked example of why the
  artifact layer exists: the answer is a specific pin on a specific board, and
  it lives in the schematic. Open the file and read the pin. Do not accept a
  pin number from a language model — that is precisely the number it will
  invent.

## Two rules that are not troubleshooting

**Never power a LoRa board without an antenna attached.** Not for a second, not
"just to check the screen."

Band, power, and duty-cycle limits are legal questions with retrievable
answers. Get them from the regulations, not from a model.
