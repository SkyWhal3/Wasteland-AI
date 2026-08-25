# OFFGRID KNOWLEDGE + AI NODE — PUBLIC EDITION

**A build guide for an off-grid, solar-powered offline knowledge server (Wikipedia +
emergency medicine + repair guides) with optional local AI and LoRa mesh access.**

Released as-is, no warranty, public domain. **Especially no warranty on the electrical
sections — verify every number against your own datasheets before wiring anything.**
Written for the Front Range (Colorado Springs area, ~6,000 ft) but portable anywhere
with the worksheet in §2.

**Code, issues, and releases:** https://github.com/SkyWhal3/Wasteland-AI
**Want to try it tonight without buying anything?** Start with `QUICKSTART.md` in that
repo — the scripts have demo modes that run the whole Tier-0 loop on any laptop, no
hardware at all.

*Where this doc sits:* `QUICKSTART.md` is "try it in five minutes." **This guide is
"build one — here's the money and the physics."** `00_DOCS/MANIFEST.md` is the deeper
engineering reference behind it.

---

## 0. PHILOSOPHY — READ THIS FIRST

**The LLM is the least important part of this build.**

Kiwix + Wikipedia + WikEM + the Hesperian medical guides on a Raspberry Pi is ~60 GB,
runs on 8–10 W, and gives you verified, citable, non-hallucinating information. That is
the asset. A local AI model is a *natural-language index* over that corpus — genuinely
useful, because searching a wiki requires knowing what to search for — but if you can
only build one thing, build the library.

**Build order in one sentence:** library first, librarian second, datasheets third —
and the third step decides whether any of it is usable when something breaks.

Second principle: **every power recommendation here has two columns — Buy Today and
Scavenge Later.** Different problems, different answers. Docs that mix them end up
recommending 2015 solutions at 2026 prices.

---

## 1. PICK YOUR TIER

| | Tier A — "the garage build" | Tier B — "the value king" | Tier C — "the December machine" |
|---|---|---|---|
| Cash outlay (power side) | **$0–150**¹ | **$400–700** | **$1,100–1,900** |
| Battery | Salvaged 12 V lead (buffer role) OR your existing power station | 100 Ah budget LiFePO4 (~$150–200) or golf-cart pair | 200 Ah **self-heating** LiFePO4 |
| Panels | Whatever you own; 1× 200 W @ ~$1/W if buying | 2× 200 W @ ~$1/W | 400–440 W, winter-tilted |
| Controller | Honest PWM ($20) or entry MPPT | Genuine MPPT 30 A (EPEver/Renogy class) | Victron 100/30 + VE.Direct data cable |
| Runs | Pi knowledge node, 3 seasons | Pi 24/7 year-round + AI sessions 3 seasons | **Everything, through a Colorado winter** |
| Winter honesty | Browns out in December | Pi survives; AI sessions get rare | Designed for the worst month |

¹ *If you already own a panel or a Goal-Zero-class power station — most of the camping
crowd does. Add ~$200 for one 200 W panel if not.*

**Compute side, common to every tier:** Raspberry Pi 5 (8 GB), active cooler,
bottom-mount NVMe base, 2 TB NVMe, SD card — **~$230–280 total.** The optional big-AI
workstation (128 GB Strix Halo mini PC class, ~$1,500+) is a Tier B/C add-on and is
covered in §7.

Tier A is the point. Ten people starting at Tier A beats one person speccing Tier C in
a spreadsheet forever. Every tier upgrades into the next without throwing anything away
— *if* you follow the 12 V/24 V decision table in §6.

---

## 2. THE POWER MATH YOU MUST DO ONCE

```
Array watts x December peak sun hours x 0.75 derate = daily Wh, worst month
```

**The trap that ruins this calculation:** "peak sun hours" figures come in two flavors
that differ by ~2x in winter.

- **GHI** (global horizontal irradiance) — sunlight on a panel lying **flat**.
  Colorado Springs December GHI is ~2.4 kWh/m²/day. Useless number for you.
- **POA** (plane of array) — sunlight on a panel **tilted ~50–60°** at the low winter
  sun. Colorado Springs December POA is ~4.5–5.0. **This is your number.**

Design at **4.0** for margin. Any time someone quotes you a solar figure, ask which one
it is. Verify your exact site with NREL's free PVWatts calculator (real tilt, azimuth,
horizon), then verify *that* with two weeks of winter logging (§11, step 7).

