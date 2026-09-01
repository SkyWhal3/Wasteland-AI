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

# ?ask stays disabled until you name a model — via the environment, same
# pattern as ORACLE_ALLOWLIST: the repo ships with every brain off, and an
# operator turns theirs on at launch:
#   ORACLE_OLLAMA_MODEL="qwen3:8b" python lora_oracle.py
# (model must already be pulled in Ollama; unset = ?ask serves skills,
# fence, and honest refusals only)
OLLAMA_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = os.environ.get("ORACLE_OLLAMA_MODEL") or None

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
NET_BACKEND = os.environ.get("ORACLE_NET_BACKEND") or None   # "anthropic"=on
# Sonnet 5 is the operator-chosen cost point for one-sentence radio answers
# ($2/$10 per MTok, 2026-09): a query runs ~a tenth of a cent. Bigger brains
# are an env var away (ORACLE_NET_MODEL=claude-opus-5) — never a code edit.
NET_MODEL = os.environ.get("ORACLE_NET_MODEL", "claude-sonnet-5")
# Wallet guard: frontier calls per UTC day. In-memory (restart resets),
# which errs cheap-and-available; at Sonnet pricing the default cap bounds
# worst-case spend around a quarter a day.
NET_DAILY_CAP = int(os.environ.get("ORACLE_NET_DAILY_CAP", "200"))
NET_KEY_ENV = "ANTHROPIC_API_KEY"  # env var holding the key
# Identity-linked API keys (the console's newer kind) additionally require
# the workspace id on every request. Classic workspace keys don't. Set
# ORACLE_NET_WORKSPACE to the wrkspc_... id when the API asks for it.
NET_WORKSPACE_ENV = "ORACLE_NET_WORKSPACE"
NET_URL = "https://api.anthropic.com/v1/messages"
NET_TIMEOUT_S = 45
NET_PROBE_TTL_S = 300              # re-probe the uplink at most this often

# --- Outside-world messaging: ?sms and ?email ------------------------------
# The door OUT of the mesh: DM "?sms ethan call mom im fine" and Ethan's
# actual cell phone gets an actual SMS via Twilio over the camp uplink.
# ?email is the same door with zero regulatory friction (SMTP). Both ship
# DISABLED (empty contact lists, creds only from environment). Rules that
# are code, not policy:
#   * The node must run a REAL AUTHORIZED_SENDERS allowlist (a set of node
#     numbers). Open-bench nodes do not message the outside world, period.
#   * Recipients are NAMED CONTACTS from the dicts below. A raw phone
#     number or address arriving over the air is never dialed, and phone
#     numbers are never transmitted back over the air — names only.
#   * SMS_MAX_PER_DAY caps spend and abuse; the counter survives restarts.
# US reality check: application-to-person SMS needs a Twilio number
# (~$1.15/mo) and A2P 10DLC registration (sole-proprietor path) for
# reliable delivery; a trial account can text VERIFIED numbers only —
# which for a family contact list is actually fine.
SMS_CONTACTS: dict[str, str] = {}   # e.g. {"ethan": "+13035550123"} E.164
EMAIL_CONTACTS: dict[str, str] = {} # e.g. {"ethan": "ethan@example.com"}
SMS_MAX_PER_DAY = 20                # node-wide daily ceiling
SMS_MAX_PER_CONTACT_PER_DAY = 10    # one contact can't absorb the whole budget
SMS_MIN_INTERVAL_S = 120            # node-wide spacing: no outbound flood, even
                                    # from an authorized sender in a loop
SMS_BODY_MAX = 150                  # one GSM-7 segment, minus our prefix
SMS_STATE = Path("sms_state.json")  # daily counter + inbound-check cursor
TWILIO_SID_ENV = "TWILIO_ACCOUNT_SID"    # AC... — always needed (URL path)
TWILIO_FROM_ENV = "TWILIO_FROM_NUMBER"   # the rented number, E.164
# Auth, preferred first: a RESTRICTED API key (SK... + secret, scoped to
# Messages only — revocable without rotating the account, and can't touch
# billing). The account master token also works but is the documented
# ANTI-PATTERN (review 2026-08-25): full account power on a field node.
# Use it only to limp through a console outage, then go back to the key.
TWILIO_API_KEY_ENV = "TWILIO_API_KEY_SID"
TWILIO_API_SECRET_ENV = "TWILIO_API_KEY_SECRET"
TWILIO_TOKEN_ENV = "TWILIO_AUTH_TOKEN"
SMTP_HOST_ENV = "ORACLE_SMTP_HOST"       # e.g. smtp.gmail.com (app password)
SMTP_USER_ENV = "ORACLE_SMTP_USER"
SMTP_PASS_ENV = "ORACLE_SMTP_PASS"
SMTP_PORT = 587

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
#
# The allowlist itself comes from the ORACLE_ALLOWLIST environment variable —
# same rule as every credential here: real node numbers never live in this
# file, which is why this file can stay in a public repo. Formats accepted:
#   ORACLE_ALLOWLIST="!ba0618fd"          one node, Meshtastic !hex id
#   ORACLE_ALLOWLIST="0x1234abcd,54321"   several, hex or decimal
#   ORACLE_ALLOWLIST="*"                  open bench mode (warns at startup)
#   unset                                 None -> open with warning, and the
#                                         ?sms/?email doors stay REFUSED


