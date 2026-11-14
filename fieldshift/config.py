"""Field Shift configuration: crops, strategies, thresholds and assumptions.

EVERYTHING in this file that does not come from NASA data is a working
ASSUMPTION (general agronomic literature or a manual estimate by the team).
All of them (crop calendars, margins, bare fallow, the 20 mm heavy-rain threshold,
soil available water) were reviewed by an agronomist from the Bragança region in
November 2026, with no changes to the values. They describe the region, not a
specific farm: each farm should still check them against its own conditions.

Dictionary keys (e.g. "batata", "nome", "porque") are internal identifiers and
stay in Portuguese; all text shown to the user is in English.
"""

# --- Pilot site ---------------------------------------------------------------
PILOT = {"nome": "Bragança", "lat": 41.81, "lon": -6.76}

# --- Thresholds (assumptions) -------------------------------------------------
HEAVY_RAIN_MM = 20.0       # heavy-rain day (erosion risk on bare soil)
DRY_ROOT_WETNESS = 0.50    # GWETROOT below this = dry soil (context only)
SOIL_AWC_MM = 100.0        # soil available water (mm); refine with SoilGrids
KC_BARE = 0.30             # bare-soil evaporation, fraction of reference ET

# --- Crops --------------------------------------------------------------------
# cover:  (month, day) windows in which the crop covers the soil
# season: windows in which the crop needs water (for the water deficit)
# frost:  windows in which frost below frost_t (°C) damages the crop
# kc:     mean crop coefficient over the season (demand = kc x reference ET)
# mo:     contribution to soil organic matter, 0 to 1 (assumption)
# n_fix:  nitrogen fixed and left for the next crop (kg N/ha, assumption)
# margem: gross margin in EUR/ha/year (low, central, high), manual estimate
CROPS = {
    "batata": {
        "cover": [((5, 15), (9, 15))], "season": [((4, 15), (9, 15))],
        "frost": [((4, 15), (6, 15))], "frost_t": 0.0, "kc": 0.90,
        "mo": 0.10, "n_fix": 0, "margem": (1000, 2000, 3500),
    },
    "trigo": {
        "cover": [((1, 1), (7, 10)), ((12, 1), (12, 31))], "season": [((3, 1), (6, 30))],
        "frost": [((4, 1), (5, 31))], "frost_t": -2.0, "kc": 0.80,
        "mo": 0.50, "n_fix": 0, "margem": (100, 250, 450),
    },
    "pousio": {
        "cover": [], "season": [], "frost": [], "frost_t": None, "kc": KC_BARE,
        "mo": 0.00, "n_fix": 0, "margem": (0, 0, 0),
    },
    "leguminosa": {
        "cover": [((1, 1), (6, 15)), ((12, 1), (12, 31))], "season": [((3, 1), (6, 15))],
        "frost": [((3, 15), (5, 15))], "frost_t": -3.0, "kc": 0.75,
        "mo": 0.60, "n_fix": 40, "margem": (100, 300, 550),
    },
    "luzerna": {
        "cover": [((3, 1), (11, 30))], "season": [((4, 1), (9, 30))],
        "frost": [], "frost_t": None, "kc": 0.90,
        "mo": 1.00, "n_fix": 120, "margem": (200, 450, 750),
    },
    "centeio": {
        "cover": [((1, 1), (7, 10)), ((11, 15), (12, 31))], "season": [((3, 1), (6, 30))],
        "frost": [((4, 15), (5, 31))], "frost_t": -4.0, "kc": 0.75,
        "mo": 0.60, "n_fix": 0, "margem": (50, 180, 350),
    },
}

CROP_LABELS = {
    "batata": "Potato", "trigo": "Wheat", "pousio": "Fallow (bare soil)",
    "leguminosa": "Legume (pea, lupin or faba bean)",
    "luzerna": "Lucerne or clover (forage)", "centeio": "Rye or oats",
}
# Short names for table rows
CROP_SHORT = {
    "batata": "Potato", "trigo": "Wheat", "pousio": "Fallow",
    "leguminosa": "Legume", "luzerna": "Lucerne/clover", "centeio": "Rye/oats",
}

