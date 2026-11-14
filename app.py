"""Field Shift - Streamlit app.

Usage (from the project folder):
    python run.py
"""
from pathlib import Path

import altair as alt
import folium
import numpy as np
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from fieldshift import config as cfg, indicators as ind, pso, scoring as sc

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "power_braganca_daily.csv"
NDVI_FILES = sorted((ROOT / "data").glob("ndvi_braganca_field*_monthly.csv"))
NDVI_BARE = 0.25  # NDVI below this = bare soil or dry vegetation (rule of thumb)
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Colours: one per criterion, always in the same order (palette checked for colour blindness)
CRIT_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
# Year types: internal values (from indicators.py) -> label shown on screen
YEAR_LABELS = {"seco": "dry", "normal": "normal", "chuva intensa": "heavy rain"}
YEAR_COLORS = {"dry": "#eb6834", "normal": "#9aa0a6", "heavy rain": "#2a78d6"}
CRIT_NAMES = [cfg.CRITERIA[c]["nome"] for c in sc.CRITERIA]
MARGIN_COLS = ["Low", "Central", "High"]

SCEN_ALL, SCEN_DRY, SCEN_WET, SCEN_ONE = "All years", "Dry years", "Heavy-rain years", "A single year"

st.set_page_config(page_title="Field Shift", page_icon="🌱", layout="wide")


# --------------------------------------------------------------------------- data
@st.cache_data(show_spinner="Loading NASA POWER data...")
def load_daily(lat: float, lon: float) -> pd.DataFrame:
    pilot = cfg.PILOT
    if abs(lat - pilot["lat"]) < 1e-6 and abs(lon - pilot["lon"]) < 1e-6 and DATA.exists():
        return pd.read_csv(DATA, parse_dates=["date"], index_col="date")
    from scripts.fetch_power import fetch_point
    return fetch_point(lat, lon, verbose=False)


@st.cache_data
def base_tables(lat: float, lon: float):
    d = load_daily(lat, lon)
    return ind.climate_indicators(d), ind.crop_year_table(d)


def crops_with(margins: pd.DataFrame, has_forage_outlet: bool) -> dict:
    """Crops with the margins edited by the user and the farm constraints applied."""
    crops = {k: dict(v) for k, v in cfg.CROPS.items()}
    key_of = {label: key for key, label in cfg.CROP_SHORT.items()}
    for label, row in margins.iterrows():
        crops[key_of[label]]["margem"] = tuple(float(row[c]) for c in MARGIN_COLS)
    if not has_forage_outlet:
        crops["luzerna"]["margem"] = (0.0, 0.0, 0.0)
    return crops


@st.cache_data
def load_ndvi() -> pd.DataFrame:
    """Monthly Sentinel-2 NDVI for the Bragança fields (scripts/fetch_ndvi.py)."""
    frames = []
    for f in NDVI_FILES:
        d = pd.read_csv(f)
        d["field"] = "Field " + f.stem.split("field")[1].split("_")[0]
        frames.append(d)
    return pd.concat(frames, ignore_index=True)


def pct(x: float) -> str:
    return f"{100 * x:.0f}%"


# ----------------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Your priorities")
    st.caption("From 0 (does not matter) to 10 (very important).")
    weights = {}
    for key, c in cfg.CRITERIA.items():
        weights[key] = st.slider(c["nome"], 0, 10, cfg.DEFAULT_WEIGHTS[key], help=c["descricao"])

    st.header("Your farm")
    irrigated = st.checkbox("I can irrigate the potato", value=False,
                            help="With irrigation, the potato's water shortage no longer counts as a risk; "
                                 "it counts as irrigation water instead.")
    forage_outlet = st.checkbox("I have an outlet for forage", value=True,
                                help="Own livestock or a buyer. Without an outlet, the forage earns no revenue.")

    st.header("Scenario")
    scenario = st.radio("Which years to compare?", [SCEN_ALL, SCEN_DRY, SCEN_WET, SCEN_ONE],
                        label_visibility="collapsed")

    with st.expander("Another location (experimental)"):
        st.caption("Downloads NASA POWER data for another point. The crop calendars were designed for "
                   "Bragança and do not work for the southern hemisphere.")
        lat = st.number_input("Latitude", -60.0, 70.0, cfg.PILOT["lat"], format="%.2f")
        lon = st.number_input("Longitude", -180.0, 180.0, cfg.PILOT["lon"], format="%.2f")

