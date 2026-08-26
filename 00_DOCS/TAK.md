# TAK and the mesh — a recipe, not a feature

Written 2026-08-25 after external review. Short version: **ATAK support
already exists upstream in Meshtastic. We configure it; we do not build
it.** The Oracle is a text librarian. TAK is a map/situational-awareness
product. Wiring a CoT encoder into `lora_oracle.py` would turn the
library into a position beacon and an airtime hog, and duplicate an
official plugin that does it better.

## If a hiker wants dots on a map (Phase 1 — config only)

1. Android phone runs **ATAK-CIV** plus the **official Meshtastic ATAK
   plugin** (from the plugin's GitHub releases — the plugin build must
   match the ATAK version; document which pair worked).
2. Their radio's role: **TAK** (phone attached) or **TAK_TRACKER**
   (radio-only position beacon).
3. **TAK traffic gets its own channel** with its own PSK — never the
   public LongFast primary, never the group channel. Position-report
   floods are exactly what a 131-node metro mesh does not need, and the
   plugin maintainers themselves warn against LongFast with many users.
4. Position precision on the TAK channel: the group decides, knowing
   it's a map product — but the GROUP channel keeps precision LOW and
   the public channel keeps whatever it already had. Split channels
   rather than raise precision anywhere.
5. Slow the PLI (position) interval. A map that updates every 60–120 s
   is a map; one that updates every 5 s is a jammer.

## What the Oracle does about TAK: nothing

- LIBR stays role **CLIENT**, position precision 0, telemetry minimal.
  The librarian is a *destination*, not infrastructure and not a track.
- No CoT encoding, no fountain file transfer, no voice, no payments.
  Different products; out of scope on the library node.
- A "TAK server relay" is an uplink. It gets treated exactly like MQTT:
  **off at camp**, and any deliberate use follows the bridge procedure
  in CAMP_DEPLOYMENT (broker/server you control, time-boxed, named
  owner, probe-verified off afterward).

## Phase 2, someday, maybe

If the group ever wants the Library to appear as a map marker: a tiny
standalone script (new file, NOT the oracle) emitting one slow PLI for a
fixed position. That is a privileged door — ships disabled, requires the
allowlist, same rules as ?sms. It does not exist today and nothing
requires it to.

## The one-line rule

Hikers who want ATAK get a channel, a role, and an interval. The
library gets left alone.
