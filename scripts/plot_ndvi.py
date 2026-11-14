"""Chart of the monthly Sentinel-2 NDVI for the Bragança fields (English labels).

Reads data/ndvi_braganca_field{1,2,3}_monthly.csv (made by fetch_ndvi.py)
and writes docs/ndvi_braganca.png.

  python scripts/plot_ndvi.py
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

BARE = 0.25
FIELDS = {1: "#2a78d6", 2: "#eb6834", 3: "#1baf7a"}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
INK, INK2, SURFACE, GRID = "#0b0b0b", "#52514e", "#fcfcfb", "#e4e3df"

fig, ax = plt.subplots(figsize=(9, 4.8), dpi=150)
fig.patch.set_facecolor(SURFACE)
ax.set_facecolor(SURFACE)

ax.axhspan(0, BARE, color="#efe4d6", zorder=0)
ax.axhline(BARE, color=INK2, lw=1, ls=(0, (4, 3)), zorder=1)
ax.text(0.85, 0.03, f"bare soil or dry vegetation (NDVI < {BARE})",
        color=INK2, fontsize=9, va="bottom")

ends = {}
for f, color in FIELDS.items():
    d = pd.read_csv(f"data/ndvi_braganca_field{f}_monthly.csv")
    ax.plot(d["month"], d["ndvi_median"], color=color, lw=2, marker="o", ms=5,
            markeredgecolor=SURFACE, markeredgewidth=1.5, zorder=3, label=f"Field {f}")
    ends[f] = d.iloc[-1]["ndvi_median"]

# Direct labels at the line ends, pushed apart so they never overlap.
placed = []
for f, y in sorted(ends.items(), key=lambda kv: kv[1]):
    if placed and y - placed[-1] < 0.035:
        y = placed[-1] + 0.035
    placed.append(y)
    ax.text(12.25, y, f"Field {f}", color=INK, fontsize=9, va="center")

ax.set_xlim(0.7, 13.2)
ax.set_ylim(0, 0.7)
ax.set_xticks(range(1, 13), MONTHS)
ax.set_ylabel("NDVI (monthly median, 2017–2025)", color=INK2, fontsize=9)
ax.tick_params(colors=INK2, labelsize=9, length=0)
ax.grid(axis="y", color=GRID, lw=0.8)
for s in ax.spines.values():
    s.set_visible(False)
ax.legend(loc="upper center", ncols=3, frameon=False, fontsize=9, bbox_to_anchor=(0.5, 1.0))
fig.suptitle("Sentinel-2: the cereal fields have no green vegetation from June to October",
             x=0.06, ha="left", fontsize=12, color=INK, fontweight="bold")
fig.text(0.06, 0.02, "Three fields north-east of Bragança, Portugal · Sentinel-2 L2A, cloud-masked (SCL) · "
         "Contains modified Copernicus Sentinel data 2017–2025", fontsize=8, color=INK2)
fig.tight_layout(rect=(0, 0.04, 1, 0.97))

Path("docs").mkdir(exist_ok=True)
fig.savefig("docs/ndvi_braganca.png", facecolor=SURFACE)
print("docs/ndvi_braganca.png")
