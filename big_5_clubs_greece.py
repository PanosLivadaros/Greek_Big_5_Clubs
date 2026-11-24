import time
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pytrends.request import TrendReq

pytrends = TrendReq(hl="en-US", tz=120, retries=0, backoff_factor=0)

def with_retry(fn, *args, tries=4, wait=10, **kwargs):
    """Retry a pytrends call, since Google sometimes returns 429 (rate limit)."""
    for i in range(tries):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            print(f"Attempt {i+1} failed: {type(e).__name__}: {e}")
            if i < tries - 1:
                time.sleep(wait * (i + 1))
    raise RuntimeError("All attempts failed")

for t in ["Olympiacos", "Panathinaikos", "AEK Athens", "PAOK", "Aris Thessaloniki"]:
    print(t, "->", with_retry(pytrends.suggestions, t)[:2], "\n")
    time.sleep(2)

######################################################################

TOPICS = { # Paste the mids you chose, e.g. "/m/0xxxxx", current mids for football/soccer, commented out mids for basketball
    "Olympiacos":    '/m/0hqzm6r', # '/m/0fw9vx'
    "Panathinaikos": '/m/025rpyx', # '/m/0h4y62'
    "AEK":           '/m/03x6rj', # '/m/0h39nb'
    "PAOK":          '/m/03lx_t', # '/m/06n_4j'
    "Aris":          '/m/0263n1s', # '/m/027g090'
}

pytrends.build_payload(list(TOPICS.values()), geo="GR", timeframe="today 5-y")
time.sleep(2)
raw = pytrends.interest_by_region(resolution="REGION", inc_low_vol=True, inc_geo_code=True)
raw = raw.rename(columns={mid: team for team, mid in TOPICS.items()})
raw.to_csv("trends_raw.csv")

with open("trends_raw.csv", encoding="utf-8") as f:
    for line in f:
        print(line.rstrip("\n"))

######################################################################

TEAMS = list(TOPICS.keys())

def norm(s):
    return (s.lower().replace("eastern", "east").replace("western", "west")
             .replace("northern", "north").replace("southern", "south")
             .replace("region of ", "").replace(" region", "").strip())

df = raw[TEAMS].copy()
df.index = [norm(i) for i in df.index]

print("Regions found:", len(df))
print("\nMissing values per column:\n", df.isna().sum())
print("\nRegions where all five clubs are 0 (too little data):",
      list(df.index[df.sum(axis=1) == 0]))

df = df.apply(pd.to_numeric, errors="coerce")
totals = df.sum(axis=1).replace(0, np.nan)
share = df.div(totals, axis=0).astype(float) * 100

empty_regions = share.index[share.isna().all(axis=1)].tolist()
print("Regions with no data (excluded from winners/averages):", empty_regions)

share.round(1).to_csv("club_share_by_region.csv")

valid = share.dropna(how="all")
winners = valid.idxmax(axis=1)

summary = pd.DataFrame({
    "regions_won":      winners.value_counts().reindex(TEAMS, fill_value=0),
    "avg_share_pct":    valid.mean().round(1),
    "max_share_pct":    valid.max().round(1),
    "strongest_region": valid.idxmax(),
    "weakest_region":   valid.idxmin(),
}).sort_values(["regions_won", "avg_share_pct"], ascending=False)

summary.to_csv("club_summary.csv")

######################################################################

order = valid.sort_values("PAOK").index.tolist() + empty_regions
n_regions = len(order)

fig_height = max(6, 0.3 * n_regions)
ax = share.loc[order].plot(kind="barh", stacked=True, figsize=(10, fig_height), width=0.8)
fig = ax.figure
ax.set_xlabel("Share of big-5 club search interest (%)")
ax.set_ylabel("")
ax.set_title("Football club interest by Greek region (Google Trends, last 5 years)")
ax.legend(loc="center left", bbox_to_anchor=(1, 0.5))
plt.tight_layout(); plt.savefig("club_share_by_region.png", dpi=150)

VIEW_ROWS = 30
if n_regions > VIEW_ROWS:
    fig.set_size_inches(10, 8)
    plt.tight_layout()
    ax.set_ylim(n_regions - VIEW_ROWS - 0.5, n_regions - 0.5)

    def _scroll(event):
        lo, hi = ax.get_ylim()
        shift = 3 if event.button == "up" else -3
        shift = max(shift, -0.5 - lo)
        shift = min(shift, (n_regions - 0.5) - hi)
        ax.set_ylim(lo + shift, hi + shift)
        fig.canvas.draw_idle()

    fig.canvas.mpl_connect("scroll_event", _scroll)

plt.show()

######################################################################

plot_df = summary[["regions_won", "avg_share_pct", "max_share_pct"]].sort_values(
    "avg_share_pct", ascending=False
)
clubs = plot_df.index.tolist()
x = np.arange(len(clubs))

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))

bars = ax1.bar(x, plot_df["regions_won"], color="#4C72B0")
ax1.bar_label(bars, padding=2)
ax1.set_xticks(x, clubs)
ax1.set_ylabel("Regions won (total: 191)")
ax1.set_title("Regions won")
ax1.set_ylim(0, 200)

w = 0.38
b1 = ax2.bar(x - w/2, plot_df["avg_share_pct"], w, label="Average share", color="#55A868")
b2 = ax2.bar(x + w/2, plot_df["max_share_pct"], w, label="Max share (best region)", color="#C44E52")
ax2.bar_label(b1, fmt="%.0f", padding=2)
ax2.bar_label(b2, fmt="%.0f", padding=2)
ax2.set_xticks(x, clubs)
ax2.set_ylabel("Share of big-5 search interest (%)")
ax2.set_title("Average vs. maximum share")
ax2.legend()

for ax in (ax1, ax2):
    ax.spines[["top", "right"]].set_visible(False)

plt.tight_layout()
plt.savefig("club_summary_chart.png", dpi=150)
plt.show()
