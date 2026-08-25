# OFFGRID AI + KNOWLEDGE BASE — BUILD MANIFEST v3

**Design point:** 400–440 W solar array, Colorado Springs (~6,000 ft), worst-month
(December) budget, tilted array.
**Real energy budget:** ~1.0 kWh/day usable on a clear December day. Survival baseline
target: **≤350 Wh/day**.

**v3 changes (after two external adversarial reviews, adjudicated):**
- Tier 1 idle load eliminated — recovers ~315 Wh/day, the worst line in v2
- Power states, battery bands, and a surplus-compute scheduler added
- Battery self-heating draw budgeted (it was missing)
- Supervisor MCU + black-box logger + status display added, staged
- Layer 0 (physical inventory + substitution data) added to the knowledge model
- Retrieval-only domains expanded from three to six
- Runtime snapshot policy: known-good combinations, never updated in place
- 12 V vs 24 V made an explicit fork with a decision rule
- Winter-measurement and air-gapped recovery steps added to build order
- December solar figure DEFENDED at 4.0 PSH — see the note in §1, this argument is settled

---

## 0. THE ORGANIZING PRINCIPLE — FIVE LAYERS

Most offline-knowledge projects collect layers 1 and 2, skip 0, 3, and 4, and end up
with a library you can read but not act on.

| Layer | What it is | Example | Source |
|---|---|---|---|
| **0. Identity** | What you physically possess | "This exact SX1262 board, this GPIO map, this regulator" | Your inventory, built by you |
| **1. Conceptual** | What a thing is | "A MOSFET is a voltage-controlled switch" | Wikipedia, textbooks |
| **2. Procedural** | How to do a thing | "How to solder SMD without a hot plate" | Stack Exchange, iFixit |
| **3. Artifact** | The numbers for *your* thing | Pinout of the SX1262 on your board | Datasheets, schematics, FSMs, tables |
| **4. Toolchain** | The ability to act | esptool, KiCad, a compiler | Archived binaries + dependency caches |

Layers 1–2 are commodity. Layers 0 and 3–4 are specific to your hardware and require
deliberate collection. **Layer 0 is the bridge**: it is how the system goes from "I have
some radio board" to "this exact board uses this firmware and this datasheet, both of
which are at these paths."

**This defines the LLM's actual job.** It is not a knowledge store. It is a *translator
between layers*: "my node stopped transmitting" → "check the PA supply rail, pin 14 per
the datasheet in RADIO/SX1262.pdf." That translation only works if layers 0 and 3 exist.
Without them the model does not say "I don't know the pinout" — it invents one.
Confidently.

---

## 1. THE POWER MATH (read this first)

```
400 W panels x 4.0 peak sun hours (Dec, TILTED) x 0.75 derate = 1,200 Wh/day
Minus controller + battery round-trip losses (~15%)           = ~1,020 Wh/day usable
```

### The 4.0 figure is correct. Here is why, so this stops being relitigated.

December horizontal irradiance (GHI) in Colorado Springs is ~2.4–2.5 kWh/m²/day. If a
reviewer quotes you that number, they are describing a panel lying flat on the ground.
**Yours are tilted ~50–55°**, pointed nearly square at a winter sun that sits ~27° above
the horizon at noon. Plane-of-array irradiance on that tilt, at this altitude, in this
dry climate, runs 4.5–5.0 kWh/m²/day in December. The 4.0 design point is therefore
*conservative*, with the 0.75 derate on top of it.

Rule: **any solar figure you are given, ask whether it is horizontal (GHI) or
plane-of-array (POA).** They differ by ~2x in winter and the difference is the whole
design.

Verify for your exact site: run NREL PVWatts with your real tilt, azimuth, and horizon.
Then confirm empirically — see build order step 7.

### Load budget, v3 (Tier 1 idle ELIMINATED)

| Load | Draw | Hours/day | Wh/day |
|---|---|---|---|
| Pi 5 + NVMe + LoRa + VE.Direct logging | 10 W | 24 | 240 |
| Networking / misc | 4 W | 24 | 96 |
| Supervisor MCU + status display | 0.5 W | 24 | 12 |
| **Survival baseline** | | | **~350** |
| Battery self-heating (Dec cold mornings) | 50–130 W | 0–1.5 | **0–100** |
| Tier 1 session (when taken) | 130 W | 2 | **260** |
| **Typical December working day** | | | **~610–710** |

Against ~1,020 Wh available on a clear day, this leaves real margin — margin that v2
did not have, because v2 burned 315 Wh/day keeping a mini PC idle for no capability.

**The battery heater was missing from v2 and it matters.** A self-heating LiFePO4 draws
50–130 W warming itself before the BMS accepts a single watt of charge, on exactly the
cold clear mornings you are counting on. Renogy-style packs power the heater from the
incoming charge source, so it naturally runs only when the sun (or charger) is present —
but it is still consumption, and it is now budgeted.

### Autonomy (multi-day snow, zero production)

```
2.56 kWh bank x ~90% usable = ~2.3 kWh
2.3 kWh / 350 Wh survival baseline = ~6.5 days dark-sky survival, Tier 0 only
```

Colorado gets multi-day snow-cover stretches. Six days of Tier-0 autonomy is the number
that says the knowledge node stays up through them. Tier 1 sessions during those
stretches come out of that reserve — see the bands below.

### Power states

The system has three states, and the question changes from *"can I afford to keep the
AI running"* to **"can I afford to ask this question."**

- **STATE 0 — Life support.** Pi + radio + telemetry + supervisor. Always on. ~10–12 W.
- **STATE 1 — Knowledge workstation.** Tier 1 box. **Fully off by default.** Powered on
  demand (physical switch, relay, or WoL), does its session, powers off.
- **STATE 2 — Heavy computation.** The Monument. Mechanically isolated. Gets power only
  when surplus exists and never at the survival system's expense.

### Battery bands (software-enforced, not just a gauge you glance at)

