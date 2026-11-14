"""Componente SI: otimização por enxame de partículas (PSO) sobre os pesos.

"SI" foi assumido como Swarm Intelligence. Com apenas quatro estratégias não
faz sentido usar PSO para escolher a estratégia: a pontuação ponderada chega.
O PSO é usado onde há mesmo um espaço contínuo para explorar, o dos pesos:

  1. flip_distance: qual é a menor mudança nas prioridades que faz mudar a
     estratégia em primeiro lugar? (mede a solidez da recomendação)
  2. calibrate_to_ranking: que prioridades explicam a ordenação que o
     agricultor diz preferir? (revela as prioridades implícitas)

O PSO é escrito em numpy, sem dependências, para ser fácil de ler e auditar.
"""
import numpy as np


def pso_minimise(f, dim, n_particles=40, iters=150, seed=0, w=0.72, c1=1.49, c2=1.49,
                 init=None):
    """PSO clássico (melhor global) no cubo [0, 1]^dim. f recebe uma matriz (n, dim)."""
    rng = np.random.default_rng(seed)
    x = rng.random((n_particles, dim))
    if init is not None:
        x[0] = np.clip(init, 0, 1)
    v = (rng.random((n_particles, dim)) - 0.5) * 0.2
    pbest, pval = x.copy(), f(x)
    g = pbest[pval.argmin()].copy()
    gval = pval.min()
    history = [gval]
    for _ in range(iters):
        r1, r2 = rng.random(x.shape), rng.random(x.shape)
        v = w * v + c1 * r1 * (pbest - x) + c2 * r2 * (g - x)
        x = np.clip(x + v, 0, 1)
        val = f(x)
        better = val < pval
        pbest[better], pval[better] = x[better], val[better]
        if pval.min() < gval:
            gval, g = pval.min(), pbest[pval.argmin()].copy()
        history.append(gval)
    return g, float(gval), history


def _to_weights(x):
    x = np.atleast_2d(x)
    s = x.sum(axis=1, keepdims=True)
    return np.where(s > 0, x / np.where(s > 0, s, 1), 1 / x.shape[1])


def flip_distance(matrix: np.ndarray, weights: np.ndarray, margin=1e-3, seed=0):
    """Menor mudança de pesos que troca a estratégia em primeiro lugar.

    matrix: notas (estratégias x critérios). weights: pesos que somam 1.
    Devolve None se nenhuma combinação de pesos mudar o primeiro lugar.
    A distância é a fração do peso total que mudou de critério (0 a 1).
    """
    w0 = np.asarray(weights, dtype=float)
    winner = int((matrix @ w0).argmax())
    others = [i for i in range(matrix.shape[0]) if i != winner]

    def cost(x):
        w = _to_weights(x)
        scores = w @ matrix.T
        gap = scores[:, winner] - scores[:, others].max(axis=1) + margin
        moved = 0.5 * np.abs(w - w0).sum(axis=1)
        return moved + 10.0 * np.clip(gap, 0, None) + (gap > 0) * 1.0

    best = None
    for s in range(4):  # vários arranques: o problema tem vários mínimos locais
        x, val, _ = pso_minimise(cost, len(w0), seed=seed + s, init=w0)
        if val < 1.0 and (best is None or val < best[1]):
            best = (x, val)
    if best is None:
        return None
    w = _to_weights(best[0])[0]
    return {"pesos": w, "distancia": float(0.5 * np.abs(w - w0).sum()),
            "vencedor_antes": winner, "vencedor_depois": int((matrix @ w).argmax())}


def calibrate_to_ranking(matrix: np.ndarray, order: list[int], margin=0.01, seed=0):
    """Pesos que reproduzem a ordenação pretendida (order = índices, do melhor ao pior).

    Minimiza o número de pares fora de ordem e, em caso de empate, prefere
    pesos equilibrados. Devolve os pesos e quantos pares ficaram por cumprir.
    """
    pairs = [(order[i], order[j]) for i in range(len(order)) for j in range(i + 1, len(order))]
    n_crit = matrix.shape[1]

    def cost(x):
        w = _to_weights(x)
        s = w @ matrix.T
        viol = sum(np.clip(margin - (s[:, a] - s[:, b]), 0, None) for a, b in pairs)
        wrong = sum((s[:, a] <= s[:, b]).astype(float) for a, b in pairs)
        balance = np.abs(w - 1 / n_crit).sum(axis=1)
        return wrong + 5.0 * viol + 0.01 * balance

    best = min((pso_minimise(cost, n_crit, seed=seed + s) for s in range(4)), key=lambda r: r[1])
    w = _to_weights(best[0])[0]
    s = matrix @ w
    wrong = sum(1 for a, b in pairs if s[a] <= s[b])
    return {"pesos": w, "pares_errados": wrong, "n_pares": len(pairs),
            "ordem_obtida": [int(i) for i in np.argsort(-s)], "historico": best[2]}