is_pilot = abs(lat - cfg.PILOT["lat"]) < 1e-6 and abs(lon - cfg.PILOT["lon"]) < 1e-6
place = f"{cfg.PILOT['nome']}, Portugal" if is_pilot else f"{lat:.2f}°, {lon:.2f}°"

try:
    clim, crop_table = base_tables(lat, lon)
except Exception as exc:  # no network, or no data for this point
    st.error(f"Could not get NASA POWER data for this point ({exc}).")
    st.stop()

# --------------------------------------------------------------------------- header
st.title("Field Shift: compare crop rotations")
st.caption(f"Pilot site: {place} · Daily NASA POWER climate, 2000–2025 · NASA Space Apps Challenge 2026")
st.warning("This tool supports the decision; it does not replace it. The results combine NASA climate data with "
           "agronomic and market assumptions that still have to be validated by a local agronomist.", icon="⚠️")

years_all = clim.index
if scenario == SCEN_DRY:
    years = clim.index[clim["tipo_ano"] == "seco"]
elif scenario == SCEN_WET:
    years = clim.index[clim["tipo_ano"] == "chuva intensa"]
elif scenario == SCEN_ONE:
    years = [st.sidebar.select_slider("Year", options=list(years_all), value=int(clim["precip_mm"].idxmin()))]
else:
    years = years_all
years = list(years)

# ----------------------------------------------------------- 1. what the data shows
st.header("1. What NASA data shows about the site")
st.caption("This section only describes the site's conditions. It says nothing about the effect of the rotations.")

left, right = st.columns([1, 2])
with left:
    m = folium.Map(location=[lat, lon], zoom_start=9, tiles="OpenStreetMap")
    folium.Marker([lat, lon], tooltip=place).add_to(m)
    # Approximate NASA POWER cell (0.5° x 0.625°): the data is regional, not field-level
    folium.Rectangle([[lat - 0.25, lon - 0.3125], [lat + 0.25, lon + 0.3125]], color="#2a78d6",
                     weight=1, fill=True, fill_opacity=0.08,
                     tooltip="Approximate area the climate data refers to").add_to(m)
    st_folium(m, height=320, use_container_width=True, returned_objects=[])
    st.caption("The rectangle shows the approximate area of one NASA POWER cell. The data is regional.")
with right:
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Rain per year", f"{clim['precip_mm'].mean():.0f} mm")
    k2.metric("Mean temperature", f"{clim['t_media'].mean():.1f} °C")
    k3.metric("Frost days per year", f"{clim['dias_geada'].mean():.0f}")
    k4.metric("Heavy-rain days", f"{clim['dias_chuva_intensa'].mean():.1f}",
              help=f"Days with {cfg.HEAVY_RAIN_MM:.0f} mm or more, per year")

    cdf = clim.reset_index()
    cdf["in_scenario"] = cdf["ano"].isin(years)
    cdf["year_type"] = cdf["tipo_ano"].map(YEAR_LABELS)
    chart = alt.Chart(cdf).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        x=alt.X("ano:O", title=None, axis=alt.Axis(labelAngle=0, values=list(range(2000, 2026, 5)))),
        y=alt.Y("precip_mm:Q", title="Rain (mm per year)"),
        color=alt.Color("year_type:N", title="Year type",
                        scale=alt.Scale(domain=list(YEAR_COLORS), range=list(YEAR_COLORS.values())),
                        legend=alt.Legend(orient="top")),
        opacity=alt.condition("datum.in_scenario", alt.value(1.0), alt.value(0.3)),
        tooltip=[alt.Tooltip("ano:O", title="Year"), alt.Tooltip("precip_mm:Q", title="Rain (mm)", format=".0f"),
                 alt.Tooltip("year_type:N", title="Year type"),
                 alt.Tooltip("dias_chuva_intensa:Q", title="Heavy-rain days"),
                 alt.Tooltip("dias_geada:Q", title="Frost days"),
                 alt.Tooltip("t_media:Q", title="Mean temperature (°C)", format=".1f")],
    ).properties(height=230)
    st.altair_chart(chart, use_container_width=True)
    st.caption("Dry year: among the 20% with the least rain. Heavy-rain year: among the 20% with the most "
               f"heavy-rain days. Faded bars are outside the chosen scenario ({scenario.lower()}).")

