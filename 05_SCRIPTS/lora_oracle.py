#!/usr/bin/env python3
"""
lora_oracle.py — the mesh bot. A remote command line into the knowledge node,
reachable over Meshtastic from miles away. NOT "ChatGPT over radio."

Commands (send as a DIRECT MESSAGE to this node):
  ?help              list commands
  ?power             battery/solar snapshot  (reads power_monitor.py's latest.json)
  ?med <query>       RETRIEVAL-ONLY medical lookup from Kiwix (WikEM) — no AI
  ?find <query>      look up a part in INVENTORY.csv (Layer 0, manifest §7.1)
  ?ask <question>    small local model via Ollama — OFF until configured, and
                     always labeled "AI:" because model output is not a source

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
import json
import queue
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
    from pubsub import pub
    import meshtastic
    import meshtastic.serial_interface
except ImportError as e:
    print(f"Missing dependency ({e}). Run: pip install -r requirements.txt",
          file=sys.stderr)
    sys.exit(2)

# ----------------------------- CONFIG ---------------------------------------
SERIAL_PORT = None                 # None = auto-detect the Meshtastic node
MAX_CHARS = 200                    # hard reply cap — do not raise casually
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
# ---------------------------------------------------------------------------

_last_seen: dict[int, float] = {}   # sender node number -> last-served time
_JOBS: queue.Queue = queue.Queue()  # (sender, text) handed from radio thread
MY_NUM: int | None = None           # our node number, set in main()


def clip(s: str) -> str:
    """The one non-negotiable function in this file."""
    s = " ".join(s.split())                       # collapse whitespace
    return s if len(s) <= MAX_CHARS else s[:MAX_CHARS - 1] + "…"


def log(line: str) -> None:
    stamp = datetime.now().isoformat(timespec="seconds")
    with open(ORACLE_LOG, "a", encoding="utf-8") as f:
        f.write(f"{stamp} {line}\n")
    print(f"{stamp} {line}")


# ----------------------------- commands -------------------------------------

def cmd_help(_arg: str) -> str:
    return ("CMDS: ?power | ?med <q> | ?find <part> | ?ask <q>. "
            "?med is retrieval-only (WikEM). Full text at the node's WiFi.")


def cmd_power(_arg: str) -> str:
    try:
        d = json.loads(LATEST_JSON.read_text())
    except (OSError, json.JSONDecodeError):
        return "POWER: no data (is power_monitor.py running?)"
    parts = [f"BAND {d.get('band', '?')}"]
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


def _strip_html(html: str) -> str:
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(text.split())


def _kiwix_article_html(path: str) -> str | None:
    """Fetch an article's raw HTML from kiwix-serve.

    The suggestion 'path' is relative to the book (e.g. "A/Dehydration").
    Current kiwix-serve serves content at /content/<book>/<path>; older
    builds used /<book>/<path>. Try both so one script spans versions —
    this is the known-fragile seam, flagged in the README.
    """
    for url in (f"{KIWIX_URL}/content/{KIWIX_BOOK}/{path}",
                f"{KIWIX_URL}/{KIWIX_BOOK}/{path}"):
        try:
            r = requests.get(url, timeout=10)
        except requests.RequestException:
            return None
        if r.ok:
            return r.text
    return None


def cmd_med(query: str) -> str:
    """RETRIEVAL ONLY. Finds the best-matching WikEM article via kiwix-serve's
    /suggest endpoint and returns title + opening text + where to read it.
    No language model is involved in this path, by design (manifest §9)."""
    if not query:
        return "Usage: ?med <topic>   e.g. ?med tourniquet"
    try:
        r = requests.get(f"{KIWIX_URL}/suggest",
                         params={"content": KIWIX_BOOK, "term": query},
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
    html = _kiwix_article_html(hits[0]["path"])
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


def cmd_ask(question: str) -> str:
    """Optional small-model path. Output is ALWAYS labeled 'AI:' — model text
    is an index into the library, never a source. Medical/reloading/canning/
    electrical questions belong in the retrieval paths, not here."""
    if OLLAMA_MODEL is None:
        return "ASK disabled on this node. Use ?med / ?find, or the node's WiFi."
    if not question:
        return "Usage: ?ask <question>"
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
            "?find": cmd_find, "?ask": cmd_ask}


def handle(text: str) -> str:
    cmd, _, arg = text.partition(" ")
    handler = COMMANDS.get(cmd.lower())
    return handler(arg.strip()) if handler else "Unknown cmd. ?help for the list."


# --------------------------- mesh plumbing ----------------------------------

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
        _last_seen[sender] = now
        _JOBS.put((sender, text))
    except Exception as e:                          # a bot that crashes on one
        log(f"ERROR in receive callback: {e}")      # bad packet is useless


def main():
    global MY_NUM
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
