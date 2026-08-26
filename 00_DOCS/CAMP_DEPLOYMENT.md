# Camp deployment — the mesh, the library, and the dish

Written 2026-08-25 for a trip ~2 weeks out. This is the field configuration
of the whole system: what gets packed, how it wires together, and what
"working" means. The bench procedures live in RADIO_BENCH_TEST.md; this doc
is the deployment they build toward.

## What the camp system is

Two networks with different physics, joined at one table:

```
  [Starlink Mini] ~50-100W, coverage: the campsite, WHEN powered
        |  wifi
  [NUC / laptop] kiwix-serve (Wikipedia+WikEM+iFixit) + Ollama + lora_oracle
        |  usb                                + camp WiFi hotspot "LIBRARY"
  [LIBR radio]  the oracle's own node (nRF52840, stationary at the table)
        )))  LoRa 915MHz — miles, text-only
  [tree relays] 1-2 nodes hoisted high, battery/solar — the range multiplier
        )))
  [pocket nodes] one per hiker  <-bluetooth->  [everyone's existing phone]
```

- **Within WiFi range of the table**: full library in a phone browser —
  Wikipedia with images, WikEM, iFixit. No internet involved.
- **Beyond WiFi, within mesh**: text commands to the oracle by DM
  (?med ?find ?ask ?net ?power) and person-to-person messages. Miles of
  coverage if the relays hang high.
- **When the dish is up**: ?ask answers come from a frontier model
  (labeled `NET:`); the moment it sleeps, the local model takes over
  (labeled `AI:`). Same commands, same fence, smaller brain. `?net` tells
  you which brain is on duty.
- **The fence does not care which brain answers.** Fenced domains
  (medical, water, plant edibility, generator safety, ...) are
  retrieval-only against real documents, whether the backend is a 3B model
  on the NUC or a frontier model over Starlink. Enforced in code
  (safety_router routes before any model call in cmd_ask).

## The plant-ID reality check

"What species is this flower?" works over text badly — LoRa moves no
photos. What DOES work: walk back within WiFi range, photograph it, browse
Wikipedia's flora pages on the local kiwix. The fence has a new provisional
domain for the follow-up question: anything shaped like "can I eat it" is
retrieval-only, and **mushrooms fence outright** — a death cap resembles an
edible straw mushroom, a false morel resembles breakfast, and the fatal
dose of amanitin fits on a cracker. The library answer is a field guide
with photographs, not a model's confidence.

## Hardware

**Owned / borrowed already**: Starlink Mini (Joe), Heltec V4 (Ryan's, one
antenna question pending), T-Deck Plus (Adam, in transit), NUC11 (the camp
brain), Windows laptop optional.

**The order (Rokland or equivalent)**:

| Item | Qty | ~$ | Job |
|---|---|---|---|
| Heltec Mesh Node T114 (no display, no GPS) | 1 | 37 | LIBR — the oracle's radio |
| T114 or RAK WisBlock Mini kit | 1–2 | 32–37 ea | tree relays (battery+solar connectors onboard) |
| LowMesh Pocket-M or 3rd T114 + printed case | 1 | 45 / 37 | Joe's pocket node |
| 915 MHz whip antennas (spares) + SMA extension | — | 15–25 | tree relay reach + the apartment window fix |
| LiPo packs w/ 1.25mm plugs, or 18650 holders | 2–3 | 15 | relay + pocket power |

**NOT buying, deliberately**: anything cellular. A 4G modem where there are
no towers is ballast. Phones talk to pocket nodes over Bluetooth — the
Meshtastic app is the UI, and it needs zero cell service.

**⚠ Battery polarity warning**: 1.25mm JST-style battery plugs have NO
standard polarity — vendors ship both orientations, and a reversed pack
kills a board instantly. Check the + marking on the PCB against the red
wire BEFORE plugging any new battery into any Heltec/RAK board. Every time.

## Power budget (camp, per day)

| Load | Draw | Hours | Wh/day |
|---|---|---|---|
| Starlink Mini | ~30 W | 4 (query windows + sync) | ~120 |
| NUC (library + oracle + model) | ~15–25 W | 12 | ~240 |
| LIBR radio (nRF) | ~0.03 W | 24 | ~1 |
| Tree relays | ~0.03 W each | 24 | ~1 each |
| Pocket nodes | — | — | own batteries, days each |

The mesh is effectively free. The NUC is the real load and the dish is
second — which is why the *architecture* assumes both can be off: the mesh
and pocket nodes keep working when everything at the table is asleep.

**Feeding the NUC from a battery — no inverter needed.** The NUC11TN
board accepts **12–24 V DC (±5%)** per its Technical Product
Specification (corroborated 2026-08-25 by two secondary sources quoting
the TPS — the wall brick is 19 V ⎓ 6.32 A, just a mid-range point;
**verify against the archived PDF before building the cable**, which is
still a browser job). So: 12.8 V LiFePO4 → **inline 10 A fuse** → barrel
plug (5.5 mm, **center positive** — meter it before first plug-in) →
NUC. Zero conversion loss vs ~25–30% wasted through an inverter. Notes:
at 12 V the NUC can draw up to ~10 A at full tilt, so 16 AWG wire, short
run; the ±5% floor is 11.4 V, which a LiFePO4 only approaches in its
last few percent — set the pack's low-voltage cutoff ≥11.8 V and the
board never sees a brownout.

## Channels and roles

