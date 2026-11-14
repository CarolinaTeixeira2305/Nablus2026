"""
Fase 1 - Recolha de dados diarios NASA POWER para o ponto-piloto de Braganca.

Uso:
    python scripts/fetch_power.py

Saida:
    data/power_braganca_daily.csv

Notas:
- API publica do NASA POWER, sem registo. Comunidade AG (agroclimatologia).
- Pedidos em blocos de 5 anos para evitar respostas demasiado grandes.
- Valores -999 (ausentes) sao convertidos para NaN.
"""

from pathlib import Path
import time

import pandas as pd
import requests

LAT = 41.81
LON = -6.76
START_YEAR = 2000
END_YEAR = 2025
BLOCK_YEARS = 5

PARAMS = [
    "T2M",             # temperatura media do ar (C)
    "T2M_MIN",         # temperatura minima (C)
    "T2M_MAX",         # temperatura maxima (C)
    "PRECTOTCORR",     # precipitacao corrigida (mm/dia)
    "RH2M",            # humidade relativa (%)
    "ALLSKY_SFC_SW_DWN",  # radiacao solar de onda curta (MJ/m2/dia)
    "WS2M",            # vento a 2 m (m/s)
    "GWETTOP",         # humidade do solo superficial (0-1, fracao)
    "GWETROOT",        # humidade do solo na zona radicular (0-1, fracao)
    "EVPTRNS",         # evapotranspiracao (mm/dia)
]

API = "https://power.larc.nasa.gov/api/temporal/daily/point"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "power_braganca_daily.csv"


def fetch_block(start: int, end: int, lat: float = LAT, lon: float = LON) -> pd.DataFrame:
    params = {
        "parameters": ",".join(PARAMS),
        "community": "AG",
        "longitude": lon,
        "latitude": lat,
        "start": f"{start}0101",
        "end": f"{end}1231",
        "format": "JSON",
    }
    for attempt in range(3):
        r = requests.get(API, params=params, timeout=120)
        if r.status_code == 200:
            break
        time.sleep(5 * (attempt + 1))
    r.raise_for_status()

    series = r.json()["properties"]["parameter"]
    df = pd.DataFrame(series)
    df.index = pd.to_datetime(df.index, format="%Y%m%d")
    return df.replace(-999.0, pd.NA)


def fetch_point(lat: float = LAT, lon: float = LON, verbose: bool = True) -> pd.DataFrame:
    """Serie diaria completa para um ponto (usada tambem pela aplicacao)."""
    blocks = []
    for y0 in range(START_YEAR, END_YEAR + 1, BLOCK_YEARS):
        y1 = min(y0 + BLOCK_YEARS - 1, END_YEAR)
        if verbose:
            print(f"A recolher {y0}-{y1} ...")
        blocks.append(fetch_block(y0, y1, lat, lon))
        time.sleep(1)

    df = pd.concat(blocks).sort_index()
    df = df[~df.index.duplicated()]
    df.index.name = "date"
    return df.astype(float)


def main():
    df = fetch_point()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT)
    print(f"Guardado: {OUT} ({len(df)} dias, {df.index.min().date()} a {df.index.max().date()})")
    print("Valores em falta por coluna:")
    print(df.isna().sum())


if __name__ == "__main__":
    main()
