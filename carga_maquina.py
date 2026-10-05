"""
carga_maquina.py
----------------
Estima a CARGA DE FORJAMENTO (toneladas-força) de uma peça a partir do
diâmetro, e seleciona a PRENSA (tonelagem) que vai processá-la — o
"cálculo de carga máquina" da forjaria.

Replica a planilha oficial
    CALCULO DE CARGA - FORJARIA.xlsb  (aba "CARGA MÁQUINA")
cujas fórmulas (lidas via Excel) são:

    ÁREA  = PI() * (D/2)^2                                    (mm²)
    CARGA = (8 * K * (1.1 + 20/D)^2 * ÁREA * SÍGMA) / 1000    (toneladas)

      K     = (1 - 0.001*D)  se D <  300 mm   (correção por diâmetro)
            = 0.7            se D >= 300 mm   (valor de K em D=300, capeado)
      SÍGMA = 7.5 kgf/mm²    (fator de resistência do material; a planilha
                              usa 7.5 como padrão)

É a forma clássica de força de forjamento (fator de atrito/geometria
`(1.1 + 20/D)²` sobre a área projetada). Em D=300 as duas expressões de K
coincidem (1 - 0.001*300 = 0.7), então a carga é contínua na fronteira.

RESSALVAS (as próprias notas da planilha):
- "cálculo apenas para referência";
- a ESPESSURA DA ALMA da peça afeta diretamente a carga e NÃO entra nesta
  fórmula (que usa só o diâmetro) — portanto é uma ESTIMATIVA, tende a ser
  conservadora para peças de alma fina.

A seleção de prensa (qual máquina) NÃO está na planilha: aqui adotamos a
regra do Fabio — a MENOR prensa que atende, admitindo uma TOLERÂNCIA de
sobrecarga: a prensa aguenta até `tolerancia` acima da capacidade nominal
(padrão 5%). Assim uma carga de 1650 t fica na prensa de 1600 t (porque
1600 × 1,05 = 1680 ≥ 1650), em vez de pular pra 2500 t.
"""
from __future__ import annotations

import math

from config_custos import CUSTO_HORA_PRENSA

SIGMA_PADRAO = 7.5
# capacidades de prensa disponíveis (toneladas), vindas do parque já
# cadastrado em config_custos — fonte única de verdade.
PRENSAS_TON = sorted(CUSTO_HORA_PRENSA.keys())


def area_projetada_mm2(diametro_mm: float) -> float:
    """Área projetada do círculo de diâmetro D (mm²)."""
    return math.pi * (diametro_mm / 2.0) ** 2


def _fator_k(diametro_mm: float) -> float:
    if diametro_mm < 300.0:
        return 1.0 - 0.001 * diametro_mm
    return 0.7


def calcular_carga_ton(diametro_mm: float, sigma: float = SIGMA_PADRAO) -> float:
    """Carga de forjamento estimada, em toneladas-força.

    Mesma conta da planilha. Levanta ValueError se o diâmetro não for > 0.
    """
    if diametro_mm is None or diametro_mm <= 0:
        raise ValueError("diâmetro deve ser maior que zero (mm).")
    area = area_projetada_mm2(diametro_mm)
    k = _fator_k(diametro_mm)
    carga = (8.0 * k * (1.1 + 20.0 / diametro_mm) ** 2 * area * sigma) / 1000.0
    return carga


TOLERANCIA_PADRAO = 0.05  # prensa aceita até 5% acima da capacidade nominal


def selecionar_prensa(
    carga_ton: float,
    tolerancia: float = TOLERANCIA_PADRAO,
    prensas: list[float] | None = None,
) -> float | None:
    """Menor prensa que atende a carga, admitindo `tolerancia` de sobrecarga.

    Uma prensa de capacidade T é aceita se `carga_ton <= T * (1 + tolerancia)`
    — ou seja, admite-se até `tolerancia` acima do nominal (padrão 5%), então
    carga 1650 t fica na prensa 1600 t.

    Retorna None se a carga exceder até a maior prensa (já com a tolerância)
    — a peça não cabe no parque; caso a sinalizar, não escolher às cegas.
    """
    for t in sorted(prensas or PRENSAS_TON):
        if carga_ton <= t * (1.0 + tolerancia):
            return t
    return None


def prensa_para_diametro(
    diametro_mm: float,
    sigma: float = SIGMA_PADRAO,
    tolerancia: float = TOLERANCIA_PADRAO,
) -> dict:
    """Pipeline completo: diâmetro -> carga -> prensa.

    Retorna dict com carga_ton, prensa_ton (None se excede o parque),
    area_mm2 e os parâmetros usados — pronto pra exibir ou alimentar o
    custo/modelo de forjaria.
    """
    carga = calcular_carga_ton(diametro_mm, sigma)
    prensa = selecionar_prensa(carga, tolerancia)
    return {
        "diametro_mm": diametro_mm,
        "sigma": sigma,
        "tolerancia": tolerancia,
        "area_mm2": round(area_projetada_mm2(diametro_mm), 1),
        "carga_ton": round(carga, 1),
        "prensa_ton": prensa,
        "excede_parque": prensa is None,
    }