- **The allowlist is a go/no-go gate: LIBR does not join a live mesh
  until `AUTHORIZED_SENDERS` is a real, non-empty set of node numbers.**
  Open mode (None or "*") is a bench convenience for Level-1 testing
  only. Every world-reaching command (?sms, ?email, uplink status)
  already refuses in open mode by code; this line makes it a deployment
  rule too.
- Primary: **LongFast, default key** — the public mesh, unchanged.
- Secondary: **the group channel, custom random PSK**, created at home,
  shared by QR **in person, before the trip**. Position precision LOW.
- Roles: everything CLIENT in town. In true backcountry (no other mesh for
  miles), the tree relays MAY run ROUTER for the weekend — set it at camp,
  **revert to CLIENT before coming home**, because a ground-level ROUTER in
  the city degrades the 131-node neighborhood mesh.
- **MQTT stays OFF on every node at camp. No exceptions in the field.**
  Misconfigured MQTT republishes mesh traffic — including private-channel
  positions — to public internet brokers. It is the single most common way
  campers accidentally livestream their campsite to the world.

### The deliberate exception — bridging two distant groups (the Utah door)

MQTT is a **software toggle** in every Meshtastic node (Radio Config →
MQTT) — no extra hardware, ever. It is how two meshes in different states
exchange messages over the internet. Done deliberately, it is safe; the
recipe is everything (hardened per external review, 2026-08-25):

1. Create a **dedicated bridge channel** (e.g. `XMAS`) with its own random
   PSK, shared with the far group out-of-band. NOT the primary, NOT the
   group channel.
2. **Use a broker you control** (a Mosquitto container on the home node's
   network is fine). If you cannot run your own broker, do not open the
   door — the public Meshtastic broker sees your node IDs, timing, and
   channel name even though message bodies stay PSK-encrypted.
3. On **one** node per side (an ESP32 home node on WiFi, never a pocket
   node): enable MQTT, and set **uplink + downlink per-channel, on the
   bridge channel ONLY**. Then — before saving — read the channel list
   back and confirm out loud: **"LongFast uplink OFF, downlink OFF; group
   channel OFF, OFF."** The classic foot-gun is a global enable plus a
   wrong assumption about which channels it grabbed.
4. **Nothing but text on the bridge channel**: position precision 0 AND
   telemetry/node-info uplink off. Precision 0 alone is necessary, not
   sufficient — device telemetry and node-info packets leak too.
5. **Time-box it with a named owner.** The door stays open for the
   occasion — an evening, not a week — and ONE named person is
   responsible for closing it.
6. **Verify the cleanup.** After disable + delete, run
   `meshtastic_probe.py` against the bridge node: it now grades an
   MQTT-enabled node as a hard **FAIL**, so a clean probe IS the proof
   the door is shut. "I turned it off" is a claim; a probe is a receipt.

## The SOS reality

A man-down message beats no message by miles, and the mesh delivers it:
canned message + position share from the phone app reaches every node,
and anyone at the table can relay by Starlink to 911/GEOS. But be honest
about what this is NOT: a PLB or satellite messenger with SAR dispatch
(inReach/ZOLEO class). The mesh SOS depends on someone being in camp with
the dish. State that plainly to the group before the first hike.

## T-minus checklist

**T-14 (now)**
- [x] Wikipedia (115 GB) + iFixit (3.3 GB) ZIM downloads started —
      resumable: `curl.exe -L -C - -o <file>.part <same URL>` again
- [x] Oracle gateway code: fence-first ?ask, NET/AI labeling, ?net
- [ ] Place the Rokland order (T114s, batteries, antennas)
- [~] **DC input range ANSWERED** (12–24 V ±5%, battery-direct is GO — see
      power section) via two secondary sources quoting the TPS. The PDF
      itself is STILL a browser job for the archive: intel.com 403s
      automation; save NUC11TN_TechProdSpec.pdf into
      02_CORPORA/datasheets/compute/ + a CORPUS_INDEX row, and confirm the
      12–24 V line before building the battery cable. Generac 9-26kW while
      you're at it.
- [ ] Ask Joe: Starlink Mini power setup (battery? hours/day he'll run it)

**T-7**
- [ ] NUC build: kiwix-serve with all three ZIMs · Ollama + a small model
      (8B-class Q4) · oracle venv · `NET_BACKEND="anthropic"` + API key in
      env (key never enters the repo) · `AUTHORIZED_SENDERS` = the group's
      node numbers once radios exist
- [ ] Create the group channel, QR everyone's radios at one table
- [ ] Full-stack home test: phone → mesh DM → oracle → NET: answer with
      home internet standing in for Starlink; then pull the plug and watch
      it degrade to AI: gracefully
- [ ] Probe + backup EVERY radio (meshtastic_probe.py, bench doc procedure)

**T-2**
- [ ] Charge everything; label every battery pack with its polarity check
- [ ] Export all node configs to 04_CONFIG/meshtastic/
- [ ] Walk test in the neighborhood: pocket node range vs the V4 baseline
- [ ] Pack: nodes, batteries, USB bricks, cables (DATA cables, tested),
      SMA spares, zip ties + paracord for the tree relays, the NUC + its
      power solution, printed copy of this doc

**Day 0, at camp, in order**
1. Antennas on everything BEFORE power. Always.
2. Tree relays up first (high beats far — 20 ft of rope is free range),
   confirm they mesh.
3. Table: NUC up, kiwix + oracle up, LIBR on USB, `?net` from a phone.
4. Starlink up when Joe says so → `?net` flips to frontier. Sync window.
5. Walk test outward until DMs stop landing; that radius is today's map.
