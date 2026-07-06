# Saqi v2

An offline irrigation controller for smallholder farms. One box at the water manifold keeps
a daily water account for each soil zone of the farm and runs the pump itself: it opens the
right zone valve when a zone's account runs low, stops exactly when the refill is committed,
and never needs internet, a server, or a person driving out to turn the water off.

## Why v2 exists

[Saqi v1](https://github.com/USER/saqi) argued, in simulation, that a farm can share scarce
water with a mesh of per-tree devices and no central computer, and that this survives network
failures that break a cloud controller. That research stands.

Then I interviewed the farmer I know best: my father. Two things came out of it.

First, per-tree sensing is redundant on a real smallholder farm. Trees in the same soil, on
the same slope, watered on the same line, sit at practically the same moisture. What actually
differs is the handful of soil zones the farm splits into. Commercial precision agriculture
reaches the same conclusion; it calls them management zones.

Second, information is not the bottleneck. Products already exist here (in Tunisia, Seabex
tells you from satellite data when and how much to irrigate) and most farmers around us
irrigate from their own well, so saving water is not what they care about. What costs them is
the pump's diesel and the trips: somebody still has to drive out, open the valve, wait, and
close it. Every existing tool stops at the phone notification. Nobody automates the stopping.

So v2 keeps v1's allocation brain and re-aims it: zones instead of trees, one local controller
instead of a mesh, and the objective translated from litres into what a well irrigator feels,
pump hours and trips. The mesh idea from v1 does not die; it moves up a level, to several farms
sharing one well or canal with no central authority, which is future work.

## How it works

- The farm is split once into zones by soil type, using satellite imagery and the farmer's
  own knowledge. That map is static and lives on the device. No live satellite in the loop:
  satellite soil moisture reads the top few centimetres on a multi-day revisit, while olive
  roots drink from a metre down.
- Each zone has a water account: a running depletion estimate in mm, drained daily by
  evapotranspiration (computed FAO-56 style from a cheap local weather reading), topped up
  by rain and irrigation, and corrected by one soil probe per zone.
- When a zone's account crosses its refill line, the controller sequences the pump: driest
  zone first, within the pump's daily capacity, stopping each refill on committed water
  (what has been applied, not what a lagging sensor reads) so nothing drains past the roots.

## What is simulated and what the device does

The zoning and the water accounting are both in this repo, with one simplification each. The
zone map is a given input (the `ZONES` table at the top of `saqi2.py`, five zones with their
soil capacities); on a real farm that map is drawn once, from satellite imagery and the
farmer's knowledge, then lives on the device as exactly such a table. The ET accounting runs
every simulated day (crop coefficient times reference ET per zone), but the simulation draws
ET0 from typical dry-season values; the device computes it from its own weather reading.
In short: the repo proves the decision logic, the pilot proves the physics.

## What the simulation shows

A 120-day dry season on a 5-zone, 1.1-hectare farm, averaged over 30 random seasons, comparing
the three things a farmer can actually buy: a timer box (blind automation), an advice app
(perfect information, human execution), and Saqi v2 (informed automation).

![season](saqi2_season.png)

The timer box stresses the fast-drying sandy zones for ~18 days each while over-watering the
clay. The advice app eliminates stress, but at the cost of 79 trips to the farm in one season,
and manual stopping still drains water past the roots. The controller matches the app's zero
stress with zero trips, the fewest pump hours, and nothing wasted.

![timer vs auto](saqi2_timer_vs_auto.png)

Knowing when to water is not the hard part. Acting on it is.

## Running it

```bash
pip install -r requirements.txt
python3 saqi2.py   # -> saqi2_season.png, saqi2_timer_vs_auto.png
```

## Hardware target

One ESP32 controller at the manifold, a latching solenoid valve per zone, one capacitive soil
probe per zone, a small solar panel and battery. Rough parts cost for a 5-zone farm is under
$100. A two-zone pilot on my family's farm in Sidi Bou Zid is the next step; the plan is in
`docs/DESIGN.md`.

## Limitations

The soil and weather model is deliberately simple, and the manual-watering baseline encodes
assumptions (visit behaviour, 15% overfill) that should be measured, not assumed. The constants
that matter (each zone's capacity, drying rate, and how fast applied water settles) have to be
calibrated on a real farm; that calibration is the first job of the pilot.

## AI use

I used AI assistants to help debug the code.

## License

MIT. See `LICENSE`.
