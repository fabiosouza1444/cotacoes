"""
visor3d.py
-----------
Visualizador 3D por familia de peca, pro app_cotacao.py. So ilustrativo
(o modelo de tempo/custo nao usa nada daqui) -- roda 100% no NAVEGADOR
de quem abre o app (three.js via CDN + STLLoader, STL embutido como
base64 no HTML do componente). Ninguem instala nada, nem o servidor
Streamlit precisa de kernel CAD em tempo de execucao (a conversao STEP
-> STL ja foi feita uma vez, ver converter_stp.py / converter_stp_
engrenagem.py).

DECISAO DE CONFIDENCIALIDADE (22/09/2026)
Os arquivos em assets_3d/ sao geometria REAL de peca de cliente (volante
Scania PIC 21.240, engrenagem Scania PN 2528365 "Gear fuel pump") --
nao formas
genericas. Cogitei um modelo procedural (sem geometria de cliente, ver
_render_generico abaixo, mantido como fallback) mas o Fabio decidiu
usar a peca real depois de comparar os dois lado a lado -- decisao dele,
documentada aqui pra quem mexer nisso depois saber que foi deliberada,
nao um descuido.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

_DIR_ASSETS = Path(__file__).parent / "assets_3d"

# familia (tipo_peca do app) -> (arquivo stl, correcao de eixo Z-up->Y-up,
# escala relativa da cena, nome pra legenda/atribuicao)
_MODELOS_REAIS = {
    "volante": dict(arquivo="volante_scania.stl", nome="Volante — Scania, PIC 21.240"),
    "engrenagem": dict(arquivo="engrenagem_scania.stl", nome="Engrenagem cilíndrica — Scania, PN 2528365"),
    "forjaria": dict(arquivo="engrenagem_scania.stl", nome="Engrenagem cilíndrica — Scania, PN 2528365"),
}

# fallback procedural (sem geometria de cliente) -- mantido caso a
# decisao de usar peca real mude no futuro. Ver _render_generico().
_CONFIG_GENERICO = {
    "volante": dict(raio=2.6, espessura=0.42, dentes=80, profDente=0.16,
                     furo=0.26, raioFuros=0.62, furosFixacao=8),
    "engrenagem": dict(raio=1.6, espessura=0.78, dentes=26, profDente=0.24,
                        furo=0.32, raioFuros=0.0, furosFixacao=0),
    "forjaria": dict(raio=1.6, espessura=0.78, dentes=26, profDente=0.24,
                      furo=0.32, raioFuros=0.0, furosFixacao=0),
}


def _stl_base64(nome_arquivo: str) -> str | None:
    caminho = _DIR_ASSETS / nome_arquivo
    if not caminho.exists():
        return None
    return base64.b64encode(caminho.read_bytes()).decode("ascii")


_CABECALHO_CENA = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  html, body {{ margin:0; padding:0; overflow:hidden; background:transparent; }}
  #viewer {{ width:100%; height:{altura_px}px; }}
</style>
</head>
<body>
<div id="viewer"></div>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.min.js"></script>
"""

_RODAPE_CENA = """
</body>
</html>
"""


def _cena_base(altura_px: int) -> str:
    return _CABECALHO_CENA.format(altura_px=altura_px)


def render_html(tipo_peca: str, altura_px: int = 230) -> str:
    """HTML autocontido pra st.components.v1.html — peça real (STL
    embutido em base64) quando o asset existe; cai pro genérico se não."""
    info = _MODELOS_REAIS.get(tipo_peca)
    b64 = _stl_base64(info["arquivo"]) if info else None

    if not info or b64 is None:
        return _render_generico(tipo_peca, altura_px)

    return _render_stl_base64(b64, altura_px)