def _parse_allowlist(raw: str | None) -> set[int] | str | None:
    """ORACLE_ALLOWLIST -> allowlist. Bad tokens fail loudly at startup,
    not silently at 2 a.m. when a denied neighbor wonders why."""
    if raw is None or not raw.strip():
        return None
    raw = raw.strip()
    if raw == "*":
        return "*"
    out: set[int] = set()
    for tok in raw.split(","):
        tok = tok.strip()
        if tok.startswith("!"):
            out.add(int(tok[1:], 16))
        elif tok.lower().startswith("0x"):
            out.add(int(tok, 16))
        else:
            out.add(int(tok, 10))
    return out


AUTHORIZED_SENDERS: set[int] | str | None = _parse_allowlist(
    os.environ.get("ORACLE_ALLOWLIST"))

MAX_LOG_BYTES = 1_000_000          # oracle.log rotates past this (SD cards die)

# --- Radio packet modes (idea harvested from review of peer projects; ------
# --- implementation is original, MIT-clean) --------------------------------
#   ultra   one packet, the clip() cap — THE MESH DEFAULT, always
#   compact 2..MAX_PARTS packets suffixed " [i/n]" with a gap between them —
#           only when the sender asks (?ask compact <q>) or the node config
#           says so, and ONLY for unfenced model prose
#   full    uncapped — WiFi/demo/log surfaces only; the radio path degrades
#           full to ultra because the mesh never gets an uncapped send
# Fenced domains NEVER leave ultra: one packet + a pointer IS the answer.
# A 131-node metro mesh punishes multi-part spam; airtime is a commons.
RADIO_MODE = os.environ.get("RADIO_MODE", "ultra").lower()
PART_USABLE = 194                  # payload bytes per part, before " [i/n]"
PART_GAP_S = 2.0                   # pause between parts; raise on a busy mesh
MAX_PARTS = 4

AUDIT_LOG = Path("oracle_audit.jsonl")   # one line per served query — the
                                         # radio path's flight recorder
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


# The reply mode travels WITH the reply, set by the command that built it —
# provenance, not guesswork. Worker resets it before each job; the single-
# threaded worker makes this safe. None = node default (RADIO_MODE).
# Fenced/retrieval paths pin "ultra"; only unfenced model prose may go
# "compact", and only when asked.
_REPLY = {"mode": None}


def clip_bytes(s: str, max_bytes: int) -> str:
    """Trim to a UTF-8 byte budget without splitting a multibyte char.
    ('°' is two bytes; a packet boundary through the middle of it would
    render as mojibake on every phone in camp.)"""
    s = " ".join(s.split())
    while s and len(s.encode("utf-8")) > max_bytes:
        s = s[:-1]
    return s


def packetize(text: str, mode: str | None = None) -> list[str]:
    """Turn one reply into 1..MAX_PARTS radio-safe strings. Never empty.
    ultra -> [clip(text)]. compact -> byte-budgeted slices, ' [i/n]'
    suffixes counted INSIDE the budget, single-part compact drops the
    pointless '[1/1]'. full -> untouched (caller must never TX it)."""
    mode = (mode or RADIO_MODE or "ultra").lower()
    if mode == "full":
        return [text]
    if mode != "compact":
        return [clip(text)]
    raw = " ".join(text.split())
    parts: list[str] = []
    buf = raw
    while buf and len(parts) < MAX_PARTS:
        chunk = clip_bytes(buf, PART_USABLE)
        if not chunk:
            break
        parts.append(chunk)
        buf = buf[len(chunk):].lstrip()
    if not parts:
        return [clip(raw)]
    if buf:                       # ran out of parts before out of text
        parts[-1] = clip_bytes(parts[-1], PART_USABLE - 3) + "…"
    if len(parts) == 1:
        return [clip(parts[0])]
    n = len(parts)
    return [f"{p} [{i + 1}/{n}]" for i, p in enumerate(parts)]


