import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Saqi v2: one offline controller, zones instead of trees.
# Each zone keeps a water account (depletion in mm). The controller refills
# accounts by sequencing the pump, and stops on committed water.

DAYS = 120
KC = 0.35                # olive under regulated deficit irrigation
RAIN_P = 0.04
STRESS = 0.65            # fraction of TAW where stress starts
PUMP_LPH = 4000          # pump output, liters/hour
PUMP_HOURS = 8           # max pump hours per day
TIMER_HOURS = 5          # cheap timer box: same hours for every zone, blind
OVERFILL = 0.15          # manual stopping waters ~15% past full

ZONES = [
    # name, area m2, TAW mm (soil water capacity), exposure
    ("sandy south", 2400, 46, 1.15),
    ("sandy east", 1800, 50, 1.05),
    ("loam center", 3000, 72, 1.0),
    ("loam west", 2200, 68, 0.95),
    ("clay north", 1600, 90, 0.9),
]


class Farm:
    def __init__(self, rng):
        self.rng = rng
        self.n = len(ZONES)
        self.area = np.array([z[1] for z in ZONES], float)
        self.taw = np.array([z[2] for z in ZONES], float)
        self.exp = np.array([z[3] for z in ZONES], float)
        self.dep = self.taw * rng.uniform(0.3, 0.5, self.n)   # depletion, mm
        self.stress_days = np.zeros(self.n)
        self.water = 0.0          # liters pumped
        self.hours = 0.0          # pump hours
        self.drained = 0.0        # liters lost past field capacity
        self.trips = 0            # times someone had to go to the farm
        self.debt = np.zeros(self.n)   # advice mode: water still owed to a zone

    def weather(self):
        et0 = 4.5 + 2.0 * self.rng.random()                   # mm/day, dry season
        rain = self.rng.uniform(4, 18) if self.rng.random() < RAIN_P else 0.0
        return et0, rain

    def apply(self, give_mm):
        # give_mm: irrigation depth per zone for today
        liters = give_mm * self.area
        self.water += liters.sum()
        self.hours += liters.sum() / PUMP_LPH
        new_dep = self.dep - give_mm
        over = np.maximum(-new_dep, 0.0)
        self.drained += (over * self.area).sum()
        self.dep = np.maximum(new_dep, 0.0)

    def evolve(self, et0, rain):
        self.dep = np.clip(self.dep + KC * et0 * self.exp - rain, 0.0, self.taw)
        self.stress_days += self.dep > STRESS * self.taw


def cap_to_pump(give_mm, farm):
    # the pump can only deliver so much in a day; driest zones first
    need_l = give_mm * farm.area
    budget = PUMP_HOURS * PUMP_LPH
    order = np.argsort(-(farm.dep / farm.taw))
    out = np.zeros(farm.n)
    for z in order:
        take = min(need_l[z], budget)
        out[z] = take / farm.area[z]
        budget -= take
        if budget <= 0:
            break
    return out


def timer(farm, day):
    # common practice: fixed rotation, one zone per day, same hours for all
    give = np.zeros(farm.n)
    z = day % farm.n
    give[z] = TIMER_HOURS * PUMP_LPH / farm.area[z]
    return give


def advice(farm, day):
    # the app knows exactly who needs water; a person drives out when it says
    # so and soaks each zone until it looks done, which runs past full
    crossed = (farm.dep > 0.5 * farm.taw) & (farm.debt <= 0)
    farm.debt[crossed] = farm.dep[crossed] * (1 + OVERFILL)
    give = cap_to_pump(farm.debt.copy(), farm)
    farm.debt = np.maximum(farm.debt - give, 0.0)
    if give.any():
        farm.trips += 1
    return give


def auto(farm, day):
    # the controller: refill any zone past threshold, exactly to full,
    # committed-water stop, driest first under pump capacity
    give = np.where(farm.dep > 0.5 * farm.taw, farm.dep, 0.0)
    return cap_to_pump(give, farm)


def season(strategy, seed):
    rng = np.random.default_rng(seed)
    farm = Farm(rng)
    trace = []
    for day in range(DAYS):
        farm.apply(strategy(farm, day))
        farm.evolve(*farm.weather())
        trace.append(farm.dep / farm.taw)
    return farm, np.array(trace)


def run(seeds=range(30)):
    out = {}
    for name, strat in [("Timer box", timer), ("Advice app", advice), ("Saqi v2", auto)]:
        stats = np.array([[f.water / 1000, f.hours, f.stress_days.mean(), f.drained / 1000, f.trips]
                          for f, _ in (season(strat, s) for s in seeds)])
        out[name] = stats.mean(0)
    return out


if __name__ == "__main__":
    res = run()
    names = list(res)
    colors = ["#888888", "#d1662f", "#2ca02c"]

    fig, ax = plt.subplots(1, 4, figsize=(12.5, 3.6))
    panels = [(2, "Stress-days per zone", "days"), (4, "Trips to the farm", "trips"),
              (1, "Pump hours (diesel)", "hours"), (3, "Water drained, wasted", "m3")]
    for a, (idx, title, unit) in zip(ax, panels):
        vals = [res[n][idx] for n in names]
        a.bar(names, vals, color=colors)
        a.set_title(title, fontsize=10.5)
        a.set_ylabel(unit, fontsize=9)
        a.tick_params(axis="x", labelsize=8.5)
        for j, v in enumerate(vals):
            a.text(j, v, f"{v:.0f}", ha="center", va="bottom", fontsize=9)
    fig.suptitle("120-day dry season, 5 soil zones, 30 seeds: knowing when to water is not the hard part, acting on it is", fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    fig.savefig("saqi2_season.png", dpi=130)

    _, tr_tim = season(timer, 3)
    _, tr_auto = season(auto, 3)
    z = 0    # the sandy zone dries fastest
    fig2, a = plt.subplots(figsize=(9, 3.6))
    a.plot(tr_tim[:, z], color="#888888", lw=1.8, label="timer box, same hours for every zone")
    a.plot(tr_auto[:, z], color="#2ca02c", lw=1.8, label="Saqi v2, watered when the account runs low")
    a.axhline(STRESS, color="#d1662f", ls="--", lw=1)
    a.text(DAYS - 1, STRESS + 0.015, "stress line", ha="right", fontsize=9, color="#d1662f")
    a.set_xlabel("day")
    a.set_ylabel("depletion (fraction of soil capacity)")
    a.set_title("Sandy zone: a blind timer slowly loses it; the controller holds it in the band", fontsize=11)
    a.legend(fontsize=9)
    fig2.tight_layout()
    fig2.savefig("saqi2_timer_vs_auto.png", dpi=130)

    for n in names:
        w, h, sd, dr, tp = res[n]
        print(f"{n:12s} water {w:6.0f} m3   pump {h:5.0f} h   stress {sd:5.1f} d/zone   drained {dr:5.0f} m3   trips {tp:4.0f}")
    print("saved saqi2_season.png, saqi2_timer_vs_auto.png")