**Reference budget (400 W array, December, tilted):** ~1,200 Wh/day raw, **~1,020
usable** after controller + battery losses.

**Reference loads:**

| Load | Draw | Wh/day |
|---|---|---|
| Pi 5 + NVMe + LoRa radio + logging | 10 W × 24 h | 240 |
| Network / misc | 4 W × 24 h | 96 |
| **Survival baseline** | | **~350** |
| LiFePO4 self-heating (cold mornings) | 50–130 W, 0–1.5 h | 0–100 |
| AI workstation session (optional) | 130 W × 2 h | 260 |
| **Working December day** | | **~610–710** |

**The two silent budget killers:**
1. **An inverter left switched on.** A 1,000 W+ inverter idles at 6–12 W = up to
   290 Wh/day doing nothing — potentially a third of your whole budget. Physical
   switch or relay. Run DC loads on DC-DC bucks, never through an inverter
   (battery→AC→DC wastes 15–20%; battery→buck→DC wastes ~5%).
2. **A computer idling "just in case."** The big box is OFF by default and boots on
   demand. The question is never "can I afford to keep the AI on" — it's **"can I
   afford to ask this question."**

---

## 3. BATTERIES — BUY TODAY vs SCAVENGE LATER

### 3.1 The economics (lifetime delivered energy per dollar)

| Battery | Price | Usable/cycle | Cycles | $/kWh delivered |
|---|---|---|---|---|
| **Salvaged** car battery (SLI) | $0 | ~0.3 kWh @ 25% DoD | 50–150 | **free, but tiny** |
| ***New* car battery** | ~$130 | ~0.35 kWh | 50–150 | **$2.50–6 — worst buy on this table** |
| Golf-cart pair (2× GC2 6 V) | ~$260 | ~1.3 kWh @ 50% | 500–1,000 | $0.20–0.40 |
| Budget 100 Ah LiFePO4 | ~$150–200 | ~1.15 kWh @ 90% | ~2,500–3,500 | **~$0.05** |
| 200 Ah self-heating LiFePO4 | ~$550–950 | ~2.3 kWh | ~3,000 | ~$0.08 — and it charges in December |