| Band | SOC | Policy |
|---|---|---|
| **GREEN** | >70% | Everything permitted, including Tier 1 sessions |
| **YELLOW** | 40–70% | Tier 1 for essential queries only; no background jobs |
| **RED** | 20–40% | Tier 0 + comms only |
| **BLACK** | <20% | Pi + Oracle at minimum duty; everything else hard-off |

Enforced by `power_monitor.py` reading the VE.Direct feed, backstopped by the
supervisor MCU (§4).

### Surplus scheduler — compute as a dump load

Excess midday solar is not a problem, it is an opportunity. When the battery is full
and the sun is strong, the surplus is free:

```
PV surplus > 150 W            -> run checksum verification, backups
PV surplus > 300 W            -> run indexing / embedding jobs
PV surplus > 400 W, SOC > 70% -> Tier 1 session without touching reserve
SOC < 50%                     -> kill background jobs
SOC < 30%                     -> kill Tier 1
SOC < 20%                     -> BLACK: survival mode
```

The archive's maintenance work (§15) becomes something the system does with sunlight it
would otherwise waste.

### Standing efficiency rules

- Run the mini PC off a DC-DC buck from the battery, never through an inverter.
  Battery → 120 VAC → 19 VDC costs 15–20%; battery → DC-DC → 19 VDC costs ~5%. The gap
  is ~100–150 Wh/day — the entire Pi allocation.
- **A 1000 W+ inverter idles at 6–12 W. Switched off means a physical switch or relay,
  not a habit.** Left on 24/7 it eats up to 29% of the budget doing nothing.

---

## 2. POWER HARDWARE

### 2.1 The 12 V vs 24 V fork — decide at battery purchase

24 V is the correct *greenfield* architecture: half the current everywhere, thinner
wire, smaller fuses, and the mini PC's 19–24 V input is a clean buck away. But this
build is not greenfield — the inverter, AC charger, battery box, and the entire vehicle
side are 12 V, and the alternator DC-DC becomes a different part number (12/24 vs
12/12) under a 24 V bank.

**Decision rule:** stay **12 V** if the array stays ≤ ~400–440 W and the existing 12 V
gear matters to you. Go **24 V** if you expect the array past ~600 W, a second large
load, or long wire runs. The commitment point is the **battery purchase** — the Victron
controller auto-detects 12/24 V, so it is not the fork. If you go 24 V: the DC-DC
alternator charger must be a 12→24 model, the AC charger must be 24 V-capable, and the
12 V loads (radios, automotive accessories) hang off a 24→12 converter.

Sub-rule from the reviews, worth keeping: **oversize the array before oversizing the
battery.** Surplus PV is a scheduler input (§1); surplus battery is just money sitting
at a state of charge it shouldn't be stored at.

### 2.2 Array

Two panel families evaluated. **The wiring rule is panel-specific — recalculate every
time, from the actual datasheet.**

| | Renogy 200W N-type bifacial | Lumera 220W bifacial (24V cfg) | Lumera 220W bifacial (12V cfg) |
|---|---|---|---|
| Vmp | 25 V | 37.56 V | 18.25 V |
| Imp | 8 A | 6.12 A | 12.04 A |
| **Voc** | **29.6 V** | **43.72 V** | **22.0 V** |
| Isc | 8.7 A | 6.71 A | 13 A |
| Series fuse | 25 A | 15 A | 15 A |

**Cold-weather Voc is the number that kills controllers.** Worst case is a clear cold
dawn — panel at ambient, sun just hit it, no load.

```
Voc_cold = Voc_STC x [1 + BetaVoc x (T_min - 25)]

Use the ACTUAL BetaVoc from the datasheet. If unknown, -0.3%/degC is a
conservative placeholder:
  at -30 C -> multiplier 1.165
  at -40 C -> multiplier 1.195
```

**Design margin rule (adopted from review): never design string Voc within 20% of the
controller's absolute maximum.** For a 100 V controller, cold Voc stays under 80 V.
This is a margin rule, not an electrical requirement — for an off-grid system where
replacement electronics may be unobtainable, waste a little copper and sleep at night.

Worked results against a 100 V controller at −30 °C:

- Renogy 200W ×2 series: 59.2 V STC → **~69 V**. Passes the 80% rule. Series correct.
- Lumera 24V cfg ×2 series: 87.4 V STC → **~102 V**. **OVER THE ABSOLUTE LIMIT. Never.**
- Lumera 24V cfg ×2 parallel: 43.72 V STC → **~51 V**. Safe, huge margin. **Parallel.**

Parallel Lumeras keep what series was for anyway: 6.12 A per panel means thin wire, and
Vmp 37.56 V is high enough that the MPPT wakes early in dim light — the December
shoulder-hour harvest.

**Never mix panel models or configs on one MPPT.** One array, one operating voltage; a
mismatched panel gets dragged off its maximum power point and you lose more than you
gained. Mismatched panels → second small controller.

**Winter operations:** fixed winter tilt 50–62° both aims at the low sun and sheds
snow. Add a snow-clearing tool (soft roof rake) to the kit and clearing to the routine.
Snow albedo is also when bifacial rear-side gain actually pays — the design month and
the bifacial month are the same month.

### 2.3 Charge controller

**Victron BlueSolar MPPT 100/30** (~$118) + **VE.Direct-to-USB cable**.

Naming is **100 V max PV input / 30 A max battery-side charge current**. Battery bank
voltage, not panel config, sets capacity:

| Battery bank | 100/30 max array |
|---|---|
| 12 V | 440 W |
| 24 V | 880 W |

Two failure modes, different consequences: exceeding **wattage** → harmless clipping
(Victron explicitly permits array oversizing). Exceeding **voltage** → dead controller,
not warranty-covered.

**BlueSolar over SmartSolar, deliberately.** The VE.Direct port is the part that
matters — it is the Pi's live feed of PV watts, battery voltage, and yield for
`power_monitor.py` and the band logic. Bluetooth is convenience. The VE.Direct-USB
cable doubles as the configuration tool (laptop + VictronConnect).

