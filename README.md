# Field Shift: Adapting Farms with NASA Data

Ferramenta de apoio à decisão que compara rotações de culturas com dados de clima da NASA.
NASA Space Apps Challenge 2026.

- Ponto-piloto: Bragança (41.81° N, 6.76° W, confirmar no mapa)
- Entrega: domingo, 15 de novembro de 2026 (hora limite a confirmar)
- Estado em 14 de novembro, 12h30: dados, indicadores, pontuação, componente SI e aplicação a funcionar. Falta o NDVI, o solo, a validação e a apresentação. Ver `docs/ponto_de_situacao.pdf`.

## Como correr

```bash
python -m pip install -r requirements.txt
python run.py                     # arranca a aplicação e abre-a no browser
```

Usar sempre `python -m ...` e `python run.py`, e não os comandos `pip` e `streamlit` diretos. Em Windows esses comandos muitas vezes não estão no PATH e dão o erro "streamlit is not recognized". O `run.py` também evita a mensagem de boas-vindas do Streamlit que pede um email na primeira vez. Se `python` não for reconhecido em Windows, trocar por `py`.

Os dados de Bragança já estão em `data/`. Para os voltar a gerar:

```bash
python scripts/fetch_power.py     # descarrega o NASA POWER, 2000 a 2025 (cerca de 30 s)
python scripts/indicators.py      # recalcula os indicadores e a pontuação
python -m pip install pytest      # só para os testes
python -m pytest -q               # 15 testes
```

A aplicação precisa de internet para desenhar o mapa. O resto funciona sem rede.

## Decisões (registadas na sexta-feira à noite)

| Tema | Decisão | Motivo |
|---|---|---|
| "SI" | Swarm Intelligence limitado: PSO só sobre os pesos | Com 4 estratégias, PSO não é necessário para escolher; serve para explorar as prioridades |
| Clima | NASA POWER (fonte principal); IPMA só como validação, se houver tempo | Sem registo, rápido de integrar |
| Solo | SoilGrids (global) | Não há tempo para validar cartografia local |
| Satélite | Sentinel-2 para NDVI e solo nu; se a conta não estiver ativa até sábado à noite, avançar só com NASA POWER | Plano B explícito |
| Mercado | Estimativa manual, marcada como hipótese | Sem tempo para recolher preços reais |

## Estratégias a comparar

- **A. Atual (base):** batata → trigo → pousio
- **B. Leguminosa no pousio:** batata → trigo → ervilha, tremoço ou fava
- **C. Forragem no pousio:** batata → trigo → luzerna ou trevo
- **D. Cereal resistente:** batata → centeio ou aveia → leguminosa

Para cada uma, a aplicação mostra o porquê, a evidência, os benefícios, o que ainda não sabemos e os riscos a validar com um técnico local.

## Como funciona

1. **O que os dados mostram sobre o local** (`fieldshift/indicators.py`, `climate_indicators`). Por ano: chuva, temperatura, dias de geada, dias de chuva intensa (20 mm ou mais) e anomalias face à média de 2000 a 2025. Cada ano é classificado como seco (20% com menos chuva), de chuva intensa (20% com mais dias de chuva forte) ou normal.
2. **Como cada rotação fica exposta** (`crop_year_table`, `strategy_year_table`). Um calendário por cultura diz quando o solo está coberto, quando a cultura precisa de água e quando é sensível à geada. Daí saem quatro indicadores por ano:
   - dias de solo nu;
   - chuva intensa a cair em solo nu (mm), como medida do risco de erosão;
   - falta de água (mm): um balanço diário entre a chuva e a procura da cultura, com um solo que guarda até 100 mm;
   - dias de geada em fases sensíveis.
   Cada fase da rotação ocupa um terço da exploração, por isso o valor da estratégia é a média das três culturas.
