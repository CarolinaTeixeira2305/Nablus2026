"""Field Shift - aplicação Streamlit.

Uso (a partir da pasta do projeto):
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

# Cores: uma por critério, sempre na mesma ordem (paleta validada para daltonismo)
CRIT_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
YEAR_COLORS = {"seco": "#eb6834", "normal": "#9aa0a6", "chuva intensa": "#2a78d6"}
CRIT_NAMES = [cfg.CRITERIA[c]["nome"] for c in sc.CRITERIA]

st.set_page_config(page_title="Field Shift", page_icon="🌱", layout="wide")


# --------------------------------------------------------------------------- dados
@st.cache_data(show_spinner="A carregar os dados do NASA POWER...")
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
    """Culturas com as margens editadas pelo utilizador e as restrições aplicadas."""
    crops = {k: dict(v) for k, v in cfg.CROPS.items()}
    for name, row in margins.iterrows():
        crops[name]["margem"] = (float(row["Baixa"]), float(row["Central"]), float(row["Alta"]))
    if not has_forage_outlet:
        crops["luzerna"]["margem"] = (0.0, 0.0, 0.0)
    return crops


def pct(x: float) -> str:
    return f"{100 * x:.0f}%"


# ----------------------------------------------------------------------- barra lateral
with st.sidebar:
    st.header("As suas prioridades")
    st.caption("De 0 (não importa) a 10 (muito importante).")
    weights = {}
    for key, c in cfg.CRITERIA.items():
        weights[key] = st.slider(c["nome"], 0, 10, cfg.DEFAULT_WEIGHTS[key], help=c["descricao"])

    st.header("A sua exploração")
    irrigated = st.checkbox("Tenho rega para a batata", value=False,
                            help="Com rega, a falta de água da batata deixa de contar como risco e passa a contar como água de rega.")
    forage_outlet = st.checkbox("Tenho destino para a forragem", value=True,
                                help="Pecuária própria ou comprador. Sem destino, a forragem não dá receita.")

    st.header("Cenário")
    scenario = st.radio("Que anos comparar?", ["Todos os anos", "Anos secos", "Anos de chuva intensa", "Um ano"],
                        label_visibility="collapsed")

    with st.expander("Outro local (experimental)"):
        st.caption("Descarrega os dados do NASA POWER para outro ponto. Os calendários das culturas "
                   "foram pensados para Bragança e não servem para o hemisfério sul.")
        lat = st.number_input("Latitude", -60.0, 70.0, cfg.PILOT["lat"], format="%.2f")
        lon = st.number_input("Longitude", -180.0, 180.0, cfg.PILOT["lon"], format="%.2f")

is_pilot = abs(lat - cfg.PILOT["lat"]) < 1e-6 and abs(lon - cfg.PILOT["lon"]) < 1e-6
place = cfg.PILOT["nome"] if is_pilot else f"{lat:.2f}°, {lon:.2f}°"

try:
    clim, crop_table = base_tables(lat, lon)
except Exception as exc:  # sem rede ou ponto sem dados
    st.error(f"Não foi possível obter os dados do NASA POWER para este ponto ({exc}).")
    st.stop()

# ----------------------------------------------------------------------------- topo
st.title("Field Shift: comparar rotações de culturas")
st.caption(f"Ponto-piloto: {place} · Clima diário do NASA POWER, 2000 a 2025 · NASA Space Apps Challenge 2026")
st.warning("Esta ferramenta apoia a decisão, não a substitui. Os resultados juntam dados de clima da NASA com "
           "hipóteses agronómicas e de mercado que ainda têm de ser validadas por um técnico local.", icon="⚠️")

years_all = clim.index
if scenario == "Anos secos":
    years = clim.index[clim["tipo_ano"] == "seco"]
elif scenario == "Anos de chuva intensa":
    years = clim.index[clim["tipo_ano"] == "chuva intensa"]
elif scenario == "Um ano":
    years = [st.sidebar.select_slider("Ano", options=list(years_all), value=int(clim["precip_mm"].idxmin()))]
else:
    years = years_all
years = list(years)

# ----------------------------------------------------------- 1. o que os dados mostram
st.header("1. O que os dados da NASA mostram sobre o local")
st.caption("Esta secção só descreve as condições do local. Não diz nada sobre o efeito das rotações.")

left, right = st.columns([1, 2])
with left:
    m = folium.Map(location=[lat, lon], zoom_start=9, tiles="OpenStreetMap")
    folium.Marker([lat, lon], tooltip=place).add_to(m)
    # Célula aproximada do NASA POWER (0,5° x 0,625°): o dado é regional, não da parcela
    folium.Rectangle([[lat - 0.25, lon - 0.3125], [lat + 0.25, lon + 0.3125]], color="#2a78d6",
                     weight=1, fill=True, fill_opacity=0.08,
                     tooltip="Área aproximada a que os dados de clima se referem").add_to(m)
    st_folium(m, height=320, use_container_width=True, returned_objects=[])
    st.caption("O retângulo mostra a área aproximada de uma célula do NASA POWER. Os dados são regionais.")
with right:
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Chuva por ano", f"{clim['precip_mm'].mean():.0f} mm")
    k2.metric("Temperatura média", f"{clim['t_media'].mean():.1f} °C")
    k3.metric("Dias de geada por ano", f"{clim['dias_geada'].mean():.0f}")
    k4.metric("Dias de chuva intensa", f"{clim['dias_chuva_intensa'].mean():.1f}",
              help=f"Dias com {cfg.HEAVY_RAIN_MM:.0f} mm ou mais, por ano")

    cdf = clim.reset_index()
    cdf["no_cenario"] = cdf["ano"].isin(years)
    chart = alt.Chart(cdf).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        x=alt.X("ano:O", title=None, axis=alt.Axis(labelAngle=0, values=list(range(2000, 2026, 5)))),
        y=alt.Y("precip_mm:Q", title="Chuva (mm por ano)"),
        color=alt.Color("tipo_ano:N", title="Tipo de ano",
                        scale=alt.Scale(domain=list(YEAR_COLORS), range=list(YEAR_COLORS.values())),
                        legend=alt.Legend(orient="top")),
        opacity=alt.condition("datum.no_cenario", alt.value(1.0), alt.value(0.3)),
        tooltip=[alt.Tooltip("ano:O", title="Ano"), alt.Tooltip("precip_mm:Q", title="Chuva (mm)", format=".0f"),
                 alt.Tooltip("tipo_ano:N", title="Tipo de ano"),
                 alt.Tooltip("dias_chuva_intensa:Q", title="Dias de chuva intensa"),
                 alt.Tooltip("dias_geada:Q", title="Dias de geada"),
                 alt.Tooltip("t_media:Q", title="Temperatura média (°C)", format=".1f")],
    ).properties(height=230)
    st.altair_chart(chart, use_container_width=True)
    st.caption("Ano seco: entre os 20% com menos chuva. Ano de chuva intensa: entre os 20% com mais dias "
               f"de chuva forte. As barras apagadas ficam fora do cenário escolhido ({scenario.lower()}).")

# --------------------------------------------------------------- 2. comparação
st.header("2. Comparação das estratégias")

with st.expander("Hipóteses de margem por cultura (pode editar)"):
    st.caption("Margem bruta em euros por hectare e por ano. São estimativas manuais da equipa, não preços "
               "de mercado confirmados. Troque pelos seus valores.")
    default_margins = pd.DataFrame(
        {k: v["margem"] for k, v in cfg.CROPS.items()}, index=["Baixa", "Central", "Alta"]).T
    default_margins.index.name = "Cultura"
    margins = st.data_editor(default_margins, use_container_width=True, key="margins")

crops = crops_with(margins, forage_outlet)
strat_years = ind.strategy_year_table(crop_table, crops=crops, irrigated_potato=irrigated)
# Escalas de referência fixas: sem rega, margens centrais, todo o histórico
refs = sc.reference_scales(ind.strategy_year_table(crop_table, crops=crops))
sub = sc.subscores(strat_years, refs)
summary = sc.summarise(sub, weights, years)
w = sc.normalise_weights(weights)
names = {k: v["nome"] for k, v in cfg.STRATEGIES.items()}

best = summary.index[0]
second = summary.index[1]
gap = summary.loc[best, "pontuacao"] - summary.loc[second, "pontuacao"]
n_years = int(summary["n_anos"].iloc[0])
year_text = f"em {years[0]}" if n_years == 1 else f"nos {n_years} anos do cenário"
if gap < 2:
    st.info(f"**{names[best]}** e **{names[second]}** ficam praticamente empatadas {year_text} "
            f"({summary.loc[best, 'pontuacao']:.0f} e {summary.loc[second, 'pontuacao']:.0f} pontos em 100). "
            "A diferença é menor do que a incerteza dos dados.")
else:
    st.success(f"Com as suas prioridades, **{names[best]}** fica em primeiro {year_text}, com "
               f"{summary.loc[best, 'pontuacao']:.0f} pontos em 100. Fica à frente em "
               f"{summary.loc[best, 'pct_anos_1o']:.0f}% dos anos.")

if not forage_outlet:
    st.caption("Sem destino para a forragem, a estratégia C fica sem receita no ano da luzerna ou do trevo.")

# Contributo de cada critério para a pontuação (explica o porquê da ordenação)
contrib = summary[sc.CRITERIA].mul(100 * w, axis=1)
contrib.columns = CRIT_NAMES
long = contrib.reset_index().melt("estrategia", var_name="criterio", value_name="pontos")
long["nome"] = long["estrategia"].map(names)
long["ordem"] = long["criterio"].map({n: i for i, n in enumerate(CRIT_NAMES)})
order = [names[k] for k in summary.index]
bars = alt.Chart(long).mark_bar(stroke="white", strokeWidth=1.5).encode(
    y=alt.Y("nome:N", sort=order, title=None, axis=alt.Axis(labelLimit=220),
            scale=alt.Scale(paddingInner=0.3, paddingOuter=0.2)),
    x=alt.X("pontos:Q", title="Pontuação (0 a 100)", scale=alt.Scale(domain=[0, 100])),
    color=alt.Color("criterio:N", title="Critério", sort=CRIT_NAMES,
                    scale=alt.Scale(domain=CRIT_NAMES, range=CRIT_COLORS), legend=alt.Legend(orient="top")),
    order=alt.Order("ordem:Q"),
    tooltip=[alt.Tooltip("nome:N", title="Estratégia"), alt.Tooltip("criterio:N", title="Critério"),
             alt.Tooltip("pontos:Q", title="Pontos", format=".1f")],
)
totals = summary.reset_index().assign(nome=lambda t: t["estrategia"].map(names))
labels = alt.Chart(totals).mark_text(align="left", dx=6, fontWeight="bold").encode(
    y=alt.Y("nome:N", sort=order), x="pontuacao:Q", text=alt.Text("pontuacao:Q", format=".0f"))
st.altair_chart((bars + labels).properties(height=alt.Step(40)), use_container_width=True)
st.caption("Cada cor mostra quantos pontos vêm de cada critério. Um critério com prioridade 0 não aparece.")

# Tabela comparativa
ind_means = strat_years[strat_years["ano"].isin(years)].groupby("estrategia").mean(numeric_only=True)
low = ind.strategy_year_table(crop_table, crops=crops, margin_case=0).groupby("estrategia")["margem_eur_ha"].mean()
high = ind.strategy_year_table(crop_table, crops=crops, margin_case=2).groupby("estrategia")["margem_eur_ha"].mean()
table = pd.DataFrame({
    "Posição": summary["posicao"],
    "Estratégia": [names[k] for k in summary.index],
    "Pontuação": summary["pontuacao"].round(0),
    "Entre anos": [f"{a:.0f} a {b:.0f}" for a, b in zip(summary["p10"], summary["p90"])],
    "Anos em 1.º (%)": summary["pct_anos_1o"].round(0),
    "Margem (€/ha)": [f"{ind_means.loc[k, 'margem_eur_ha']:.0f} ({low[k]:.0f} a {high[k]:.0f})" for k in summary.index],
})
st.dataframe(table, hide_index=True, use_container_width=True)
table2 = pd.DataFrame({
    "Estratégia": [names[k] for k in summary.index],
    "Solo nu (dias)": ind_means.loc[summary.index, "dias_solo_nu"].round(0),
    "Chuva forte em solo nu (mm)": ind_means.loc[summary.index, "chuva_intensa_solo_nu_mm"].round(0),
    "Falta de água (mm)": ind_means.loc[summary.index, "defice_hidrico_mm"].round(0),
    "Geada (dias)": ind_means.loc[summary.index, "dias_geada_sensivel"].round(1),
    "Azoto (kg/ha)": ind_means.loc[summary.index, "azoto_fixado_kg"].round(0),
})
st.dataframe(table2, hide_index=True, use_container_width=True)
st.caption("Valores médios por ano, para a exploração inteira (um terço da área em cada fase da rotação). "
           "A coluna «Entre anos» é o intervalo em que a pontuação fica em 8 de cada 10 anos. "
           "A geada conta só os dias em fases sensíveis das culturas. "
           "A margem mostra a estimativa central e, entre parênteses, a baixa e a alta.")
if irrigated:
    rega = ind_means["rega_mm"].mean()
    st.caption(f"Com rega, a batata precisa em média de cerca de {3 * rega:.0f} mm de água de rega por ano na sua parcela.")

# Incerteza das margens: a ordenação aguenta?
winners = {}
for case, label in [(0, "baixas"), (2, "altas")]:
    sy = ind.strategy_year_table(crop_table, crops=crops, irrigated_potato=irrigated, margin_case=case)
    winners[label] = sc.summarise(sc.subscores(sy, refs), weights, years).index[0]
if all(v == best for v in winners.values()):
    st.caption(f"Teste às margens: {names[best]} continua em primeiro com as margens baixas e com as altas.")
else:
    st.caption("Teste às margens: o primeiro lugar muda com as margens baixas "
               f"({names[winners['baixas']]}) ou altas ({names[winners['altas']]}). Confirme os preços antes de decidir.")

# Cenários lado a lado (seca e chuva intensa)
st.subheader("E se o ano for seco ou de chuva intensa?")
scen = {"Todos os anos": list(years_all),
        "Anos secos": list(clim.index[clim["tipo_ano"] == "seco"]),
        "Anos de chuva intensa": list(clim.index[clim["tipo_ano"] == "chuva intensa"])}
rows = []
for label, ys in scen.items():
    res = sc.summarise(sub, weights, ys)
    row = {"Cenário": f"{label} ({len(ys)})"}
    for pos, (k, r) in enumerate(res.iterrows(), start=1):
        row[f"{pos}.º"] = f"{cfg.STRATEGIES[k]['curto']} ({r['pontuacao']:.0f})"
    rows.append(row)
st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
st.caption("Entre parênteses, o número de anos de cada cenário e a pontuação de cada estratégia.")

# -------------------------------------------------------------- 3. estratégias
st.header("3. Cada estratégia em detalhe")
tabs = st.tabs([names[k] for k in cfg.STRATEGIES])
for tab, (key, s) in zip(tabs, cfg.STRATEGIES.items()):
    with tab:
        st.markdown("**Sequência:** " + " → ".join(cfg.CROP_LABELS[c] for c in s["culturas"]))
        a, b = st.columns(2)
        with a:
            st.markdown(f"**Porquê.** {s['porque']}")
            st.markdown(f"**Evidência.** {s['evidencia']}")
            st.markdown(
                f"**O que os dados do local mostram.** Em média, {ind_means.loc[key, 'dias_solo_nu']:.0f} dias de solo nu "
                f"por ano, {ind_means.loc[key, 'chuva_intensa_solo_nu_mm']:.0f} mm de chuva intensa a cair em solo nu e "
                f"{ind_means.loc[key, 'defice_hidrico_mm']:.0f} mm de água em falta para as culturas.")
            st.markdown("**Benefícios esperados**\n" + "\n".join(f"- {x}" for x in s["beneficios"]))
        with b:
            st.markdown("**O que ainda não sabemos**\n" + "\n".join(f"- {x}" for x in s["lacunas"]))
            st.markdown("**Riscos a validar com um técnico local**\n" + "\n".join(f"- {x}" for x in s["riscos"]))

# ----------------------------------------------------------------- 4. SI (PSO)
st.header("4. Quão firme é este resultado?")
st.caption("Componente de Swarm Intelligence: um enxame de partículas (PSO) procura no espaço das prioridades. "
           "A pontuação acima não depende dele.")
keys = list(summary.index)
matrix = sc.criteria_matrix(sub, years).loc[keys].to_numpy()

flip = pso.flip_distance(matrix, w)
c1, c2 = st.columns(2)
with c1:
    st.subheader("Quanto teriam de mudar as prioridades?")
    if flip is None:
        st.write(f"Nenhuma combinação de prioridades tira **{names[best]}** do primeiro lugar neste cenário.")
    else:
        new = keys[flip["vencedor_depois"]]
        st.write(f"Bastava mover **{pct(flip['distancia'])}** do peso total entre critérios para "
                 f"**{names[new]}** passar para primeiro.")
        st.caption("Abaixo de 10%, o resultado é frágil. Acima de 25%, é firme.")
        cmp = pd.DataFrame({"Critério": CRIT_NAMES, "Agora": (100 * w).round(0),
                            "Para mudar": (100 * flip["pesos"]).round(0)})
        st.dataframe(cmp, hide_index=True, use_container_width=True)
        st.caption("Peso de cada critério, em percentagem.")
with c2:
    st.subheader("Que prioridades explicam a sua escolha?")
    st.write("Se já tem uma ordem de preferência, o enxame procura as prioridades que a explicam.")
    pref = st.multiselect("Ordene as estratégias, da preferida à menos preferida",
                          options=list(cfg.STRATEGIES), format_func=lambda k: names[k])
    if len(pref) == len(cfg.STRATEGIES):
        res = pso.calibrate_to_ranking(matrix, [keys.index(k) for k in pref])
        if res["pares_errados"] == 0:
            st.write("Estas prioridades reproduzem a sua ordem:")
        else:
            st.write(f"Nenhuma combinação reproduz a ordem completa. A mais próxima falha "
                     f"{res['pares_errados']} de {res['n_pares']} comparações:")
        st.dataframe(pd.DataFrame({"Critério": CRIT_NAMES, "Peso (%)": (100 * res["pesos"]).round(0)}),
                     hide_index=True, use_container_width=True)
    else:
        st.caption("Escolha as quatro estratégias para ver o resultado.")

# --------------------------------------------------------- 5. limites e fontes
st.header("5. Limites e fontes")
a, b = st.columns(2)
with a:
    st.markdown("**O que esta ferramenta não sabe**\n" + "\n".join(f"- {x}" for x in cfg.LIMITATIONS))
with b:
    src = pd.DataFrame([{"Critério": c["nome"], "De onde vem": c["fonte"]} for c in cfg.CRITERIA.values()])
    st.markdown("**De onde vem cada critério**")
    st.dataframe(src, hide_index=True, use_container_width=True)
    st.markdown("Clima: [NASA POWER](https://power.larc.nasa.gov/), comunidade de agroclimatologia, "
                "dados diários de 2000 a 2025. Mapa: OpenStreetMap.")
