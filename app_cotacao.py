"""
app_cotacao.py - Estimativa de Tempo e Custo de Fabricacao | Cinpal
---------------------------------------------------------------------
Interface para o custeista obter uma estimativa inicial de tempo (e,
quando a tarifa existe, custo em R$) a partir dos dados do orcamento --
sem precisar que o processo ja esteja planejado.

Como rodar:
    pip install streamlit
    streamlit run app_cotacao.py
    -> abre em http://localhost:8501

REVISAO 22/09/2026 -- redesenho visual (skill frontend-design)
A versao anterior caia em varios padroes genericos de interface gerada:
cartoes identicos com o mesmo raio de borda e mesma sombra suave em tudo,
rotulos em CAIXA-ALTA com letter-spacing, metadados juntados por "*",
banner com gradiente como elemento decorativo. Redesenhado em cima do
proprio vocabulario visual do assunto: a peca e sempre lida a partir de
um DESENHO TECNICO (linha de cota, bloco de titulo, notas numeradas) --
entao a interface usa essa mesma gramatica em vez da de um dashboard
SaaS generico. Ver DESIGN_NOTES.md para o plano completo e a critica.

Principio de design (mantido): nenhum modelo aqui explica mais que ~55%
da variacao. Mostrar um numero exato passaria uma precisao que nao
existe -- por isso o resultado central e uma FAIXA (agora desenhada como
uma cota real, com tolerancia), nao um numero isolado.
"""

from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import visor3d
from config_custos import custo_forjado, custo_usinagem, CUSTO_HORA_USINAGEM

BASE = Path(__file__).parent

