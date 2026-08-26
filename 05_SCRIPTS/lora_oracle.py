#!/usr/bin/env python3
"""
lora_oracle.py — the mesh bot. A remote command line into the knowledge node,
reachable over Meshtastic from miles away. NOT "ChatGPT over radio."

Commands (send as a DIRECT MESSAGE to this node):
  ?help              list commands
  ?power             battery/solar snapshot  (reads power_monitor.py's latest.json)
  ?med <query>       RETRIEVAL-ONLY medical lookup from Kiwix (WikEM) — no AI
  ?find <query>      look up a part in INVENTORY.csv (Layer 0, manifest §7.1)
  ?ask <question>    a model, behind the fence — OFF until configured. With an
                     uplink (Starlink at camp) and NET_BACKEND set, a frontier
                     model answers, labeled "NET:". Otherwise local Ollama,
                     labeled "AI:". The safety_router routes BEFORE either —
                     fenced domains get no model answer from any brain.
  ?net               uplink status: which brain answers ?ask right now

Design rules, enforced in code (not vibes):
  * DM-ONLY. Channel messages are ignored — this bot cannot spam the mesh.
  * 200-character cap on every reply (Meshtastic usable payload is ~230 bytes).
  * One query per sender per RATE_LIMIT_S seconds.
  * ?med never touches a language model. Retrieval only. See manifest §9.
  * The radio callback does NO slow work. It validates, rate-limits, and
    queues; kiwix/Ollama lookups run in the main loop. The meshtastic library
    delivers packets on its own worker thread — blocking that thread for
    seconds (or 2 minutes, for ?ask) would stall the whole radio interface.

Run:  python lora_oracle.py     (Meshtastic node on USB; kiwix-serve running)
"""

from __future__ import annotations

import csv
import html
import json
import os
import queue
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import safety_router  # the fence runs BEFORE any brain, local or cloud

try:
    import requests
except ImportError as e:
    print(f"Missing dependency ({e}). Run: pip install -r requirements.txt",
          file=sys.stderr)
    sys.exit(2)
# The radio libraries (meshtastic, pubsub) are imported inside main() —
# --demo mode runs the full command pipeline with no radio and no radio deps.

# ----------------------------- CONFIG ---------------------------------------
SERIAL_PORT = None                 # None = auto-detect the Meshtastic node
MAX_CHARS = 200                    # hard reply cap — do not raise casually
MAX_BYTES = 230                    # the radio's real ceiling is BYTES
RATE_LIMIT_S = 60                  # per-sender cooldown
KIWIX_URL = "http://127.0.0.1:8080"
KIWIX_BOOK = "wikem_en_all"        # must match a book kiwix-serve is serving
LATEST_JSON = Path("latest.json")  # written by power_monitor.py
STALE_AFTER_S = 300                # ?power warns if telemetry is older than this
ORACLE_LOG = Path("oracle.log")

# Layer 0 inventory — first existing path wins. The second entry matches the
# manifest §13 layout when this script runs from 05_SCRIPTS/.
INVENTORY_CANDIDATES = [
    Path("INVENTORY.csv"),
    Path(__file__).resolve().parent.parent / "00_INVENTORY" / "INVENTORY.csv",
]

# ?ask stays disabled until you set a model, e.g. "qwen2.5:3b" pulled in Ollama.
OLLAMA_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = None                # None = ?ask disabled (safe default)