def audit(sender, text: str, parts: list[str], mode: str) -> None:
    """One JSONL line per served query — command, mode, parts, chars, never
    the reply body (the log has that) and never a failure that kills the
    oracle. The radio path's flight recorder."""
    try:
        if AUDIT_LOG.exists() and AUDIT_LOG.stat().st_size > MAX_LOG_BYTES:
            AUDIT_LOG.replace(AUDIT_LOG.with_suffix(".jsonl.old"))
        with open(AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "sender": sender,
                "cmd": text.split(None, 1)[0].lower() if text else "",
                "mode": mode,
                "parts": len(parts),
                "chars": sum(len(p) for p in parts),
            }) + "\n")
    except (OSError, ValueError):
        pass


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
    return ("CMDS: ?power ?med <t> [pN] ?find ?ask ?more ?net ?sms ?email. "
            "?med=retrieval-only. NET:=frontier AI:=local. Library at node WiFi.")


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


def _article_text(markup: str) -> tuple[str, str]:
    """Choose the radio window's verbatim text. Page chrome that wastes the
    200 chars gets cut first — figures, captions, infobox tables, thumb/TOC
    divs (the first flight spent its whole window on burn-anatomy diagram
    captions). Then, if the article has a Management/Treatment section, the
    window anchors THERE: in the field nobody needs Background first.
    Section selection is retrieval targeting, not paraphrase — every word
    that goes out is still the source's, in the source's order (§9)."""
    m = re.sub(r"<figure\b.*?</figure>|<figcaption\b.*?</figcaption>",
               " ", markup, flags=re.S | re.I)
    m = re.sub(r"<table\b.*?</table>", " ", m, flags=re.S | re.I)
    m = re.sub(r'<div\b[^>]*class="[^"]*(?:thumb|toc|gallery|infobox|navbox)'
               r'[^"]*"[^>]*>.*?</div>', " ", m, flags=re.S | re.I)
    # WikEM's action sections wear several names ("General Management",
    # "Application of Tourniquet", "Treatment"...): list every heading with
    # its position, then take the best keyword match, bounded at the NEXT
    # heading so the window never pages into See Also / References.
    heads = [(h.start(), h.end(), _strip_html(h.group(2)))
             for h in re.finditer(r"<h([12])[^>]*>(.*?)</h\1>",
                                  m, flags=re.S | re.I)]
    # Application outranks Treatment: on device articles (tourniquet) the
    # "Treatment" substring also lives in "Removal at Medical Treatment",
    # and the field reader wants the thing APPLIED before removed.
    for kw in ("Management", "Application", "Treatment", "Technique",
               "Procedure"):
        for i, (_, h_end, h_text) in enumerate(heads):
            if kw.lower() in h_text.lower():
                seg_end = heads[i + 1][0] if i + 1 < len(heads) else len(m)
                text = _strip_html(m[h_end:seg_end])
                if len(text) >= 20:
                    return f"§{kw.upper()}", text
                # a heading with no body under it is a stub — keep looking
    return "", _strip_html(m)


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


def _page_window(snippet: str, room: int, page_no: int) -> tuple[str, int, int]:
    """Verbatim window N for '?med burn p2'. Pages are WALKED, not gridded:
    each page ends on a sentence boundary (or at worst a word boundary) and
    the next begins exactly where the last ended, so no characters ever
    fall into the crack between pages. Returns (body, page, total)."""
    room = max(room, 40)
    pages: list[str] = []
    rest = snippet
    while rest:
        if len(rest) <= room:
            pages.append(rest)
            break
        body = rest[:room]
        cut = body.rfind(". ")
        if cut >= room // 2:
            body = body[:cut + 1]
        elif " " in body:
            body = body[:body.rindex(" ")]
        if not body:                      # unbreakable blob — take the slice
            body = rest[:room]
        pages.append(body)
        rest = rest[len(body):].lstrip()
    total = max(1, len(pages))
    page_no = min(max(1, page_no), total)
    return (pages[page_no - 1] if pages else ""), page_no, total