3. **Pontuação ponderada** (`fieldshift/scoring.py`). Cada critério (água, receita, erosão, matéria orgânica, geada) vira uma nota de 0 a 1 contra uma escala fixa. A pontuação é a soma das notas, ponderada pelas prioridades do agricultor, de 0 a 100. A incerteza aparece de três formas: o intervalo em que a pontuação fica em 8 de cada 10 anos, a percentagem de anos em que a estratégia fica em primeiro, e um teste com as margens baixas e altas.
4. **Componente SI** (`fieldshift/pso.py`). Um PSO escrito em numpy responde a duas perguntas: quanto teriam de mudar as prioridades para o primeiro lugar mudar, e que prioridades explicam a ordem que o agricultor prefere.
5. **Aplicação** (`app.py`). Uma página Streamlit com mapa, sliders de prioridades, restrições (rega, destino para a forragem), cenários (todos os anos, anos secos, anos de chuva intensa, um ano), margens editáveis e avisos de validação.

## Resultados atuais (prioridades iguais)

| Cenário | 1.º | 2.º | 3.º | 4.º |
|---|---|---|---|---|
| Todos os anos (26) | D (69) | B (67) | C (65) | A (60) |
| Anos secos (6) | D (71) | C (69) | B (69) | A (65) |
| Anos de chuva intensa (7) | D (64) | B (63) | C (60) | A (54) |

As diferenças entre B, C e D são pequenas e mudam com as prioridades. O que é firme é que a rotação atual fica em último nos três cenários: trocar o pousio reduz os dias de solo nu de 250 para 158 a 184 por ano.

## Estrutura

```
field_shift/
├── README.md
├── requirements.txt
├── run.py                   # arranque: python run.py
├── app.py                   # aplicação Streamlit
├── fieldshift/
│   ├── config.py            # culturas, estratégias, limiares e hipóteses (editar aqui)
│   ├── indicators.py        # indicadores de clima, por cultura e por estratégia
│   ├── scoring.py           # pontuação ponderada e incerteza
│   └── pso.py               # componente SI (PSO sobre os pesos)
├── scripts/
│   ├── fetch_power.py       # Fase 1: recolha NASA POWER
│   └── indicators.py        # Fase 2: gera as tabelas em data/
├── data/                    # CSV gerados
├── tests/test_core.py
├── docs/                    # ponto de situação e capturas de ecrã da demonstração
└── notebooks/               # análise exploratória (vazio)
```

## Fontes

| Fonte | Uso | Estado |
|---|---|---|
| NASA POWER (API diária, comunidade AG) | Clima, geada, radiação, humidade do solo | Em uso |
| Sentinel-2 (Copernicus) | NDVI, solo nu | Por integrar (precisa de conta) |
| SoilGrids (ISRIC) | Textura, matéria orgânica, água utilizável | Por integrar |
| SRTM | Declive, para o risco de erosão | Por integrar |
| IPMA | Validação de temperatura e precipitação | Por fazer |
| OpenStreetMap | Fundo do mapa | Em uso |

## Hipóteses a validar com um técnico local

Estão todas em `fieldshift/config.py`:

- calendários das culturas (cobertura do solo, época de rega, fase sensível à geada);
- o pousio fica com o solo nu o ano inteiro;
- limiar de chuva intensa (20 mm por dia) e água utilizável do solo (100 mm);
- coeficientes culturais e índice de matéria orgânica por cultura;
- azoto fixado pelas leguminosas;
- margens por cultura (baixa, central, alta), que são estimativas manuais.

## Limitações a declarar

- Os dados de clima e satélite medem condições, não o efeito real das rotações sobre o solo. O efeito vem de literatura agronómica e precisa de validação por peritos locais.
- O NASA POWER tem uma grelha de cerca de 50 km: é contexto regional, não mede a parcela.
- Os dias de solo nu vêm de um calendário de culturas, não de imagens de satélite.
- A receita não varia com o clima: um ano seco não baixa a margem.
- A resolução varia entre fontes; a harmonização é aproximada.
- Os preços e a produção são estimativas.
- A ferramenta apoia a decisão, não a substitui.