# --- Uplink backend: ?ask via a frontier model WHEN the internet exists ----
# The gateway play (00_DOCS/CAMP_DEPLOYMENT.md): a hiker with a $30 node and
# no phone signal DMs the oracle; if the camp Starlink is up, the answer
# comes from a frontier model and is labeled "NET:"; the moment the dish
# sleeps, ?ask falls back to the local Ollama model ("AI:") with no config
# change. Two invariants, enforced in code:
#   1. The safety fence routes the question BEFORE any brain sees it. The
#      six-plus fenced domains are retrieval-only no matter how smart the
#      backend is — a frontier model produces a *plausible* med dose, and
#      plausible-but-unverified is exactly what the fence exists to block.
#   2. The uplink is treated as temporary by design. Every net path has a
#      local fallback; nothing breaks when the internet goes away.
# Ships disabled (None), same rule as OLLAMA_MODEL. The API key comes from
# the environment variable named below — never from this file, which is why
# this file can live in a public repo.
NET_BACKEND = None                 # None = local-only node; "anthropic" = on
NET_MODEL = "claude-opus-5"        # current Anthropic model id (2026-08)
NET_KEY_ENV = "ANTHROPIC_API_KEY"  # env var holding the key
NET_URL = "https://api.anthropic.com/v1/messages"
NET_TIMEOUT_S = 45
NET_PROBE_TTL_S = 300              # re-probe the uplink at most this often

# Who may use this oracle. Three settings, in hardening order:
#   None        OPEN (bench default): anyone can query; loud warning at boot.
#   "*"         OPEN, EXPLICITLY: same behavior, but on record as a choice.
#               Configs written with "*" will survive a future release where
#               the default flips to deny-all (planned production posture —
#               see 00_DOCS/SECURITY.md).
#   {123, 456}  ALLOWLIST (deployed): only these node numbers get replies;
#               everyone else gets silence (zero airtime) + a local log line.
# Node numbers come from this script's startup line or `meshtastic --nodes`.
# Why it matters: ?power reveals whether anyone is home and how much reserve
# you have; ?find reveals what you own.
AUTHORIZED_SENDERS: set[int] | str | None = None

MAX_LOG_BYTES = 1_000_000          # oracle.log rotates past this (SD cards die)
# ---------------------------------------------------------------------------

_last_seen: dict[int, float] = {}   # sender node number -> last-served time
_JOBS: queue.Queue = queue.Queue(maxsize=8)   # radio thread -> worker,
                                    # bounded so a burst can't eat RAM
MY_NUM: int | None = None           # our node number, set in main()


def clip(s: str) -> str:
    """The one non-negotiable function in this file. Caps by CHARACTERS for
    humans and by UTF-8 BYTES for the radio — Meshtastic's payload limit is
    bytes, and '°' is two of them."""
    s = " ".join(s.split())                       # collapse whitespace
    if len(s) > MAX_CHARS:
        s = s[:MAX_CHARS - 1] + "…"
    while len(s.encode("utf-8")) > MAX_BYTES:
        s = s[:-2] + "…"
    return s


def log(line: str) -> None:
    stamp = datetime.now().isoformat(timespec="seconds")
    try:                    # size-capped: keep the current log + one .old
        if ORACLE_LOG.exists() and ORACLE_LOG.stat().st_size > MAX_LOG_BYTES:
            ORACLE_LOG.replace(ORACLE_LOG.with_suffix(".log.old"))
    except OSError:
        pass                # logging must never take the oracle down
    with open(ORACLE_LOG, "a", encoding="utf-8") as f:
        f.write(f"{stamp} {line}\n")
    print(f"{stamp} {line}")


# ----------------------------- commands -------------------------------------

def cmd_help(_arg: str) -> str:
    return ("CMDS: ?power | ?med <q> | ?find <part> | ?ask <q> | ?net. "
            "?med is retrieval-only. NET:=frontier AI:=local. Library at node WiFi.")


