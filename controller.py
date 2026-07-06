import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Reference brain for the Saqi v2 box: the exact loop the ESP32 firmware ports.
# Run it to replay a season where things go wrong on purpose.

DAYS = 100
KC = 0.35
ET_BIAS = 1.08          # the model over-estimates drying a little; anchoring fixes it
TRIGGER = 0.50
STRESS = 0.65
PUMP_LPH = 4000
PUMP_HOURS = 8
MAX_DRAW = 30000        # liters/day the well tolerates
MAX_ZONE_MM = 25        # per-zone cutoff per day, runtime fail-safe
ANCHOR_EVERY = 7        # re-anchor the account to the probe weekly
DEAD_AFTER = 10         # identical probe readings for this long = dead probe
RESPONSE = 0.4          # watered soil must show at least this share of the credit

ZONES = [("sandy", 2400, 46, 1.15), ("loam", 3000, 72, 1.0)]


class World:
    # ground truth the controller cannot see directly
    def __init__(self, rng):
        self.rng = rng
        self.n = len(ZONES)
        self.area = np.array([z[1] for z in ZONES], float)
        self.taw = np.array([z[2] for z in ZONES], float)
        self.exp = np.array([z[3] for z in ZONES], float)
        self.dep = self.taw * 0.4
        self.probe_stuck = [None] * self.n     # None or the frozen reading
        self.valve_stuck = [False] * self.n
        self.stress_days = np.zeros(self.n)

    def weather(self, day):
        et0 = 4.5 + 2.0 * self.rng.random()
        rain = 25.0 if day in (45, 46) else 0.0
        return et0, rain

    def deliver(self, give_mm):
        done = np.where([s for s in self.valve_stuck], 0.0, give_mm)
        self.dep = np.maximum(self.dep - done, 0.0)
        return done

    def evolve(self, et0, rain):
        self.dep = np.clip(self.dep + KC * et0 * self.exp - rain, 0.0, self.taw)
        self.stress_days += self.dep > STRESS * self.taw

    def probe(self, z):
        if self.probe_stuck[z] is not None:
            return self.probe_stuck[z]
        return self.dep[z] + self.rng.normal(0, 0.4)


class Controller:
    def __init__(self, world):
        self.w = world
        self.n = world.n
        self.taw = world.taw.copy()
        self.area = world.area.copy()
        self.dep = self.taw * 0.4              # its belief
        self.history = [[] for _ in range(self.n)]
        self.probe_ok = [True] * self.n
        self.hold_until = np.zeros(self.n, int)    # zone parked after a valve alarm
        self.gave = np.zeros(self.n)
        self.alarms = []
        self.log = []

    def boot(self, day):
        # power came back: never trust valve state, close everything first
        self.log.append((day, "boot: all valves closed, pump off"))

    def check_probes(self, day):
        for z in range(self.n):
            r = self.w.probe(z)
            self.history[z].append(r)
            h = self.history[z][-DEAD_AFTER:]
            if self.probe_ok[z] and len(h) == DEAD_AFTER and np.ptp(h) < 0.01:
                self.probe_ok[z] = False
                self.alarms.append((day, f"probe {ZONES[z][0]}: no movement for {DEAD_AFTER} days, running on model only"))

    def check_response(self, day):
        # yesterday's watering must show up in the soil, or the line is broken.
        # a probe that has stopped moving cannot testify, so it is excluded:
        # a frozen probe looks exactly like a dead valve otherwise
        for z in range(self.n):
            alive = self.probe_ok[z] and np.ptp(self.history[z][-5:]) > 0.01
            if self.gave[z] > 5.0 and alive and day >= self.hold_until[z]:
                expected = self.gave[z]
                actual = self.history[z][-2] - self.history[z][-1] + KC * 5.5 * self.w.exp[z]
                if actual < RESPONSE * expected:
                    self.alarms.append((day, f"valve {ZONES[z][0]}: watered {expected:.0f}mm but soil did not respond, check valve/line"))
                    self.dep[z] = self.history[z][-1]      # trust the probe, undo the credit
                    self.hold_until[z] = day + 7           # park the zone, alarm once, wait for a human

    def anchor(self, day):
        if day % ANCHOR_EVERY == 0:
            for z in range(self.n):
                if self.probe_ok[z]:
                    self.dep[z] = np.clip(self.history[z][-1], 0.0, self.taw[z])

    def decide(self, day):
        give = np.zeros(self.n)
        budget = min(PUMP_HOURS * PUMP_LPH, MAX_DRAW)
        for z in np.argsort(-(self.dep / self.taw)):
            if day < self.hold_until[z]:
                continue
            if self.dep[z] > TRIGGER * self.taw[z]:
                mm = min(self.dep[z], MAX_ZONE_MM)             # runtime cutoff
                mm = min(mm, budget / self.area[z])
                give[z] = mm
                budget -= mm * self.area[z]
        return give

    def day(self, day, reboot=False):
        if reboot:
            self.boot(day)
        et0, rain = self.w.weather(day)                        # DHT22 + rain gauge
        self.dep = np.clip(self.dep + KC * et0 * ET_BIAS * self.w.exp - rain, 0.0, self.taw)
        self.check_probes(day)
        self.check_response(day)
        self.anchor(day)
        give = np.zeros(self.n) if (reboot or rain > 2) else self.decide(day)
        delivered = self.w.deliver(give)
        self.dep = np.maximum(self.dep - give, 0.0)            # committed stop: credit what was commanded
        self.gave = give
        self.w.evolve(et0, rain)
        return delivered


if __name__ == "__main__":
    rng = np.random.default_rng(11)
    world = World(rng)
    ctrl = Controller(world)
    trace = []

    for day in range(DAYS):
        if day == 20:
            world.probe_stuck[0] = world.dep[0]        # sandy probe freezes
        if day == 75:
            world.valve_stuck[1] = True                # loam valve jams shut
        if day == 85:
            world.valve_stuck[1] = False               # farmer fixes it after the alarm
        ctrl.day(day, reboot=(day == 60))
        trace.append(world.dep / world.taw)

    trace = np.array(trace)
    events = [(20, "probe freezes"), (45, "storm"), (60, "power loss"), (75, "valve jams"), (85, "fixed")]

    fig, a = plt.subplots(figsize=(9.5, 3.8))
    a.plot(trace[:, 0], color="#d1662f", lw=1.8, label="sandy zone (probe dies day 20)")
    a.plot(trace[:, 1], color="#2ca02c", lw=1.8, label="loam zone (valve jams day 75)")
    a.axhline(STRESS, color="#888888", ls="--", lw=1)
    a.text(DAYS - 1, STRESS + 0.015, "stress line", ha="right", fontsize=9, color="#888888")
    for d, name in events:
        a.axvline(d, color="#aaaaaa", lw=0.8, ls=":")
        a.text(d + 0.8, 0.97, name, rotation=90, fontsize=7.5, ha="left", va="top", color="#666666")
    a.set_xlabel("day")
    a.set_ylabel("true depletion (fraction)")
    a.set_ylim(0, 1.0)
    a.set_title("A season of faults: detect, degrade, alarm, recover", fontsize=11)
    a.legend(fontsize=9, loc="lower right")
    fig.tight_layout()
    fig.savefig("saqi2_faults.png", dpi=130)

    print("alarms and events:")
    for d, msg in sorted(ctrl.alarms + ctrl.log):
        print(f"  day {d:3d}  {msg}")
    print(f"stress days: sandy {world.stress_days[0]:.0f}, loam {world.stress_days[1]:.0f} of {DAYS}")
    print("saved saqi2_faults.png")
