"""
pagina_volante.py
-----------------
Página "Volante — tempo de processo" do app_cotacao.py. Modelo treinado com
tempo de folha de processo, separado da aba Volante antiga (tempo orçado).

Usa modelo_tempo_volante.pkl (completo, só na rede) ou, se não houver,
modelo_tempo_volante_publico.pkl (deploy: repositório público, sem PN nem
cliente nas peças parecidas).
"""
import pandas as pd
import streamlit as st

import orcamento_volante as O

MATERIAIS = {"Ferro fundido (não especificado)": "FOFO", "GG25 / EN-GJL-250": "FOFO_GG25",
             "GG30 / EN-GJL-300": "FOFO_GG30", "Nodular": "FOFO_NODULAR"}


@st.cache_resource
def _pacote(caminho: str):
    return O.carregar(caminho)


def _num(rotulo, valor=0, ajuda=None):
    return st.number_input(rotulo, min_value=0, max_value=200, value=valor, step=1, help=ajuda)


def render(base, analise_stp=None):
    arq = next((base / a for a in ("modelo_tempo_volante.pkl", "modelo_tempo_volante_publico.pkl")
                if (base / a).exists()), None)
    if arq is None:
        st.error("Modelo de tempo de processo não encontrado.")
        st.stop()
    p = _pacote(str(arq))
    m = p["metricas"]
    peso_stp = float(analise_stp["peso_kg"]) if analise_stp else 0.0

    col_form, col_res = st.columns([1.15, 1], gap="large")
    with col_form:
        with st.form("form_volante_processo"):
            st.markdown('<p class="painel-rotulo">Dados do desenho</p>', unsafe_allow_html=True)
            a, b = st.columns(2)
            peso = a.number_input("Peso acabado (kg)", 0.0, 500.0, peso_stp, 0.5)
            bruto = b.number_input("Peso bruto fundido (kg)", 0.0, 500.0, 0.0, 0.5,
                                   help=f"Vazio (0) = estima pelo acabado (×{p['razao_bruto']:.2f}).")
            a, b = st.columns(2)
            clientes = p["categorias"]["cliente_n"] + ["Outro"]
            cliente = a.selectbox("Cliente", clientes, index=len(clientes) - 1)
            material = b.selectbox("Material", list(MATERIAIS))

            st.markdown('<p class="painel-rotulo" style="margin-top:14px;">Furação</p>', unsafe_allow_html=True)
            a, b, c = st.columns(3)
            with a:
                vir = _num("Furos p/ virabrequim")
                radial = _num("Furos radiais (Ø externo)", ajuda="Ex.: 58 furos do anel de rotação.")
            with b:
                emb = _num("Furos p/ embreagem")
                outros = _num("Outros furos", ajuda="Fuligem, referência, posicionador etc.")
            with c:
                rosc = _num("Destes, roscados")
                alarg = _num("Destes, alargados")
            a, b, c = st.columns(3)
            with a:
                rasgos = _num("Rasgos fresados")
            with b:
                pinos = _num("Pinos montados")
            with c:
                inclinado = st.checkbox("Furo inclinado")
            enviar = st.form_submit_button("Orçar", type="primary")

    with col_res:
        if not enviar or peso <= 0:
            st.markdown(
                '<div class="vazio"><div class="vazio-texto">Preencha o peso e a furação do desenho<br>'
                'e clique em Orçar.</div></div>', unsafe_allow_html=True)
        else:
            o = O.orcar(p, {
                "peso_liquido": peso, "peso_bruto": bruto or None, "cliente_n": cliente, "mat_n": MATERIAIS[material],
                "g_furos": vir + emb + radial + outros, "g_vir": vir, "g_emb": emb, "g_rosc": rosc, "g_radial": radial,
                "g_alarg": alarg, "g_rasgos": rasgos, "g_pinos": pinos, "g_inclinado": int(inclinado)})
            st.markdown(
                f"""
                <div class="cota-topo">
                  <span class="cota-valor">{o['total']:.1f}</span><span class="cota-unidade">min/peça</span>
                  <span class="cota-tol">faixa {o['p10']:.0f} a {o['p90']:.0f} min</span>
                </div>
                <p class="cota-rotulo">Usinagem e montagem, padrão das folhas de 2026.</p>
                <div class="custo">
                  <div class="custo-rotulo">Com margem de segurança de {O.MARGEM:.0%}</div>
                  <div class="custo-valor">{o['com_margem']:.1f} min/peça</div>
                  <div class="custo-detalhe">Fundição do bruto, à parte: ~{o['fundicao']:.1f} min/peça (peças parecidas).
                  Cremalheira não incluída.{' Peso bruto estimado: ' + format(o['peso_bruto'], '.1f') + ' kg.' if o['bruto_estimado'] else ''}</div>
                </div>
                """, unsafe_allow_html=True)
            st.markdown('<p class="painel-rotulo" style="margin-top:18px;">Por etapa</p>', unsafe_allow_html=True)
            st.dataframe(pd.DataFrame({"Etapa": list(o["etapas"]), "min/peça": [round(v, 1) for v in o["etapas"].values()]}),
                         hide_index=True, width="stretch")

    if enviar and peso > 0:
        st.markdown('<p class="painel-rotulo" style="margin-top:18px;">Volantes parecidos (folha 2026)</p>', unsafe_allow_html=True)
        s = o["parecidas"]
        t = pd.DataFrame({"Peso (kg)": s.peso_liquido.round(1), "Furos": s.g_furos.astype(int), "Radiais": s.g_radial.astype(int),
                          "Roscados": s.g_rosc.astype(int), "Tempo folha (min)": s.tempo.round(1),
                          "Tornear": s.t_tornear.round(1), "Furação": s.t_furacao.round(1)})
        if "codigo" in s:
            t.insert(0, "Código", s.codigo)
            t.insert(1, "Cliente", s.cliente_n)
        st.dataframe(t, hide_index=True, width="stretch")

    st.markdown(
        f"""
        <div class="bloco-titulo">
          <div class="bt-celula"><div class="bt-rotulo">escopo</div>
            <div class="bt-valor">Volantes 46-35/85 de montadora<br>tempo da folha de processo</div></div>
          <div class="bt-celula"><div class="bt-rotulo">validação (peças de outro bruto)</div>
            <div class="bt-valor">erro médio {m['mape']:.0f}% · mediana {m['mediana']:.0f}%<br>{m['ate20']:.0f}% das peças com erro até 20%</div></div>
          <div class="bt-celula"><div class="bt-rotulo">base de treino</div>
            <div class="bt-valor">{m['n']} volantes<br>{m['n_2026']} com folha 2026</div></div>
        </div>
        """, unsafe_allow_html=True)