def cmd_med(query: str) -> str:
    """RETRIEVAL ONLY. Finds the best-matching WikEM article via kiwix-serve's
    /suggest endpoint and returns title + a verbatim window + where to read
    it. '?med burn p2' pages deeper into the same article, one packet per
    request — the human pulls at reading pace, so depth never multi-parts.
    No language model is involved in this path, by design (manifest §9)."""
    _REPLY["mode"] = "ultra"      # medical NEVER multi-parts: one packet,
    if not query:                 # a title, and where to read the source
        return "Usage: ?med <topic> [pN]   e.g. ?med tourniquet / ?med burn p2"
    pm = re.match(r"^(.+?)\s+p(\d{1,2})$", query.strip(), flags=re.I)
    page_no = 1
    if pm:
        query, page_no = pm.group(1), int(pm.group(2))
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

    # A stub/disambiguation page ("Tourniquet") often outranks the real
    # article ("Extremity tourniquet"): scan the top suggestions and serve
    # the first whose article HAS a Management/Treatment section, falling
    # back to the first fetchable hit. The served title is displayed, so
    # the reader always sees exactly which article they are getting.
    # ('value' is the plain title; 'label' can carry <b>…</b> markup we
    # are NOT sending over a 200-char radio message.)
    title, section, snippet = "", "", ""
    for h in hits[:3]:
        t = h.get("value") or re.sub(r"<[^>]+>", "", h.get("label", query))
        page = _kiwix_article_html(book, h["path"])
        if not page:
            continue
        sec_i, snip_i = _article_text(page)
        if not title or sec_i:
            title, section, snippet = t, sec_i, snip_i
        if sec_i:
            break
    if not title:
        return f"WIKEM: article fetch failed for '{query}'."
    # drop the leading title repetition if present
    if not section and snippet.lower().startswith(title.lower()):
        snippet = snippet[len(title):].lstrip(" -:")
    base_head = f"WIKEM: {title.upper()}{(' ' + section) if section else ''}"
    tail = " | FULL TEXT AT NODE"
    room = MAX_CHARS - len(base_head) - 9 - len(tail)   # 9 = " 12/34 | "
    body, page_no, total = _page_window(snippet, room, page_no)
    head = f"{base_head} {page_no}/{total} | " if total > 1 else f"{base_head} | "
    return head + body + tail


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
    down uplink doesn't add a timeout to every command. Any HTTP response at
    all (even a 4xx) proves DNS + TCP + TLS work; only a transport error is
    'down'. Pure connectivity — callers decide what to do with it (?ask
    checks NET_BACKEND separately; ?sms/?email need only the pipe)."""
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


# The radio pre-prompt — the whole field-comms doctrine, stated once, sent
# with every call. Kept STABLE on purpose (byte-identical prompts are how
# caching and behavior stay predictable); per-query context goes in the
# user message, never in here.
NET_SYSTEM = (
    "You are the reply engine of an off-grid field library, reached over "
    "Meshtastic LoRa radio at 200 characters per packet. Your ENTIRE reply "
    "must fit one packet: max 160 characters, ASCII only, no markdown, no "
    "preamble, no hedging. Lead with the single most useful fact or action, "
    "in plain imperative field language. If a number matters and you are "
    "not certain of it, reply 'unsure - check the library' rather than "
    "guess. If asked for a medication dose, ammunition load, canning time, "
    "wire or fuse size, structural span, water-treatment dose, or a "
    "wild-plant or mushroom edibility call, reply exactly FENCED - a code "
    "fence upstream handles those from source documents. The reader is "
    "off-grid: assume camp tools only, no internet, no stores.")

_LAST_ASK = {"q": None, "a": None}   # ?more continuation memory (one slot —
                                     # this node answers one allowlisted human)
_NET_SPEND = {"day": "", "calls": 0}


def _net_budget_ok() -> bool:
    """Spend the daily frontier-call budget one call at a time; over cap the
    caller falls back to the local brain / honest refusal. Attempts count
    (not just successes) — the conservative direction for a wallet guard."""
    today = time.strftime("%Y-%m-%d", time.gmtime())
    if _NET_SPEND["day"] != today:
        _NET_SPEND.update(day=today, calls=0)
    if _NET_SPEND["calls"] >= NET_DAILY_CAP:
        return False
    _NET_SPEND["calls"] += 1
    return True


def _net_headers() -> dict:
    """Request headers for the uplink call. Identity-linked keys need the
    workspace id header; classic keys ignore its absence. Pure function,
    pinned by the smoke suite."""
    h = {"x-api-key": os.environ.get(NET_KEY_ENV),
         "anthropic-version": "2023-06-01",
         "content-type": "application/json"}
    ws = os.environ.get(NET_WORKSPACE_ENV)
    if ws:
        h["anthropic-workspace-id"] = ws
    return h


def _net_payload(question: str, prior: tuple[str, str] | None = None) -> dict:
    """The wire body for one radio-shaped frontier call. Pure function so
    the smoke suite can pin its exact shape without any network. `prior`
    threads the last Q/A back as real conversation turns — that is the
    whole multi-turn mechanism behind ?more."""
    msgs = []
    if prior:
        msgs += [{"role": "user", "content": prior[0]},
                 {"role": "assistant", "content": prior[1]}]
    msgs.append({"role": "user", "content": question})
    return {"model": NET_MODEL,
            "max_tokens": 1000,   # covers adaptive thinking + the sentence
            "system": NET_SYSTEM,
            "messages": msgs,
            "output_config": {"effort": "low"}}


def _ask_net(question: str, prior: tuple[str, str] | None = None) -> str | None:
    """One frontier-model call over the uplink, radio-shaped. Raw HTTP on
    purpose: this project keeps dependencies minimal and version-bounded, and
    the oracle already speaks plain requests to kiwix and Ollama. Returns None
    if the model refused or produced nothing — caller falls back to local."""
    if not _net_budget_ok():
        log(f"NET daily cap ({NET_DAILY_CAP}) reached; falling back local")
        return None
    r = requests.post(
        NET_URL,
        headers=_net_headers(),
        json=_net_payload(question, prior),
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
    if text.upper().startswith("FENCED"):
        # The system prompt's backup fence fired — which means a fenced
        # question got PAST the router. Worth a loud log line: that is a
        # keyword gap to fix, not a reply to send.
        log(f"NET fence echo tripped (router keyword gap?): {question!r}")
        return None
    return text or None


def cmd_net(_arg: str) -> str:
    """Uplink status: which brain answers ?ask right now, and why."""
    if NET_BACKEND is None:
        return "NET: backend disabled - this is a local-only node by config."
    if not _allowlist_active():
        # Review finding (2026-08-25): on an open node, "the camp has live
        # internet" is reconnaissance handed to strangers. Allowlisted
        # senders get the real status; everyone else learns nothing.
        return "NET: status is allowlist-only on this node. ?med and ?find always work."
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


# ----------------------- outside-world messaging ---------------------------

def _allowlist_active() -> bool:
    """True only when AUTHORIZED_SENDERS is a real, non-empty set of node
    numbers. None (open bench) and "*" (explicitly open) both fail — a node
    that answers strangers does not get to message the outside world."""
    return isinstance(AUTHORIZED_SENDERS, set) and len(AUTHORIZED_SENDERS) > 0


def _sms_state() -> dict:
    try:
        return json.loads(SMS_STATE.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _sms_state_save(d: dict) -> None:
    try:
        SMS_STATE.write_text(json.dumps(d))
    except OSError:
        pass                       # a broken counter must not break sending


def _sms_quota() -> tuple[int, dict, str]:
    """(node sends today, per-contact sends today, date string) — UTC day,
    survives restarts. Two caps because they answer different abuse shapes:
    the global cap bounds spend, the per-contact cap stops one chatty thread
    from eating everyone's budget."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    st = _sms_state()
    if st.get("date") != today:
        return 0, {}, today
    return st.get("count", 0), st.get("per", {}), today


