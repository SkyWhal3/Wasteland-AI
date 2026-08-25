---
name: generator-service
description: >
  Fires on portable / inverter generator questions — won't start, hard start,
  oil and oil changes, altitude and jetting, fuel and ethanol, break-in,
  storage, load and paralleling, carbon monoxide siting, and connecting a
  generator to a building. Honda EU-series, Yamaha, Predator, Champion,
  Generac, Westinghouse, and the rest.
fires_on: [generator, genset, eu2000, eu2200, honda eu, predator 3500,
           champion dual fuel, inverter generator, pull start, recoil,
           main jet, high altitude kit, carb, carburetor, gas cap vent]
ask_first:
  - "Exact model off the sticker? EU2000i and EU2200i are different machines
     with different parts — a model that guesses between them is guessing."
  - "What altitude are you running at? Jetting changes above roughly 5,000 ft."
  - "Is it in the inventory? Run ?find <brand> — that returns the manual path."
  - "For a no-start: when did it last run, and what fuel is in it right now?"
open_these:
  - 02_CORPORA/datasheets/power/generators/GENERATOR_INDEX.md   (CHECK THIS FIRST —
    it says whether this node holds the manual for the machine in front of you)
  - 02_CORPORA/datasheets/power/generators/<model>_manual.pdf
  - "?find <brand>   — Layer 0: do we own one, where is it, which manual"
never_generate:
  - jet part numbers or drill sizes
  - oil weight, oil capacity, or service intervals
  - spark plug part numbers or gap
  - torque values
  - CO clearance distances
  - any procedure for connecting a generator to building wiring
fence: retrieval_only   # applies to the CO and backfeed sections ONLY
human_verified: false
---

## Before anything: is this machine documented here?

Open `generators/GENERATOR_INDEX.md`. It lists every manual on this node and,
just as importantly, the known gaps. Currently held: Honda EU2200i, Predator
3500 and 4400, Champion dual-fuel (3800/4250/6250 W), Onan RV (handbook plus
two operator manuals), and Generac air-cooled standby 7–16 kW.

If the machine is not on that list, the procedures below still apply — they
are engine fundamentals. **The model-specific numbers do not.** Jet, gap,
torque, capacity, clearance: from the document or not at all.

## Won't start — in this order

**1. THE OIL SENSOR. Check this before touching anything else.**
Honda inverter sets (and most modern clones) have a low-oil cutout that
*prevents starting*, and it reads the sensor's position — so a machine that is
low **or simply sitting on a slope** presents as "cranks, won't fire." This is
the single most common cause and it looks exactly like a fuel problem.
Level the machine, check the dipstick, top up per the manual, retry.
An hour of carburetor teardown has been lost to this more times than anyone
wants to admit.

**2. The boring switches.** Fuel valve on. Choke correct for temperature.
Run/stop switch on. Vent on the gas cap open (a closed vent starves it after
a minute or two of running — classic "runs then dies").

**3. Fuel age.** Ethanol fuel varnishes a pilot jet in roughly three months.
Symptoms: starts on choke, dies off choke; or runs only at full throttle.
Fresh fuel first, then the carburetor bowl, then the pilot jet. Old fuel is
the second most common cause after the oil sensor.

**4. Spark.** Pull the plug, look for fouling, check for spark against the
block. Plug type and gap: **the manual** — do not accept a remembered value.

**5. Only now** consider the carburetor, valve clearance, or the ignition coil.

## Oil

Weight, capacity, and change interval are model-specific and printed in the
manual — **open it**. Two things that are procedure, not values, and worth
saying out loud:

- Inverter generators hold a startlingly small amount of oil (well under a
  quart, typically). "Topped it up a bit" can mean overfilled.
- Break-in matters on these engines: the first oil change comes much earlier
  than the routine interval. Manual, section on break-in.

## Altitude — the part that gets invented

Above roughly **5,000 ft** a carburetted engine runs progressively rich: less
air, same fuel metering. Symptoms are power loss, sooty plug, black smoke,
fouling, and rough running under load. At Front Range altitudes this is not a
fine-tuning question — it's the difference between a generator that carries
its rated load and one that won't.

The fix is a **manufacturer high-altitude jet kit** for that exact model and
altitude band. Honda publishes the part numbers in service bulletins; the other
brands publish them in the manual or on the support site.

**Do not accept a jet number, drill size, or "just go one size smaller" from a
language model — that is the exact answer shape that gets invented.** Get the
part number from the manufacturer document for your model. Note that some kits
are altitude-*banded* (e.g. one kit for 5,000–8,000 ft, another above), so the
altitude you actually run at matters.

Also: a machine jetted for high altitude runs **lean** at sea level. If it
comes back down, the jetting goes back too.

## Carbon monoxide — RETRIEVAL ONLY (§9)

**Never indoors. That includes a garage with the door open, a carport, a
covered porch, a tent, a camper, an open window nearby, or "just for a
minute."** This is a categorical rule, not a distance to be estimated —
generator CO kills people every year, and it kills them fast enough that they
do not get up and walk out.

For **how far** from doors, windows, and vents, and for placement relative to
prevailing wind: **retrieve the number from the manual or the CDC/CPSC
guidance. Do not let a model produce a clearance distance.**

A battery CO alarm anywhere the generator runs near people is cheap. If
anyone gets a headache, nausea, or confusion around a running generator:
outside air first, questions second, then `?med carbon monoxide`.

## Connecting to a building — RETRIEVAL ONLY (§9)

Backfeeding a house through an outlet — a double-male "suicide cord" — kills
people. It energizes the line outside your house, which can kill a lineman
working to restore power, and it puts unfused live pins in your hand.

The only correct answers are a **transfer switch** or a **panel interlock kit**,
installed to code. That is an electrician-and-permit conversation, and the
procedure is **not** something this system will generate. Retrieve the code
section, the interlock manufacturer's instructions, or call a person.

Powering appliances by plugging them **directly into the generator** with
properly rated cords is a different and entirely fine thing.

## Load, fuel, storage

- **Rated vs surge**: motors (pumps, compressors, fridges) draw several times
  their running watts at startup. Sizing comes from the appliance's plate and
  the generator's *rated continuous* number, not the big number on the box.
- **Paralleling** two inverter sets requires the manufacturer's kit and
  compatible models. Check the manual before assuming yours can.
- **Storage**: either run the carburetor dry or use stabilized fuel — the
  manual says which that engine wants. Storing a carburetted engine with
  ethanol fuel in the bowl is how you create next season's no-start.
- A generator is a **charging source, not a power source**, in this
  architecture: it runs a proper battery charger sized so the engine works
  near its efficient load, rather than idling to trickle. See BUILD_GUIDE §3
  and the manifest's charging-path section.
