# Estimativa de tempo e custo de fabricação — Cinpal

App de apoio ao custeio: estima tempo (e, quando a tarifa existe, custo em R$)
de usinagem/forjaria a partir de peso e dimensional — sem precisar que o
processo já esteja planejado.

## Rodar localmente

```bash
pip install -r requirements.txt
streamlit run app_cotacao.py
```

## Login

O app pede usuário/senha antes de mostrar qualquer coisa. Não fica no
código — vem de "secrets":

- **Local**: crie `.streamlit/secrets.toml` (já no `.gitignore`, nunca vai
  pro GitHub) com:
  ```toml
  [auth]
  usuario = "comercial"
  senha = "comercial"
  ```
- **Streamlit Community Cloud**: no painel do app, `Settings > Secrets`,
  cole o mesmo bloco acima. Precisa configurar lá também — o `secrets.toml`
  local não é enviado com o `git push`.

O login vale só pra aba/sessão do navegador (fecha o navegador, pede de
novo) — é uma camada simples pra não deixar o link solto publicamente,
não um controle de acesso por usuário individual.

## O que este repositório contém (e por quê)

Só o necessário pra rodar o app — os modelos treinados (`.pkl`), o código
da interface, e dois arquivos `.stl` ilustrativos (volante e engrenagem)
usados só para o visor 3D de exemplo por família de peça.

**Não contém**: os dados brutos de orçamento (planilhas históricas de
cotação), scripts de treino/extração, nem as tarifas internas completas —
`config_custos.py` traz só a fórmula e as tarifas já decididas para uso
neste app.

## Sobre o upload de `.stp`

O upload ao vivo (converte o desenho, mede peso/diâmetro e gera o visor
3D real da peça) depende do `cadquery` (kernel CAD), incluído no
`requirements.txt`. Esse pacote traz um binário nativo (OCP/OpenCascade)
que precisa de algumas bibliotecas gráficas do sistema — por isso o
`packages.txt` (lido automaticamente pelo Streamlit Community Cloud antes
do `pip install`) declara `libgl1`, `libglu1-mesa`, `libxrender1`,
`libxext6`, `libsm6`, `libice6` e `libgomp1`. Sem esse arquivo, o
`cadquery` pode instalar mas falhar ao carregar — o app captura isso e
mostra um aviso em vez de quebrar, mas o upload real não funciona.

Se mesmo assim o upload não funcionar em algum ambiente hospedado, as
demais funções (peso/diâmetro digitados, visor 3D ilustrativo por
família, faixa de tempo, custo) continuam funcionando normalmente.

## Estimativa de apoio, não cotação

Os modelos explicam entre ~8% e ~53% da variação de tempo observada,
dependendo da família de peça — ver o bloco de metadados no rodapé do
próprio app (R², MAPE, tamanho da base de treino) para os números
validados de cada modelo.