### 2.4 Battery

| | AGM starting/marine (~100 Ah) | LiFePO4 200 Ah (12 V) |
|---|---|---|
| Usable at safe DoD | ~50 Ah / 600 Wh | ~180 Ah / 2,300 Wh |
| Covers survival baseline? | ~1.7 days | ~6.5 days |
| Cycle life at that depth | 400–600 | 3,000–6,000 |

**Know which AGM you have.** If the label only lists CCA it is a starting battery;
deep cycling kills it in months. Bench-test tier only.

**Low-temperature cutoff ≠ self-heating. This decides your December.**
- **Cutoff** — BMS refuses charge below freezing. Protects the pack. Does not charge it.
- **Self-heating** — pack warms itself, then charges. Draws 50–130 W to do it (§1).

Cutoff-only means the bank declines charge on exactly the cold sunny mornings with the
least margin. **Buy self-heating.** Confirm the heater draws from the charge source
(standard on Renogy-style packs) so it can only run when energy is actually arriving.

**Monitoring:** lead-acid-calibrated meters lie about LiFePO4 — the chemistry sits flat
near 13.2 V for 80% of discharge, so a voltage gauge reads "full" until it reads
"empty." Use a shunt-based monitor (Victron SmartShunt has VE.Direct — same data path).

### 2.5 Charging paths — three, in priority order

**1. AC charger (grid + generator, one box).** NOCO Genius 10 has a proper lithium mode
— fine for overnight grid top-off, useless behind a generator (10 A ≈ 14 h for a 200 Ah
refill; nobody runs a generator 14 hours). If a generator enters the plan, add a
30–50 A charger (Victron Blue Smart IP22 class) and size it so the generator runs near
its efficiency sweet spot, not at 20% load.

**2. Solar.** §§2.2–2.3.

**3. Alternator DC-DC (waste-heat capture).** The economics only work one way:

| | Cost per kWh |
|---|---|
| Idling an engine *to* charge | $3–4 — ~25x grid |
| Capturing an idle happening anyway | ~$0.50–0.90 |

**Never connect LiFePO4 directly to an alternator:** (1) near-zero internal resistance
pulls the alternator flat-out continuously — alternator cooling is sized for
intermittent peak; (2) wrong charge profile; (3) **load dump** — a BMS disconnect
mid-charge leaves the alternator driving an open circuit at full field current, and the
spike eats diodes and whatever shares the bus. A DC-DC charger current-limits, runs the
right profile, and isolates the systems.

Yield: 30 A ≈ 405 Wh per engine-hour; 50 A ≈ 675 Wh. **1.5–2.5 h of engine time covers
a working day.**

**Spec:** Victron Orion XS 12/12-50 (~$280, VE.Direct — same logging path). **Anderson
SB120** (a 50 A charger draws ~55 A input — over an SB50's rating). **4 AWG** minimum
(~2.5% drop over 20 ft); undersized wire silently halves the charger. **80 A ANL fuse
at both ends.**

**Smart-alternator vehicles (variable-voltage, e.g. modern diesels):** use **ignition
sense, not voltage sense** — smart alternators deliberately drop output and a
voltage-sensing charger chatters chasing it. **Tap the main battery, not a
stop-start-managed auxiliary.** A diesel at 700–800 RPM idle makes well under half the
alternator's rating; hold 1,200–1,500 RPM for rated charger output.

Sequencing: the DC-DC purchase waits for the LiFePO4 — an AGM only accepts 20–30 A, so
a 50 A charger would be battery-limited anyway.

### 2.6 Protection — do not skip

- **Inverter feed:** an 1100 W inverter pulls ~92–100 A continuous, 200 A+ surge.
  **150 A ANL or Class T within ~7 in of the battery positive**, 4 AWG minimum. A 100 A
  short with no fuse does not trip anything — it welds, then it burns.
- **Fuse hierarchy, stated plainly:** the **battery-side fuse** on the controller
  (40 A for a 30 A unit) is the one that prevents a shorted controller from welding to
  the battery. The **PV-side breaker is a service disconnect**, not the safety device.
- **String fuses:** unneeded at two parallel strings; required at three+, rated per the
  panel's series-fuse spec.
- **Battery-box breakers are a ceiling:** a 60 A breaker caps ~650 W regardless of the
  inverter's rating. Bypassing the box to the posts bypasses its protection — know
  which you have done, and fuse accordingly.

---

## 3. COMPUTE — THREE TIERS, THREE POWER STATES

### Tier 0 — Life support (STATE 0, always on)
**Raspberry Pi 5, 8/16 GB** + active cooler + bottom-mount NVMe base (keeps GPIO free)
+ 2 TB NVMe
- ~10 W with radio and logging
- Runs: `kiwix-serve` + 1–4 B model (llama.cpp) + LoRa Oracle + `power_monitor.py`
- Serves a WiFi AP for phones/laptops
- **Enable the Pi's built-in hardware watchdog on day one** (one line in config; systemd
  handles the rest). The supervisor MCU (§4) backstops it later.

### Tier 1 — Knowledge workstation (STATE 1, off by default)
**Strix Halo mini PC — AMD Ryzen AI Max+ 395, 128 GB unified LPDDR5X** (GMKtec EVO-X2,
Framework Desktop, HP ZBook Ultra G1a)
- ~215 GB/s memory bandwidth; 96 GB assignable to the iGPU; 70B Q4 resident or 30B MoE fast
- ~120–140 W under load. **Idle is irrelevant because it does not idle** — boots on
  demand, works, powers off
- **Measure the real numbers of the specific unit you buy** and update the §1 table;
  vendor idle/load figures vary by board
- The AMD software path (ROCm/Vulkan on this silicon) is still moving — which is why
  runtime snapshots (§6) are policy, not preference