# Satellite check: does the cereal calendar match the imagery?
if is_pilot and NDVI_FILES:
    st.subheader("Satellite check: when is the soil without green vegetation?")
    ndvi = load_ndvi()
    # Window in which the wheat calendar (config.py) leaves the soil uncovered
    (m0, d0), (m1, d1) = cfg.CROPS["trigo"]["cover"][0][1], cfg.CROPS["trigo"]["cover"][1][0]
    # Each point sits mid-month: day d of month m is at m - 0.5 + (d - 1) / 31
    bare_from, bare_to = m0 - 0.5 + d0 / 31, m1 - 0.5 + (d1 - 1) / 31
    # Mid grey and a transparent band: readable in both the light and the dark theme
    band = alt.Chart(pd.DataFrame({"x0": [bare_from], "x1": [bare_to]})).mark_rect(
        color="#b08a5e", opacity=0.22).encode(x="x0:Q", x2="x1:Q")
    band_label = alt.Chart(pd.DataFrame({"x": [(bare_from + bare_to) / 2], "y": [0.66]})).mark_text(
        color="#9aa0a6", fontSize=11).encode(x="x:Q", y="y:Q", text=alt.value("wheat calendar: soil uncovered"))
    rule = alt.Chart(pd.DataFrame({"y": [NDVI_BARE]})).mark_rule(
        color="#9aa0a6", strokeDash=[4, 3]).encode(y="y:Q")
    lines = alt.Chart(ndvi).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=40, filled=True)).encode(
        x=alt.X("month:Q", title=None, scale=alt.Scale(domain=[1, 12.4], nice=False),
                axis=alt.Axis(values=list(range(1, 13)), labelExpr=f"{MONTHS}[datum.value - 1]")),
        y=alt.Y("ndvi_median:Q", title="NDVI (monthly median, 2017–2025)", scale=alt.Scale(domain=[0, 0.7])),
        color=alt.Color("field:N", title=None, scale=alt.Scale(range=["#2a78d6", "#eb6834", "#1baf7a"]),
                        legend=alt.Legend(orient="top")),
        tooltip=[alt.Tooltip("field:N", title="Field"), alt.Tooltip("month:Q", title="Month"),
                 alt.Tooltip("ndvi_median:Q", title="Median NDVI", format=".2f"),
                 alt.Tooltip("share_bare:Q", title="Years with NDVI < 0.25", format=".0%")],
    )
    st.altair_chart((band + band_label + rule + lines).properties(height=260), use_container_width=True)
    summer = ndvi[ndvi["month"].isin([7, 8, 9])]["ndvi_median"].max()
    winter = ndvi[ndvi["month"].isin([1, 2, 3])]["ndvi_median"]
    st.caption(
        f"Three cereal fields north-east of Bragança, Sentinel-2 (ESA Copernicus), cloud-masked. From July to "
        f"September the median NDVI stays below {NDVI_BARE:.2f} (maximum {summer:.2f}): the soil has no green "
        "vegetation, as the wheat calendar says. The drop already starts in May and June, as the grain ripens and "
        f"dries. In winter NDVI is between {winter.min():.2f} and {winter.max():.2f}: there is vegetation, but it is "
        "sparse, far from a lush pasture (0.7 to 0.9). Low NDVI can also be stubble, which still protects the soil. "
        "Details in docs/ndvi_sentinel2.md.")

# --------------------------------------------------------------- 2. comparison
st.header("2. Comparing the strategies")

