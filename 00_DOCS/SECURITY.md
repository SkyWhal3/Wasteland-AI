# SECURITY — threat model and hardening for the Wasteland AI stack

Written 2026-08-25. Answers the three questions everyone asks, then the
checklist. Companion to MANIFEST.md §12.1 (the radio security reality check).

---

## Q1: "Can people reach our stack over Meshtastic?"

Yes — that's the point — but through a keyhole, on purpose:

- The **only** thing listening on the mesh is `lora_oracle.py`, and it only
  reacts to **direct messages** that start with `?`. Channel traffic is
  ignored in code; the bot is structurally incapable of spamming LongFast.
- It **never initiates**. It replies, 200 chars max, one query per sender
  per minute. (A future "alert my own nodes when the battery goes BLACK"
  feature would be a deliberate design change, not a config flip.)
- **Who can query it is now a config decision:** `AUTHORIZED_SENDERS` in
  the oracle's config block. `None` = open mode (bench testing) with a loud
  startup warning. Set it to your people's node numbers before the node
  lives on a real mesh, because:
  - `?power` tells a stranger your battery reserve and, over days, your
    consumption pattern — that's **occupancy intelligence**.
  - `?find` tells a stranger **what you own and where it lives**.
  Denied senders get silence (zero airtime spent on strangers) and a local
  log line, so you can see who's knocking.
- Remember §12.1: DMs on firmware 2.5+ are public-key encrypted end-to-end;
  the default LongFast channel is NOT private; and a fixed node is an RF
  beacon regardless of any of this. The allowlist controls who gets
  *answers* — it does not hide the node's *existence*.

## Q2: "Can someone inject a virus through the radio?"

**Not through the oracle's designed paths.** What arrives by radio is a
≤237-byte text string. The oracle never executes it: there is no `eval`, no
shell call, no file write anywhere downstream of radio input. The text is
compared against five command names, and the argument goes to, at most:
a URL-encoded query to local kiwix-serve, a substring search of a CSV, or
(if you enabled `?ask`) a text prompt to local Ollama. Worst realistic
outcome: a weird reply. The radio callback also survives malformed packets
(exception-guarded) and floods (bounded queue, per-sender rate limit).

The paths malware would ACTUALLY take are boring and off-air:

| Vector | Reality | Mitigation |
|---|---|---|
| **The build machine** (this Windows box) | The stack inherits whatever built it | Standard PC hygiene; verify downloads before they enter the archive |
| **pip supply chain** | A poisoned package runs with your user's rights | Version-bounded requirements; offline wheel cache = the real pin; never `pip install` random extras on the node |
| **Downloaded models/ZIMs** | GGUF/ZIM are *data*, not executables — the realistic risk is corruption or a parser bug, not a classic virus | Get quants from reputable uploaders; `sha256` on ingest into the INDEX files; `verify_checksums.py` annually |
| **Meshtastic firmware itself** | Radio packet parsing bugs have existed in every radio stack ever | Flash from archived known-good releases; update deliberately, not automatically; keep the `.bin` that worked |
| **USB sticks / sneakernet** | The classic | Checksum on ingest; the archive is read-mostly by design |
| **pi_agent.py** | It executes model-written code ON PURPOSE | Jailed to the scratch SSD, disabled by default, per-file size caps; run it as an unprivileged user; review before promoting code out of the sandbox. The jail is a seatbelt, not a prison — its docstring says so in bold |

## Q3: "Security for login?"

The stack's services and what guards each:

- **SSH (the Pi):** key-based auth only. Generate a key on your machine
  (`ssh-keygen -t ed25519`), copy it (`ssh-copy-id`), then in
  `/etc/ssh/sshd_config`: `PasswordAuthentication no`. Don't run the
  default `pi` username. This is the single highest-value login hardening.
- **Open WebUI:** the FIRST account created becomes admin — create it
  yourself immediately after install. Leave signup disabled for strangers
  (Admin Panel → disable open registration). It listens on the LAN only.
- **kiwix-serve and Ollama:** bind to `127.0.0.1` (our configs already
  assume this). The footgun is `OLLAMA_HOST=0.0.0.0` from internet
  tutorials — that exposes an unauthenticated model API to the whole LAN.
  Don't, unless you mean to, and then firewall it.
- **The WiFi AP:** WPA2 minimum with a real passphrase (the AP's range is
  your physical perimeter plus a parking lot). The AP serves the library;
  it should not bridge to the internet in deployed mode.
- **Nothing is port-forwarded. Ever.** The stack's whole model is local.
  Remote access = Meshtastic DMs through the oracle's keyhole, or you
  physically walk to it. If you one day want real remote admin, that's a
  VPN (WireGuard) discussion, not a port forward.

## Physical / seizure reality

The node is findable by RF direction-finding (§12.1) and stealable by hand.
What's on it: your inventory (what you own, where), your power logs (when
you're home), your notes. Decide deliberately:

- **Always-on node:** full-disk encryption conflicts with unattended boot
  (someone must type a key after every power blip — on a solar system,
  that's weekly). Most groups accept plaintext here and keep the node
  physically hidden instead. Know that's the trade you're making.
- **The faraday/offsite copy: ENCRYPT IT.** It travels, it gets lost, it
  has everything. LUKS (Linux) or VeraCrypt (cross-platform) container;
  the passphrase lives in heads, plural.

## The checklist

- [ ] `AUTHORIZED_SENDERS` set before the oracle leaves the bench
- [ ] Private secondary channel: random 256-bit PSK; LongFast treated as public
- [ ] SSH: ed25519 keys, `PasswordAuthentication no`, non-default username
- [ ] Open WebUI admin account created by YOU; open signup disabled
- [ ] Ollama/kiwix on 127.0.0.1 only; no port forwards anywhere
- [ ] AP: WPA2+, strong passphrase, no internet bridge in deployed mode
- [ ] `sha256` recorded on ingest for every model/ZIM/PDF (INDEX files)
- [ ] `verify_checksums.py check` yearly (surplus scheduler's job)
- [ ] Known-good Meshtastic firmware `.bin` archived per board
- [ ] Faraday/offsite drive encrypted; passphrase known by 2+ people
- [ ] pi_agent: still disabled, or enabled with AGENT_ROOT on the scratch
      SSD and an unprivileged user