- **Budget alternative:** Mac Mini M4 Pro 64 GB — less capacity, ~half the session power,
  more mature software path
- **Cheap alternative:** 32–64 GB mini PC + used RTX 3060 12 GB

### Tier 2 — The Monument (STATE 2, archive-only)
A very large MoE (2T+ total / ~100B active class) on a disk-streaming host.
**Fault-contained like aerospace hardware: its own storage, its own power path, its own
OS, its own runtime, zero dependency on Tier 0/1.** When it fails, the survival system
does not notice.

**Policy: no build effort and no dollars until a verified offline runtime exists for
the exact architecture.** Novel attention variants and routing schemes are unsupported
until someone writes the kernels. Archive the weights, archive the converter source
tree, and stop. A pile of tensors with no runtime is a brick, and this section exists
so the brick cannot eat the project.

---

## 4. THE SUPERVISOR — the thing that keeps the computer alive when the computer is stupid

The Pi is server + radio + storage + AI + telemetry. Too much responsibility for one
Linux box with no backstop. Staged:

**Phase A (day one, ~$0–25):**
- Enable the Pi's hardware watchdog (BCM watchdog + systemd `RuntimeWatchdogSec`)
- Put Tier 1 behind a relay or smart switch the Pi controls
- Physical master switch on the inverter

**Phase B (the proper build, ~$30–60):**
An **ESP32 / RP2040-class supervisor**, independent of Linux, with:
- Battery voltage + current (shunt/INA-class sensor), enclosure temperature
- Pi heartbeat monitor: missing heartbeat → wait → hard power-cycle → log the event
- Hard power control over Tier 1 and the radio
- Physical "survival mode" switch that forces BLACK band
- **Black-box logging** to its own flash/SD, independent of Linux:
  `timestamp, V_batt, I_batt, SOC, V_pv, I_pv, P_pv, I_pi, I_tier1, I_radio, temp` —
  the Pi ingests it periodically; **the computer dying no longer kills the data**
- **Status display** (e-paper or OLED) readable with every Linux box dead:
  `SYSTEM / BATTERY % / PV W / PI / RADIO / STORAGE / LAST BACKUP` — the
  "is the bunker alive" panel

The Pi is the computer. The MCU is the immune system.

---

## 5. STORAGE

| Item | Capacity | Purpose |
|---|---|---|
| Cold archive (D: array) | 8–16 TB | Master copy, everything |
| Working NVMe (Tier 1) | 4 TB | Active models + vector DB + hot ZIMs |
| Pi NVMe | 2 TB | ZIMs + small models + datasheets + Layer 0 |
| **Offsite / faraday copy** | 4 TB rugged USB | Small models + core ZIMs + toolchain + layers 0/3 |

The 4 TB rugged drive is the crown. It gets its own recovery test (§14, step 12) on an
air-gapped machine — an untested backup is a rumor.

---

## 6. LAYER 4 — TOOLCHAIN

**Archive the tool, not the download page.**

### AI runtimes — as frozen snapshots
**Policy: a "model" is a *working combination*, captured whole and never updated in
place.**

```
RUNTIME_2026_08/
├── model.gguf
├── tokenizer/
├── runtime/              <- the llama.cpp build that works, binaries + source bundle
├── runtime_commit.txt
├── launch.sh             <- exact flags
├── benchmark.txt         <- measured tok/s and power
├── system-info.txt
├── dependencies/         <- wheels, libs
├── drivers/              <- the ROCm/CUDA version this combination was proven on
├── known-issues.md
└── sha256.txt
```

New runtime → new directory (`RUNTIME_2027_02/`), old one untouched. This builds a
compatibility ladder backwards through time. Given the churn in the AMD inference
stack, archive **multiple known-good llama.cpp builds**, not "llama.cpp."

- **llama.cpp** — `git bundle create --all` + release binaries; record commits
- **Ollama**, **LM Studio** — installers, Windows + Linux
- **whisper.cpp**
- **Open WebUI** — `docker save` the image to .tar
- **Qdrant** — single static binary
- **Docling / PyMuPDF**
- **Kiwix-tools** — static ARM64 (Pi) + x86_64 builds

### Radio / mesh toolchain
- **Meshtastic firmware source** — full git bundle, with submodules
- **Prebuilt firmware for your exact boards** (.bin ESP32 / .uf2 nRF52) — *even though
  you have source*. Rebuilding offline means archiving the entire PlatformIO tree
  (`~/.platformio`: Xtensa GCC, frameworks, caches) — doable, brittle. A compiled
  binary always un-bricks a node.
- **esptool.py**, **adafruit-nrfutil** + wheels
- **Reticulum (RNS)**, **NomadNet**, **Sideband**, **RNode firmware**, **Ratspeak** —
  source + `pip download` of every dependency
- **Meshtastic docs** — `wget --mirror`
- **CHIRP** + radio definitions

### Electronics / RF toolchain
**KiCad** + libraries · **ngspice** + models · **Falstad** offline build · **4nec2/NEC2**
· **GNU Radio**, **rtl_sdr**, **SDR++**, **GQRX** — source + .debs

### The dependency layer (CRITICAL)
- Python 3.11 standalone + full wheel cache (`pip download -r requirements.txt -d ./wheels --only-binary=:all:`)
- ROCm / CUDA installers + driver files matching your GPU, **per runtime snapshot**
- Docker Engine offline packages
- Raspberry Pi OS image + `rpi-imager`
- apt offline mirror or `apt-offline` cache
- Ubuntu/Debian Server ISO

---

## 7. LAYERS 0 + 3 — IDENTITY AND ARTIFACTS

**The highest-value, least-collected layers. Sequencing rule adopted from review:
complete this section for gear you own BEFORE collecting more models.** Layer 3 is the
difference between a useful system and a confident hallucinator.

### 7.1 Layer 0 — the identity inventory
`00_INVENTORY/INVENTORY.csv`, one row per physical item:

```
id, manufacturer, part_number, revision, serial, location,
known_good (Y/N), last_tested, power_requirements, compatible_firmware,
datasheet_path, manual_path, schematic_path, photo_path,
exact_replacement, compatible_substitute, approximate_substitute, salvage_source
```

The last four columns are the **substitution data**: when the exact part is gone, the
system answers "these items in your physical inventory are plausible substitutes —
here are their datasheets" instead of hallucinating an equivalent. Populate
substitutions for the parts that matter (MOSFETs, regulators, diodes, fuses, radio
modules, connectors, bearings) as you touch them; do not try to do it all at once.

### 7.2 Your gear's artifacts
`02_CORPORA/datasheets/`:
- **Semtech SX1262/SX1276** datasheets + AN1200.22 (LoRa airtime and link-budget math)
- **ESP32-S3** TRM, **nRF52840** datasheet
- **Board schematics** — LilyGO (GitHub), RAK WisBlock docs
- **Victron manuals + the VE.Direct protocol whitepaper** — this is how
  `power_monitor.py` gets written
- Every manual: inverter, chargers, battery, panels, controller, supervisor parts
- **Your vehicle's factory service manual** — highest-value non-obvious item here
- Every datasheet for every part in the bins

### 7.3 Standards and reference tables
Wire ampacity / voltage-drop tables · coax loss by frequency · VSWR ↔ return loss ·
drill/tap charts, thread standards, hardness conversions · E-series values ·
transistor cross-reference · FCC Part 15 + Part 97 text · span tables, concrete mix
ratios, IRC excerpts

### 7.4 Electronics fundamentals — best free resource on this list
**NEETS** — Navy Electricity and Electronics Training Series. 24 public-domain
modules, ~48 MB total, `archive.org/details/NEETSModules`. Matter and DC through AC,
transformers, motors, tubes, solid-state, amplifiers, propagation, transmission lines,
antennas, logic, microelectronics, radar. Modules 10 and 17 alone cover most of an
RF/antenna corpus. Written by working technicians for self-study from zero.

---

## 8. LAYERS 1–2 — KNOWLEDGE CORPORA

Primary: `https://download.kiwix.org/zim/` · Mirror:
`https://www.mirrorservice.org/sites/download.kiwix.org/zim/` · **Use the torrents.**

Flavors: `maxi` = full + images · `nopic` = full text, ~75% smaller ← **the default** ·
`mini` = intro only ← for the Pi

### Core set
| ZIM | Approx | Notes |
|---|---|---|
| `wikipedia_en_all_nopic` | ~55 GB | **The backbone. This is the default, not maxi** |
| `wikipedia_en_all_mini` | ~5 GB | Pi / emergency copy |
| `wikipedia_en_all_maxi` | ~102 GB | Optional; images matter for repair/anatomy |
| `wikem_en_all` | ~1 GB | **Emergency medicine. Highest value-per-byte here** |
| `wikipedia_en_medicine_maxi` | ~5 GB | Medical subset |
| `mdwiki_en_all` | ~2 GB | Medical, curated |
| `appropedia_en_all` | ~2 GB | Appropriate tech, off-grid, agriculture |
| `ifixit_en_all` | ~5 GB | Repair guides with photos |
| `wikihow_en_maxi` | ~30 GB | Practical how-to |
| `gutenberg_en_all` | ~65 GB | Public domain books |
| `wikibooks_en_all_maxi` | ~10 GB | Textbooks |
| `wiktionary_en_all_nopic` | ~4 GB | |
| `wikiversity_en_all` | ~3 GB | Courses |

### Stack Exchange ZIMs (1–10 GB each, extremely high signal)
`stackoverflow`, `electronics`, `physics`, `chemistry`, `biology`, `medicalsciences`,
`gardening`, `homebrew`, `outdoors`, `ham`, `diy`, `engineering`, `aviation`,
`mechanics`, `security`

### Non-Kiwix
- **Hesperian** — *Where There Is No Doctor / Dentist*, *A Book for Midwives* — free PDFs
- **Survivor Library** — pre-1940 technical/trade books
- **US Army field manuals** — public domain
- **ARRL Handbook / Antenna Book**, **Machinery's Handbook** — rip owned copies
- **OpenStreetMap** regional extracts (Geofabrik) + OsmAnd/Organic Maps
- **USGS topo quads** (topoView)
- **USDA Complete Guide to Home Canning** — free, authoritative, altitude-aware
- **WHO/CDC water treatment guides**, well construction, slow sand filters
- **Merck Veterinary Manual**
- Seed saving: isolation distances, viability, germination testing
- Heat-treat data (1018/1045/4140/O1/A2/D2); Lincoln + Miller welding guides
- **Your own corpus** — personal research, build notes, case files. The part nobody
  else has, and the part RAG makes useful *today*.

### The bootstrap tier (repair → reproduce → rebuild)
The corpus above repairs civilization's existing stuff. This tier builds things when
manufactured stuff is gone — it is why Survivor Library and the Gingery series are
here, and it deserves deliberate collection, not accident:

- **Water:** wells, cisterns, hand pumps, filtration, distillation, disinfection
- **Food:** soil fertility, fermentation, root cellars, animal husbandry
- **Energy:** water wheels, windmills, biomass gasification, steam, mechanical transmission
- **Materials:** charcoal, lime, cement, glass, brick, pottery, leather, soap, adhesives
- **Machine tools:** Gingery lathe-from-scrap sequence, forge, furnace, casting,
  jigs, metrology

---

## 9. RETRIEVAL-ONLY DOMAINS

**Domains where a hallucinated answer causes physical harm. The system retrieves and
displays source text verbatim with attribution. It does not generate, paraphrase,
interpolate, convert units, or improvise. Enforced in code, not in a prompt.**

### 9.1 The six
1. **Medical.** Return the WikEM/Hesperian passage + article title. No model in the
   loop. A small model inventing a pediatric dose for someone who cannot check it is
   the worst failure this system can produce.