def render_html_stl_bytes(stl_bytes: bytes, altura_px: int = 230) -> str:
    """Mesmo visor, mas pra um STL que acabou de ser convertido na hora
    a partir do .stp que o custeista subiu (ver stp_bytes_para_stl_bytes),
    nao um dos assets fixos por familia."""
    b64 = base64.b64encode(stl_bytes).decode("ascii")
    return _render_stl_base64(b64, altura_px)


class ConversaoStpError(Exception):
    """Erro ao converter um .stp enviado pelo usuario -- mensagem em
    portugues, pronta pra mostrar na interface (nao um traceback cru)."""


def analisar_stp_bytes(stp_bytes: bytes, densidade_kg_m3: float = 7850.0) -> dict:
    """Converte um .stp/.step em memoria PRA STL (visor) e, na mesma
    passada, calcula peso estimado (volume x densidade) e diametro
    maximo (bounding box) -- pra auto-preencher os campos do formulario.

    Import de cadquery e' PREGUICOSO (so acontece se essa funcao for
    chamada) -- cadquery/OCP e' uma dependencia pesada (kernel CAD),
    nao faz sentido pagar esse custo de import toda vez que o app sobe
    se ninguem usar o upload nesta sessao. Roda so no processo do
    SERVIDOR Streamlit (nao no navegador) -- quem hospeda o app precisa
    ter `pip install cadquery` feito.

    peso_kg e diametro_max_mm sao ESTIMATIVAS GEOMETRICAS da peca do
    .stp enviado (que costuma ser a peca ACABADA) -- nao confundir com
    peso de peca BRUTA forjada (que tem sobra de material pra usinar,
    ver ressalva em app_cotacao.py).

    Levanta ConversaoStpError (mensagem em portugues) se nao conseguir
    ler o arquivo ou se a geometria nao render um solido valido -- nunca
    devolve um numero de peso/diametro chutado.
    """
    import tempfile
    from pathlib import Path as _Path

    try:
        import cadquery as cq
    except ImportError as e:
        raise ConversaoStpError(
            "Conversão de .stp indisponível neste servidor — falta instalar "
            "`cadquery` (`pip install cadquery`)."
        ) from e

    with tempfile.TemporaryDirectory() as tmp:
        entrada = _Path(tmp) / "peca.stp"
        saida = _Path(tmp) / "peca.stl"
        entrada.write_bytes(stp_bytes)
        try:
            modelo = cq.importers.importStep(str(entrada))
            solido = modelo.val()
            volume_mm3 = float(solido.Volume())
            bb = solido.BoundingBox()
            dims = sorted([bb.xlen, bb.ylen, bb.zlen])
            cq.exporters.export(modelo, str(saida), tolerance=0.12, angularTolerance=0.3)
        except Exception as e:
            raise ConversaoStpError(
                f"Não consegui analisar esse arquivo — confira se é um "
                f".stp/.step válido de uma peça sólida ({e})."
            ) from e

        if volume_mm3 <= 0:
            raise ConversaoStpError(
                "O arquivo abriu, mas não encontrei um sólido válido (volume "
                "zero) — não dá pra estimar peso a partir dele."
            )

        # peca em forma de disco (volante/engrenagem): a menor das 3
        # dimensoes da caixa delimitadora e' a espessura (eixo axial); o
        # "diametro maximo" e' a maior das outras duas.
        diametro_max_mm = dims[2]
        peso_kg = (volume_mm3 / 1e9) * densidade_kg_m3

        return {
            "stl_bytes": saida.read_bytes(),
            "peso_kg": round(peso_kg, 2),
            "diametro_max_mm": round(diametro_max_mm, 1),
            "dimensoes_mm": tuple(round(d, 1) for d in dims),
            "volume_mm3": round(volume_mm3, 1),
        }