Three conclusions:
1. **Never BUY a car battery for storage.** Worst $/kWh by 10×. (It's the intuitive
   move. It's wrong.)
2. **Budget LiFePO4 rewrote the old wisdom.** Golf-cart pairs were the 2015 answer and
   remain the lead-acid fallback; at ~$150/100 Ah, lithium wins on everything except
   sub-freezing charging.
3. **Salvage is a scavenge-column answer.** At $0, unbeatable. At any price above $0,
   LiFePO4 wins.

### 3.2 Where salvaged lead genuinely earns its place

- **It charges below freezing.** Slowly, but with no BMS lockout and no heater draw.
  A legitimate winter advantage lithium has to spend money and watt-hours to match.
- **Every parking lot is infrastructure.** A car is ~1 kWh of shallow-cycle storage
  bolted to a 100 A+ alternator bolted to a generator with a fuel tank. The battery is
  the *least* valuable part of that stack — see the Scavenge Appendix (§14).
- **No electronics to fail.** 1850s technology. Nothing to firmware-brick.
- **Right role: buffer, not reservoir.** Lights, fans, radio, shallow 10–20% cycles —
  while the compute stack lives on lithium.

### 3.3 ⚠ LEAD-ACID SAFETY BOX — non-negotiable rules

- **PARALLEL ONLY for mismatched batteries. NEVER series salvage.** Series-connecting
  unequal batteries over-discharges and reverse-charges the weakest one — it dies
  fast and can vent. 24 V from lead requires a **matched pair bought together** plus a
  ~$20 battery equalizer.
- **Flooded batteries vent hydrogen while charging.** Not indoors near your
  electronics, never in a sealed box. (AGM relaxes this; flooded does not.)
- **DoD ceilings:** ~50% for true deep-cycle, ~20% for car (SLI) batteries. Recharge
  promptly — sulfation is a clock that runs whenever lead sits discharged.
- **Never charge a frozen battery.** A charged lead battery won't freeze until about
  −60 °F; a *discharged* one freezes near −10 °F. Keep them charged and they winter
  fine.
- **A $25 load tester separates keepers from cores.** Expect salvage to hold 40–70% of
  rated capacity. Parts stores pay $10–25 core charge for the losers — even failures
  are beer money.

### 3.4 LiFePO4 rules

- **Low-temperature CUTOFF ≠ SELF-HEATING.** Cutoff protects the pack by *refusing*
  charge below freezing — meaning your battery declines the sunny 20 °F morning you
  need most. Self-heating warms itself then charges (drawing 50–130 W to do it —
  budget it). **For winter builds, buy self-heating.** Three-season builds can save
  money with cutoff-only.
- **Lead-acid battery meters lie about lithium.** LiFePO4 sits flat at ~13.2 V for 80%
  of its discharge; a voltage gauge reads "full" until it reads "empty." Use a
  shunt-based monitor.
- Don't store at 100% SOC indefinitely; cycle it.

### 3.5 The power-station path (Goal Zero / Jackery / EcoFlow class)

If you already own one, **it's a valid Tier A/B core, not a compromise** — Pi on the
regulated 12 V or USB-C PD output, folding panel into the solar input, zero wiring.
Three honest caveats:
1. **Check the solar input Voc ceiling before connecting anything.** Many units cap at
   22–60 V input. Two "12 V" panels in series (~44–54 V Voc) exceeds some older units.
   Read the label on the port.
2. **Use DC outputs, not the AC inverter** — the internal inverter idles at 5–15 W.
   Same budget-killer as any inverter, hiding in a friendlier box.
3. You're paying 2–4× DIY $/Wh for integration and safety. Fair trade for many people.
   Just know it.

---

## 4. PANELS + CONTROLLERS AT THE $1/WATT TIER

"12 V panel" means Vmp ~18–20 V, Voc ~22–27 V. Rigid 200 W N-type panels run about
$1/watt delivered. Two rules cover every configuration on a 100 V-class MPPT:

**Rule 1 — cold voltage.** Panels gain voltage as temperature drops (~+0.3%/°C below
25 °C). Worst case is a clear cold dawn. Compute it:

```
Voc_cold = Voc_datasheet x 1.165   (at -30 C; use your actual low + datasheet coefficient)
```

**Design rule: keep string Voc_cold under 80% of the controller's absolute max.**
For 12 V-type panels on a 100 V controller: **two in series max** (~50 V STC → ~60 V
cold ✓). **Three in series (~75 V → ~90 V cold) violates the margin. Never.** Four
panels = two series pairs in parallel (2S2P).

Higher-voltage "24 V-type" panels (Voc ~40–46 V): **two in series exceeds 100 V in
Colorado cold. Parallel only.** Recompute for *your exact panel* — the wiring rule is
panel-specific, always.

**Rule 2 — exceeding the controller's WATT rating is harmless (it clips at peak);
exceeding its VOLT rating kills it, and that's not warranty-covered.**

### ⚠ THE FAKE-MPPT BOX

The $25 Amazon "MPPT" controller is a PWM unit with a lying label — an entire
documented scam genre. Real MPPT contains a heavy inductor and holds the panel at its
power point (~18 V) instead of dragging it down to battery voltage. **If "MPPT" costs
under ~$60, it isn't.** The genuine budget ladder: **EPEver Tracer AN → Renogy Rover →
Victron.** Victron's BlueSolar costs more and earns it one specific way: the VE.Direct
serial port feeds live solar/battery data to the Pi (see `power_monitor.py` in the
code folder).

**And a rehabilitation: honest PWM is legitimate at the bottom.** A 12 V-type panel on
a 12 V battery is the one configuration where PWM's loss is smallest (~15–25%). A $20
real PWM plus one extra $50 panel can beat a $100 MPPT on total system cost. MPPT is
not a purity test.

**Wiring minimums (every tier):**
- Fuse the **battery side** of the controller (40 A for a 30 A unit) — that's the fuse
  that prevents a fire; the PV-side breaker is a service disconnect.
- Any inverter over ~400 W: dedicated fuse (ANL/Class T) within ~7 inches of the
  battery positive, sized to the inverter's real draw (an 1,100 W unit pulls ~100 A
  continuous — 150 A fuse, 4 AWG minimum).
- Voltage drop eats 12 V systems alive. Size wire for the run; when in doubt, one
  gauge fatter.

---

## 5. WINTER OPERATIONS (Front Range specific)