def cmd_power(_arg: str) -> str:
    try:
        d = json.loads(LATEST_JSON.read_text())
    except (OSError, json.JSONDecodeError):
        return "POWER: no data (is power_monitor.py running?)"
    parts = [f"BAND {d.get('band', '?')}"]
    if d.get("demo"):
        parts.insert(0, "DEMO")          # synthetic telemetry, say so
    if d.get("batt_V") is not None:
        parts.append(f"BAT {d['batt_V']}V")
    if d.get("soc_pct") is not None:
        parts.append(f"SOC {d['soc_pct']:.0f}%")
    if d.get("pv_W") is not None:
        parts.append(f"PV {d['pv_W']:.0f}W")
    if d.get("yield_today_kWh") is not None:
        parts.append(f"TODAY {d['yield_today_kWh']}kWh")
    # Old data presented as current is a lie — say when the monitor went quiet.
    try:
        age = (datetime.now(timezone.utc)
               - datetime.fromisoformat(d["utc"])).total_seconds()
        if age > STALE_AFTER_S:
            parts.append(f"STALE {int(age // 60)}min — monitor down?")
    except (KeyError, ValueError, TypeError):
        parts.append("STALE ?")
    return " | ".join(parts)


def _strip_html(markup: str) -> str:
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", markup, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)        # &lt;35&#176;C -> <35°C (after tag strip)
    return " ".join(text.split())


_BOOK_CACHE: str | None = None


def _kiwix_book() -> str:
    """Return a book name the server ACTUALLY serves.

    The #1 predicted support issue, confirmed against a live kiwix-serve
    3.8.1: URL book names are the ZIM filename stem (e.g.
    'wikem_en_all_maxi_2026-07'), NOT the catalog name ('wikem_en_all') and
    not whatever a doc said last year. So: try the configured KIWIX_BOOK,
    and if the server doesn't know it, read the server's own catalog for
    its /content/<name> links, prefer a wikem-ish one, probe it, cache it.
    """
    global _BOOK_CACHE
    if _BOOK_CACHE:
        return _BOOK_CACHE

    def probe(name: str) -> bool:
        try:
            r = requests.get(f"{KIWIX_URL}/suggest",
                             params={"content": name, "term": "a"}, timeout=5)
            return r.ok
        except requests.RequestException:
            return False

    if probe(KIWIX_BOOK):
        _BOOK_CACHE = KIWIX_BOOK
        return _BOOK_CACHE
    try:
        cat = requests.get(f"{KIWIX_URL}/catalog/v2/entries", timeout=5).text
    except requests.RequestException:
        return KIWIX_BOOK              # server unreachable; caller reports it
    names = re.findall(r'href="/content/([^"/]+)"', cat)
    names.sort(key=lambda n: "wikem" not in n.lower())    # wikem-ish first
    for name in names:
        if probe(name):
            log(f"KIWIX_BOOK '{KIWIX_BOOK}' not served; auto-discovered '{name}'")
            _BOOK_CACHE = name
            return name
    return KIWIX_BOOK


def _kiwix_article_html(book: str, path: str) -> str | None:
    """Fetch an article's raw HTML from kiwix-serve.

    The suggestion 'path' is relative to the book. Current kiwix-serve
    serves content at /content/<book>/<path> (verified live on 3.8.1);
    older builds used /<book>/<path>. Try both so one script spans versions.
    """
    for url in (f"{KIWIX_URL}/content/{book}/{path}",
                f"{KIWIX_URL}/{book}/{path}"):
        try:
            r = requests.get(url, timeout=10)
        except requests.RequestException:
            return None
        if r.ok:
            r.encoding = "utf-8"      # ZIM HTML is UTF-8; don't let a missing
            return r.text             # charset header mojibake the degrees
    return None