2. **Ammunition reloading.** A wrong charge is a detonation. Data comes from the powder
   or bullet manufacturer for the exact component combination. **Never interpolate
   between published loads. Never substitute a component and keep the charge. Never
   convert between powders.** Manuals disagree because test barrels differ — cite
   manual and edition, always. Start low, work up.
   Archive: **SAAMI cartridge/chamber drawings** (free PDFs); manufacturer data —
   **Hodgdon/IMR/Winchester, Alliant, Vihtavuori, Accurate/Ramshot** — all published
   free online, all scrapeable, scrape now; owned **Lyman/Hornady/Sierra/Nosler/Speer**
   manuals; burn-rate charts (note publisher + date); case capacity and headspace
   tables. Load-data *apps* are online/DRM'd — the manufacturer web data is the
   archivable form.
3. **Home canning.** Botulism. Processing times are a function of jar size, product
   density, and **altitude** — Colorado Springs at ~6,000 ft changes every number in
   the book. USDA guide, verbatim, or nothing.
4. **Electrical sizing.** Wire ampacity, fuse sizing, battery/inverter interconnects,
   PV string configuration, lithium charge parameters. "The model remembered the
   equation wrong" is a fire. Retrieve the table; show the table.
5. **Structural and rigging.** Load-bearing spans, lifting, cranes, anchors, pressure
   vessels, compressed gas. Source-bound, always.
6. **Water treatment dosing.** Chemical doses and contact times — retrieve from
   WHO/CDC/EPA tables only.

(Automotive safety systems — brakes, restraints, steering — follow the same rule via
the FSM: the answer is a page reference, not a paragraph of model prose.)

### 9.2 The safety router — every query classified before any model runs

```
                    ┌── RETRIEVAL-ONLY   (the six domains: verbatim + citation)
                    │
Question → Router ──┼── ARTIFACT LOOKUP  (layer 0/3: filename + page, open the PDF)
                    │
                    ├── NORMAL RAG       (prose corpus, cited chunks + model synthesis)
                    │
                    └── GENERAL MODEL    (labeled as such)
```

**Every response labels its provenance**, destroying the illusion that all sentences
carry equal authority:

```
SOURCE:          Victron VE.Direct whitepaper, p. 17
INTERPRETATION:  The controller is reporting bulk-stage charging.
MODEL INFERENCE: This suggests the array is under-delivering for the hour; check snow.
```

A first-pass router is a keyword/regex classifier over the six domains plus an
artifact-lookup path — a novice-feasible Python script, not an ML project. Tighten later.

### 9.3 Corpus split by retrieval mode

| Mode | Content | Why |
|---|---|---|
| **Vector-indexed** | Prose: notes, logs, articles, literature, WikEM text | Chunks cleanly |
| **File-tree + full-text only** | Datasheets, schematics, load data, standards tables, FSMs | **Tables do not chunk** |
| **Bridge** | `INVENTORY.csv`, `CORPUS_INDEX.csv` | Prose-ish; names the file to open |

**Datasheets never enter the vector store.** A pin table sliced across a chunk boundary
returns half a pinout with no header, and the model fills the gap — the confident wrong
pin number, manufactured by your own pipeline. Layer-3 retrieval targets a **filename
and page number**, not a paragraph.

---

## 10. MODELS (GGUF, Q4_K_M unless noted)

Source: `https://huggingface.co/` — `bartowski` and `unsloth` publish reliable quants.
**Names below are a snapshot that will age; `MODEL_INDEX.csv` is the record.** Treat
quant sizes as approximate until the actual file is measured. Sequencing rule: **layer
0/3 completion outranks new model downloads.**

### Pi / low-power tier
| Model | Size | Why |
|---|---|---|
| Qwen3.5 4B | ~2.5 GB | Best small all-rounder. Default |
| Phi-4-mini 3.8B | ~2.3 GB | Reasoning-heavy, math |
| Llama 3.2 3B | ~2 GB | Fallback, huge ecosystem |
| SmolLM3 3B | ~1.8 GB | Runs on anything |

### Workhorse tier
| Model | Size | Why |
|---|---|---|
| **Qwen3-30B-A3B class MoE** | ~18 GB | **Primary.** ~3B active, fast |
| Gemma 4 26B-A4B | ~16 GB | Multimodal — reads images/diagrams |
| Llama 3.3 70B | ~40 GB | Deepest general knowledge, slower |
| Qwen3 Coder 30B | ~18 GB | Code + electronics |
| gpt-oss-20b | ~12 GB | Permissive-license generalist |

### Specialist
| Model | Purpose |
|---|---|
| `nomic-embed-text` / `bge-m3` | **Embeddings. Cannot skip** |
| `whisper-small`/`medium` ggml | Offline transcription |
| Piper voices | Offline TTS |
| Medical-tuned (OpenBioLLM/Meditron) | Optional; **§9 still governs — retrieval wins** |

`MODEL_INDEX.csv` schema (expanded per review):
```
model, revision, date_acquired, quantization, runtime, runtime_commit,
memory_required, tokens_per_sec, power_draw_W, known_good (Y/N),
fallback_runtime, sha256, source_url
```

**Q4 vs Q5 rule:** larger model at Q4 beats smaller at Q8 in the same memory. Below
~7B use Q5_K_M/Q6 — small models degrade harder under quantization.

---

## 11. THE RAG PIPELINE

Simplest path that works, in order:

1. **Ollama** on the Tier 1 box (`ollama serve`)
2. **Open WebUI** in Docker → chat + upload + RAG, almost no code
3. `nomic-embed-text` inside Ollama
4. Prose corpus into Open WebUI Knowledge
5. **Kiwix-serve** on :8080 as the browsable wiki
6. **Datasheets as a plain indexed file tree** — §9.3, never ingested
7. The **safety router** (§9.2) in front, once 1–6 work

**Do not start with Qdrant.** Ollama + Open WebUI answering questions about your own
PDFs is a one-evening win that proves the stack. Upgrade to Qdrant + custom ingest +
ZIM indexing after.