- **Tilt 50–62°.** Aims at the low sun AND sheds snow. The design month and the
  bifacial-gain month (snow albedo) are the same month.
- **Snow does not always clear itself.** Soft roof rake in the kit; clearing in the
  routine.
- **Autonomy math:** usable bank Wh ÷ 350 Wh survival baseline = days the knowledge
  node survives a storm with zero production. (200 Ah LiFePO4 ≈ 6.5 days. One salvaged
  car battery ≈ 20 hours. That gap is what Tier C buys.)
- Load-shedding bands, enforced in software (`power_monitor.py`):
  **GREEN** >70% SOC — everything allowed · **YELLOW** 40–70% — no background jobs,
  AI for essentials · **RED** 20–40% — Pi + comms only · **BLACK** <20% — minimum
  survival duty.

---

## 6. 12 V OR 24 V — THE DECISION TABLE

| Your situation | Answer |
|---|---|
| Salvage-heavy, ≤400 W array, 12 V accessory world | **12 V.** The ecosystem is the argument. |
| Motorhome/cabin already wired 24 V | **Stay 24 V**; hang 12 V loads off a $25 24→12 buck |
| Buying everything new, planning 600 W+, long wire runs | **24 V** — matched batteries only |
| Any mismatched or salvaged bank | **12 V, parallel, no exceptions** |

The commitment point is the **battery purchase** — decent MPPTs auto-detect 12/24 V,
so the controller isn't the fork. A 100 V/30 A controller handles 440 W at 12 V and
**880 W at 24 V** — going 24 V doubles the same controller.

---

## 7. COMPUTE — TWO TIERS, TWO POWER STATES

### Tier 0 — the knowledge node (always on, ~10 W)
**Raspberry Pi 5, 8 GB** + active cooler + bottom-mount NVMe base (keeps the GPIO
free) + 2 TB NVMe. Runs:
- `kiwix-serve` — offline Wikipedia/WikEM/iFixit over its own WiFi AP
- a 1–4 B parameter model via llama.cpp/Ollama (slow, but always there)
- `power_monitor.py` (solar telemetry, checksum-validated) and `lora_oracle.py`
  (the mesh bot) — with `safety_router.py`, `verify_checksums.py`, a sandboxed
  coding agent, and a test suite, in the repo's `05_SCRIPTS/`
- **Enable the Pi's built-in hardware watchdog on day one** — one config line; it
  reboots a hung Pi at 3 AM without you.

### Tier 1 — the AI workstation (OFF by default, boots on demand)
128 GB unified-memory mini PC class (AMD "Strix Halo" / Ryzen AI Max+ 395 boxes,
~$1,500+; or a used-GPU tower). Runs 30–70 B models well at ~120–140 W *during
sessions only*. This is a want, not a need — **the Pi alone is a complete Tier A/B
project.** If you buy one: measure its real idle/load numbers yourself, and freeze
known-good model+runtime combinations as dated snapshots you never update in place
(the AMD inference software stack is still moving fast).

**Check your closet before your wallet.** Any 4-core-plus x86 mini PC or laptop with
32–64 GB of RAM runs the workhorse model class (a ~30 B mixture-of-experts at Q4, which
only activates ~3 B parameters per token) at a usable speed on CPU alone — no GPU. A
retired office mini PC plus ~$120 of RAM is the single best capability-per-dollar move
in this entire document, and it defers the $1,500 purchase indefinitely. Corporate
e-waste is full of these.

---

## 8. THE KNOWLEDGE BASE — FIVE LAYERS

| Layer | What | Where it comes from |
|---|---|---|
| **0 — Identity** | What you physically own: part, revision, location, substitutes | You build it: `INVENTORY.csv` |
| **1 — Concepts** | What things are | Wikipedia ZIM |
| **2 — Procedures** | How to do things | Stack Exchange, iFixit, wikiHow ZIMs |
| **3 — Artifacts** | The numbers for YOUR things | Datasheets, schematics, service manuals |
| **4 — Toolchain** | The ability to act offline | Archived installers, compilers, firmware |

Layers 1–2 are commodity downloads. **Layers 0, 3, 4 are the difference between a
library and a workshop** — and they're what the AI needs to translate "my node stopped
transmitting" into "check pin 14, per the datasheet at this path" instead of inventing
a pin number. An LLM without layer 3 doesn't say "I don't know." It hallucinates,
confidently.

