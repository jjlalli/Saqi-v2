# Saqi v2 design

## The pivot, honestly

v1 modelled a farm as a mesh of small nodes, one per patch of the grove, agreeing on water
with no central computer.
The research finding (decentralized coordination survives network failure that breaks a
central controller) is true and stays published in the v1 repo.

Interviews with my father (a retired teacher who works our family's olive grove in Sidi
Bouzid) and other farmers nearby changed the deployment design:

1. Per-tree granularity is unnecessary. Same soil + same slope + same line = same moisture.
   The farm's real structure is 3 to 8 soil zones, not hundreds of trees.
2. The market already sells information. Satellite advisory products (Seabex here in
   Tunisia) tell farmers when and how much to water. They do not act. The farmer still
   drives out, opens the valve, waits, and closes it.
3. Most local irrigation runs from private wells. Well owners do not pay per litre, so
   "save water" does not sell. What they feel is diesel (pump hours) and time (trips).
   The value of automation is that the farm waters itself correctly while the owner is
   in Tunis.

So: one offline controller per farm, zones as the unit, pump hours and trips as the
objective. "Central" here means local-central (a box the farmer owns, at the manifold),
not the remote cloud v1 argued against. The v1 mesh returns at the next scale up:
several farms sharing one well, canal, or GDA network with no central authority. That is
the research track, not the product track.

## Architecture

```
[weather reading]      [zone map: soil types, areas]      [1 soil probe / zone]
        \                       |                                /
         v                      v                               v
   +---------------------------------------------------------------+
   |  controller (ESP32): daily FAO-56 water account per zone,     |
   |  refill trigger, driest-first sequencing under pump capacity, |
   |  committed-water stop                                         |
   +---------------------------------------------------------------+
        |                |                 |
        v                v                 v
   [valve zone 1]   [valve zone 2]  ...  [pump relay]
```

- Zone map: drawn once, static, on-device. It maps soil, not moisture: each zone's texture
  and water-holding capacity, which do not change with weather. Sources: the farmer's own
  knowledge of the land, a jar test per candidate zone, infiltration timing (how fast poured
  water disappears), and satellite/soil databases (bare-soil imagery, SoilGrids) to help
  draw the borders. A one-time moisture snapshot would be useless; that is not what this is.
  Everything that changes day to day (weather, moisture state) is handled by the accounts
  below, daily.
- Water account: depletion (mm) per zone. Daily ET from temperature/humidity (FAO-56
  Hargreaves is enough), rain in, irrigation in. One capacitive probe per zone corrects
  model drift weekly.
- Decision: refill when depletion crosses ~50% of the zone's available water; stress
  begins near 65%, so the margin absorbs a hot day. Driest zone first, capped by daily
  pump capacity. Stop each refill on committed water, not on the lagging probe (see
  control.py in v1 for the demonstration of why).
- No internet by default. An optional weekly phone-hotspot sync can pull a weather
  forecast; nothing depends on it.

## Pilot (two zones, family farm)

| Part | Qty | ~Cost |
|---|---|---|
| ESP32 dev board | 1 | $8 |
| Latching solenoid valve 12V | 2 | $30 |
| Capacitive soil probe | 2 | $6 |
| DHT22 temp/humidity sensor | 1 | $5 |
| Tipping-bucket rain gauge | 1 | $10 |
| H-bridge driver board, wiring, enclosure | 1 | $15 |
| Solar panel 6V 2W + 18650 + TP4056 | 1 | $15 |
| Boost converter 3.7V to 12V (valve supply) | 1 | $2 |

The valves are latching, so the driver has to reverse polarity to close them (an H-bridge, not
a single MOSFET), and their 12V pulse comes from the boost converter, not the 3.7V cell.

Firmware loop: wake, read probe + weather, update accounts, decide, drive valves, log to
SD/flash, deep sleep. Log everything; the pilot's first output is calibration constants,
its second is the season data.