def _outside_gates(contacts: dict, kind: str) -> str | None:
    """The gate sequence shared by ?sms and ?email. Returns a refusal string,
    or None if clear to proceed. Order matters — config gates come before
    the network probe so an unconfigured node never touches the network."""
    if not _allowlist_active():
        return (f"{kind}: needs an AUTHORIZED_SENDERS allowlist on this "
                "node. Open nodes don't message the outside world.")
    if not contacts:
        return f"{kind}: no contacts configured on this node."
    return None


def cmd_sms(arg: str) -> str:
    """?sms <name> <message>  |  ?sms check
    Real SMS to a NAMED contact via Twilio, over whatever uplink exists.
    'check' polls the Twilio number's inbox for replies (pull, not push —
    Starlink CGNAT can't receive webhooks, and pull costs airtime only
    when a human asks)."""
    refusal = _outside_gates(SMS_CONTACTS, "SMS")
    if refusal:
        return refusal

    sid = os.environ.get(TWILIO_SID_ENV)
    from_num = os.environ.get(TWILIO_FROM_ENV)
    key = os.environ.get(TWILIO_API_KEY_ENV)
    secret = os.environ.get(TWILIO_API_SECRET_ENV)
    token = os.environ.get(TWILIO_TOKEN_ENV)
    auth = (key, secret) if (key and secret) else \
           ((sid, token) if token else None)
    if not (sid and from_num and auth):
        return "SMS: Twilio credentials not in this node's environment."

    if arg.strip().lower() == "check":
        return _sms_check(sid, auth, from_num)

    name, _, body = arg.partition(" ")
    name, body = name.lower().strip(), body.strip()
    if not name or not body:
        return "Usage: ?sms <name> <message>  or  ?sms check"
    if name not in SMS_CONTACTS:
        return f"SMS: unknown contact '{name}'. Known: {', '.join(sorted(SMS_CONTACTS))}"

    count, per, today = _sms_quota()
    if count >= SMS_MAX_PER_DAY:
        return f"SMS: daily cap reached ({SMS_MAX_PER_DAY}). Resets midnight UTC."
    if per.get(name, 0) >= SMS_MAX_PER_CONTACT_PER_DAY:
        return f"SMS: daily cap for that contact reached ({SMS_MAX_PER_CONTACT_PER_DAY})."
    since_last = time.time() - _sms_state().get("last_send_ts", 0)
    if since_last < SMS_MIN_INTERVAL_S:
        return f"SMS: spacing - wait {int(SMS_MIN_INTERVAL_S - since_last)}s between texts."
    if not net_up():
        return "SMS: no uplink right now. Message NOT sent - retry when ?net says UP."

    body = body[:SMS_BODY_MAX]
    try:
        r = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            auth=auth,
            data={"To": SMS_CONTACTS[name], "From": from_num,
                  "Body": f"[camp mesh] {body}"},
            timeout=30)
    except requests.RequestException:
        _NET_STATE.update(ok=False, at=time.monotonic())
        return "SMS: uplink died mid-send. NOT confirmed sent."
    if r.status_code != 201:
        log(f"SMS to {name} failed: HTTP {r.status_code} {r.text[:200]}")
        return f"SMS: Twilio refused (HTTP {r.status_code}). See node log."
    per = dict(per); per[name] = per.get(name, 0) + 1
    _sms_state_save({"date": today, "count": count + 1, "per": per,
                     "last_send_ts": time.time(),
                     "last_check": _sms_state().get("last_check", "")})
    log(f"SMS sent to contact '{name}' ({count + 1}/{SMS_MAX_PER_DAY} today)")
    # The ACK deliberately omits the contact name: the sender already typed
    # it, and on a mixed-firmware mesh a DM can fall back to channel-key
    # encryption — no names over the air that don't have to be.
    return f"SMS sent ({count + 1}/{SMS_MAX_PER_DAY} today)."


