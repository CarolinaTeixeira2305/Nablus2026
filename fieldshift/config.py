"""Configuração do Field Shift: culturas, estratégias, limiares e hipóteses.

TUDO o que está neste ficheiro e não vem de dados NASA é uma HIPÓTESE de
trabalho (literatura agronómica geral ou estimativa manual da equipa) e tem de
ser validado por um técnico local antes de qualquer decisão no terreno.
"""

# --- Ponto-piloto -----------------------------------------------------------
PILOT = {"nome": "Bragança", "lat": 41.81, "lon": -6.76}

# --- Limiares (hipóteses) ----------------------------------------------------
HEAVY_RAIN_MM = 20.0       # dia de chuva intensa (risco de erosão em solo nu)
DRY_ROOT_WETNESS = 0.50    # GWETROOT abaixo disto = solo seco (só contexto)
SOIL_AWC_MM = 100.0        # água utilizável no solo (mm); refinar com SoilGrids
KC_BARE = 0.30             # evaporação de solo nu, fração da ET de referência

# --- Culturas ----------------------------------------------------------------
# cover:  janelas (mês, dia) em que a cultura cobre o solo
# season: janelas em que a cultura precisa de água (para o défice hídrico)
# frost:  janelas em que a geada causa dano, abaixo de frost_t (°C)
# kc:     coeficiente cultural médio na época (procura = kc x ET de referência)
# mo:     contributo para a matéria orgânica do solo, de 0 a 1 (hipótese)
# n_fix:  azoto fixado que fica para a cultura seguinte (kg N/ha, hipótese)
# margem: margem bruta em EUR/ha/ano (baixa, central, alta), estimativa manual
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
    "batata": "Batata", "trigo": "Trigo", "pousio": "Pousio (solo nu)",
    "leguminosa": "Leguminosa (ervilha, tremoço ou fava)",
    "luzerna": "Luzerna ou trevo (forragem)", "centeio": "Centeio ou aveia",
}

# --- Estratégias -------------------------------------------------------------
# Para cada uma: porquê, evidência, benefícios, lacunas e riscos a validar,
# como pede o enunciado do desafio.
STRATEGIES = {
    "A": {
        "nome": "A. Atual", "curto": "A. Atual",
        "culturas": ["batata", "trigo", "pousio"],
        "porque": "É a rotação que o agricultor já faz. Serve de referência para todas as comparações.",
        "evidencia": "Os dados de clima do local mostram em que alturas o pousio fica exposto a chuva intensa e a batata fica sem água.",
        "beneficios": ["Conhecida, sem custos nem equipamento novos.", "O pousio dá descanso ao solo e folga de trabalho."],
        "lacunas": ["Não sabemos se o pousio fica mesmo nu ou com vegetação espontânea.", "Faltam rendimentos reais da exploração."],
        "riscos": ["Solo nu durante o pousio: erosão e perda de matéria orgânica.", "Batata exigente em água e sensível a doenças fúngicas."],
    },
    "B": {
        "nome": "B. Leguminosa no pousio", "curto": "B. Leguminosa",
        "culturas": ["batata", "trigo", "leguminosa"],
        "porque": "Troca o pousio por uma leguminosa de grão, que cobre o solo no outono e no inverno e fixa azoto.",
        "evidencia": "Literatura agronómica geral: as leguminosas fixam azoto e reduzem a adubação da cultura seguinte. Confiança média; o valor local depende da espécie e do solo.",
        "beneficios": ["Menos adubo azotado para a batata.", "Solo coberto na época em que hoje fica nu.", "Uma colheita extra."],
        "lacunas": ["Rendimento e preço das leguminosas na região.", "Quanto azoto fica de facto no solo."],
        "riscos": ["Janela de sementeira em Bragança (frio e geada na primavera).", "Mercado para ervilha, tremoço ou fava.", "Doenças se a leguminosa voltar demasiado cedo à mesma parcela."],
    },
    "C": {
        "nome": "C. Forragem no pousio", "curto": "C. Forragem",
        "culturas": ["batata", "trigo", "luzerna"],
        "porque": "Troca o pousio por luzerna ou trevo, que cobrem o solo quase todo o ano e dão forragem.",
        "evidencia": "Literatura agronómica geral: as forragens perenes protegem o solo e aumentam a matéria orgânica. Confiança média; uma luzerna de um só ano rende menos do que uma de vários anos.",
        "beneficios": ["É a opção com mais dias de solo coberto.", "Forragem para pecuária ou para venda.", "Mais azoto e matéria orgânica."],
        "lacunas": ["Se há pecuária ou comprador para a forragem.", "Custo de instalação para apenas um ano de cultura."],
        "riscos": ["Gasta mais água no verão; sem rega pode produzir pouco.", "Exige equipamento de corte e de enfardar.", "A luzerna não tolera solos ácidos; confirmar o pH."],
    },
    "D": {
        "nome": "D. Cereal resistente", "curto": "D. Cereal resistente",
        "culturas": ["batata", "centeio", "leguminosa"],
        "porque": "Troca o trigo por centeio ou aveia, mais tolerantes ao frio e à seca, e o pousio por uma leguminosa.",
        "evidencia": "Literatura agronómica geral: o centeio tolera melhor frio, seca e solos pobres do que o trigo. Confiança média; é uma cultura tradicional de Trás-os-Montes.",
        "beneficios": ["Menor risco de geada e de seca no cereal.", "Solo coberto mais cedo no outono.", "Azoto da leguminosa."],
        "lacunas": ["Preço e procura de centeio ou aveia.", "Rendimento na região."],
        "riscos": ["Margem do centeio normalmente abaixo da do trigo.", "Os mesmos riscos da leguminosa da estratégia B."],
    },
}

# --- Critérios (prioridades do agricultor) -----------------------------------
# fonte: de onde vem o valor de cada critério, para o utilizador saber em que confiar
CRITERIA = {
    "agua": {"nome": "Água", "descricao": "Menos falta de água para as culturas",
             "fonte": "Dados NASA POWER + calendário das culturas (hipótese)"},
    "receita": {"nome": "Receita", "descricao": "Maior margem por hectare",
                "fonte": "Estimativa manual (hipótese)"},
    "erosao": {"nome": "Erosão", "descricao": "Menos chuva intensa em solo nu",
               "fonte": "Dados NASA POWER + calendário das culturas (hipótese)"},
    "materia_organica": {"nome": "Matéria orgânica", "descricao": "Mais matéria orgânica no solo",
                         "fonte": "Literatura agronómica (hipótese)"},
    "geada": {"nome": "Geada", "descricao": "Menos geada em fases sensíveis",
              "fonte": "Dados NASA POWER + calendário das culturas (hipótese)"},
}
DEFAULT_WEIGHTS = {"agua": 5, "receita": 5, "erosao": 5, "materia_organica": 5, "geada": 5}

LIMITATIONS = [
    "Os dados de clima e de satélite medem as condições do local, não o efeito real das rotações sobre o solo.",
    "O efeito das rotações vem de literatura agronómica geral e precisa de validação por peritos locais.",
    "O NASA POWER tem uma grelha de cerca de 50 km: é contexto regional, não mede a parcela.",
    "Os dias de solo nu vêm de um calendário de culturas. O NDVI do Sentinel-2 em três parcelas de cereal confirma "
    "o verão sem vegetação verde, mas não sabemos que cultura esteve em cada parcela em cada ano.",
    "As margens e os preços são estimativas manuais, não valores de mercado confirmados.",
    "A ferramenta apoia a decisão, não a substitui. O agricultor e o técnico local têm a última palavra.",
]