---

## 12. COMMS LAYER

### 12.1 Security reality check
- **Meshtastic's default channel is not private.** Primary ships with PSK `AQ==` —
  publicly known; any stock node decrypts it. Orange lock in the app.
- **No perfect forward secrecy** — a leaked channel key retroactively exposes captured
  traffic.
- **Reticulum has never been externally audited** (the project says so). It provides
  **initiator anonymity**; the **destination hash is exposed** to transport nodes.
  "Can't see who you're talking to" is marketing, not protocol. It silently falls back
  to unreviewed pure-Python crypto if OpenSSL/PyCA is missing — verify the OpenSSL path.
- **MQTT bridging is publishing** — mesh traffic to a broker, by default the public
  one. For cross-site links, Reticulum over a TCPInterface between endpoints you
  control.
- **A fixed node is an RF beacon at a fixed address.** ROUTER role transmits
  constantly from one location forever; an SDR + directional antenna finds it in an
  afternoon, and position broadcast puts it on public maps without the afternoon.
  Set position precision low or off; meaningless node name; accept that direction
  finding works regardless.

### 12.2 Configuration
- **LongFast stays primary** with the default key — that is community relaying. Treat
  it as a public bulletin board.
- **Secondary channel, random 256-bit PSK** for private traffic; secondaries don't
  need matching modem presets, so community relaying is unaffected.
- **Prefer DMs** — firmware 2.5+ DMs use public-key crypto (encrypted to recipient,
  signed by sender). Real E2EE, unlike channel PSKs.
- All periodic broadcasts (position, telemetry, traceroute) ride the primary under the
  public key. Configure accordingly.

### 12.3 Hardware
- **SX1262 over SX1276** — lower RX current (24/7 solar), better sensitivity
- **USB dongle over Pi HAT** — reflash without opening the stack; serial beats
  SPI+daemon for a novice build; the Pi's one PCIe lane stays on NVMe
- **Base antenna 5.8–6 dBi, not 10** — omni gain flattens the vertical pattern
  (~35° at 5.8 dBi); in terrain with elevation spread, high gain shoots over the
  uphill node and under the downhill one
- **Longer 400-grade coax beats shorter 240-grade** — at 915 MHz, ~25 ft of 400-grade
  ≈ 1.0 dB vs ~15 ft of 240-grade ≈ 1.7 dB. 3 dB of cable loss is half your power.
- **SMA, not RP-SMA** (WiFi gear is RP-SMA; mixing = no connection or damage). Heltec
  V3 uses IPEX/u.FL — needs a pigtail.
- **Coax surge arrestor**, bulkhead, grounded at entry — a roof antenna feeding a
  radio feeding a Pi feeding the network is a surge path through everything. ~$40.
- **Never power a LoRa board without an antenna attached.**

### 12.4 The Oracle — a remote command line, not a chatbot
Meshtastic's wire ceiling is a 237-byte payload; **usable is ~230 after overhead.
Design to 200 characters, enforced in code.** A packet is 1–2 s of airtime rebroadcast
by every node in range — airtime is a commons. Private channel or DM only; rate-limit
per node (≥1 min).

**Structured responses, not prose** (adopted from review — this is the right model):

```
?power                     ?find sx1262               ?med dehydration
BAT 76%                    SX1262                     SEE: WIKEM/DEHYDRATION
PV 184W                    DATASHEET p4               RETRIEVAL ONLY.
LOAD 21W                   RADIO/SX1262.pdf           FULL TEXT AT NODE.
RESERVE 2.1D
```

Command paths, per §9:
- `?med` → verbatim Kiwix/WikEM snippet + title. **No model.**
- `?find` → Layer 0/3 lookup: part, datasheet path, page
- `?power` → live VE.Direct + supervisor state
- `?ask` → the small model, output labeled MODEL INFERENCE

The Oracle is a remote shell into the knowledge system. "ChatGPT over LoRa" is the
wrong goal and the bandwidth enforces the right one.

---

## 13. D:\ FOLDER STRUCTURE

```
D:\OFFGRID\
├── 00_DOCS\
│   ├── MANIFEST.md  BUILD_LOG.md  POWER_BUDGET.xlsx  RECOVERY_PROCEDURE.md
├── 00_INVENTORY\
│   ├── INVENTORY.csv            <- LAYER 0: identity + substitution columns
│   └── photos\
├── 01_MODELS\
│   ├── tier0_small\  tier1_workhorse\  embeddings\  speech\
│   ├── runtimes\RUNTIME_2026_08\   <- frozen known-good combinations
│   └── MODEL_INDEX.csv
├── 02_CORPORA\
│   ├── kiwix_zim\
│   ├── datasheets\radio\ power\ vehicle\ components\
│   ├── reference_tables\        <- ampacity, coax loss, load data, spans
│   ├── pdfs\medical\ technical\ personal\
│   ├── bootstrap\               <- §8 bootstrap tier
│   ├── maps\
│   └── CORPUS_INDEX.csv
├── 03_SOFTWARE\
│   ├── runtimes\ docker_images\ python\ drivers\ os_images\ apt_mirror\
│   └── firmware\                <- prebuilt .bin/.uf2 per board + platformio cache
├── 04_CONFIG\
│   ├── docker-compose.yml  modelfiles\  systemd\  dotfiles\
│   ├── meshtastic\              <- channel configs, exported node settings
│   └── supervisor\              <- MCU firmware + wiring notes
├── 05_SCRIPTS\
│   ├── ingest_pdfs.py  verify_checksums.py  power_monitor.py
│   ├── lora_oracle.py  safety_router.py
└── 06_MONUMENT\                 <- isolated. excluded from backups and from hope
```

---

## 14. BUILD ORDER

Each step is useful alone — never a half-finished pile of nothing.