def _sms_check(sid: str, auth: tuple, from_num: str) -> str:
    """Pull inbound SMS newer than the last check. Numbers are reverse-mapped
    to contact names; unknown senders show as 'unknown' — no numbers over
    the air, ever."""
    if not net_up():
        return "SMS: no uplink right now."
    try:
        r = requests.get(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            auth=auth,
            params={"To": from_num, "PageSize": 10},
            timeout=30)
        r.raise_for_status()
        msgs = r.json().get("messages", [])
    except (requests.RequestException, ValueError):
        return "SMS: could not reach Twilio inbox."
    st = _sms_state()
    last = st.get("last_check", "")
    by_number = {v: k for k, v in SMS_CONTACTS.items()}
    fresh = []
    newest = last
    for m in msgs:
        if m.get("direction") != "inbound":
            continue
        sent = m.get("date_sent") or m.get("date_created") or ""
        if sent <= last:
            continue
        newest = max(newest, sent)
        who = by_number.get(m.get("from", ""), "unknown")
        fresh.append(f"{who}: {m.get('body', '')}")
    if not fresh:
        return "SMS inbox: nothing new."
    st.update(last_check=newest)
    _sms_state_save(st)
    return "INBOX | " + " | ".join(reversed(fresh))


def cmd_email(arg: str) -> str:
    """?email <name> <message> — same door as ?sms, zero regulatory friction:
    plain SMTP with an app password. The reliable path while 10DLC paperwork
    pends, and free forever after."""
    refusal = _outside_gates(EMAIL_CONTACTS, "EMAIL")
    if refusal:
        return refusal
    host = os.environ.get(SMTP_HOST_ENV)
    user = os.environ.get(SMTP_USER_ENV)
    pw = os.environ.get(SMTP_PASS_ENV)
    if not (host and user and pw):
        return "EMAIL: SMTP credentials not in this node's environment."
    name, _, body = arg.partition(" ")
    name, body = name.lower().strip(), body.strip()
    if not name or not body:
        return "Usage: ?email <name> <message>"
    if name not in EMAIL_CONTACTS:
        return f"EMAIL: unknown contact '{name}'. Known: {', '.join(sorted(EMAIL_CONTACTS))}"
    if not net_up():
        return "EMAIL: no uplink right now. NOT sent - retry when ?net says UP."
    import smtplib
    from email.message import EmailMessage
    msg = EmailMessage()
    msg["From"] = user
    msg["To"] = EMAIL_CONTACTS[name]
    msg["Subject"] = "[camp mesh] message relayed from the field"
    msg.set_content(body + "\n\n(sent over LoRa mesh -> camp gateway; "
                           "replies are not monitored continuously)")
    try:
        with smtplib.SMTP(host, SMTP_PORT, timeout=30) as s:
            s.starttls()
            s.login(user, pw)
            s.send_message(msg)
    except (smtplib.SMTPException, OSError) as e:
        log(f"EMAIL to {name} failed: {e}")
        return "EMAIL: send failed. See node log."
    log(f"EMAIL sent to contact '{name}'")
    return f"EMAIL sent to {name}."


