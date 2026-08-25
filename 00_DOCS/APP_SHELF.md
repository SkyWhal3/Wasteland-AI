# APP SHELF — prepackaged software worth carrying

```
STATUS:  planning doc — the selection filter and the current shortlist.
         Nothing here is bundled yet; entries graduate to 03_SOFTWARE/
         one at a time, with source bundles and checksums.
SCOPE:   extends MANIFEST §6 (Layer 4, toolchain) from "tools that keep
         the stack alive" to "applications that do survival work."
         The manifest itself is not edited by this doc — §6's rules
         (archive the tool, frozen snapshots, source not URLs) all apply.
```

**Why a shelf at all:** so the AI doesn't re-derive an irrigation timer or
sun-angle table from scratch every time, and so the human isn't writing
code at 2 a.m. for a problem the open-source world solved in 2015. The AI's
job is to *operate and adapt* known-good tools, not to reinvent them.

---

## The five-point filter (all five, or no slot)

1. **Runs on Pi/Pico-class hardware, fully offline** — no cloud tether, no
   license server, no phone-home.
2. **Its data outlives it** — CSV, SQLite, plain files a human can read
   after the app is dead. An app that holds data hostage is a liability.
3. **Freezable** — small enough to archive as a known-good snapshot, or
   genuinely maintained. A 500-line Python tool ages fine; a 500k-line
   Electron app is a future corpse.
4. **Recurring value** — solves a computation/logging problem that comes
   back monthly, not once.
5. **Source archived** — `git bundle create --all` + a built binary +
   sha256 in the INDEX. The §6 pattern, no exceptions.

---

## CORE SHELF — earns a place on every node

| Tool | What it buys | Size-ish | Notes |
|---|---|---|---|
| **Syncthing** | Node↔node file sync over LAN/WiFi — the document-transfer layer for backups and, later, federation payloads (see FUTURE_FEDERATION.md: announcements ride the mesh, payloads ride WiFi/sneakernet) | ~25 MB, single binary | The sleeper pick of the whole shelf |
| **chrony + gpsd** (+ $10 GPS puck) | Correct time forever, no NTP required. Logs, schedulers, and crypto all quietly assume time; GPS makes the node stratum-1 | tiny, in apt mirror | Nobody misses time sync until it's gone |
| **calibre** | Librarian for the ~65 GB Gutenberg pile + your PDFs; serves ebooks over the LAN | ~150 MB | Tier 1 box (or `calibre-server` on the Pi) |
| **Anki** + medical/first-responder/ham decks | Trains the HUMAN — spaced repetition is the highest value-per-watt "medical software" that exists | ~150 MB + decks | Decks are corpus: checksum them like ZIMs |
| **Solar arithmetic** (a pinned solar-position library + seasonal tilt tables) | Sun angles for the 4×/year tilt change, offline yield estimates, inputs for the §1 surplus scheduler | ~1 MB | The *software* half of "solar tracking" — see Rejected for the hardware half |
| **kiwix-tools, Meshtastic firmware, esptool, llama.cpp, whisper.cpp, Piper, CHIRP, SDR suite** | — | — | Already specified in MANIFEST §6/§10; listed here only so nobody duplicates them |

## TASK SHELF — optional, per mission

| Tool | When it earns the bytes |
|---|---|
| **Irrigation controller** — a ~100-line MicroPython valve scheduler (see `05_SCRIPTS/agent_examples/` patterns), or OpenSprinkler source-bundled for the grown-up version | You grow food. The high-value part is actually corpus: FAO-56 evapotranspiration + crop-water tables → `02_CORPORA/reference_tables/` |
| **QGIS** + Geofabrik extracts | Land/water/route planning on the Tier 1 box. Heavy (~1 GB) but nothing else does terrain analysis offline |
| **CUPS + a cheap mono laser** | Paper is the ultimate offline format. Print the procedure BEFORE the outage, laminate the one-pagers |
| **OpenSCAD / KiCad** (KiCad already §6) | You have a printer/CNC or design boards. Snapshot the exact version; both projects move fast |

## REJECTED — written down so the argument doesn't repeat

| Rejected | Why |
|---|---|
| **Mechanical solar trackers** (and their control software) | Motors + actuators + grease that seizes in a Colorado February, for ~25% gain on a 400 W array. The manifest already chose fixed winter tilt (§2.2). Software does the tracking math; the panels stay bolted down |
| **Home Assistant / Node-RED as the control plane** | A multi-GB always-on platform to flip relays that the §4 supervisor MCU flips with 200 lines of C and a watchdog. It would *become* Tier 0's biggest failure surface. Automation lives in small auditable scripts + the MCU |
| **Medical dose calculators** | §9 territory. Carve-out rule: a deterministic tool that DISPLAYS the published table + citation (no interpolation, no unit conversion, human-verified like a seed) is admissible. Anything that computes beyond the table's cells is not. When in doubt: show the table |
| **Anything Electron-shaped heavier than the data it manages** | Filter points 2 and 3 |

---

## Packaging pattern (per adopted tool)

```
03_SOFTWARE/apps/<name>/
├── <name>.bundle          <- git bundle create --all (full history)
├── <binary/appimage/deb>  <- built artifact for Pi (arm64) + x86_64
├── wheels/                <- pip deps if Python (--only-binary=:all:)
├── VERSION.txt            <- exact version/commit this snapshot froze
└── sha256.txt
```
One row in the 03_SOFTWARE index per app. New version → new folder,
old one untouched — same ladder-backwards-through-time rule as runtimes.

## Updates (the 30-day-staleness goal, done safely)

- **A/B, never in place:** fetch the new snapshot NEXT TO the old one,
  verify, self-test, then move a symlink. Content (ZIMs, decks, docs) may
  auto-apply; code and firmware stage and wait for a human yes.
- **Signed:** a release manifest of sha256s, signed (minisign/signed tag)
  by a key whose PUBLIC half shipped with the install. The box trusts the
  key it was born with, not the network.
- **Offline-quiet:** no internet = silent no-op. Offline is this box's
  natural habitat, not an error state.
- **Mesh announces, sneakernet delivers:** "v1.3 available, sha:…" fits in
  one LoRa DM; the payload travels by USB stick or Syncthing when nodes
  share WiFi. Payloads never ride LoRa — airtime is a commons. This is the
  same hash-cited machinery as FUTURE_FEDERATION.md's `SRC` verb.

## Graduation checklist (planning → shelf)

- [ ] Passes all five filter points, argued in one paragraph
- [ ] Bundled per the packaging pattern, hashes in the INDEX
- [ ] Tested on the actual Pi (not just x86)
- [ ] One seed_qa entry: "how do I use X offline" with the launch command
- [ ] BUILD_LOG entry
