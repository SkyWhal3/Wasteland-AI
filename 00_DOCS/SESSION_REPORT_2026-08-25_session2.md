# Session report — 2026-08-25, session 2 (for external review)

Briefing for reviewers catching up since the v1.6 review. Everything below
is in the repo as of commit `6653193`; this is the map, not the territory.
Deep dives: `CODE_REVIEW_2026-08-25_session2.md` (safety deltas),
`CAMP_DEPLOYMENT.md` (field architecture), `RADIO_BENCH_TEST.md` (bench
procedures). Release: v1.7 "first hardware contact" is tagged and latest.

## 1. The project touched real hardware, and the stack held

A borrowed Heltec WiFi LoRa 32 V4 became the first physical radio this
code ever met. `meshtastic_probe.py` (new, read-only by design: writes no
settings, transmits nothing, prints no keys) auto-detected it over native
USB, graded it mesh-ready against the first-power-up checklist, and
exported a full config backup into the git-ignored config tree before
anything else happened.

**The finding that reframed the radio plan: the node's database held 131
distinct nodes.** The Colorado Front Range has a large, living Meshtastic
mesh, community channel included. We are not bootstrapping a network; we
are joining one.

**An antenna investigation followed** (the borrowed unit's SMA bulkhead
had been spinning loose; it got mechanically re-secured, then went
RF-quiet). The probe grew a `--listen` passive RX mode — packets, unique
nodes, RSSI/SNR, graded GOOD/WEAK/SILENT — which caught the failure on
its first production run and, across desk/window/street sessions, split
the diagnosis: the first-floor indoor location is confirmed as a severe
RF shadow (0 packets at the desk; only decode-floor signals at the
window); the antenna itself now looks probably-healthy pending one
strong-signal outdoor datapoint. The methodology (passive RX before any
TX on a suspect feedline; reciprocity; the spinning-bulkhead-twists-the-
IPEX-pigtail failure mode) is written into RADIO_BENCH_TEST.md.

## 2. Safety architecture: one real gap closed, one domain added, one door built

- **Closed gap (tightening):** `?ask` never actually consulted
  `safety_router` — the fence on the model path was docstring-advisory.
  It now routes BEFORE any model call, with smoke tests. This mattered
  double because of what follows.
- **Uplink gateway (ships disabled):** with a backend configured, a key
  in the environment, and a live uplink (cached probe), `?ask` answers
  via a frontier model labeled `NET:`, degrading automatically to the
  local model (`AI:`), then to retrieval-only. The fallback chain ends
  LOCAL by design; the fence is identical for every brain. New `?net`
  reports which brain is on duty.
- **Eighth fenced domain (provisional): `plant_edibility`.** The camp use
  case walks from "what species is this" straight into "can I eat it."
  Ingestion intent is fenced; "mushroom" fences outright; species
  identification stays free (boundary self-test included). Router
  contract now 34/34.
- **Outside-world messaging (ships disabled): `?sms` / `?email`.** A DM
  can become a real SMS (Twilio) or email (SMTP) to a NAMED contact.
  Layered code-enforced gates: requires a real AUTHORIZED_SENDERS
  allowlist (open and "*" modes refuse — first functional difference
  between open and allowlisted operation), named contacts only, no
  numbers ever transmitted over the air, persisted daily send cap,
  creds from environment only, inbound is pull-only (`?sms check`).
- **MQTT doctrine refined:** flat prohibition at camp unchanged; a
  documented deliberate-bridge procedure (dedicated channel, own PSK,
  position precision 0, one home node per side, toggled off afterward)
  now exists for deliberately linking distant groups.

## 3. The library got real

- **English Wikipedia complete with images (115 GB)** + **iFixit
  complete (3.3 GB)** downloaded, ZIM-magic validated, sha256'd,
  indexed. Corpus: **88 files, ~119 GB, verified clean.**
- Eleven manuals joined earlier the same day: Kohler CH245–CH440
  SERVICE, Yanmar L48/L70/L100 diesel SERVICE (clone rule extended to
  diesel: Chinese 170F/178F/186F singles follow the Yanmar pattern —
  procedures yes, numbers no), vintage Honda EM owner's manuals, Onan
  Emerald Plus operator + SERVICE, Heltec V4 datasheet/schematics,
  Quectel L76K pair (GPS shared by both fielded radio models).