# ------------------- skills: one-packet radio telegrams ---------------------
# Every skill file in 02_CORPORA/skills/ carries a `radio_payload:` line in
# its frontmatter — the "if only one packet gets through" version of its
# procedure, written to the same rules as the skill itself (pointers and
# categorical checks; the numbers stay in the manuals). When the router
# matches a skill, the oracle serves that telegram instead of burning model
# tokens on prose the skill already answers better. tests/test_skills.py
# enforces the byte budget on every payload.
SKILLS_DIR = Path(__file__).resolve().parent.parent / "02_CORPORA" / "skills"
_SKILL_CACHE: dict[str, str | None] = {}


def _skill_payload(name: str | None) -> str | None:
    """The skill's frontmatter telegram, or None. Caches misses too, so the
    radio worker never re-reads a file per query."""
    if not name:
        return None
    if name not in _SKILL_CACHE:
        payload, dashes = None, 0
        try:
            for line in (SKILLS_DIR / f"{name}.md").read_text(
                    encoding="utf-8").splitlines():
                if line.strip() == "---":
                    dashes += 1
                    if dashes == 2:
                        break              # frontmatter only — never the body
                elif line.startswith("radio_payload:"):
                    payload = line.partition(":")[2].strip().strip('"') or None
        except OSError:
            pass                           # missing file = no telegram
        _SKILL_CACHE[name] = payload
    return _SKILL_CACHE[name]


def cmd_ask(question: str) -> str:
    """The model path — but the FENCE ROUTES FIRST, before any brain, local
    or cloud. Then: frontier model when the uplink is up and configured
    (labeled 'NET:'), local Ollama otherwise (labeled 'AI:'). Model text is
    an index into the library, never a source, whoever generated it."""
    if not question:
        return "Usage: ?ask <question>   (?ask compact <q> allows a multi-part reply)"

    # "?ask compact <q>" — the sender is asking to spend airtime. Honored
    # only if the reply turns out to be unfenced model prose.
    want_compact = False
    first, _, rest = question.partition(" ")
    if first.lower() == "compact" and rest.strip():
        want_compact, question = True, rest.strip()

    decision = safety_router.route(question)
    if decision.route == "RETRIEVAL_ONLY":
        # No model answers fenced questions — not the local one, not the
        # frontier one. Same rule that keeps ?med retrieval-only. And a
        # fenced reply never multi-parts: the pointer IS the answer.
        _REPLY["mode"] = "ultra"
        telegram = _skill_payload(decision.skill)
        if telegram:
            # File-backed pointer content, not model output: the fence stays
            # intact and the reply gets useful. Warning tag rides packet 1.
            return f"FENCED ({decision.domain}). {telegram}"
        hint = "?med <topic>" if decision.domain == "medical" else "the library at node WiFi"
        return f"FENCED ({decision.domain}): no AI answer here by design. Source docs only - {hint}."
    if decision.route == "ARTIFACT_LOOKUP":
        _REPLY["mode"] = "ultra"
        return "Spec/part question - try ?find <part>, or the datasheet shelf at node WiFi."

    # A matched skill IS the answer on the radio: its telegram is the
    # repo-authored, reviewable distillation of the procedure — one packet,
    # zero model tokens, and it asks the disambiguating question a model
    # never would. Library first, model second: the brains below now only
    # field questions no procedure covers. (`?ask compact` does not override
    # this — compact buys airtime for model prose, and a skill-matched
    # question never reaches a model while its telegram exists.)
    if decision.skill:
        telegram = _skill_payload(decision.skill)
        if telegram:
            _REPLY["mode"] = "ultra"
            return telegram

    # Honesty label (review harvest): when no skill/manual backs the answer,
    # say so in the label — a fluent paragraph with no source is an index
    # entry, not a reference. (A skill match reaching this point means the
    # skill file lost its radio_payload; the name still counts as a doc.)
    tag = "" if decision.skill else "(no doc)"

    if NET_BACKEND == "anthropic" and os.environ.get(NET_KEY_ENV) and net_up():
        try:
            text = _ask_net(question)
            if text:
                if want_compact:
                    _REPLY["mode"] = "compact"
                _LAST_ASK.update(q=question, a=text)
                reply = f"NET{tag}: " + text
                if len(reply) + 8 <= MAX_CHARS:   # teach the follow-up door
                    reply += " | ?more"
                return reply
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
        if want_compact:
            _REPLY["mode"] = "compact"
        text = r.json().get("response", "").strip()
        _LAST_ASK.update(q=question, a=text)
        reply = f"AI{tag}: " + text
        if len(reply) + 8 <= MAX_CHARS:
            reply += " | ?more"
        return reply
    except requests.RequestException:
        return "AI backend unreachable."


