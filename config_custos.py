"""
config_custos.py
------------------
Tarifas usadas para converter TEMPO (minutos, previsto pelos modelos)
em CUSTO (R$) por peca. Valores informados por Fabio em 17/09/2026 --
NAO sao derivados de dado historico, sao estimativa de negocio.

Formula do custo de FORJADO:
    custo_forjado = (tempo_forjaria_min / 60) * CUSTO_HORA_PRENSA[tonelagem]
                  + peso_kg * CUSTO_MATERIA_PRIMA_KG

(o tempo de usinagem tem sua propria tarifa -- ainda NAO informada, ver
CUSTO_HORA_USINAGEM abaixo, hoje None ate ter o valor).

------------------------------------------------------------------
CUSTO-HORA POR PRENSA (R$/hora)
------------------------------------------------------------------
Cada classe de prensa tem tarifa propria -- prensas maiores custam mais
por hora de operacao (mais energia, mais depreciacao de matriz, etc.).

Caso especial 6300T: o custo "real" informado foi R$ 1.146/h, mas foi
combinado usar R$ 1.050/h no modelo -- e a prensa mais cara e que mais
demanda tempo, entao usar o valor cheio penalizaria demais as pecas que
passam por ela; o valor reduzido equilibra isso. Ver CUSTO_HORA_PRENSA
abaixo: a chave guarda o valor USADO (1050), o comentario guarda o
valor nominal (1146) para rastreabilidade.

12500T: prensa mais pesada do parque, nao apareceu nas ~211 amostras
usadas para validar o modelo de forjaria (a maior tonelagem observada
nos dados foi 6300T) -- a tarifa esta documentada aqui mas o modelo
preditivo de tempo de forjaria (salvar_modelo_forjaria.py) nunca viu
essa classe treinando, entao uma peca que caia nela deve ser tratada
com cautela extra (extrapolacao, nao interpolacao).
"""
from __future__ import annotations

# tonelagem (T) -> R$/hora [USADO no calculo]
CUSTO_HORA_PRENSA: dict[float, float] = {
    1600.0:  350.0,
    2500.0:  500.0,
    3000.0:  650.0,
    4000.0:  800.0,
    6300.0:  1050.0,   # nominal informado: R$ 1.146/h; reduzido p/ 1.050/h
                       # de propósito -- é a prensa mais cara e que mais
                       # demanda tempo, o valor cheio penalizaria demais.
    12500.0: 5500.0,   # fora do range visto no treino do modelo de forjaria
}

# tonelagem (T) -> R$/hora NOMINAL (antes do ajuste de equilibrio acima).
# So para auditoria/rastreabilidade -- nao usar no calculo.
CUSTO_HORA_PRENSA_NOMINAL: dict[float, float] = {
    6300.0: 1146.0,
}

# R$/kg -- estimativa media inicial de aço, ainda não segmentada por liga
# (a base tem 60+ variantes de material cadastradas, ex. SAE 8620, SAE
# 1045, 20MnCr5... um custo por liga é o próximo refinamento natural,
# quando/se o Fabio passar os valores).
CUSTO_MATERIA_PRIMA_KG: float = 8.0

# Tarifa de usinagem (R$/hora) -- AINDA NAO INFORMADA. Deixe None até
# receber o valor; o app deve avisar "custo de usinagem indisponível"
# em vez de calcular com um número inventado.
CUSTO_HORA_USINAGEM: float | None = None


def custo_forjado(tempo_forjaria_min: float, peso_kg: float, tonelagem: float) -> float | None:
    """R$ estimado para a etapa de forjaria de uma peça.

    Retorna None se a tonelagem não tem tarifa cadastrada (evita
    inventar custo para uma classe de prensa desconhecida).
    """
    tarifa = CUSTO_HORA_PRENSA.get(tonelagem)
    if tarifa is None:
        return None
    custo_prensa = (tempo_forjaria_min / 60.0) * tarifa
    custo_material = peso_kg * CUSTO_MATERIA_PRIMA_KG
    return round(custo_prensa + custo_material, 2)


def custo_usinagem(tempo_usinagem_min: float) -> float | None:
    """R$ estimado para a etapa de usinagem. None até termos a tarifa."""
    if CUSTO_HORA_USINAGEM is None:
        return None
    return round((tempo_usinagem_min / 60.0) * CUSTO_HORA_USINAGEM, 2)