1. **Pi 5 + Kiwix + `wikipedia_en_all_mini`.** One evening. Offline Wikipedia at 8 W.
   Enable the hardware watchdog while you're in the config.
2. **Add `wikem`, `appropedia`, `ifixit`, medical ZIMs, Hesperian PDFs.** One evening.
3. **Ollama + a 4B model on the Pi.** Slow, but proves the software path.
4. **Open WebUI + your own PDF corpus.** First immediate real-world payoff.
5. **Layer 0 + Layer 3 for gear you own.** INVENTORY.csv + datasheets. Boring,
   decisive, and it outranks downloading more models.
6. **Solar + battery + DC-DC + VE.Direct logging.** The Pi runs on sun and reports it.
7. **Measure winter for two weeks.** Array at winter tilt, log every watt via
   VE.Direct. Reality-check §1 before trusting it. (Insert whenever winter arrives.)
8. **Comms layer.** USB SX1262 on the Pi, base antenna + surge arrestor, channel
   config, Oracle with the §12.4 command set.
9. **Supervisor Phase B.** ESP32 + black box + status display.
10. **Alternator DC-DC** — after the LiFePO4 lands (AGM is charger-limited anyway).
11. **Tier 1 box.** Measure its real idle/load numbers; update §1. Freeze
    RUNTIME_<date> snapshots as combinations prove out.
12. **Archive the toolchain; then the recovery test** — wipe a spare machine,
    **air-gapped**, rebuild from the **faraday drive specifically**. An untested
    backup is a rumor.
13. The Monument — if and only if a verified runtime exists. Otherwise it stays §3
    policy: weights archived, zero effort.

---

## 15. MAINTENANCE

- `sha256sum` everything on ingest; hashes live in the INDEX files
- **Verify checksums annually** — bit rot on multi-TB cold storage is real and silent.
  Let the surplus scheduler do it on sunny afternoons.
- Refresh ZIMs yearly (Kiwix rebuilds quarterly)
- Re-run the recovery test yearly, air-gapped, from the faraday copy
- Cycle the LiFePO4; don't store at 100% SOC
- New hardware → same-day Layer 0 row + datasheet. No exceptions.
- Clear snow off the array; it will not clear itself at 50° every time
- Re-run §16 validation after every hardware change and at least once per winter

---

## 16. VALIDATION — THE ONLY TEST THAT MEANS ANYTHING

Pick a real task:
- Reflash a bricked LoRa node
- Diagnose why the MPPT isn't charging
- Work up a load for a cartridge you haven't loaded before
- Look up a drug interaction
- Calculate pressure-canning time for a product at 6,000 ft
- Find a substitute in your own inventory for a dead regulator

**Unplug the router. Do it using only the archive.**

Whatever you had to guess at is the gap list. Everything else is theory.

---

## 17. HONEST ASSESSMENT

**The LLM is the least important part of this build.** Kiwix + Wikipedia + WikEM +
Hesperian on a Pi is ~60 GB at 8 W of verified, citable, non-hallucinating
information. That is the asset. The model is a *natural-language index* over it —
valuable, because searching a wiki requires knowing what to search for. But if you
had to pick one, pick the books.

**The most likely failure mode** (both external reviews converged on this, and they
are right): **under-budgeted Colorado winter reality** — snow on the array, heater
draw, multi-day low-sun stretches — browning out Tier 0 while the recovery procedure
sits untested and Layer 3 sits incomplete, leaving a model that invents pinouts.
Every v3 change traces back to that sentence: the idle-load cut, the heater line, the
bands, the supervisor, the winter measurement step, the air-gapped test, the
Layer-3-before-models rule.

**The ceiling.** You cannot make a semiconductor. "Keeping technology alive" is two
different goals with two different corpora: (1) maximize the working lifetime of
existing artifacts — layers 0/3, iFixit, FSMs, substitution data; (2) rebuild the
pre-semiconductor tier from scratch — the bootstrap tier, Survivor Library,
Machinery's Handbook, Gingery. Wikipedia is the connective tissue between them.

Build the library first. Add the librarian second. Collect the datasheets third — and
the third step decides whether any of it is usable.

---

## APPENDIX — ADVERSARIAL REVIEW PROMPT

For running this document past other models. Paste the manifest, then:

```
You are reviewing a technical build manifest for an off-grid AI and knowledge-archive
system. Be adversarial and specific. I want errors found, not encouragement.

Work through these in order and cite the section number for each finding:

1. ELECTRICAL SAFETY. Check every calculation. Verify the cold-weather Voc math in
   §2.2 against the stated controller ceiling AND the 80% design-margin rule, the
   fuse sizing in §2.6 against the stated loads, and the wire gauge claims. Flag
   anything that could destroy equipment or start a fire. Show your arithmetic.

2. ENERGY BUDGET. Check §1 for Colorado Springs at ~6,000 ft. IMPORTANT: state
   explicitly whether any solar figure you cite is horizontal (GHI) or plane-of-array
   (POA) for the stated ~50-55 degree winter tilt — these differ by ~2x in December
   and conflating them invalidates the review. Check the load table, the heater line,
   and the autonomy math.

3. FACTUAL ERRORS. Flag anything wrong or outdated: model names, protocol details,
   product specs, payload limits, security claims. State your training cutoff and
   mark claims you cannot verify.

4. SAFETY-CRITICAL CONTENT. §9 designates six retrieval-only domains. Is the list
   right? What other domain in this document would cause physical harm if a language
   model hallucinated an answer? Is the router design in §9.2 sufficient to enforce it?

5. MISSING. What would you add that isn't here? Rank by value-per-dollar and
   value-per-watt, not by how interesting it is.

6. CUT. What is overbuilt, redundant, or a waste of money? Argue for deleting at
   least three things.

7. FAILURE MODE. What is the single most likely reason this project ends as an
   unfinished pile of parts? Be blunt. If your answer matches §17, say what §17
   still underestimates.

Do not summarize the document back to me. Do not compliment it. Findings only.
```
