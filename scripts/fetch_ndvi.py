"""Monthly Sentinel-2 NDVI for one field, from the Copernicus Data Space Ecosystem.

Goal (status doc, item 5): check the bare-soil months that today come only from
the crop calendar in fieldshift/config.py against satellite imagery.

Setup (once):
  1. Create a free account at https://dataspace.copernicus.eu
  2. Open https://shapps.dataspace.copernicus.eu/dashboard/ -> User settings
     -> OAuth clients -> Create. Copy the client ID and the secret (the
     secret is shown only once).
  3. Put them in environment variables (never commit them to the repo):
       PowerShell:  $env:CDSE_CLIENT_ID="..."; $env:CDSE_CLIENT_SECRET="..."
       bash:        export CDSE_CLIENT_ID=... CDSE_CLIENT_SECRET=...

Run from the project folder (paths are relative to it). The data in data/
was made with:
  python scripts/fetch_ndvi.py --lat 41.8387 --lon -6.7206 --half-size 25 --name braganca_field1
  python scripts/fetch_ndvi.py --lat 41.8324 --lon -6.7279 --half-size 25 --name braganca_field2
  python scripts/fetch_ndvi.py --lat 41.8431 --lon -6.7046 --half-size 25 --name braganca_field3

Pick lat/lon ON AN ACTUAL FARM FIELD (e.g. from a satellite map), well inside
the field, not the town centre: the town would give urban NDVI.

Output (NAME = --name, default "braganca"):
  data/ndvi_NAME_obs.csv         one row per 5-day window with clear pixels
  data/ndvi_NAME_year_month.csv  median NDVI per year and month, bare yes/no
  data/ndvi_NAME_monthly.csv     per calendar month: median, p20, p80, share of bare years
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd
import requests

TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/"
    "protocol/openid-connect/token"
)
STATS_URL = "https://sh.dataspace.copernicus.eu/api/v1/statistics"

# NDVI below this is treated as bare / almost bare soil. 0.25 is a common
# rule of thumb; say in the presentation that it is an assumption.
BARE_SOIL_NDVI = 0.25

# Pixels flagged by the Sentinel-2 scene classification (SCL) as cloud
# shadow (3), cloud medium/high (8, 9), cirrus (10) or snow (11) are dropped.
EVALSCRIPT = """
//VERSION=3
function setup() {
  return {
    input: [{ bands: ["B04", "B08", "SCL", "dataMask"] }],
    output: [
      { id: "ndvi", bands: 1, sampleType: "FLOAT32" },
      { id: "dataMask", bands: 1 }
    ]
  };
}
function evaluatePixel(s) {
  const ndvi = (s.B08 - s.B04) / (s.B08 + s.B04 + 1e-6);
  const cloudy = [3, 8, 9, 10, 11].includes(s.SCL);
  return { ndvi: [ndvi], dataMask: [cloudy ? 0 : s.dataMask] };
}
"""


def get_token() -> str:
    cid = os.environ.get("CDSE_CLIENT_ID")
    secret = os.environ.get("CDSE_CLIENT_SECRET")
    if not cid or not secret:
        sys.exit("Set CDSE_CLIENT_ID and CDSE_CLIENT_SECRET first (see top of this file).")
    r = requests.post(
        TOKEN_URL,
        data={"grant_type": "client_credentials", "client_id": cid, "client_secret": secret},
        timeout=30,
    )
    if r.status_code != 200:
        sys.exit(f"Could not get a token ({r.status_code}): {r.text[:300]}")
    return r.json()["access_token"]


def square(lat: float, lon: float, half_m: float) -> dict:
    """Small square polygon around the point, half_m metres to each side."""
    import math

    dlat = half_m / 111_320
    dlon = half_m / (111_320 * math.cos(math.radians(lat)))
    ring = [
        [lon - dlon, lat - dlat],
        [lon + dlon, lat - dlat],
        [lon + dlon, lat + dlat],
        [lon - dlon, lat + dlat],
        [lon - dlon, lat - dlat],
    ]
    return {"type": "Polygon", "coordinates": [ring]}


def fetch_year(token: str, geom: dict, start: str, end: str) -> list[dict]:
    body = {
        "input": {
            "bounds": {
                "geometry": geom,
                "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"},
            },
            "data": [
                {
                    "type": "sentinel-2-l2a",
                    "dataFilter": {"maxCloudCoverage": 80, "mosaickingOrder": "leastCC"},
                }
            ],
        },
        "aggregation": {
            "timeRange": {"from": f"{start}T00:00:00Z", "to": f"{end}T23:59:59Z"},
            # Sentinel-2 revisits every ~5 days; one value per 5-day window.
            "aggregationInterval": {"of": "P5D"},
            "evalscript": EVALSCRIPT,
            "resx": 0.0001,  # degrees, about 10 m
            "resy": 0.0001,
        },
        "calculations": {"default": {"statistics": {"default": {"percentiles": {"k": [50]}}}}},
    }
    r = requests.post(
        STATS_URL,
        json=body,
        headers={"Authorization": f"Bearer {token}"},
        timeout=120,
    )
    if r.status_code != 200:
        sys.exit(f"Statistical API error ({r.status_code}): {r.text[:500]}")

    rows = []
    for item in r.json().get("data", []):
        if "error" in item:
            continue
        stats = item["outputs"]["ndvi"]["bands"]["B0"]["stats"]
        n = stats.get("sampleCount", 0) - stats.get("noDataCount", 0)
        if n <= 0 or stats.get("mean") is None:
            continue  # fully cloudy or no acquisition in this window
        rows.append(
            {
                "date": item["interval"]["from"][:10],
                "ndvi_mean": stats["mean"],
                "ndvi_median": stats.get("percentiles", {}).get("50.0", stats["mean"]),
                "clear_pixels": n,
            }
        )
    return rows


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--lat", type=float, required=True, help="latitude of a farm field")
    p.add_argument("--lon", type=float, required=True, help="longitude of a farm field")
    p.add_argument("--start", default="2017-01-01", help="Sentinel-2 L2A is reliable from 2017")
    p.add_argument("--end", default="2025-12-31")
    p.add_argument("--half-size", type=float, default=25, help="half side of the square, metres")
    p.add_argument("--out-dir", default="data")
    p.add_argument("--name", default="braganca", help="used in the output file names")
    a = p.parse_args()

    token = get_token()
    geom = square(a.lat, a.lon, a.half_size)

    # One request per year keeps each response small.
    rows: list[dict] = []
    y0, y1 = int(a.start[:4]), int(a.end[:4])
    for year in range(y0, y1 + 1):
        s = a.start if year == y0 else f"{year}-01-01"
        e = a.end if year == y1 else f"{year}-12-31"
        got = fetch_year(token, geom, s, e)
        print(f"{year}: {len(got)} clear observations")
        rows += got

    if not rows:
        sys.exit("No clear observations. Check the coordinates and the date range.")

    obs = pd.DataFrame(rows)
    obs["date"] = pd.to_datetime(obs["date"])
    obs = obs.sort_values("date")

    obs["year"] = obs["date"].dt.year
    obs["month"] = obs["date"].dt.month
    by_ym = obs.groupby(["year", "month"])["ndvi_median"].median().reset_index()
    by_ym["bare"] = by_ym["ndvi_median"] < BARE_SOIL_NDVI

    monthly = (
        by_ym.groupby("month")
        .agg(
            ndvi_median=("ndvi_median", "median"),
            ndvi_p20=("ndvi_median", lambda s: s.quantile(0.2)),
            ndvi_p80=("ndvi_median", lambda s: s.quantile(0.8)),
            share_bare=("bare", "mean"),
            years=("year", "nunique"),
        )
        .reset_index()
    )

    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    obs.drop(columns=["year", "month"]).to_csv(out / f"ndvi_{a.name}_obs.csv", index=False)
    by_ym.to_csv(out / f"ndvi_{a.name}_year_month.csv", index=False)
    monthly.to_csv(out / f"ndvi_{a.name}_monthly.csv", index=False)

    print()
    print(monthly.round(2).to_string(index=False))
    print(f"\nBare soil = monthly NDVI < {BARE_SOIL_NDVI}. Files written to {out}/")


if __name__ == "__main__":
    main()