st.set_page_config(
    page_title="Estimativa de fabricação · Cinpal",
    page_icon="📐",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Modelos disponiveis
# ---------------------------------------------------------------------------
# Cada entrada aqui e um modelo TREINADO E VALIDADO de verdade (ver
# salvar_modelo_producao.py / salvar_modelo_engrenagens.py / salvar_modelo_
# forjaria.py). Trocar a aba troca o .pkl carregado e os campos pedidos --
# nao existe campo que pareca influenciar o calculo sem influenciar.

CATALOGO_MODELOS = {
    "volante": {
        "rotulo": "Volante",
        "sub": "peça fundida",
        "pkl": "modelo_producao.pkl",
        "legenda": "Dois números do bloco de título do desenho: a massa "
                   "da peça acabada e o maior diâmetro cotado.",
    },
    "engrenagem": {
        "rotulo": "Engrenagem",
        "sub": "usinagem, peça forjada",
        "pkl": "modelo_engrenagens.pkl",
        "legenda": "Dois pesos do orçamento de forjaria: o peso líquido "
                   "e o peso bruto da peça forjada, antes de usinar.",
    },
    "forjaria": {
        "rotulo": "Engrenagem",
        "sub": "forjaria, peça forjada",
        "pkl": "modelo_forjaria.pkl",
        "legenda": "Peso planificado da peça e a tonelagem da prensa — o "
                   "tempo de forjaria depende mais de qual prensa é usada "
                   "do que do tamanho da peça.",
    },
}

# ---------------------------------------------------------------------------
# Estilo
# ---------------------------------------------------------------------------
# Vocabulario emprestado do proprio desenho tecnico: papel de prancha,
# tinta azul-anteprojeto, um unico acento (laranja de forja), regua fina
# em vez de sombra suave, cota real em vez de card verde generico, bloco
# de titulo em vez de badges com gradiente.

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');

    :root {
        --ink:      #14304F;
        --ink-70:   #3C556F;
        --ink-45:   #7C8CA0;
        --rule:     #C7CDC7;
        --rule-lt:  #DEE2DC;
        --paper:    #FFFFFF;
        --ground:   #EFF1EF;
        --forge:    #C1440E;
        --forge-10: #FBEDE6;
        --steel:    #2F6E5C;
        --steel-10: #E9F1EE;
    }

    html, body, [class*="st-"], .stApp {
        font-family: 'IBM Plex Sans', -apple-system, 'Segoe UI', sans-serif;
        color: var(--ink);
    }
    .stApp { background: var(--ground); }
    header[data-testid="stHeader"] { background: transparent; }
    .block-container { padding-top: 2.4rem; padding-bottom: 3rem; max-width: 1180px; }
    .mono { font-family: 'IBM Plex Mono', monospace; }

    /* A regra acima e ampla (pega [class*="st-"]) e sobrescrevia a fonte
       de icone do proprio Streamlit (seta do expander, etc. usam uma
       fonte de icone tipo Material Symbols, nao SVG) -- quebrava o
       glifo em texto sobreposto. Devolve a fonte de icone nesses casos. */
    [data-testid="stIconMaterial"],
    [data-testid="stExpanderToggleIcon"],
    span[class*="material-symbols"] {
        font-family: 'Material Symbols Rounded', 'Material Icons', sans-serif !important;
    }

    /* ---------- Cabecalho: sem banner, sem gradiente ---------- */
    .cab-eyebrow {
        font-size: .82rem; color: var(--ink-45); margin: 0 0 2px 0;
    }
    .cab-titulo {
        font-size: 1.7rem; font-weight: 600; color: var(--ink);
        margin: 0; letter-spacing: -.015em; line-height: 1.25;
    }
    .cab-regua {
        border: none; border-top: 1px solid var(--rule); margin: 18px 0 20px 0;
    }

    /* ---------- Seletor de tipo de peca (lista vertical, ao lado do 3D) ---------- */
    div[data-testid="stRadio"] > label { display: none; }
    div[data-testid="stRadio"] > div { gap: 2px; }
    div[data-testid="stRadio"] label {
        background: transparent !important; border: none !important;
        border-left: 2px solid var(--rule-lt) !important; border-radius: 0 !important;
        padding: 9px 4px 9px 14px !important; margin: 0 !important;
        font-weight: 500 !important; font-size: .95rem !important; color: var(--ink-70) !important;
        transition: border-color .15s ease, color .15s ease;
    }
    div[data-testid="stRadio"] label:has(input:checked) {
        border-left: 2px solid var(--forge) !important; color: var(--ink) !important;
    }

    /* ---------- Paineis (sem raio, sem sombra -- regua fina) ---------- */
    .painel {
        background: var(--paper); border: 1px solid var(--rule);
        padding: 24px 26px; margin-bottom: 16px;
    }
    .painel-rotulo {
        font-size: .8rem; font-weight: 600; color: var(--ink); margin: 0 0 4px 0;
    }
    .painel-legenda {
        font-size: .84rem; color: var(--ink-70); margin: 0 0 16px 0; line-height: 1.55;
    }
    .campo-rotulo {
        font-size: .78rem; color: var(--ink-45); margin: 0 0 12px 0;
    }

    /* ---------- Cota (resultado) -- o momento principal ---------- */
    .cota-topo { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; margin-bottom: 6px; }
    .cota-valor {
        font-family: 'IBM Plex Mono', monospace; font-size: 3rem; font-weight: 600;
        color: var(--forge); line-height: 1; letter-spacing: -.01em;
    }
    .cota-unidade {
        font-family: 'IBM Plex Mono', monospace; font-size: 1.05rem; color: var(--forge); opacity: .78;
    }
    .cota-tol {
        font-family: 'IBM Plex Mono', monospace; font-size: 1.1rem; color: var(--ink-70);
    }
    .cota-rotulo { font-size: .84rem; color: var(--ink-70); margin: 2px 0 26px 0; }

    .cota-eixo { position: relative; height: 30px; margin: 0 2px; }
    .cota-base { position: absolute; top: 14px; left: 0; right: 0; height: 1px; background: var(--rule); }
    .cota-faixa {
        position: absolute; top: 10px; height: 9px;
        background: var(--forge-10); border-left: 1.5px solid var(--forge); border-right: 1.5px solid var(--forge);
    }
    .cota-central { position: absolute; top: 6px; width: 2px; height: 17px; background: var(--ink); }
    .cota-ponta { position: absolute; top: 10px; width: 1px; height: 9px; background: var(--ink-45); }
    .cota-eixo-rotulos {
        display: flex; justify-content: space-between; margin-top: 8px;
        font-family: 'IBM Plex Mono', monospace; font-size: .72rem; color: var(--ink-45);
    }
    .cota-eixo-legenda { text-align: center; font-size: .74rem; color: var(--ink-45); margin-top: 2px; }

    /* ---------- Custo (R$) ---------- */
    .custo { border-top: 1px solid var(--rule); margin-top: 22px; padding-top: 18px; }
    .custo-rotulo { font-size: .8rem; color: var(--ink-70); margin-bottom: 6px; }
    .custo-valor {
        font-family: 'IBM Plex Mono', monospace; font-size: 1.7rem; font-weight: 600; color: var(--ink);
    }
    .custo-detalhe { font-size: .8rem; color: var(--ink-45); margin-top: 5px; line-height: 1.5; }
    .custo-pendente {
        border-top: 1px solid var(--rule); margin-top: 22px; padding-top: 16px;
        font-size: .82rem; color: var(--ink-45);
    }

    /* ---------- Estado vazio (o tracejado de drawing = "a definir") ---------- */
    .vazio { border: 1.5px dashed var(--rule); padding: 50px 24px; text-align: center; }
    .vazio-icone { font-size: 1.8rem; opacity: .4; }
    .vazio-texto { color: var(--ink-45); font-size: .88rem; margin-top: 12px; line-height: 1.6; }

    /* ---------- Nota (equivalente a nota numerada de desenho) ---------- */
    .nota {
        border-top: 1px solid var(--rule); padding-top: 14px; margin-top: 18px;
        font-size: .83rem; color: var(--ink-70); line-height: 1.6;
    }
    .nota b { color: var(--ink); font-weight: 600; }

    /* ---------- Bloco de titulo (metadados do modelo) ---------- */
    .bloco-titulo {
        display: grid; grid-template-columns: repeat(4, 1fr);
        border: 1px solid var(--rule); margin-top: 30px;
    }
    .bt-celula {
        padding: 10px 16px; border-left: 1px solid var(--rule);
    }
    .bt-celula:first-child { border-left: none; }
    .bt-rotulo { font-size: .7rem; color: var(--ink-45); margin-bottom: 3px; }
    .bt-valor { font-family: 'IBM Plex Mono', monospace; font-size: .82rem; color: var(--ink); line-height: 1.4; }

    /* ---------- Ajustes de widgets Streamlit ---------- */
    .stNumberInput label, .stSelectbox label {
        font-size: .82rem !important; font-weight: 500 !important; color: var(--ink) !important;
    }
    .stNumberInput input, .stSelectbox [data-baseweb="select"] > div {
        font-family: 'IBM Plex Mono', monospace !important;
        border-radius: 2px !important; border-color: var(--rule) !important;
    }
    .stNumberInput input:focus { border-color: var(--forge) !important; box-shadow: none !important; }
    div[data-testid="stForm"] {
        border: 1px solid var(--rule); border-radius: 0; padding: 24px 26px; background: var(--paper);
    }
    .stButton button, div[data-testid="stFormSubmitButton"] button {
        background: var(--forge) !important; color: #FFF !important;
        border: none !important; border-radius: 2px !important;
        font-weight: 500 !important; font-size: .92rem !important;
        padding: .65rem 1rem !important; letter-spacing: .01em;
        transition: background .15s ease;
    }
    div[data-testid="stFormSubmitButton"] button:hover { background: #A23A0C !important; }
    div[data-testid="stExpander"] { border: 1px solid var(--rule) !important; border-radius: 0 !important; background: var(--paper); }
    hr { margin: 1.1rem 0 !important; border-color: var(--rule) !important; }
    #MainMenu, footer { visibility: hidden; }

    @media (max-width: 640px) {
        .cab-titulo { font-size: 1.35rem; }
        .cota-valor { font-size: 2.3rem; }
        .bloco-titulo { grid-template-columns: repeat(2, 1fr); }
        .bt-celula:nth-child(3) { border-left: none; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Carregamento do modelo selecionado
# ---------------------------------------------------------------------------

@st.cache_resource
def carregar_modelo(nome_pkl: str):
    caminho = BASE / nome_pkl
    if not caminho.exists():
        st.error(f"Modelo não encontrado em `{nome_pkl}`.")
        st.stop()
    with open(caminho, "rb") as f:
        return pickle.load(f)


def _rotulo_campo(feature: str, rotulos: dict) -> str:
    return rotulos.get(feature, feature)


def _fmt_brl(v: float) -> str:
    """1234.5 -> '1.234,50' (separador de milhar '.', decimal ',')."""
    s = f"{v:,.2f}"
    return s.replace(",", "@").replace(".", ",").replace("@", ".")


def _config_input(feature: str) -> dict:
    """Heurística de min/max/step por nome da feature -- todas hoje são
    pesos (kg) ou diâmetros (mm), então dá pra inferir a faixa pelo nome."""
    fl = feature.lower()
    if "diam" in fl:
        return dict(min_value=0.0, max_value=800.0, step=5.0)
    if "peso" in fl or "weight" in fl:
        return dict(min_value=0.0, max_value=500.0, step=0.5)
    return dict(min_value=0.0, max_value=100000.0, step=1.0)


# ---------------------------------------------------------------------------
# Cabecalho + seletor de tipo de peca (FORA do form -- precisa reagir na hora)
# ---------------------------------------------------------------------------

st.markdown(
    """
    <p class="cab-eyebrow">Cinpal · apoio ao custeio</p>
    <p class="cab-titulo">Estimativa de tempo e custo de fabricação</p>
    """,
    unsafe_allow_html=True,
)

# Seletor de tipo de peca e o visor 3D lado a lado -- o 3D e so
# ilustrativo (nao entra no calculo), mas ajuda a confirmar visualmente
# que familia foi escolhida antes de preencher os dados.
col_sel, col_3d = st.columns([1, 1.3], gap="large")

with col_sel:
    st.markdown('<p class="campo-rotulo">Tipo de peça</p>', unsafe_allow_html=True)
    opcoes = list(CATALOGO_MODELOS.keys())
    tipo_peca = st.radio(
        "Tipo de peça",
        opcoes,
        format_func=lambda k: f"{CATALOGO_MODELOS[k]['rotulo']} — {CATALOGO_MODELOS[k]['sub']}",
        label_visibility="collapsed",
    )

# Densidade usada pra estimar peso a partir do volume do .stp -- ferro
# fundido pro volante (peca fundida), aco pra engrenagem (peca forjada).
# Sao valores tipicos de engenharia, nao a liga exata de cada PIC.
_DENSIDADE_KG_M3 = {"volante": 7200.0, "engrenagem": 7850.0, "forjaria": 7850.0}


@st.cache_data(show_spinner=False)
def _analisar_stp_cache(stp_bytes: bytes, densidade: float) -> dict:
    # cacheado pelo CONTEUDO do arquivo + densidade -- reenviar o mesmo
    # .stp, ou so trocar outro campo do formulario (que dispara um rerun
    # do Streamlit), nao reconverte/reanalisa de novo.
    return visor3d.analisar_stp_bytes(stp_bytes, densidade_kg_m3=densidade)


with col_3d:
    arquivo_stp = st.file_uploader(
        "Peça sendo cotada (opcional)", type=["stp", "step"],
        key=f"upload_{tipo_peca}",
        help="Sobe o .stp da peça deste orçamento pra ver o modelo real e "
             "pré-preencher peso/diâmetro. Fica só nesta sessão — não é salvo.",
    )

    analise_stp = None
    nome_peca_ao_vivo = None
    if arquivo_stp is not None:
        try:
            with st.spinner("Convertendo e medindo o desenho…"):
                analise_stp = _analisar_stp_cache(
                    arquivo_stp.getvalue(), _DENSIDADE_KG_M3.get(tipo_peca, 7850.0)
                )
            nome_peca_ao_vivo = arquivo_stp.name
        except visor3d.ConversaoStpError as e:
            st.warning(f"{e} Mostrando a peça ilustrativa padrão.")

    if analise_stp is not None:
        components.html(
            visor3d.render_html_stl_bytes(analise_stp["stl_bytes"], altura_px=190), height=192
        )
        st.markdown(
            f'<p class="cota-eixo-legenda" style="margin-top:-4px;">'
            f'Peça enviada agora — {nome_peca_ao_vivo}</p>',
            unsafe_allow_html=True,
        )
    else:
        components.html(visor3d.render_html(tipo_peca, altura_px=190), height=192)
        st.markdown(
            f'<p class="cota-eixo-legenda" style="margin-top:-4px;">{visor3d.legenda(tipo_peca)}</p>',
            unsafe_allow_html=True,
        )

st.markdown('<hr class="cab-regua">', unsafe_allow_html=True)

info_modelo = CATALOGO_MODELOS[tipo_peca]
art = carregar_modelo(info_modelo["pkl"])

FEATURES  = art["features"]
MEDIANAS  = art["medianas"]
MODELOS   = art["modelos"]
ESCOPO    = art["escopo"]
TARGET    = art["target_stats"]
METRICAS  = art["metricas_validacao_LOO"]
ROTULOS   = art.get("rotulos", {})
LOG_TARGET = bool(art.get("log_target", False))

MAPE = float(METRICAS.get("MAPE_ensemble", 40.0))
R2   = float(METRICAS.get("R2_ensemble", 0.0))

col_form, col_res = st.columns([1.15, 1], gap="large")

# ---------------------------------------------------------------------------
# Formulario -- campos gerados a partir das FEATURES do modelo escolhido
# ---------------------------------------------------------------------------

with col_form:
    st.markdown(
        f'<p class="painel-rotulo">Dados do orçamento</p>'
        f'<p class="painel-legenda">{info_modelo["legenda"]}</p>',
        unsafe_allow_html=True,
    )

    # features DERIVADAS não viram campo de formulário — hoje só area_proxy
    # (= diameter_max² / 1000), calculada a partir de outra feature já pedida.
    FEATURES_DERIVADAS = {"area_proxy"}
    FEATURES_PEDIDAS = [f for f in FEATURES if f not in FEATURES_DERIVADAS]

    # De onde vem o auto-preenchimento de cada feature, a partir do .stp
    # analisado -- e se e' medida DIRETA da peça enviada (volante: a peça
    # do .stp e' a mesma que o modelo pede, peça acabada) ou uma
    # APROXIMAÇÃO (engrenagem: o modelo quer peso do BRUTO forjado, mas o
    # .stp que o cliente manda e' da peça ACABADA -- a peça bruta pesa
    # mais, tem sobra de material pra usinar. Uso o peso calculado como
    # estimativa de PISO, deixando isso explícito, não escondido).
    _MAPA_STP_DIRETO = {"weight_kg": "peso_kg", "diameter_max": "diametro_max_mm"}
    _MAPA_STP_APROX = {"peso_forjado": "peso_kg", "peso_bruto": "peso_kg"}

    id_origem = "manual"
    if analise_stp is not None:
        import hashlib
        id_origem = hashlib.md5(arquivo_stp.getvalue()).hexdigest()[:8]

        campos_diretos = [f for f in FEATURES_PEDIDAS if f in _MAPA_STP_DIRETO]
        campos_aprox = [f for f in FEATURES_PEDIDAS if f in _MAPA_STP_APROX]
        if campos_diretos:
            st.markdown(
                '<div class="nota">Peso e diâmetro pré-preenchidos a partir do '
                '.stp enviado — pode ajustar antes de calcular.</div>',
                unsafe_allow_html=True,
            )
        if campos_aprox:
            st.markdown(
                '<div class="nota"><b>Estimativa aproximada:</b> o .stp enviado é '
                'da peça acabada, mas este modelo pede o peso do bruto forjado '
                '(que pesa mais — tem sobra de material pra usinar). Preenchi com '
                'o peso calculado da peça acabada como piso — ajuste para cima com '
                'o dado real da forjaria se tiver.</div>',
                unsafe_allow_html=True,
            )

    with st.form(f"entrada_{tipo_peca}"):
        st.markdown('<p class="campo-rotulo">Entradas do modelo</p>', unsafe_allow_html=True)
        valores_form: dict[str, float] = {}
        cols = st.columns(min(len(FEATURES_PEDIDAS), 2)) if len(FEATURES_PEDIDAS) > 1 else [st.container()]
        for i, feat in enumerate(FEATURES_PEDIDAS):
            with cols[i % len(cols)]:
                if feat == "tonelagem":
                    # não é um valor livre -- são as prensas reais que a
                    # Cinpal tem (vistas nos roteiros de forjaria). Não dá
                    # pra identificar isso a partir da geometria do .stp
                    # (é decisão de processo, não propriedade da peça) --
                    # fica sempre manual, de propósito.
                    opcoes_t = [1600.0, 2500.0, 3000.0, 4000.0, 6300.0]
                    padrao = float(MEDIANAS.get(feat, 2500.0))
                    idx_padrao = min(range(len(opcoes_t)), key=lambda k: abs(opcoes_t[k]-padrao))
                    valores_form[feat] = st.selectbox(
                        _rotulo_campo(feat, ROTULOS), opcoes_t, index=idx_padrao,
                        format_func=lambda t: f"{t:.0f} T",
                        key=f"{tipo_peca}_{feat}",
                    )
                    continue

                chave_stp = _MAPA_STP_DIRETO.get(feat) or _MAPA_STP_APROX.get(feat)
                if analise_stp is not None and chave_stp is not None:
                    valor_padrao = float(analise_stp[chave_stp])
                else:
                    valor_padrao = float(MEDIANAS.get(feat, 0.0))

                cfg = _config_input(feat)
                valores_form[feat] = st.number_input(
                    _rotulo_campo(feat, ROTULOS),
                    value=valor_padrao,
                    step=cfg["step"], min_value=cfg["min_value"], max_value=cfg["max_value"],
                    help="Deixe 0 para usar a mediana do histórico.",
                    key=f"{tipo_peca}_{feat}_{id_origem}",
                )

        st.markdown("")
        enviado = st.form_submit_button("Calcular estimativa", use_container_width=True)


# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------

with col_res:
    st.markdown('<p class="painel-rotulo">Resultado</p>', unsafe_allow_html=True)

    if not enviado:
        st.markdown(
            '<div class="vazio">'
            '<div class="vazio-icone">📐</div>'
            '<div class="vazio-texto">Preencha os dados ao lado<br>'
            'e clique em <b>Calcular estimativa</b>.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        informado = {f: valores_form[f] > 0 for f in FEATURES_PEDIDAS}
        valores = {
            f: (valores_form[f] if valores_form[f] > 0 else MEDIANAS.get(f, 0.0))
            for f in FEATURES_PEDIDAS
        }
        # area_proxy (só existe no modelo de Volante) é derivada do diâmetro,
        # não perguntada diretamente -- se estiver na lista de features mas
        # não foi preenchida via form, deriva aqui.
        if "area_proxy" in FEATURES and "diameter_max" in valores:
            valores["area_proxy"] = (float(valores["diameter_max"]) ** 2) / 1000.0
            informado["area_proxy"] = informado.get("diameter_max", False)

        entrada = pd.DataFrame([valores])[FEATURES]

        # O modelo foi treinado em log1p(minutos) quando LOG_TARGET=True --
        # desfazer a transformação antes de mostrar.
        brutos = np.array([p.predict(entrada)[0] for p in MODELOS.values()])
        preds = np.expm1(brutos) if LOG_TARGET else brutos
        central = float(np.clip(np.mean(preds), 3.0, 600.0))

        # Faixa honesta: usa o MAPE medido na validação, não o spread do ensemble
        # (o spread entre modelos subestima muito a incerteza real).
        margem = central * (MAPE / 100.0)
        faixa_lo = max(3.0, central - margem)
        faixa_hi = min(600.0, central + margem)

        rotulo_area = str(ESCOPO["area"]).replace("_", " ")

        # A "cota" e o momento principal: valor central em destaque, com a
        # tolerancia ao lado (como uma cota de desenho: "27 ±4 min"), e um
        # eixo unico que mostra ONDE essa faixa cai dentro do historico da
        # base -- substitui as duas barras separadas da versao anterior.
        st.markdown(
            f"""
            <div class="cota-topo">
              <span class="cota-valor">{central:.0f}</span>
              <span class="cota-unidade">min</span>
              <span class="cota-tol">± {margem:.0f} ({MAPE:.0f}%)</span>
            </div>
            <div class="cota-rotulo">{rotulo_area}, valor central e tolerância medida na validação</div>
            """,
            unsafe_allow_html=True,
        )

        t_min, t_max = float(TARGET["min"]), float(TARGET["max"])
        span = max(t_max - t_min, 1.0)
        pct = lambda v: max(0.0, min(100.0, (v - t_min) / span * 100.0))
        p_lo, p_hi, p_c = pct(faixa_lo), pct(faixa_hi), pct(central)
        st.markdown(
            f"""
            <div class="cota-eixo">
              <div class="cota-base"></div>
              <div class="cota-ponta" style="left:0%;"></div>
              <div class="cota-ponta" style="left:100%;"></div>
              <div class="cota-faixa" style="left:{p_lo:.1f}%; width:{max(p_hi-p_lo,1.0):.1f}%;"></div>
              <div class="cota-central" style="left:{p_c:.1f}%;"></div>
            </div>
            <div class="cota-eixo-rotulos">
              <span>{t_min:.0f}</span><span>{t_max:.0f} min</span>
            </div>
            <div class="cota-eixo-legenda">posição da faixa prevista no histórico de {TARGET['n']} peças cotadas</div>
            """,
            unsafe_allow_html=True,
        )

        # ------------------------------------------------------------
        # Custo (R$) -- so calcula quando a tarifa da etapa existe.
        # Formula e tarifas em config_custos.py (informadas por Fabio,
        # 17/09/2026). Nunca inventa tarifa: se falta, avisa em vez de
        # calcular com numero chutado.
        # ------------------------------------------------------------
        if tipo_peca == "forjaria":
            tonelagem_usada = float(valores.get("tonelagem", 0))
            peso_usado = float(valores.get("peso_plano", 0))
            custo = custo_forjado(central, peso_usado, tonelagem_usada)
            if custo is not None:
                from config_custos import CUSTO_HORA_PRENSA, CUSTO_MATERIA_PRIMA_KG
                custo_prensa = (central / 60.0) * CUSTO_HORA_PRENSA[tonelagem_usada]
                custo_material = peso_usado * CUSTO_MATERIA_PRIMA_KG
                st.markdown(
                    f"""
                    <div class="custo">
                      <div class="custo-rotulo">Custo estimado — forjaria</div>
                      <div class="custo-valor">R$ {_fmt_brl(custo)}</div>
                      <div class="custo-detalhe">
                        prensa {tonelagem_usada:.0f}T: R$ {_fmt_brl(custo_prensa)} &nbsp;+&nbsp;
                        matéria-prima ({peso_usado:.1f} kg × R$ {CUSTO_MATERIA_PRIMA_KG:.0f}/kg): R$ {_fmt_brl(custo_material)}
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div class="custo-pendente">Sem tarifa cadastrada para esta '
                    'prensa — custo não calculado.</div>',
                    unsafe_allow_html=True,
                )
        elif tipo_peca == "engrenagem":
            custo = custo_usinagem(central)
            if custo is None:
                st.markdown(
                    '<div class="custo-pendente">Custo em R$ pendente — a tarifa '
                    'de usinagem (R$/hora) ainda não foi informada.</div>',
                    unsafe_allow_html=True,
                )

        st.markdown(
            f"""
            <div class="nota">
              <b>Estimativa de apoio, não cotação.</b> O modelo explica
              {R2 * 100:.0f}% da variação de tempo observada (R² {R2:.2f}) e erra
              ~{MAPE:.0f}% em média. Use como ponto de partida — a validação do
              custeista continua obrigatória.
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.expander("Detalhes técnicos"):
            st.dataframe(
                pd.DataFrame({
                    "Variável": [_rotulo_campo(f, ROTULOS) for f in FEATURES],
                    "Valor usado": [f"{float(entrada[f].iloc[0]):.2f}" for f in FEATURES],
                    "Origem": [
                        ("derivada do diâmetro" if f == "area_proxy"
                         else "informado" if informado.get(f)
                         else "mediana do histórico")
                        for f in FEATURES
                    ],
                }),
                hide_index=True, use_container_width=True,
            )
            if LOG_TARGET:
                st.caption("Modelo treinado em escala logarítmica do tempo "
                           "(tempo de usinagem é multiplicativo, não aditivo).")

            nomes = list(MODELOS.keys())
            linha = " · ".join(f"{n}: {v:.1f} min" for n, v in zip(nomes, preds))
            st.caption(f"Predição por modelo — {linha} → ensemble (média): **{central:.1f} min**")


# ---------------------------------------------------------------------------
# Bloco de titulo -- os metadados do modelo, na convencao de um bloco de
# titulo de desenho tecnico (canto da prancha): celulas rotuladas, sem
# badge, sem gradiente.
# ---------------------------------------------------------------------------

st.markdown(
    f"""
    <div class="bloco-titulo">
      <div class="bt-celula">
        <div class="bt-rotulo">escopo</div>
        <div class="bt-valor">{ESCOPO['familia_nome']}<br>{ESCOPO['tipo_bruto']} · {ESCOPO['area']}</div>
      </div>
      <div class="bt-celula">
        <div class="bt-rotulo">validação (leave-one-out)</div>
        <div class="bt-valor">R² {R2:.2f}<br>MAPE {MAPE:.0f}% · MAE {METRICAS['MAE_ensemble']:.1f} min</div>
      </div>
      <div class="bt-celula">
        <div class="bt-rotulo">base de treino</div>
        <div class="bt-valor">{TARGET['n']} peças<br>Cinpal 2020–2026</div>
      </div>
      <div class="bt-celula">
        <div class="bt-rotulo">modelo</div>
        <div class="bt-valor">RF · HistGB{' · XGB' if 'xgb' in MODELOS else ''}<br>v{art.get('versao', '—')}</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)