Milestones: bench demo (two valves switching on account state), farm install, one month
of logs, then compare the log against the simulation's predictions. A first 10-day
side-by-side test (one zone on a kit prototype, one on a timer) ran in September 2026; see
the README.

## Two pitches, one box

- To a farmer with a well: it waters the farm by itself, correctly for each soil, and the
  pump runs fewer hours. You stop driving out to open and close valves.
- To a judge, journal, or admissions reader: smallholder irrigation automation that runs
  offline for about $150 in parts on a five-zone farm, in a market where existing products
  stop at the notification.
  Water saved matters at national scale even where an individual well owner does not feel it.

Both are true. Lead with the one the audience cares about.

## What is not designed yet (product completeness)

Stated plainly, because a design that hides its gaps is not a design.

- Rain sensing. The account math includes rain but the parts list cannot measure it.
  Add a tipping-bucket rain gauge (~$10), or infer rain when zone probes rise with no
  irrigation. Without this the box waters on a rainy day.
- Fail-safes. Latching valves keep their last state on power loss, so a battery failure
  mid-irrigation means a valve stuck open. Required: max-runtime cutoff per valve,
  watchdog reset, close-everything-on-fault, and pump dry-run protection (wells recover
  slowly; the scheduler must respect a max daily draw).
- Farmer interface and override. A physical switch that forces manual mode, a "water
  now" and "skip today" control, and a minimal status view (LEDs or the Bluetooth app).
  Nobody hands their farm to a silent box; trust is the adoption problem.
- Water-side plumbing: the box must sit behind a filter (drip clogs on well water),
  and pressure and well recovery rate are scheduler constraints, not footnotes.

Current stage, honestly: decision logic validated in simulation, plus one 10-day field
test (September 2026) where a kit prototype with the committed stop used 29% less water
than a 40-minute timer on the neighbouring zone. Only litres and run time were logged, so
there is no calibration data yet. Every remaining unknown is physical, which is why the
next step is the full two-zone install with the probe log running, with the items above
included.

## Path to product

Every farm is different, but that does not make this a service. The split that makes it a
product: the box and firmware are identical for every farm; everything farm-specific is
data. All of it already lives in one config table (the `ZONES` table in the simulation:
zones, areas, soil capacities). Productizing means making that table easy to create.

- Kit + guided setup. The product ships as a kit: controller, N valve units, weather
  sensor, probes. A setup wizard on a phone (Bluetooth to the box, still no internet)
  walks the farmer through it: mark the zones (the farmer already knows where the sandy
  patch is), pick the crop, jar test or soil-type defaults. Config is questions, not code.
- Self-calibration. After install, the box learns from its own logs how fast each zone
  really dries and how much each pump-hour delivers, and corrects the entered values.
  This is what turns "needs an agronomist" into "learns your farm," and it is the next
  research problem after the pilot.
- The installer channel exists. Tunisia subsidizes drip irrigation through APIA, so local
  drip installers already touch every modernizing farm. Saqi rides that: the day the
  manifold goes in, the installer adds one box. Getting onto the subsidy-eligible
  equipment list is the biggest commercial unlock, and it is where the national
  water-savings argument matters even though a single well owner does not feel it.
- Start narrow. Olives, Sidi Bouzid, family farm as demo unit one. Then five neighbour
  farms hand-installed, then the kit through installers, then the region.
- Pricing follows the architecture: no server, so no subscription. Sell the box once,
  priced like a pump accessory. Later paid extras: installation, spare probes, and a
  multi-farm coordinator for GDAs (the v1 mesh returning as the premium tier).

Known hard parts, stated plainly: hardware support in the field (a box that dies in week
three kills village word-of-mouth), the variety of existing plumbing, and thin hardware
margins. None of this is being built now; the pilot comes first.

## Relation to v1

- v1 = the research argument (decentralization vs failure; the control loop).
- v2 = the product design that the farmer interviews produced.
- Future = the mesh between farms: v1's consensus over v2's controllers.
