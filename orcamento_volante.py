"""
orcamento_volante.py
--------------------
Orça o tempo de processo de um volante de montadora a partir do pacote
treinado por treinar_modelo_volante.py (modelo_tempo_volante.pkl). Não depende
dos bancos: é o que o app usa.

As folhas revisadas em 2026 estão mais completas que as antigas (mais operações
com tempo lançado; ~34% a mais no mesmo volante, com peso, furos e cliente
iguais). O modelo aprende com todas, marcando a folha 2026, e orça sempre no
padrão 2026.
"""
import joblib
import numpy as np
import pandas as pd

MARGEM = 0.05  # regra do Fábio: curva de aprendizado, contratos com -1%/ano; mostrada à parte
SIMILARES = ["peso_liquido", "g_furos", "g_radial", "g_rosc", "g_rasgos"]
ROTULO_ETAPA = {"t_tornear": "Tornear", "t_furacao": "Furação (centro de usinagem/furadeira)",
                "t_balancear": "Balancear", "t_montar": "Montar cremalheira", "t_outras": "Outras (bancada, lavar, gravar)"}


def carregar(caminho="modelo_tempo_volante.pkl"):
    return joblib.load(caminho)


def _vetor(pacote, e: dict) -> pd.DataFrame:
    linha = {c: 0.0 for c in pacote["colunas"]}
    for c in pacote["numericas"]:
        linha[c] = float(np.log1p(max(float(e.get(c) or 0), 0)))
    for col, validos in pacote["categorias"].items():
        v = e.get(col) or ""
        chave = f"{col}_{v if v in validos else 'OUTRO'}"
        if chave in linha:
            linha[chave] = 1.0
    return pd.DataFrame([linha], columns=pacote["colunas"])


def parecidas(pacote, e: dict, n=5) -> pd.DataFrame:
    """Volantes reais mais próximos (folhas 2026), para conferir o número."""
    b = pacote["base"]
    z = np.log1p(b[SIMILARES].astype(float))
    alvo = np.log1p(np.array([float(e.get(c) or 0) for c in SIMILARES]))
    dist = np.sqrt((((z - alvo) / pacote["escala_similar"]) ** 2).sum(axis=1))
    return b.assign(distancia=dist).nsmallest(n, "distancia")


def orcar(pacote, entrada: dict) -> dict:
    """entrada: peso_liquido (obrigatório), peso_bruto (opcional), g_* (furação), cliente_n, mat_n."""
    e = dict(entrada)
    bruto_estimado = not e.get("peso_bruto")
    if bruto_estimado:
        e["peso_bruto"] = e["peso_liquido"] * pacote["razao_bruto"]
    e["sobremetal"] = max((e["peso_bruto"] - e["peso_liquido"]) / e["peso_bruto"], 0)
    e["f2026"] = 1.0
    X = _vetor(pacote, e)
    total = float(np.expm1(pacote["modelo"].predict(X)[0]))
    bruto_etapas = {k: max(float(np.expm1(m.predict(X)[0])), 0) for k, m in pacote["etapas"].items()}
    fator = total / max(sum(bruto_etapas.values()), 1e-9)   # etapas fecham no total
    sim = parecidas(pacote, e)
    return {
        "total": total,
        "p10": total * pacote["banda"][0],
        "p90": total * pacote["banda"][1],
        "com_margem": total * (1 + MARGEM),
        "etapas": {ROTULO_ETAPA[k]: v * fator for k, v in bruto_etapas.items()},
        "fundicao": float(sim.t_fundicao.median()),
        "bruto_estimado": bruto_estimado,
        "peso_bruto": e["peso_bruto"],
        "parecidas": sim,
    }
