# Radio bench test — first contact with a Meshtastic node

This is the procedure for the first time any Meshtastic radio meets this
project: a borrowed node today, the T-Deck Plus when it arrives, every group
member's radio after that. It takes about ten minutes and leaves a paper
trail. Written 2026-08-25, when the first radio in hand turned out to be a
borrowed Heltec WiFi LoRa 32 V4 — which is why the tooling is read-only.

## The two rules that outrank everything below

1. **Antenna before power. Always.** A powered Meshtastic node transmits on
   its own schedule — you don't get a vote. Transmitting into a missing
   antenna reflects the power back into the amplifier and can kill it. The
   V4 pushes 28 dBm; that's a dead board, not a warning. If the radio came
   assembled in a case, leave the case closed.
2. **Borrowed hardware: look, don't touch.** Back up the owner's config
   before anything else, change nothing without the owner present, and
   return it exactly as it arrived. The probe script enforces the first half
   of this by being unable to write settings at all.

## One-time setup (Windows box, no radio needed yet)

```
cd "D:\Wasteland AI\05_SCRIPTS"
python -m venv .venv           # if not already made
.venv\Scripts\activate
pip install -r requirements.txt
```

`meshtastic` and `pyserial` are already in requirements.txt — nothing new to
install beyond that.

## The bench test

**1. Plug in USB-C and find the port.** Use a *data* cable — half the USB
cables in any drawer are charge-only, and a charge-only cable produces the
same symptom as a dead board.

```
python meshtastic_probe.py --list-ports
```

No port at all? Device Manager showing an unknown device means Windows needs
the USB bridge driver (CP210x or CH340/CH9102 family, depending on board).

**2. Probe it.**

```
python meshtastic_probe.py
```

The probe is **read-only**: it changes no settings, transmits nothing over
the air, and never prints encryption keys — only whether each channel key is
the public default or a real custom one. It grades what it finds:

- `PASS / INFO` — fine, move on
- `WARN` — works, but doesn't match the group plan yet
- `FAIL` — the node is not mesh-ready (the classic: **region UNSET**, which
  is why a fresh-from-the-box node sits silent)

The checklist it grades against: firmware **2.5+** · region **US** · primary
channel on the public default key (normal — that's how you talk to
strangers) · a **secondary channel with a real random PSK** for group
traffic · **position precision LOW** on any channel that shares position.

**3. Back up the config — before anyone changes anything.**

```
python meshtastic_probe.py --backup
```

Writes the node's complete configuration to `04_CONFIG/meshtastic/` with a
timestamp. That file contains the real channel keys, which is exactly why
`04_CONFIG/` is on the deny side of the whitelist `.gitignore` and can never
reach GitHub. For a borrowed radio this backup is the "return it exactly as
it arrived" insurance.

## When the T-Deck Plus arrives (first power-up of an OWNED node)

Order matters:

1. Antenna on. *Then* battery/USB.
2. Probe it. Expect `FAIL region UNSET` on a fresh device — that's correct
   behavior, the radio refuses to transmit until told where it is.
3. Update/confirm firmware **2.5 or newer** (current stable is 2.7.x) via
   the official Meshtastic web flasher.
4. Set region **US**, device name, and Bluetooth PIN via the phone app.
5. Create the **private secondary channel** with a random PSK. Share it to
   other radios by QR code, in person. The public LongFast primary stays as
   shipped.
6. Set **position precision low** on every channel that shares position.
7. Probe again — it should now grade mesh-ready, no FAILs.
8. `--backup` the finished config into `04_CONFIG/meshtastic/`.

## The two-node test (closes issue #2)

Needs two radios — e.g. the T-Deck plus the borrowed V4. Both must share a
channel (QR from step 5).

1. Node A runs the Oracle: `python lora_oracle.py` on the bench box with the
   T-Deck on USB.
2. From node B (phone app on the V4), send a **direct message** — not a
   channel broadcast — to the Oracle node.
3. Expect the Oracle's reply within its rate/length limits (DM-only,
   ≤200 chars). A channel broadcast getting silence is the allowlist and
   DM-only rules working, not a bug.
4. Walk it: same room, then across the house, then down the block. Note
   where replies stop arriving; that's your first real range data point.

## The antenna check — the closest thing to a LoRa speedtest

There is no bandwidth to speed-test (LongFast moves text at roughly a
kilobit); what you test instead is **can this radio hear the mesh, and can
the mesh hear it back**. Do it in this order, because the order is the
safety:

**1. Passive listen first — transmits nothing, risks nothing.**

```
python meshtastic_probe.py --listen 120
```

Listening never keys the radio, so it is safe on a *suspect* antenna —
which matters, because transmitting into a broken feedline reflects the
power back into the amplifier (the 28 dBm paperweight scenario). Verdicts:

- **GOOD** — multiple distinct nodes heard. Antennas are reciprocal: an
  antenna that receives well transmits well. Cleared for step 3.
- **WEAK** — packets only from one or two very loud nodes, often at SNR
  near −20 dB (LoRa's decode floor). The classic damaged-feedline
  signature: a bare connector still catches the strongest neighbor.
- **SILENT** — nothing at all. Dead hour or dead antenna.

Cross-check against the node's own memory: `lastHeard` timestamps in the
node DB show *when reception stopped*, which dates the failure.

**2. If WEAK/SILENT: location before surgery.** Move the radio to a window
or outdoors and listen again — terrain and buildings can shadow a bench
that a car ride hears fine from. Five minutes, zero risk, and it separates
"bad spot" from "bad hardware."

**3. Still deaf? The pigtail, not the nut.** On boards with an internal
IPEX/U.FL pigtail to a bulkhead SMA (Heltec V4, T-Deck, most cased builds):
when the bulkhead nut spins loose, the pigtail twists with it. Enough turns
and the U.FL snap connector pops off the board or the thin coax shears at
a crimp. Tightening the nut afterward fixes the *mechanical* problem and
leaves the *RF* problem — a connector that "feels tight" says nothing about
the path inside. Open the case (owner present if it's borrowed), reseat the
U.FL until it clicks, inspect the pigtail for kinks, listen again. While
the path is suspect, keep the radio powered off when not actively testing —
a powered node beacons into whatever feedline it has, on its own schedule.

**4. Only after RX grades GOOD: one round-trip.** Pick a loud neighbor from
the listen output and traceroute it — this is the transmit half of the test
and reports per-hop SNR in both directions:

```
python -m meshtastic --port COM13 --traceroute '!nodeid'
```

The real instrument for antenna health is a NanoVNA (~$60, measures SWR
directly); until the group owns one, receive quality + one clean round-trip
is the honest field test. Real RF *range* still needs the walk test.