def cmd_med(query: str) -> str:
    """RETRIEVAL ONLY. Finds the best-matching WikEM article via kiwix-serve's
    /suggest endpoint and returns title + opening text + where to read it.
    No language model is involved in this path, by design (manifest §9)."""
    if not query:
        return "Usage: ?med <topic>   e.g. ?med tourniquet"
    book = _kiwix_book()
    try:
        r = requests.get(f"{KIWIX_URL}/suggest",
                         params={"content": book, "term": query},
                         timeout=10)
        r.raise_for_status()
        suggestions = r.json()
    except (requests.RequestException, ValueError):
        return "WIKEM: node's kiwix-serve unreachable."

    # Real article suggestions have kind == "path" and a path; the list may
    # end with a kind == "pattern" full-text-search row we must skip.
    hits = [h for h in suggestions if h.get("kind") == "path" and h.get("path")]
    if not hits:
        return f"WIKEM: no match for '{query}'. Try another term."

    # 'value' is the plain title; 'label' can carry <b>…</b> highlight markup
    # (we are NOT sending HTML over a 200-char radio message).
    title = hits[0].get("value") or re.sub(r"<[^>]+>", "",
                                           hits[0].get("label", query))
    html = _kiwix_article_html(book, hits[0]["path"])
    snippet = ""
    if html:
        snippet = _strip_html(html)
        # drop the leading title repetition if present
        if snippet.lower().startswith(title.lower()):
            snippet = snippet[len(title):].lstrip(" -:")
    head = f"WIKEM: {title.upper()} | "
    tail = " | FULL TEXT AT NODE"
    room = MAX_CHARS - len(head) - len(tail)
    return head + snippet[:max(room, 0)] + tail