with st.expander("Margin assumptions per crop (editable)"):
    st.caption("Gross margin in euros per hectare per year. These are the team's manual estimates, not confirmed "
               "market prices. Replace them with your own values.")
    default_margins = pd.DataFrame(
        {cfg.CROP_SHORT[k]: v["margem"] for k, v in cfg.CROPS.items()}, index=MARGIN_COLS).T
    default_margins.index.name = "Crop"
    margins = st.data_editor(default_margins, use_container_width=True, key="margins")

crops = crops_with(margins, forage_outlet)
strat_years = ind.strategy_year_table(crop_table, crops=crops, irrigated_potato=irrigated)
# Fixed reference scales: no irrigation, central margins, full record
refs = sc.reference_scales(ind.strategy_year_table(crop_table, crops=crops))
sub = sc.subscores(strat_years, refs)
summary = sc.summarise(sub, weights, years)
w = sc.normalise_weights(weights)
names = {k: v["nome"] for k, v in cfg.STRATEGIES.items()}

best = summary.index[0]
second = summary.index[1]
gap = summary.loc[best, "pontuacao"] - summary.loc[second, "pontuacao"]
n_years = int(summary["n_anos"].iloc[0])
year_text = f"in {years[0]}" if n_years == 1 else f"over the {n_years} years of the scenario"
if gap < 2:
    st.info(f"**{names[best]}** and **{names[second]}** are practically tied {year_text} "
            f"({summary.loc[best, 'pontuacao']:.0f} and {summary.loc[second, 'pontuacao']:.0f} points out of 100). "
            "The difference is smaller than the uncertainty in the data.")
else:
    st.success(f"With your priorities, **{names[best]}** comes first {year_text}, with "
               f"{summary.loc[best, 'pontuacao']:.0f} points out of 100. It leads in "
               f"{summary.loc[best, 'pct_anos_1o']:.0f}% of the years.")

if not forage_outlet:
    st.caption("Without an outlet for forage, strategy C earns no revenue in the lucerne or clover year.")

# Contribution of each criterion to the score (explains why the ranking is what it is)
contrib = summary[sc.CRITERIA].mul(100 * w, axis=1)
contrib.columns = CRIT_NAMES
long = contrib.reset_index().melt("estrategia", var_name="criterion", value_name="points")
long["name"] = long["estrategia"].map(names)
long["order"] = long["criterion"].map({n: i for i, n in enumerate(CRIT_NAMES)})
order = [names[k] for k in summary.index]
bars = alt.Chart(long).mark_bar(stroke="white", strokeWidth=1.5).encode(
    y=alt.Y("name:N", sort=order, title=None, axis=alt.Axis(labelLimit=220),
            scale=alt.Scale(paddingInner=0.3, paddingOuter=0.2)),
    x=alt.X("points:Q", title="Score (0 to 100)", scale=alt.Scale(domain=[0, 100])),
    color=alt.Color("criterion:N", title="Criterion", sort=CRIT_NAMES,
                    scale=alt.Scale(domain=CRIT_NAMES, range=CRIT_COLORS), legend=alt.Legend(orient="top")),
    order=alt.Order("order:Q"),
    tooltip=[alt.Tooltip("name:N", title="Strategy"), alt.Tooltip("criterion:N", title="Criterion"),
             alt.Tooltip("points:Q", title="Points", format=".1f")],
)
totals = summary.reset_index().assign(name=lambda t: t["estrategia"].map(names))
labels = alt.Chart(totals).mark_text(align="left", dx=6, fontWeight="bold").encode(
    y=alt.Y("name:N", sort=order), x="pontuacao:Q", text=alt.Text("pontuacao:Q", format=".0f"))
st.altair_chart((bars + labels).properties(height=alt.Step(40)), use_container_width=True)
st.caption("Each colour shows how many points come from each criterion. A criterion with priority 0 does not appear.")