def cmd_more(_arg: str) -> str:
    """?more — the multi-turn door: continue the last ?ask answer with the
    next most useful details. The prior Q/A rides back to the model as real
    conversation turns. Fence position unchanged: only questions the router
    already cleared ever get cached here, so continuing one is equally
    clear. One packet out, same as everything."""
    if not _LAST_ASK["q"]:
        return "Nothing to continue - ?ask <question> first."
    follow = ("Continue: give the next most useful details beyond your "
              "previous answer. Same limits.")
    prior = (_LAST_ASK["q"], _LAST_ASK["a"])
    if NET_BACKEND == "anthropic" and os.environ.get(NET_KEY_ENV) and net_up():
        try:
            text = _ask_net(follow, prior=prior)
            if text:
                # extend the memory so a second ?more knows both parts,
                # capped so a long chain can't grow the payload unbounded
                _LAST_ASK["a"] = (_LAST_ASK["a"] + " " + text)[-600:]
                reply = "NET: " + text
                if len(reply) + 8 <= MAX_CHARS:
                    reply += " | ?more"
                return reply
        except requests.RequestException:
            _NET_STATE.update(ok=False, at=time.monotonic())
            log("NET ?more failed; trying local")
    if OLLAMA_MODEL is None:
        return "MORE: no uplink and no local model right now."
    try:
        r = requests.post(f"{OLLAMA_URL}/api/generate",
                          json={"model": OLLAMA_MODEL,
                                "prompt": (f"Earlier Q: {prior[0]}\n"
                                           f"Your answer: {prior[1]}\n"
                                           "Give the next most useful details "
                                           "in ONE sentence, max 120 chars: "),
                                "stream": False},
                          timeout=120)
        r.raise_for_status()
        text = r.json().get("response", "").strip()
        _LAST_ASK["a"] = (_LAST_ASK["a"] + " " + text)[-600:]
        return "AI: " + text
    except requests.RequestException:
        return "AI backend unreachable."


COMMANDS = {"?help": cmd_help, "?power": cmd_power, "?med": cmd_med,
            "?find": cmd_find, "?ask": cmd_ask, "?more": cmd_more,
            "?net": cmd_net, "?sms": cmd_sms, "?email": cmd_email}


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
        _REPLY["mode"] = None
        parts = packetize(handle(text), _REPLY["mode"])
        for i, p in enumerate(parts):
            n = f" part {i + 1}/{len(parts)}" if len(parts) > 1 else ""
            print(f"[{len(p)} chars{n}] {p}")


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
              f"Is it plugged in via USB? PermissionError/Access-denied "
              f"usually means something else already holds the port - "
              f"another copy of this oracle, the Meshtastic web client, or "
              f"the CLI. COM ports are one-owner-only: close the other one "
              f"and start me again. Otherwise try: meshtastic --info",
              file=sys.stderr)
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
            _REPLY["mode"] = None            # each job re-decides its mode
            reply = handle(text)
            mode = (_REPLY["mode"] or RADIO_MODE or "ultra").lower()
            if mode == "full":
                mode = "ultra"               # the RADIO never sends uncapped
            parts = packetize(reply, mode)
            log(f"FROM {sender!r}: {text!r} -> {len(parts)} part(s) "
                f"[{mode}] {parts[0]!r}")
            try:
                for i, part in enumerate(parts):
                    iface.sendText(part, destinationId=sender)
                    if i + 1 < len(parts):
                        time.sleep(PART_GAP_S)   # worker thread, not radio
            except Exception as e:       # radio hiccup: log it, stay alive
                log(f"ERROR sending reply: {e}")
            audit(sender, text, parts, mode)
            # Rate limit stays per QUERY: a 3-part reply is one query's
            # airtime spend, already bounded by MAX_PARTS.
    except KeyboardInterrupt:
        print("\nShutting down.")
        iface.close()


if __name__ == "__main__":
    main()
