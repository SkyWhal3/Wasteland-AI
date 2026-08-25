# STORAGE — sizing, redundancy, and the decade problem

Two different questions get conflated here, and the answers are opposite:

- **"Will this survive the weekend?"** — one drive. Done. Stop reading.
- **"Will this be readable in ten years?"** — a filesystem that can detect its
  own corruption, more than one copy, in more than one place, tested.

RAID answers neither of them well on its own. Here is why, with real numbers.

---

## 1. What it actually costs

Measured on this archive, 2026-08-25:

| Component | Size |
|---|---|
| Datasheets, manuals, schematics (~60 documents) | 153 MB |
| NEETS, 24 modules | 57 MB |
| WikEM ZIM | 358 MB |
| **Everything collected so far** | **567 MB** |

Projected against the full §8 corpus:

| Tier | Contents | Size |
|---|---|---|
| **Pocket** | `wikipedia_en_all_mini` + WikEM + Hesperian + this repo | **~6 GB** |
| **Pi core** | above + medical subsets + iFixit + Appropedia + datasheets + a 4B model | **~60 GB** |
| **Full library** | `wikipedia_en_all_nopic` (55 GB) + Gutenberg (65 GB) + wikiHow (30 GB) + Stack Exchange sets + maps | **~300 GB** |
| **+ toolchain and models** | offline wheels, apt mirror, OS images, firmware, 30B and 70B quants | **~600 GB – 1 TB** |
| **+ the Monument** | a 2.8T MoE at FP16 | **+5.6 TB** |

**The important line:** everything that actually keeps a person alive fits in
**60 GB.** A single 2 TB NVMe holds the full library, the toolchain, and every
model you can realistically run, with room left over. Storage is not the
constraint on this project — collection effort is, and power is.

## 2. RAID is not backup, and RAID10 is not integrity

Worth being blunt, because "I'll just RAID it" is the most common wrong answer
to the decade question.

**RAID protects against exactly one failure: a drive dying.** It does nothing
about deletion, a bad cable writing garbage, filesystem corruption, theft,
fire, a lightning strike on your PV entry, or the controller itself failing.
Every one of those is more likely over ten years than the specific event RAID
covers.

**And a mirror cannot tell you which copy is right.** This is the part that
matters for an archive. Traditional RAID1/RAID10 stores two copies with no
checksum. When they disagree — and over a decade on multi-terabyte drives they
will — the array has no way to know which one is correct. It will happily
serve you the corrupt one, and a rebuild can propagate the corruption into the
good copy.

That is precisely the failure this project already worries about, arriving
through hardware instead of a download.

## 3. What actually works for ten years

**Option A — a checksumming filesystem.** ZFS (mirror or raidz) or btrfs
(RAID1) checksum every block. On a read mismatch they know which copy is good
and **repair it automatically**. A scheduled `scrub` walks the whole pool and
fixes rot before you need the file. This is the real answer to the decade
question, and the "RAID" part is almost incidental — the checksums are the
feature.

**Option B — two plain drives and the tool you already have.** No array, no
filesystem gymnastics:

```bash
python 05_SCRIPTS/verify_checksums.py build /archive --index checksums.csv
# ... a year later, or on a sunny afternoon via the surplus scheduler ...
python 05_SCRIPTS/verify_checksums.py check /archive --index checksums.csv
# MISMATCH -> restore that file from the second drive -> rebuild the index
```

That is detect-and-repair, done manually. It is slower and less elegant than
ZFS and it works on any operating system, any filesystem, with no special
hardware — which for a project whose recovery plan involves rebuilding on
whatever machine survived is a genuine advantage.

**Keep the index on a different drive than the archive.** An index that rots
with the data it describes proves nothing.

## 4. The power problem — why RAID10 is a grid-tied answer

This is the part specific to this project and it settles the question.

A four-drive spinning array draws roughly **20–40 W continuously**, plus the
host to run it. Call it 480–960 Wh/day.

The entire off-grid budget is **~1,020 Wh/day on a clear December day**, and
the survival baseline is ~350 Wh. A RAID10 array does not fit in the power
budget. It does not fit *near* the power budget. It would consume the whole
system to protect files that the Pi reads from a 2 TB NVMe at a couple of
watts.

So the architecture splits by power domain, not by preference:

| Copy | Where | Media | Redundancy | Power |
|---|---|---|---|---|
| **Master** | Grid-tied box (your D: array) | Spinning disks, ZFS/btrfs or two-drive + checksums | Full | Mains, spun down when idle |
| **Node** | The Pi, off-grid | Single 2 TB NVMe, ~60 GB core | None — it is a *copy*, restored from master | ~2 W |
| **Faraday / offsite** | A box, elsewhere | Rugged USB **spinning** drive, encrypted | It IS the redundancy | Zero |

The node needs no redundancy because it holds nothing unique. If its drive
dies you lose a weekend, not the archive. That is the whole design.

## 5. Media choices that matter over a decade

- **Do not use an SSD for the cold copy.** Unpowered NAND leaks charge. A
  consumer SSD left in a drawer for years can become unreadable, and it fails
  in a way that gives no warning. **The faraday drive should be spinning
  rust**, and it should be powered up and verified yearly. This is the single
  most common mistake in prepper storage plans.
- **CMR, not SMR.** Shingled drives rewrite overlapping tracks and behave
  badly under large sequential writes and array rebuilds. Check before buying;
  manufacturers have not always been forthcoming about which is which.
- **Different manufacturers, or at least different batches, for the copies.**
  Drives from one batch fail at the same time, which is exactly when you
  discover both copies were the same batch.
- **M-DISC BD-R** for the genuinely long term. ~100 GB per disc, inorganic
  recording layer rated for centuries rather than years, needs no power, does
  not rot, cannot be ransomwared. The 60 GB core fits on one. A drive to read
  it is the catch — archive one of those too, or accept that you are betting
  on optical drives still existing.
- **Nothing lasts unattended.** Every medium above assumes somebody checks it.
  The yearly checksum run and the yearly recovery drill are what make this a
  plan rather than a hope.

## 6. The recommendation, short

- **Weekend / camping:** one drive. Genuinely fine.
- **Serious, single site:** two independent drives + `verify_checksums.py` +
  a yearly restore test. Cheaper and more portable than an array.
- **Decade, multi-terabyte, grid-tied master:** ZFS mirror with monthly
  scrubs. Not for the redundancy — for the checksums.
- **Always, regardless:** three copies, two media types, one off-site
  (the faraday drive), and an **air-gapped recovery drill once a year**.
  An untested backup is a rumour.

RAID10 is a fine answer to "I want the master array to survive a drive
failure without downtime." It is the wrong answer to "I want this readable in
2036," and it is an impossible answer for anything running on solar.