# Comparison tables
ind_means = strat_years[strat_years["ano"].isin(years)].groupby("estrategia").mean(numeric_only=True)
low = ind.strategy_year_table(crop_table, crops=crops, margin_case=0).groupby("estrategia")["margem_eur_ha"].mean()
high = ind.strategy_year_table(crop_table, crops=crops, margin_case=2).groupby("estrategia")["margem_eur_ha"].mean()
table = pd.DataFrame({
    "Rank": summary["posicao"],
    "Strategy": [names[k] for k in summary.index],
    "Score": summary["pontuacao"].round(0),
    "Across years": [f"{a:.0f} to {b:.0f}" for a, b in zip(summary["p10"], summary["p90"])],
    "Years in 1st (%)": summary["pct_anos_1o"].round(0),
    "Margin (€/ha)": [f"{ind_means.loc[k, 'margem_eur_ha']:.0f} ({low[k]:.0f} to {high[k]:.0f})" for k in summary.index],
})
st.dataframe(table, hide_index=True, use_container_width=True)
table2 = pd.DataFrame({
    "Strategy": [names[k] for k in summary.index],
    "Bare soil (days)": ind_means.loc[summary.index, "dias_solo_nu"].round(0),
    "Heavy rain on bare soil (mm)": ind_means.loc[summary.index, "chuva_intensa_solo_nu_mm"].round(0),
    "Water deficit (mm)": ind_means.loc[summary.index, "defice_hidrico_mm"].round(0),
    "Frost (days)": ind_means.loc[summary.index, "dias_geada_sensivel"].round(1),
    "Nitrogen (kg/ha)": ind_means.loc[summary.index, "azoto_fixado_kg"].round(0),
})
st.dataframe(table2, hide_index=True, use_container_width=True)
st.caption("Mean values per year for the whole farm (one third of the area in each rotation phase). "
           "\"Across years\" is the range the score stays in 8 years out of 10. "
           "Frost only counts days in the crops' sensitive stages. "
           "Margin shows the central estimate and, in brackets, the low and high ones.")
if irrigated:
    rega = ind_means["rega_mm"].mean()
    st.caption(f"With irrigation, the potato needs on average about {3 * rega:.0f} mm of irrigation water a year "
               "on its field.")

# Margin uncertainty: does the ranking hold?
winners = {}
for case, label in [(0, "low"), (2, "high")]:
    sy = ind.strategy_year_table(crop_table, crops=crops, irrigated_potato=irrigated, margin_case=case)
    # Each case gets its own revenue scale (as the central case does). With the central-margin scale,
    # every high margin hits the maximum, all strategies tie and the "winner" is arbitrary.
    refs_case = sc.reference_scales(ind.strategy_year_table(crop_table, crops=crops, margin_case=case))
    winners[label] = sc.summarise(sc.subscores(sy, refs_case), weights, years).index[0]
if all(v == best for v in winners.values()):
    st.caption(f"Margin test: {names[best]} stays first with both the low and the high margins.")
else:
    st.caption("Margin test: first place changes with the low margins "
               f"({names[winners['low']]}) or the high ones ({names[winners['high']]}). Check prices before deciding.")

# Scenarios side by side (dry and heavy rain)
st.subheader("What if the year is dry or very wet?")
scen = {SCEN_ALL: list(years_all),
        SCEN_DRY: list(clim.index[clim["tipo_ano"] == "seco"]),
        SCEN_WET: list(clim.index[clim["tipo_ano"] == "chuva intensa"])}
ordinal = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}
rows = []
for label, ys in scen.items():
    res = sc.summarise(sub, weights, ys)
    row = {"Scenario": f"{label} ({len(ys)})"}
    for pos, (k, r) in enumerate(res.iterrows(), start=1):
        row[ordinal.get(pos, f"{pos}th")] = f"{cfg.STRATEGIES[k]['curto']} ({r['pontuacao']:.0f})"
    rows.append(row)
st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
st.caption("In brackets: the number of years in each scenario and each strategy's score.")