## 4. Money and physics findings

- **BUILD_GUIDE §13 repriced for the 2026 DRAM shortage** (verified:
  Pi 5 16GB $120→$305; 2×32GB DDR4 SODIMM ~$120→$345–600). Pi purchase
  deferred — nothing on the critical path needs it; the shortage does
  not touch panels, batteries, radios, or cables.
- **The camp brain runs battery-direct:** the NUC11's board accepts
  12–24 V DC (±5%) per its TPS (two corroborating secondary sources;
  archiving the primary PDF is still a pending browser job, and the doc
  says verify before building the cable). LiFePO4 → 10 A fuse →
  center-positive barrel; no inverter, no conversion loss.
- Camp topology settled: LoRa mesh for miles (text), camp WiFi for the
  library (Wikipedia with images), Starlink as a greedily-used,
  never-depended-on uplink; nRF52840 base/relay nodes (~9 mA) because
  the mesh must outlive the table hardware's duty cycle.

## 5. Open questions for this review

1. §9 formalization of TWO provisional fence domains
   (`generator_safety`, `plant_edibility`) — stand alone, or fold into
   existing domains?
2. Is **allowlist-mode-required** the right permanent posture for every
   privileged capability (?sms/?email today; what else tomorrow)? It
   makes AUTHORIZED_SENDERS the skeleton key — deliberate, but worth an
   adversarial look.
3. The uplink doctrine ("use greedily, depend never"; fence identical
   for every brain; fallback ends local) — MANIFEST-worthy as written?
4. The MQTT deliberate-bridge recipe — any hole in it?
5. The `?sms` gate stack — what would you tighten? (Known accepted
   risks: shared inbox visible to all allowlisted senders; contact
   names transit the mesh in cleartext on the primary channel if a
   sender uses it there.)
6. Anything in `meshtastic_probe.py`'s read-only contract or the RX
   grading thresholds that looks wrong against real-world LoRa behavior.

Not in scope for review: live Twilio/SMS provisioning state (in
progress, account-side), member identities, node IDs, contact data —
deliberately absent from this public repo.

---

## Review outcome (same day) and disposition

Verdict received: *"Session 2 is a tightening session. Nothing loosens a
prior invariant. No blockers to v1.8."* Rulings and what happened next:

| # | Ruling | Disposition |
|---|---|---|
| 1 | Both domains stay **standalone**; make "all fungi fenced" explicit in §9 | Adjudicated. §9 wording → manifest owner. Code already fences fungi outright. |
| 2 | Allowlist-required is **permanent** for every privileged door; lock `?net` too | DONE: `?net` now discloses uplink status to allowlisted senders only; the standing principle + blast-radius table added to SECURITY.md; go/no-go line added to CAMP_DEPLOYMENT. |
| 3 | Uplink doctrine is MANIFEST-worthy, five invariants as listed | → manifest owner; the code already behaves per all five. |
| 4 | MQTT bridge recipe: name the broker, per-channel confirm, time-box + owner, no telemetry, verify cleanup | DONE: recipe rewritten as six steps; the probe now hard-FAILs an MQTT-enabled node, making a clean probe the cleanup receipt. |
| 5 | SMS: per-contact cap, per-sender rate limit, drop names from ACKs, master token = anti-pattern, pull-only stays | DONE: per-contact daily cap (10) + node-wide send spacing (120 s — stricter than per-sender, without plumbing sender identity into handlers); ACK no longer repeats the contact name (mixed-firmware DMs can fall back to channel-key encryption); anti-pattern documented in code + SECURITY.md. Shared inbox documented as a property. |
| 6 | RX grading: −20 dB is LongFast-typical not universal; GOOD = ≥2 nodes OR best SNR ≥ −8; reciprocity is a filter, not proof | DONE: grade rule, labels, and wording updated in code + bench doc; tests updated to the new semantics. |

Bonus finding while applying the patches: the smoke test, run on a
machine that now carries real Twilio credentials, sailed through the
credential gate and made a live API call — stopped only by its
deliberately fake phone number. The suite now scrubs all messaging
credentials from its own process before running: tests prove gates, and
must not depend on the machine they run on.