def cmd_find(query: str) -> str:
    """Layer 0 lookup: search INVENTORY.csv, return location + datasheet path."""
    if not query:
        return "Usage: ?find <part>   e.g. ?find sx1262"
    inv = next((p for p in INVENTORY_CANDIDATES if p.exists()), None)
    if inv is None:
        return "No INVENTORY.csv yet. Build Layer 0 (manifest §7.1)."
    q = query.lower()
    try:
        with open(inv, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                hay = " ".join(str(v) for v in row.values()).lower()
                if q in hay:
                    return (f"{row.get('part_number', query).upper()}"
                            f" | LOC: {row.get('location', '?')}"
                            f" | DS: {row.get('datasheet_path', 'none')}"
                            f" | SUB: {row.get('compatible_substitute', '-')}")
    except OSError as e:
        return f"Inventory read error: {e}"
    return f"Not in inventory: '{query}'"


# --------------------------- uplink gateway ---------------------------------

_NET_STATE = {"ok": False, "at": 0.0}   # cached probe result


def net_up(force: bool = False) -> bool:
    """Is the internet reachable RIGHT NOW? Cached for NET_PROBE_TTL_S so a
    down uplink doesn't add a timeout to every ?ask. Any HTTP response at all
    (even a 4xx) proves DNS + TCP + TLS work; only a transport error is 'down'."""
    if NET_BACKEND is None:
        return False
    now = time.monotonic()
    if not force and now - _NET_STATE["at"] < NET_PROBE_TTL_S:
        return _NET_STATE["ok"]
    try:
        requests.head("https://api.anthropic.com", timeout=4)
        ok = True
    except requests.RequestException:
        ok = False
    _NET_STATE.update(ok=ok, at=now)
    return ok


def _ask_net(question: str) -> str | None:
    """One frontier-model call over the uplink, radio-shaped. Raw HTTP on
    purpose: this project keeps dependencies minimal and version-bounded, and
    the oracle already speaks plain requests to kiwix and Ollama. Returns None
    if the model refused or produced nothing — caller falls back to local."""
    key = os.environ.get(NET_KEY_ENV)
    r = requests.post(
        NET_URL,
        headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={"model": NET_MODEL,
              "max_tokens": 1000,   # covers adaptive thinking + the sentence
              "system": ("You answer over a low-bandwidth field radio to "
                         "someone off-grid. ONE plain sentence, max 160 "
                         "characters, no markdown. If unsure, say so."),
              "messages": [{"role": "user", "content": question}],
              "output_config": {"effort": "low"}},
        timeout=NET_TIMEOUT_S)
    r.raise_for_status()
    d = r.json()
    # Frontier models can decline (stop_reason "refusal") — that's not an
    # error; the local model gets its turn. No server-side fallback model on
    # purpose: this system's fallback chain ends at the LOCAL brain, not at
    # a second cloud model.
    if d.get("stop_reason") == "refusal":
        return None
    text = " ".join(b.get("text", "") for b in d.get("content", [])
                    if b.get("type") == "text").strip()
    return text or None


def cmd_net(_arg: str) -> str:
    """Uplink status: which brain answers ?ask right now, and why."""
    if NET_BACKEND is None:
        return "NET: backend disabled - this is a local-only node by config."
    key_ok = bool(os.environ.get(NET_KEY_ENV))
    up = net_up(force=True)
    if up and key_ok:
        brain = f"{NET_MODEL} (frontier)"
    elif OLLAMA_MODEL:
        brain = f"{OLLAMA_MODEL} (local)"
    else:
        brain = "none - retrieval commands only"
    return (f"NET: uplink {'UP' if up else 'DOWN'}"
            f"{'' if key_ok else ' | key missing'} | ?ask -> {brain}")


def cmd_ask(question: str) -> str:
    """The model path — but the FENCE ROUTES FIRST, before any brain, local
    or cloud. Then: frontier model when the uplink is up and configured
    (labeled 'NET:'), local Ollama otherwise (labeled 'AI:'). Model text is
    an index into the library, never a source, whoever generated it."""
    if not question:
        return "Usage: ?ask <question>"

    decision = safety_router.route(question)
    if decision.route == "RETRIEVAL_ONLY":
        # No model answers fenced questions — not the local one, not the
        # frontier one. Same rule that keeps ?med retrieval-only.
        hint = "?med <topic>" if decision.domain == "medical" else "the library at node WiFi"
        return f"FENCED ({decision.domain}): no AI answer here by design. Source docs only - {hint}."
    if decision.route == "ARTIFACT_LOOKUP":
        return "Spec/part question - try ?find <part>, or the datasheet shelf at node WiFi."

    if NET_BACKEND == "anthropic" and os.environ.get(NET_KEY_ENV) and net_up():
        try:
            text = _ask_net(question)
            if text:
                return "NET: " + text
        except requests.RequestException:
            _NET_STATE.update(ok=False, at=time.monotonic())
            log("NET call failed mid-flight; falling back to local model")

    if OLLAMA_MODEL is None:
        return ("ASK: no uplink and no local model on this node. "
                "?med / ?find still work, full library at node WiFi.")
    try:
        r = requests.post(f"{OLLAMA_URL}/api/generate",
                          json={"model": OLLAMA_MODEL,
                                "prompt": ("Answer in ONE short sentence, "
                                           "max 120 characters: " + question),
                                "stream": False},
                          timeout=120)
        r.raise_for_status()
        return "AI: " + r.json().get("response", "").strip()
    except requests.RequestException:
        return "AI backend unreachable."


COMMANDS = {"?help": cmd_help, "?power": cmd_power, "?med": cmd_med,
            "?find": cmd_find, "?ask": cmd_ask, "?net": cmd_net}


def handle(text: str) -> str:
    cmd, _, arg = text.partition(" ")
    handler = COMMANDS.get(cmd.lower())
    return handler(arg.strip()) if handler else "Unknown cmd. ?help for the list."


# --------------------------- mesh plumbing ----------------------------------

def _authorized(sender: int) -> bool:
    """None or "*" = open; a set admits only its members. Denials are
    silent on the radio (airtime is a commons) and logged locally so you
    can see who's knocking."""
    if AUTHORIZED_SENDERS is None or AUTHORIZED_SENDERS == "*":
        return True
    return sender in AUTHORIZED_SENDERS


def on_receive(packet, interface):  # pubsub callback signature — names matter
    """Runs on the meshtastic library's thread. FAST PATH ONLY:
    validate, rate-limit, enqueue. No network calls in here, ever."""
    try:
        if MY_NUM is None or packet.get("to") != MY_NUM:
            return                                  # DM-only. Non-negotiable.
        decoded = packet.get("decoded", {})
        if decoded.get("portnum") != "TEXT_MESSAGE_APP":
            return
        text = (decoded.get("text") or "").strip()
        sender = packet.get("from")
        if not text.startswith("?") or sender is None:
            return

        now = time.time()
        if now - _last_seen.get(sender, 0) < RATE_LIMIT_S:
            return                                  # silent drop = zero airtime
        _last_seen[sender] = now                    # (rate-limits denials too)
        if not _authorized(sender):
            log(f"DENIED (not in AUTHORIZED_SENDERS) {sender!r}: {text!r}")
            return                                  # no reply — zero airtime
        try:
            _JOBS.put_nowait((sender, text))
        except queue.Full:                          # worker is drowning —
            log(f"DROPPED (queue full) {sender!r}: {text!r}")   # shed load
    except Exception as e:                          # a bot that crashes on one
        log(f"ERROR in receive callback: {e}")      # bad packet is useless


def demo_repl():
    """The Oracle at your keyboard: REAL lookups (kiwix, inventory, power
    telemetry), no radio required. This runs the exact code the mesh path
    runs — including the 200-char clip — so it doubles as the no-hardware
    test for the kiwix seam. QUICKSTART Levels 1–2 use this."""
    print("DEMO MODE — no radio, real lookups, same 200-char cap.")
    print("Try:  ?help   ?power   ?med tourniquet   ?find sx1262   (Ctrl-C quits)")
    while True:
        try:
            text = input("?> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            return
        if not text:
            continue
        if not text.startswith("?"):
            text = "?" + text            # be forgiving at the keyboard
        reply = clip(handle(text))
        print(f"[{len(reply)} chars] {reply}")


def main():
    global MY_NUM
    if "--demo" in sys.argv:
        demo_repl()
        return

    try:
        from pubsub import pub
        import meshtastic.serial_interface
    except ImportError as e:
        print(f"Missing radio dependency ({e}). "
              f"Run: pip install -r requirements.txt "
              f"(or try --demo, which needs no radio)", file=sys.stderr)
        sys.exit(2)

    print("Connecting to Meshtastic node...")
    try:
        iface = (meshtastic.serial_interface.SerialInterface(devPath=SERIAL_PORT)
                 if SERIAL_PORT else meshtastic.serial_interface.SerialInterface())
    except Exception as e:
        print(f"Could not open a Meshtastic node ({e}).\n"
              f"Is it plugged in via USB? Try: meshtastic --info", file=sys.stderr)
        sys.exit(2)

    MY_NUM = iface.myInfo.my_node_num
    pub.subscribe(on_receive, "meshtastic.receive")
    print(f"Oracle up as node {MY_NUM}. DM-only, {MAX_CHARS}-char cap, "
          f"{RATE_LIMIT_S}s rate limit. Ctrl-C to stop.")
    if OLLAMA_MODEL is None:
        print("?ask is DISABLED (OLLAMA_MODEL=None). ?med/?find/?power active.")
    if AUTHORIZED_SENDERS is None:
        print("WARNING: OPEN MODE — AUTHORIZED_SENDERS is not set, so ANY node\n"
              "on the mesh can query this oracle (?power reveals battery state,\n"
              "?find reveals inventory). Fine on a bench. Set the allowlist\n"
              "before this node lives on a real mesh — see 00_DOCS/SECURITY.md.\n"
              "(A future release makes deny-all the default; write \"*\" if\n"
              "open is truly what you want.)")
    elif AUTHORIZED_SENDERS == "*":
        print('OPEN MODE by explicit config ("*") — anyone on the mesh can query.')

    try:
        while True:
            try:
                sender, text = _JOBS.get(timeout=1)
            except queue.Empty:
                continue
            reply = clip(handle(text))
            log(f"FROM {sender!r}: {text!r} -> {reply!r}")
            try:
                iface.sendText(reply, destinationId=sender)
            except Exception as e:       # radio hiccup: log it, stay alive
                log(f"ERROR sending reply: {e}")
    except KeyboardInterrupt:
        print("\nShutting down.")
        iface.close()


if __name__ == "__main__":
    main()