### 8.1 Core corpus (Kiwix ZIMs — use the torrents)
From `download.kiwix.org/zim/` (prefer `nopic` flavors — full text, ~75% smaller):

`wikipedia_en_all_nopic` (~55 GB, the backbone) · `wikipedia_en_all_mini` (~5 GB, Pi
copy) · **`wikem_en_all` (~1 GB — emergency medicine, highest value-per-byte on this
list)** · `wikipedia_en_medicine` · `mdwiki` · `appropedia` (off-grid tech) · `ifixit`
· `wikihow` · `gutenberg` (~65 GB) · `wikibooks` · Stack Exchange sets:
`electronics, diy, ham, outdoors, gardening, mechanics, medicalsciences, physics,
chemistry, security, stackoverflow`

### 8.2 Non-Kiwix essentials (all free)
- **Hesperian guides** — *Where There Is No Doctor / Dentist* (hesperian.org)
- **NEETS** — Navy Electricity & Electronics Training Series, 24 public-domain
  modules, ~48 MB total (`archive.org/details/NEETSModules`). Best free electronics
  education in existence; modules 10 + 17 cover most RF/antenna needs.
- **USDA Complete Guide to Home Canning** — free, authoritative, altitude-aware
- **US Army field manuals** · **Survivor Library** (pre-1940 trades — the
  rebuild-from-scratch tier) · **OpenStreetMap extracts** (Geofabrik) + Organic Maps ·
  **USGS topo quads** · WHO/CDC water-treatment guides · Merck Veterinary Manual
- **Datasheets for every part you own** + your radios' board schematics + **your
  vehicle's factory service manual** (the single most under-collected high-value item)
- Rip your own copies: ARRL Handbook, Machinery's Handbook, reloading manuals

### 8.3 The RAG rule that prevents self-inflicted hallucination
**Datasheets and tables never go in the vector store.** Chunking slices a pin table
across boundaries; retrieval returns half a pinout with no header; the model fills the
gap. Prose (notes, articles, wiki text) gets vector-indexed; **datasheets/tables/load
data stay a browsable file tree**, and the AI's job is to return a *filename and page
number*.

---

## 9. ⚠ RETRIEVAL-ONLY DOMAINS — THE SAFETY SECTION

Six domains where a hallucinated answer causes physical harm. In these, the system
**retrieves and displays source text verbatim, with citation. It never generates,
interpolates, converts units, or improvises. Enforced in code** (`safety_router.py`),
not in a prompt.

1. **Medical** — return the WikEM/Hesperian passage + title. No model in the loop.
2. **Ammunition reloading** — a wrong charge is a detonation. Manufacturer data for
   the exact component combo only (Hodgdon/Alliant/Vihtavuori/Accurate all publish
   free online — scrape now; SAAMI publishes cartridge/chamber drawings free). Never
   interpolate between loads, never substitute a component and keep the charge, never
   convert between powders. Cite manual + edition. Start low, work up.
3. **Home canning** — botulism. Times are a function of jar, density, and **altitude**
   (6,000 ft changes every number). USDA verbatim or nothing.
4. **Electrical sizing** — ampacity, fusing, PV strings, lithium charge parameters.
   "The model remembered the equation wrong" is a fire. Show the table.
5. **Structural / rigging** — spans, lifting, anchors, pressure vessels. Source-bound.
6. **Water treatment dosing** — WHO/CDC/EPA tables only.

Every AI answer in the system labels its provenance —
`SOURCE:` / `INTERPRETATION:` / `MODEL INFERENCE:` — so no sentence borrows authority
it didn't earn.

---

## 10. COMMS LAYER (Meshtastic) — CONDENSED

**Security reality, before you buy:**
- The default LongFast channel key is **publicly known** — any stock node reads it.
  Treat primary as a public bulletin board (and keep relaying on it — that's the
  community service). Private traffic goes on a **secondary channel with a random
  256-bit PSK**, or better, **direct messages** (firmware 2.5+ DMs use real
  public-key crypto).
- **MQTT bridging is publishing** — it uploads mesh traffic to a broker. Know that
  before enabling it.
- **A fixed roof node is an RF beacon at your address.** Position broadcast puts your
  house on public node maps; direction-finding works regardless of encryption. Set
  position precision low/off; meaningless node name.