# --- Strategies ---------------------------------------------------------------
# For each one: why, evidence, benefits, gaps and risks to check on the farm,
# as the challenge statement asks.
STRATEGIES = {
    "A": {
        "nome": "A. Current", "curto": "A. Current",
        "culturas": ["batata", "trigo", "pousio"],
        "porque": "The rotation the farmer already uses. It is the baseline for every comparison.",
        "evidencia": "The site's climate data shows when the fallow is exposed to heavy rain and when the potato runs short of water.",
        "beneficios": ["Familiar, with no new costs or equipment.", "The fallow rests the soil and frees up labour."],
        "lacunas": ["How much spontaneous cover the fallow gets in wet winters (Sentinel-2 shows sparse winter vegetation in cereal fields).", "Real farm yields are missing."],
        "riscos": ["Bare soil during the fallow: erosion and loss of organic matter.", "Potato needs a lot of water and is prone to fungal diseases."],
    },
    "B": {
        "nome": "B. Legume instead of fallow", "curto": "B. Legume",
        "culturas": ["batata", "trigo", "leguminosa"],
        "porque": "Replaces the fallow with a grain legume, which covers the soil in autumn and winter and fixes nitrogen.",
        "evidencia": "General agronomic literature: legumes fix nitrogen and reduce fertiliser for the next crop. Medium confidence; the local value depends on the species and the soil.",
        "beneficios": ["Less nitrogen fertiliser for the potato.", "Soil covered in the season when it is bare today.", "An extra harvest."],
        "lacunas": ["Yield and price of legumes in the region.", "How much nitrogen actually stays in the soil."],
        "riscos": ["Sowing window in Bragança (cold and spring frost).", "Market for pea, lupin or faba bean.", "Diseases if the legume returns to the same field too soon."],
    },
    "C": {
        "nome": "C. Forage instead of fallow", "curto": "C. Forage",
        "culturas": ["batata", "trigo", "luzerna"],
        "porque": "Replaces the fallow with lucerne or clover, which cover the soil almost all year and provide forage.",
        "evidencia": "General agronomic literature: perennial forages protect the soil and raise organic matter. Medium confidence; a one-year lucerne yields less than a multi-year one.",
        "beneficios": ["The option with the most days of covered soil.", "Forage for livestock or for sale.", "More nitrogen and organic matter."],
        "lacunas": ["Whether there is livestock or a buyer for the forage.", "Establishment cost for just one year of crop."],
        "riscos": ["Uses more water in summer; without irrigation it may yield little.", "Needs cutting and baling equipment.", "Lucerne does not tolerate acid soils; check the pH."],
    },
    "D": {
        "nome": "D. Hardy cereal", "curto": "D. Hardy cereal",
        "culturas": ["batata", "centeio", "leguminosa"],
        "porque": "Replaces wheat with rye or oats, which tolerate cold and drought better, and the fallow with a legume.",
        "evidencia": "General agronomic literature: rye tolerates cold, drought and poor soils better than wheat. Medium confidence; it is a traditional crop in Trás-os-Montes.",
        "beneficios": ["Lower frost and drought risk for the cereal.", "Soil covered earlier in autumn.", "Nitrogen from the legume."],
        "lacunas": ["Price and demand for rye or oats.", "Yield in the region."],
        "riscos": ["Rye margin is usually below wheat's.", "The same risks as the legume in strategy B."],
    },
}

# --- Criteria (farmer's priorities) -------------------------------------------
# fonte: where each criterion's value comes from, so the user knows what to trust
CRITERIA = {
    "agua": {"nome": "Water", "descricao": "Less water shortage for the crops",
             "fonte": "NASA POWER data + crop calendar (reviewed by a local agronomist)"},
    "receita": {"nome": "Revenue", "descricao": "Higher margin per hectare",
                "fonte": "Manual estimate (reviewed by a local agronomist)"},
    "erosao": {"nome": "Erosion", "descricao": "Less heavy rain on bare soil",
               "fonte": "NASA POWER data + crop calendar (reviewed by a local agronomist)"},
    "materia_organica": {"nome": "Organic matter", "descricao": "More soil organic matter",
                         "fonte": "Agronomic literature (reviewed by a local agronomist)"},
    "geada": {"nome": "Frost", "descricao": "Less frost during sensitive stages",
              "fonte": "NASA POWER data + crop calendar (reviewed by a local agronomist)"},
}
DEFAULT_WEIGHTS = {"agua": 5, "receita": 5, "erosao": 5, "materia_organica": 5, "geada": 5}

LIMITATIONS = [
    "Climate and satellite data measure the site's conditions, not the real effect of the rotations on the soil.",
    "The effect of the rotations comes from general agronomic literature, reviewed by an agronomist from the "
    "Bragança region; it has not been measured in the field.",
    "NASA POWER has a grid of about 50 km: regional context, not field-level.",
    "Bare-soil days come from crop calendars. Sentinel-2 NDVI in three cereal fields confirms the summer without "
    "green vegetation, but we do not know which crop was on each field in each year.",
    "Margins and prices are manual estimates, not confirmed market values.",
    "The tool supports the decision; it does not replace it. The farmer and the local agronomist have the last word.",
]
