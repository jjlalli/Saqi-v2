import csv
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# First field test, Sept 2026: zone 1 on a fixed 40-minute timer, zone 2 on the
# prototype with the committed stop. Only litres and run time were recorded.

with open("data/pilot_2026-09.csv") as f:
    rows = list(csv.DictReader(f))

dates = sorted({r["date"] for r in rows})
timer = {r["date"]: r for r in rows if r["method"] == "timer"}
proto = {r["date"]: r for r in rows if r["method"] == "committed_stop"}

lt = np.array([float(timer[d]["liters"]) for d in dates])
lp = np.array([float(proto[d]["liters"]) for d in dates])
mt = np.array([float(timer[d]["minutes"]) for d in dates])
mp = np.array([float(proto[d]["minutes"]) for d in dates])
saving = 100 * (1 - lp.sum() / lt.sum())

print(f"waterings: {len(dates)} per zone")
print(f"timer      {lt.sum():6.1f} L total  {lt.mean():5.1f} L each  {lt.sum() / mt.sum():.2f} L/min")
print(f"prototype  {lp.sum():6.1f} L total  {lp.mean():5.1f} L each  {lp.sum() / mp.sum():.2f} L/min")
print(f"prototype used {saving:.0f}% less water")

x = np.arange(len(dates))
w = 0.38
fig, a = plt.subplots(figsize=(9, 3.8))
a.bar(x - w / 2, lt, w, color="#888888", label=f"zone 1, 40-min timer ({lt.sum():.0f} L)")
a.bar(x + w / 2, lp, w, color="#2ca02c", label=f"zone 2, committed stop ({lp.sum():.0f} L)")
for i in range(len(dates)):
    a.text(x[i] - w / 2, lt[i] + 0.5, f"{mt[i]:g} min", ha="center", fontsize=8, color="#555555")
    a.text(x[i] + w / 2, lp[i] + 0.5, f"{mp[i]:g} min", ha="center", fontsize=8, color="#555555")
a.set_xticks(x)
a.set_xticklabels([f"Sep {int(d[-2:])}\n{timer[d]['temp_c']}°C" for d in dates], fontsize=9)
a.set_ylabel("litres per watering")
a.set_ylim(0, 44)
a.legend(fontsize=9, loc="upper center", ncol=2, frameon=False)
a.set_title(f"First field test, Sept 2026: the committed stop used {saving:.0f}% less water than the timer", fontsize=11)
fig.tight_layout()
fig.savefig("saqi2_pilot.png", dpi=130)
print("saved saqi2_pilot.png")