**Hardware quick sheet:** SX1262-based boards over SX1276 (lower receive current,
better sensitivity) · USB dongle into the Pi over a HAT (simpler, reflashable,
keeps PCIe for the NVMe) · base antenna **5.8–6 dBi, not 10** (high-gain omnis flatten
the beam and miss uphill/downhill nodes — this is hill country) · buy the antenna KIT
with 400-grade coax (25 ft of 400-grade loses *less* than 15 ft of thin stuff) ·
**SMA ≠ RP-SMA** (WiFi antennas won't work; Heltec V3 needs an IPEX pigtail) · $40
coax surge arrestor, grounded at entry · **never power a LoRa board without an
antenna attached.**

**The Oracle bot** (`lora_oracle.py`): Meshtastic payloads top out ~230 usable bytes —
design to **200 characters, enforced in code**. It's a remote command line into the
knowledge system, not "ChatGPT over radio":

```
?power → BAND GREEN | BAT 13.4V | PV 184W | TODAY 1.42kWh
?med dehydration → WIKEM: DEHYDRATION | <verbatim opening text> | FULL TEXT AT NODE
?find sx1262 → SX1262 | LOC: bin 3 | DS: datasheets/radio/sx1262.pdf | SUB: <part>
?ask <q> → small model, labeled AI:, disabled until you configure it
```

`?power` appends `STALE 22min` if the telemetry stopped updating — old numbers
presented as current are a lie a battery system can't afford.

DM-only, one query/minute/node. **Airtime is a commons** — a chatty bot on the public
mesh makes you the neighborhood problem in a week.

**Decide who may query it.** The bot ships open (with a loud warning at startup) so
bench testing is painless, but on a real mesh set `AUTHORIZED_SENDERS` to your own
people's node numbers. Everyone else then gets silence — zero airtime spent, denial
logged locally. This matters more than it sounds: **`?power` tells a stranger whether
anyone is home and how much reserve you have, and `?find` tells them what you own.**

**You can try all of this with no radio.** `python lora_oracle.py --demo` gives you the
same commands at your keyboard, running the real lookup code against your real Kiwix
library; `python power_monitor.py --demo` runs a synthetic sun through the real battery
band logic. Run both in two terminals and type `?power` — that's the entire Tier-0 loop,
zero hardware.

---

## 11. BUILD ORDER (every step useful on its own)

0. **Try it on the computer you're reading this on.** Clone the repo, run the demo
   modes and `python safety_router.py --test`. Twenty minutes, $0, and you'll know
   whether you want the rest.
1. **Pi + Kiwix + `wikipedia_en_all_mini`.** One evening. Offline Wikipedia at 8 W —
   this alone justifies the project. Enable the hardware watchdog while you're in
   there.
   ⚠ **The trap that stops everyone on day one:** in kiwix-serve URLs (and in the
   Oracle's config), a book's name is the **ZIM filename stem** —
   `wikem_en_all_maxi_2026-07`, not the catalog name `wikem_en_all`. Guess wrong and
   you get a 404 and assume you broke something. The Oracle now probes the server and
   auto-discovers the right name; when configuring anything by hand, copy the name
   exactly as the server's own catalog prints it.
2. **Add WikEM + Hesperian + iFixit + Appropedia.** Second evening.
3. **Ollama + a 4 B model on the Pi.** Slow but real. Proves the software path.
4. **Open WebUI + your own PDFs.** First genuinely useful AI moment — it answers
   questions about *your* documents with citations.
5. **Layer 0 + Layer 3 for gear you own.** `INVENTORY.csv` + datasheets. Boring.
   Decisive. Outranks downloading more models.
6. **Power: your tier's build.** Battery → controller → panel → fuses → DC-DC bucks.
7. **Log two winter weeks** before trusting any solar math — yours or mine.
8. **Comms:** USB LoRa on the Pi, antenna + surge arrestor, channels, Oracle.
9. **Tier 1 box, if wanted.** Measure it; snapshot working runtimes.
10. **Archive the toolchain** (installers, firmware binaries for your exact boards,
    Python wheels, OS images). Then the only test that counts:
11. **Unplug the router and rebuild from your archive on a spare machine.** Whatever
    you had to guess at is your gap list. An untested backup is a rumor.

---

## 12. VALIDATION — THE ONLY TEST THAT MEANS ANYTHING

Pick a real task: reflash a bricked node · diagnose a non-charging MPPT · find the
canning time for green beans at 6,200 ft · locate a substitute in your own inventory
for a dead regulator. **Router unplugged, archive only.** Run it once per winter and
after every hardware change.

---

## 13. WHAT THIS COSTS, HONESTLY

| | Tier A | Tier B | Tier C |
|---|---|---|---|
| Power | $0–150¹ | $400–700 | $1,100–1,900 |
| Compute (Pi node) | ~$250 | ~$250 | ~$250 |
| Comms (radio+antenna+coax) | ~$60–120 | ~$120–200 | ~$150–250 |
| AI workstation | — | optional +$1,500 | optional +$1,500 |
| **Total, no workstation** | **~$310–520** | **~$770–1,150** | **~$1,500–2,400** |

¹ assuming an owned panel or power station.

² The AI workstation row assumes buying new. A mini PC or laptop you already own,
plus RAM, very often covers it — see §7.

---

## 14. SCAVENGE APPENDIX — THE PARKING-LOT DOCTRINE

For the day the market column stops existing. **Target systems, not parts:**

- **A car is a power plant:** ~1 kWh of storage + a 100 A+ alternator + a generator
  with a fuel tank. The battery is the *least* valuable component. The pattern that
  matters: engine at fast idle (1,200–1,500 RPM — at true idle an alternator makes
  under half its rating) → DC-DC charger → your bank. Capturing an idle that's
  happening anyway costs ~$0.50–0.90/kWh; idling *in order to* charge costs $3–4/kWh.
  **Never couple lithium directly to an alternator** — near-zero internal resistance
  runs the alternator flat-out until it cooks, and a BMS disconnect mid-charge
  (load dump) spikes the vehicle's whole 12 V bus. A DC-DC charger isolates,
  current-limits, and runs the right profile.
- **Load-test before you haul.** $25 tester; keepers hold >50% rated capacity;
  the rest are $10–25 core-charge refunds.
- **Salvage lead runs in parallel, shallow, as a buffer.** Never series, never deep.
- **Other high-value salvage:** pure-sine inverters from RVs · MC4 leads and mounts
  from any abandoned install · deep-cycle GC2s from golf carts (often better bones
  than car batteries) · alternators themselves (a rewound alternator + an engine =
  a generator) · UPS units (the electronics, not the tired battery).

---

## 15. FINAL HONEST ASSESSMENT

The most likely way this project dies: **under-budgeted winter** — snow on the array,
heater draw unbudgeted, a multi-day storm — browning out the node while the recovery
procedure sits untested and the datasheet layer sits empty, leaving a model that
invents pinouts. Every structural choice above traces back to that sentence.

And the ceiling, stated plainly: nobody in a garage makes a semiconductor. "Keeping
technology alive" is two different jobs — (1) extend the life of existing artifacts
(datasheets, service manuals, substitution data), and (2) rebuild the
pre-semiconductor tier from scratch (Survivor Library, Machinery's Handbook, the
Gingery lathe-from-scrap sequence). Wikipedia is the connective tissue. Build the
library first. Add the librarian second. Collect the datasheets third.

---

## APPENDIX — ADVERSARIAL REVIEW PROMPT

Improve this doc: paste it into any capable AI with the following, and bring findings
back to the group.

```
You are reviewing a public build guide for an off-grid knowledge server. Be
adversarial and specific. Findings only — no summary, no compliments.

1. ELECTRICAL SAFETY: check every number — cold-Voc math and the 80% margin rule
   (§4), fuse sizing, DoD limits, the lead-acid rules (§3.3). Show arithmetic.
2. ENERGY BUDGET (§2): state explicitly whether any solar figure you cite is GHI
   (horizontal) or POA (tilted ~50-60 deg). They differ ~2x in December; conflating
   them invalidates your review.
3. FACTUAL ERRORS: prices, product classes, protocol claims, payload limits. State
   your training cutoff; mark what you can't verify.
4. SAFETY: are the six retrieval-only domains (§9) the right list? What's missing?
5. MISSING / CUT: rank additions by value-per-dollar; argue for deleting three things.
6. FAILURE MODE: the single most likely reason a group member's build ends as a pile
   of parts. If it matches §15, say what §15 still underestimates.
```