def _render_stl_base64(b64: str, altura_px: int) -> str:
    return _cena_base(altura_px) + f"""
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/STLLoader.js"></script>
<script>
(function() {{
  const H = {altura_px};
  const container = document.getElementById('viewer');
  const W = container.clientWidth || 300;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(35, W / H, 0.1, 5000);
  const renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: true }});
  renderer.setSize(W, H);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  container.appendChild(renderer.domElement);

  scene.add(new THREE.AmbientLight(0xffffff, 0.35));
  const key = new THREE.DirectionalLight(0xffffff, 0.9);
  key.position.set(4, 6, 5);
  scene.add(key);
  const rim = new THREE.DirectionalLight(0xC1440E, 0.35);
  rim.position.set(-5, -2, -4);
  scene.add(rim);

  // Ambiente reflexivo sintetico -- sem isso o metal fica "morto": metal de
  // verdade reflete o ambiente ao redor, nao so a luz direta. Gera um
  // cubemap na hora (PMREMGenerator), sem baixar nenhuma textura externa.
  const pmrem = new THREE.PMREMGenerator(renderer);
  pmrem.compileEquirectangularShader();
  const cenaAmbiente = new THREE.Scene();
  const ceu = new THREE.Mesh(
    new THREE.SphereGeometry(30, 24, 24),
    new THREE.MeshBasicMaterial({{ color: 0xdfe3e6, side: THREE.BackSide }})
  );
  cenaAmbiente.add(ceu);
  const piso = new THREE.Mesh(
    new THREE.PlaneGeometry(60, 60),
    new THREE.MeshBasicMaterial({{ color: 0x4a5361 }})
  );
  piso.rotation.x = -Math.PI / 2;
  piso.position.y = -10;
  cenaAmbiente.add(piso);
  const brilho1 = new THREE.PointLight(0xffffff, 26, 60);
  brilho1.position.set(12, 14, 10);
  cenaAmbiente.add(brilho1);
  const brilho2 = new THREE.PointLight(0xC1440E, 14, 60);
  brilho2.position.set(-14, -6, -10);
  cenaAmbiente.add(brilho2);
  scene.environment = pmrem.fromScene(cenaAmbiente, 0.03).texture;
  pmrem.dispose();

  const acoMat = new THREE.MeshStandardMaterial({{
    color: 0x9aa1ab, metalness: 0.9, roughness: 0.28, envMapIntensity: 1.1
  }});

  const b64 = "{b64}";
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);

  const loader = new THREE.STLLoader();
  const geometry = loader.parse(bytes.buffer);
  geometry.computeBoundingBox();
  geometry.center();
  const size = new THREE.Vector3();
  geometry.boundingBox.getSize(size);
  const maiorDim = Math.max(size.x, size.y, size.z) || 1;
  const escala = 4.4 / maiorDim;

  const grupo = new THREE.Group();
  const mesh = new THREE.Mesh(geometry, acoMat);
  mesh.scale.setScalar(escala);
  grupo.add(mesh);
  grupo.rotation.x = -Math.PI / 2 + 0.30; // CAD Z-up -> cena Y-up + leve inclinacao
  scene.add(grupo);

  camera.position.set(0, 2.4, 7.2);
  camera.lookAt(0, 0, 0);

  // Gira num eixo levemente inclinado (nao o eixo Y puro) -- assim a peca
  // tomba mostrando varios angulos, tipo expositor de loja, em vez de so
  // rodar em torno do proprio furo tipo torno. Funciona independente de
  // como o .stp original veio orientado (nao precisa recalibrar toda vez
  // que troca a peca).
  const eixoGiro = new THREE.Vector3(0.22, 1, 0.14).normalize();
  function animar() {{
    requestAnimationFrame(animar);
    grupo.rotateOnWorldAxis(eixoGiro, 0.008);
    renderer.render(scene, camera);
  }}
  animar();

  window.addEventListener('resize', function() {{
    const w = container.clientWidth || 300;
    camera.aspect = w / H;
    camera.updateProjectionMatrix();
    renderer.setSize(w, H);
  }});
}})();
</script>
""" + _RODAPE_CENA