# -------------------------------------------------------------- 3. strategies
st.header("3. Each strategy in detail")
tabs = st.tabs([names[k] for k in cfg.STRATEGIES])
for tab, (key, s) in zip(tabs, cfg.STRATEGIES.items()):
    with tab:
        st.markdown("**Sequence:** " + " → ".join(cfg.CROP_LABELS[c] for c in s["culturas"]))
        a, b = st.columns(2)
        with a:
            st.markdown(f"**Why.** {s['porque']}")
            st.markdown(f"**Evidence.** {s['evidencia']}")
            st.markdown(
                f"**What the site data shows.** On average {ind_means.loc[key, 'dias_solo_nu']:.0f} bare-soil days "
                f"a year, {ind_means.loc[key, 'chuva_intensa_solo_nu_mm']:.0f} mm of heavy rain falling on bare soil "
                f"and {ind_means.loc[key, 'defice_hidrico_mm']:.0f} mm of water missing for the crops.")
            st.markdown("**Expected benefits**\n" + "\n".join(f"- {x}" for x in s["beneficios"]))
        with b:
            st.markdown("**What we do not know yet**\n" + "\n".join(f"- {x}" for x in s["lacunas"]))
            st.markdown("**Risks to check with a local agronomist**\n" + "\n".join(f"- {x}" for x in s["riscos"]))

# ----------------------------------------------------------------- 4. SI (PSO)
st.header("4. How firm is this result?")
st.caption("SI component: particle swarm optimisation (PSO) searches the space of priorities. "
           "The score above does not depend on it.")
keys = list(summary.index)
matrix = sc.criteria_matrix(sub, years).loc[keys].to_numpy()

flip = pso.flip_distance(matrix, w)
c1, c2 = st.columns(2)
with c1:
    st.subheader("How much would the priorities have to change?")
    if flip is None:
        st.write(f"No combination of priorities moves **{names[best]}** out of first place in this scenario.")
    else:
        new = keys[flip["vencedor_depois"]]
        st.write(f"Moving **{pct(flip['distancia'])}** of the total weight between criteria would be enough for "
                 f"**{names[new]}** to come first.")
        st.caption("Below 10%, the result is fragile. Above 25%, it is firm.")
        cmp = pd.DataFrame({"Criterion": CRIT_NAMES, "Now": (100 * w).round(0),
                            "To change": (100 * flip["pesos"]).round(0)})
        st.dataframe(cmp, hide_index=True, use_container_width=True)
        st.caption("Weight of each criterion, in percent.")
with c2:
    st.subheader("Which priorities explain your choice?")
    st.write("If you already have an order of preference, the swarm looks for the priorities that explain it.")
    pref = st.multiselect("Order the strategies, from most to least preferred",
                          options=list(cfg.STRATEGIES), format_func=lambda k: names[k])
    if len(pref) == len(cfg.STRATEGIES):
        res = pso.calibrate_to_ranking(matrix, [keys.index(k) for k in pref])
        if res["pares_errados"] == 0:
            st.write("These priorities reproduce your order:")
        else:
            st.write(f"No combination reproduces the full order. The closest one gets "
                     f"{res['pares_errados']} of {res['n_pares']} comparisons wrong:")
        st.dataframe(pd.DataFrame({"Criterion": CRIT_NAMES, "Weight (%)": (100 * res["pesos"]).round(0)}),
                     hide_index=True, use_container_width=True)
    else:
        st.caption("Pick all four strategies to see the result.")

# --------------------------------------------------------- 5. limits and sources
st.header("5. Limits and sources")
a, b = st.columns(2)
with a:
    st.markdown("**What this tool does not know**\n" + "\n".join(f"- {x}" for x in cfg.LIMITATIONS))
with b:
    src = pd.DataFrame([{"Criterion": c["nome"], "Where it comes from": c["fonte"]} for c in cfg.CRITERIA.values()])
    st.markdown("**Where each criterion comes from**")
    st.dataframe(src, hide_index=True, use_container_width=True)
    st.markdown("Climate: [NASA POWER](https://power.larc.nasa.gov/), agroclimatology community, "
                "daily data 2000–2025. These data were obtained from the NASA Langley Research Center "
                "(LaRC) POWER Project funded through the NASA Earth Science/Applied Science Program. "
                "Satellite: Sentinel-2 L2A, [Copernicus Data Space Ecosystem](https://dataspace.copernicus.eu/). "
                "Contains modified Copernicus Sentinel data 2017–2025. Map: © OpenStreetMap contributors.")
