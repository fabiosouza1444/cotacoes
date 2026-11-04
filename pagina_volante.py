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

EXTRAS = {"torno": "Torno (eliminar massalote)", "pintura": "Pintura do fundido", "rebarbadora": "Rebarbadora robotizada",
          "ultrassom": "Ultrassom"}
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
    m, ms = p["com"]["metricas"], p["sem"]["metricas"]
    peso_stp = float(analise_stp["peso_kg"]) if analise_stp else 0.0

    col_form, col_res = st.columns([1.15, 1], gap="large")
    with col_form:
        with st.form("form_volante_processo"):
            st.markdown('<p class="painel-rotulo">Dados do desenho</p>', unsafe_allow_html=True)
            a, b = st.columns(2)
            peso = a.number_input("Peso acabado (kg)", 0.0, 500.0, peso_stp, 0.5)
            bruto = b.number_input("Peso bruto fundido (kg)", 0.0, 500.0, 0.0, 0.5,
                                   help=f"Vazio (0) = estima pelo acabado (×{p['razao_bruto']:.2f}).")
            diam = st.number_input("Diâmetro primitivo da cremalheira (mm)", 0.0, 800.0, 0.0, 1.0,
                                   help="Dentes × módulo, na tabela do dentado. Opcional, mas estreita a faixa.")
            a, b = st.columns(2)
            clientes = p["sem"]["categorias"]["cliente_n"] + ["Outro"]
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
            st.markdown('<p class="painel-rotulo" style="margin-top:14px;">Fundição do bruto</p>', unsafe_allow_html=True)
            a, b = st.columns(2)
            figuras = a.selectbox("Figuras na matriz", ["Sugerir", 1, 2, 3, 4],
                                  help="Peças por molde. Sugerir usa o peso do bruto e o diâmetro.")
            padrao = b.checkbox("Extras pelo padrão do cliente e material", True,
                                help="Desmarque para informar abaixo; a faixa fica mais estreita.")
            extras = st.multiselect("Extras do bruto (se desmarcou o padrão)", list(EXTRAS), format_func=EXTRAS.get)
            enviar = st.form_submit_button("Orçar", type="primary")

    with col_res:
        if not enviar or peso <= 0:
            st.markdown(
                '<div class="vazio"><div class="vazio-texto">Preencha o peso e a furação do desenho<br>'
                'e clique em Orçar.</div></div>', unsafe_allow_html=True)
        else:
            o = O.orcar(p, {
                "peso_liquido": peso, "peso_bruto": bruto or None, "d_crem": diam or None, "figuras": None if figuras == "Sugerir" else figuras, "extras": None if padrao else extras, "cliente_n": cliente, "mat_n": MATERIAIS[material],
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
                  <div class="custo-detalhe">{' Peso bruto estimado: ' + format(o['peso_bruto'], '.1f') + ' kg.' if o['bruto_estimado'] else ''}{'' if o['com_diametro'] else ' Sem o diâmetro da cremalheira, a faixa fica mais larga.'}</div>
                </div>
                """, unsafe_allow_html=True)
            f = o["fundicao"]
            nomes = ", ".join(EXTRAS[x].lower() for x in f["extras"]) or "nenhum"
            st.markdown(
                f"""
                <div class="custo">
                  <div class="custo-rotulo">Fundição do bruto, à parte</div>
                  <div class="custo-valor">{f['tempo']:.1f} min/peça</div>
                  <div class="custo-detalhe">Faixa {f['p10']:.1f} a {f['p90']:.1f} min.
                  {f['figuras']} figura(s) na matriz{' (sugerido)' if f['figuras_sugeridas'] else ''};
                  extras: {nomes}{' (padrão)' if f['extras_padrao'] else ''}.</div>
                </div>
                """, unsafe_allow_html=True)
            cr = o["cremalheira"]
            st.markdown(
                f"""
                <div class="custo">
                  <div class="custo-rotulo">Cremalheira, à parte (padrão)</div>
                  <div class="custo-valor">{cr['tempo']:.1f} min/peça</div>
                  <div class="custo-detalhe">Faixa {cr['tempo'] * cr['banda'][0]:.0f} a {cr['tempo'] * cr['banda'][1]:.0f} min.
                  Mais têmpera por indução: {cr['tempera']:.1f} min (tarifa própria).</div>
                </div>
                <div class="custo">
                  <div class="custo-rotulo">Volante completo (bruto + usinagem + cremalheira + têmpera)</div>
                  <div class="custo-valor">{o['completo']:.1f} min/peça</div>
                  <div class="custo-detalhe">Com margem de {O.MARGEM:.0%}: {o['completo_margem']:.1f} min/peça. Soma de áreas com
                  custo por minuto diferente: use as parcelas para custear.</div>
                </div>
                """, unsafe_allow_html=True)
            st.markdown('<p class="painel-rotulo" style="margin-top:18px;">Por etapa (usinagem)</p>', unsafe_allow_html=True)
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
            <div class="bt-valor">com diâmetro: erro médio {m['mape']:.0f}%, {m['ate20']:.0f}% até 20%<br>sem: erro médio {ms['mape']:.0f}%, {ms['ate20']:.0f}% até 20%</div></div>
          <div class="bt-celula"><div class="bt-rotulo">base de treino</div>
            <div class="bt-valor">{ms['n']} volantes<br>{ms['n_2026']} com folha 2026</div></div>
        </div>
        """, unsafe_allow_html=True)
