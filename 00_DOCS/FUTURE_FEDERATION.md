# FUTURE: FEDERATION — specialist nodes exchanging knowledge claims

```
STATUS:    design sketch. Nothing here is built, scheduled, or promised.
PREREQS:   your node boots, survives a winter, and passes §16 validation.
           Federation is what working nodes do, not what unbuilt nodes plan.
ORIGIN:    sparked by an external review of this repo (ChatGPT, 2026-08),
           formalized and constrained here against the manifest's rules.
```

## The idea in four sentences

One Wasteland node can't hold everything, and doesn't need to. Node A goes
deep on electronics + radio; Node B on agriculture + water; Node C on
machine tools + metallurgy; Node D on medicine. A low-bandwidth protocol
lets them exchange **knowledge claims** — questions, measurements,
procedures, warnings — over the Meshtastic mesh they already share. Not
model chatter: **claims with provenance**, checkable against documents.

The industrial revolution didn't stop at better individual machines; it
built systems of them. Same move, cognitive version — with no central AI
provider anywhere in the loop.

## The message types

| Verb | Meaning | Example payload |
|---|---|---|
| `Q` (QUESTION) | I need an answer from your specialty | `Q metallurgy: case-harden 1018 with charcoal — send PROCEDURE` |
| `SRC` (SOURCE_REQUEST) | Send/confirm a document I lack | `SRC sha:9f31ab — do you hold this? size?` |
| `OBS` (OBSERVATION) | Something seen, timestamped, located | `OBS 2026-11-03: elk moved early, Rampart Range` |
| `MEAS` (MEASUREMENT) | An instrument reading | `MEAS well 2: 41 ppm nitrate, strips lot B` |
| `PROC` (PROCEDURE) | A worked, sourced how-to | `PROC solder SMD w/ skillet — SRC ifixit#… sha:44c1` |
| `DISC` (DISCOVERY) | New capability/resource/technique | `DISC salvaged 500x 18650, testing capacity` |
| `WARN` (WARNING) | Hazard, time-sensitive | `WARN water: giardia suspected Fountain Ck @ mile 12` |

A claim that fits one LoRa DM (≤200 chars), fully dressed:

```
WARN water: giardia suspected, Fountain Ck @ mile 12
SRC WHO_water_2017.pdf#p44 sha:9f31ab
BY !a1b2c3 (human:AF) 2026-08-25
```

## The one design move that makes it real: **cite by hash**

Node A never sends "here's how to treat the water." It sends a claim plus
`sha:9f31ab` — the checksum of the source document, as recorded in its
`CORPUS_INDEX.csv`. Node B looks that hash up in its OWN index:

- **Holds it** → the claim is verifiable locally, against B's own copy.
- **Doesn't** → the honest state is "unverified claim + a fetch target,"
  and B can `SRC`-request the document by sneakernet or scheduled transfer.

This turns gossip into checkable references, and it's why everyone running
`verify_checksums.py` against the same public corpora quietly matters:
**shared checksums are the federation's truth anchors.** Two nodes that
both hold `sha:9f31ab` don't have to trust each other — they trust the
document, which neither can silently alter. (Hashes are already in the
INDEX file schemas; this is the payoff.)

The claim format at rest already exists too: it's the `seed_qa/`
frontmatter (question / answer / source / `human_verified`). The wire
format is that, compressed to airtime.

## The two hard problems (skip these and the idea is a hazard)

### 1. Claims are DATA, never instructions

A `WARN` or `DISC` arriving by radio is the mesh-native version of prompt
injection. Rules:

- No received claim is ever executed, auto-applied, or fed to a model as
  an instruction. Claims are *displayed to humans* and *filed with
  provenance*.
- Every claim carries `BY`: node id + a human's initials + date. Meshtastic
  2.5+ DMs are public-key signed/encrypted — the node id is cryptographically
  meaningful; the humans behind the nodes are the actual trust layer.
- `human_verified` travels with the claim and is displayed. A claim drafted
  by a model and unsigned by a person is marked exactly that, or better,
  never sent (see invariant 4).
- Received claims land in a quarantine log, not in the corpus. Promotion
  into `seed_qa/` or the corpus is a human act.

### 2. THE FENCE SURVIVES FEDERATION

The six retrieval-only domains (§9) do not soften because the answer came
from a friend's node. **Invariant: in the six domains, a claim IS a
hash-cited pointer to an authoritative document, or it does not exist.**
A remote `PROC` for canning times or a charge weight, however trusted the
sender, is displayed with its source or refused. Remote text never bypasses
the local safety router; there is no "but Node D is the medical node"
exception — Node D's authority is that it *holds WikEM and Hesperian*, and
the hash citation is how it proves that per-claim.

## The invariants (v0 contract)

1. Claims are data, never instructions. Humans read; humans act.
2. Six-domain claims are hash-cited pointers to documents — or refused.
3. Everything inbound passes the LOCAL safety router before any local
   model sees it.
4. Models don't make claims. Humans make claims (a model may draft; a
   human signs, and the signature is the `BY` line).
5. Airtime is a commons: claims budgeted per node per day, no automatic
   re-forwarding (the mesh already floods at the packet layer — the
   protocol must not flood at the claim layer).
6. No hub. Any node can leave; nothing central breaks. A node's authority
   is its corpus + its human, never its position in the network.

## The embarrassing secret: v0 is mostly already built

The Oracle already speaks half the verbs, unidirectionally: `?power` is a
`MEAS` server, `?med` is `SRC`+snippet, `?find` is a `Q` against Layer 0.
The v0 experiment is two nodes and a weekend:

1. Both nodes: allowlists set (SECURITY.md), corpora checksummed, PKC
   firmware confirmed.
2. Add two Oracle commands: `?src <sha-prefix>` ("do you hold this? →
   title/size/OK") and `?claim <verb> <text>` (files inbound claims to the
   quarantine log with sender + timestamp; replies `FILED`).
3. Exchange one of each claim type by hand between two humans at two
   keyboards. Read the quarantine logs. Feel what's missing.
4. THEN argue about chunking (multi-part claims), store-and-forward for
   sleeping nodes, and claim expiry — with data, not vibes.

## Non-goals, permanently

- Relaying model output between nodes ("my AI told your AI") — the
  bandwidth prevents it and the philosophy forbids it.
- Auto-executing anything received.
- Any central registry, coordinator, or blessed super-node.
- Building any of this before the §14 build order is done. The little
  10 W node earns the network by existing first.
