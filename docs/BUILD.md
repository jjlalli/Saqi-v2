# Bench build guide (two-zone pilot)

Everything in `controller.py` is the logic; this is how to give it a body. Target: two
valves switching on account state on a table, then the farm.

## Wiring (ESP32 pin map)

| Signal | Pin | Notes |
|---|---|---|
| Soil probe zone 1 (capacitive, analog) | GPIO 34 | ADC1 only; ADC2 clashes with radio |
| Soil probe zone 2 | GPIO 35 | ADC1 |
| DHT22 temp/humidity | GPIO 4 | 10k pull-up to 3.3V |
| Rain gauge (tipping bucket, reed switch) | GPIO 27 | interrupt, count tips, debounce ~100ms |
| Valve 1 driver (H-bridge pulse, latching) | GPIO 25 + 26 | pulse ~50ms to open, reverse to close |
| Valve 2 driver | GPIO 32 + 33 | same |
| Pump relay | GPIO 14 | through driver board, never direct |
| Manual override switch | GPIO 13 | physical switch, forces everything closed |
| Status LEDs (ok / watering / alarm) | GPIO 21, 22, 23 | three states a farmer can read at a glance |

Power: 18650 through TP4056 charger fed by the 6V 2W panel, 3.3V regulator to the board.
The valve pulses draw more than the regulator likes; put a capacitor (1000uF) across the
valve supply.

## Firmware loop (port of controller.py, in order)

1. On boot: close both valves, pump off, then read state from flash. Power loss must
   never leave a valve open.
2. Wake daily (deep sleep otherwise; wake also on manual switch or rain-gauge interrupt).
3. Read probes, DHT22, rain count. Update each zone's account.
4. Run the checks in controller.py order: dead-probe check first, then valve-response
   check (a frozen probe cannot testify about a valve), weekly probe anchoring.
5. Decide: driest zone first, trigger at 50% depletion, caps: per-zone runtime cutoff,
   daily pump budget, daily well draw.
6. Actuate with the committed stop: compute minutes from liters needed and pump rate,
   run the valve that long, done. Do not chase the probe reading.
7. Log everything to flash (day, readings, decisions, alarms). The log is the product
   of the pilot.
8. Alarm behaviour: one alarm per fault, park the zone 7 days, alarm LED on. No retry
   hammering.

## Calibration protocol (first week on the farm)

1. Pump rate: run the pump into a known container. Liters per hour, per zone line.
2. Probe endpoints: reading in oven-dry soil and in saturated soil from each zone.
   Map linearly between them; per-zone, soils differ.
3. Zone capacity (TAW): start from the soil-type table in DESIGN.md (jar test per zone),
   then let the logs correct it: after a full refill, days until the probe returns to
   trigger gives the real drying rate.
4. Compare the first two weeks of logs against `saqi2.py` predictions; adjust KC and
   exposure per zone.

## Acceptance checklist (the box passes when)

- [ ] Pull the battery mid-watering, reconnect: both valves close on boot.
- [ ] Freeze a probe (unplug it): model-only alarm within 10 days, watering continues.
- [ ] Block a line: one alarm, zone parked, no retry flood.
- [ ] Tip the rain gauge 25mm worth: no watering that day, accounts credited.
- [ ] Flip the manual switch: everything closes, stays closed until flipped back.
- [ ] A week unattended on the bench: daily decisions logged, no spurious valve action.
