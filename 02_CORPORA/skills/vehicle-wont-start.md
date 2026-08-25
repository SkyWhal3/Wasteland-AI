---
name: vehicle-wont-start
description: >
  Fires on a vehicle that will not start, cranks but does not fire, does not
  crank at all, or dies shortly after starting. Splits the problem correctly
  first, then points at the factory service manual for anything specific.
fires_on: [wont start, will not start, wont crank, no crank, cranks but,
           clicking noise, dead battery, jump start, alternator, starter,
           engine dies, stalls, check engine]
ask_first:
  - "Does the starter turn the engine over, or not? Everything downstream
     depends on that one answer, so establish it before anything else."
  - "Year, make, model, engine — the service manual is per-vehicle and a
     generic answer is worth very little."
  - "Battery voltage resting, and voltage WHILE cranking. A battery can read
     12.6 V and still collapse under load."
  - "What changed? Sat unused, ran out of fuel, cold snap, work done recently,
     warning light before it quit?"
open_these:
  - 02_CORPORA/datasheets/vehicle/<year_make_model>_factory_service_manual.pdf
  - "?find battery   — Layer 0, if the vehicle battery is inventoried"
never_generate:
  - torque specifications, fluid types or capacities, wiring colours
  - fuse box positions or ratings
  - anything touching brakes, restraints, or steering — those are page
    references, never prose
fence: none   # but safety systems follow the retrieval-only rule
human_verified: false
---

## Split it first: does it crank?

This single question separates two entirely different problem spaces, and
skipping it is why people replace fuel pumps to fix bad grounds.

## It does NOT crank

Electrical, almost always, and usually cheap:

1. **Battery under load.** Resting voltage lies. A battery reading 12.6 V at
   rest can collapse to 8 V the instant the starter engages. Measure while
   cranking, or load-test it properly.
2. **Terminals and grounds.** Corrosion at the posts, and — the one people miss
   — the **engine-to-chassis ground strap**. A bad ground produces the full
   theatre of weird symptoms: dash lights dimming, rapid clicking, starter
   silence.
3. **Rapid clicking** usually means not enough current: battery, cable, or
   connection. **A single loud clunk** and nothing points more toward the
   starter solenoid or the starter itself.
4. **Safety interlocks.** Automatic transmissions will not crank out of Park or
   Neutral, manuals need the clutch fully down, and the switch that senses this
   fails more often than people expect. Try Neutral if you are in Park.
5. **Immobiliser or security.** A blinking security light on the dash means the
   vehicle is refusing on purpose. That is a manual procedure, not a mechanical
   fault, and it is usually key or transponder related.

## It cranks but does not fire

Then it is missing fuel, spark, air, or compression — and in the field you can
usually establish which:

1. **Fuel.** Do you hear the pump prime when the key goes to ON? Is there
   actually fuel in the tank, and is the gauge trustworthy? Stale fuel after a
   long sit is extremely common on seasonal vehicles and small engines alike.
2. **Spark.** Pull a plug, look at it, check for spark against a good ground.
   A plug soaked in fuel means you have fuel and no ignition, which is already
   half the diagnosis.
3. **Air.** Blocked intake, collapsed hose, or — after standing outside for
   months — a rodent nest. Look before disassembling.
4. **Compression.** A timing belt or chain that has skipped or snapped gives a
   healthy, unusually fast, unusually smooth crank with no hint of firing.
   That is the sound of an engine with no compression, and on many engines it
   also means internal damage.
5. **Cold.** Diesels have their own cold-start systems and their own procedure.
   Follow the manual for that vehicle rather than general advice.

## Where the answers actually live

Anything specific — a torque value, a fuse position, a relay location, a wire
colour, a test procedure with numbers — comes out of the **factory service
manual for that exact vehicle**. The manifest calls the FSM the highest-value
under-collected document in the whole archive, and this is why: a generic
answer is often close enough to be believable and wrong enough to waste a day.

**Brakes, restraints, and steering are page references, not paragraphs.** The
system retrieves the procedure; it does not summarise it.
