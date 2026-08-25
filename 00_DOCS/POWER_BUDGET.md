# POWER BUDGET — v3 design numbers vs. measured reality

Design numbers below are from MANIFEST.md §1 (adjudicated, December-worst-case,
Colorado Springs, tilted array). The **Measured** column is empty on purpose:
build order step 7 says log a real winter fortnight via VE.Direct before
trusting any of this. `power_log.csv` is the evidence; update this table from it.

## Production (design)

```
400 W panels × 4.0 PSH (Dec, TILTED — this is POA, not GHI) × 0.75 derate = 1,200 Wh/day
minus controller + battery round-trip (~15%)                             ≈ 1,020 Wh/day usable
```

## Loads (design vs measured)

| Load | Design draw | Hours | Design Wh/day | Measured Wh/day |
|---|---|---|---|---|
| Pi 5 + NVMe + LoRa + VE.Direct logging | 10 W | 24 | 240 | |
| Networking / misc | 4 W | 24 | 96 | |
| Supervisor MCU + status display | 0.5 W | 24 | 12 | |
| **Survival baseline** | | | **~350** | |
| Battery self-heating (cold mornings) | 50–130 W | 0–1.5 | 0–100 | |
| Tier 1 session (when taken) | 130 W | 2 | 260 | |
| **Typical December working day** | | | **~610–710** | |

## Autonomy (design)

```
2.56 kWh bank × ~90% usable = ~2.3 kWh
2.3 kWh / 350 Wh baseline  = ~6.5 days dark-sky, Tier 0 only
```

## Bands (enforced by power_monitor.py; backstopped by the supervisor MCU)

GREEN >70% · YELLOW 40–70% · RED 20–40% · BLACK <20%
(MPPT-only = crude resting-voltage estimate; the SmartShunt makes it real.)

## Measurement TODOs
- [ ] Two-week December log at winter tilt (build step 7)
- [ ] Measure the actual Tier 1 box idle/load once purchased (§3)
- [ ] Measure real heater draw on the LiFePO4 once purchased (§2.4)
- [ ] Compare PVWatts (real tilt/azimuth/horizon) against the logged fortnight