def _render_generico(tipo_peca: str, altura_px: int) -> str:
    """Fallback procedural, sem geometria de cliente -- ver docstring do
    modulo. Usado so se o .stl correspondente nao existir em assets_3d/."""
    cfg = _CONFIG_GENERICO.get(tipo_peca, _CONFIG_GENERICO["engrenagem"])
    cfg_json = json.dumps(cfg)

    return _cena_base(altura_px) + f"""
<script>
(function() {{
  const H = {altura_px};
  const container = document.getElementById('viewer');
  const W = container.clientWidth || 300;
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(35, W / H, 0.1, 100);
  camera.position.set(0, 2.4, 7.2);
  camera.lookAt(0, 0, 0);
  const renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: true }});
  renderer.setSize(W, H);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  container.appendChild(renderer.domElement);
  scene.add(new THREE.AmbientLight(0xffffff, 0.55));
  const key = new THREE.DirectionalLight(0xffffff, 0.95); key.position.set(4, 6, 5); scene.add(key);
  const rim = new THREE.DirectionalLight(0xC1440E, 0.4); rim.position.set(-5, -2, -4); scene.add(rim);
  const acoMat = new THREE.MeshStandardMaterial({{ color: 0x8b93a1, metalness: 0.78, roughness: 0.32 }});
  const acoEscuro = new THREE.MeshStandardMaterial({{ color: 0x384150, metalness: 0.6, roughness: 0.5 }});
  const CFG = {cfg_json};
  const grupo = new THREE.Group();
  grupo.add(new THREE.Mesh(new THREE.CylinderGeometry(CFG.raio, CFG.raio, CFG.espessura, 72), acoMat));
  const larguraDente = (2 * Math.PI * CFG.raio / CFG.dentes) * 0.58;
  for (let i = 0; i < CFG.dentes; i++) {{
    const ang = (i / CFG.dentes) * Math.PI * 2;
    const dente = new THREE.Mesh(new THREE.BoxGeometry(CFG.profDente, CFG.espessura * 0.92, larguraDente), acoMat);
    const r = CFG.raio + CFG.profDente / 2 - 0.02;
    dente.position.set(Math.cos(ang) * r, 0, Math.sin(ang) * r);
    dente.rotation.y = -ang;
    grupo.add(dente);
  }}
  grupo.add(new THREE.Mesh(new THREE.CylinderGeometry(CFG.raio * CFG.furo, CFG.raio * CFG.furo, CFG.espessura * 1.05, 48), acoEscuro));
  if (CFG.furosFixacao > 0) {{
    const rf = CFG.raio * CFG.raioFuros;
    for (let i = 0; i < CFG.furosFixacao; i++) {{
      const ang = (i / CFG.furosFixacao) * Math.PI * 2;
      const f = new THREE.Mesh(new THREE.CylinderGeometry(CFG.raio * 0.045, CFG.raio * 0.045, CFG.espessura * 1.02, 20), acoEscuro);
      f.position.set(Math.cos(ang) * rf, 0, Math.sin(ang) * rf);
      grupo.add(f);
    }}
  }}
  grupo.rotation.x = 0.30;
  scene.add(grupo);
  const eixoGiro = new THREE.Vector3(0.22, 1, 0.14).normalize();
  function animar() {{ requestAnimationFrame(animar); grupo.rotateOnWorldAxis(eixoGiro, 0.008); renderer.render(scene, camera); }}
  animar();
  window.addEventListener('resize', function() {{
    const w = container.clientWidth || 300;
    camera.aspect = w / H;
    camera.updateProjectionMatrix();
    renderer.setSize(w, H);
  }});
}})();
</script>
""" + _RODAPE_CENA


def legenda(tipo_peca: str) -> str:
    info = _MODELOS_REAIS.get(tipo_peca)
    if info and _stl_base64(info["arquivo"]) is not None:
        return f"Ilustrativo — {info['nome']} (não entra no cálculo)"
    return "Ilustrativo — representação esquemática (não entra no cálculo)"
