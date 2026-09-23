# Estimativa de tempo e custo de fabricação — Cinpal

App de apoio ao custeio: estima tempo (e, quando a tarifa existe, custo em R$)
de usinagem/forjaria a partir de peso e dimensional — sem precisar que o
processo já esteja planejado.

## Rodar localmente

```bash
pip install -r requirements.txt
streamlit run app_cotacao.py
```

## O que este repositório contém (e por quê)

Só o necessário pra rodar o app — os modelos treinados (`.pkl`), o código
da interface, e dois arquivos `.stl` ilustrativos (volante e engrenagem)
usados só para o visor 3D de exemplo por família de peça.

**Não contém**: os dados brutos de orçamento (planilhas históricas de
cotação), scripts de treino/extração, nem as tarifas internas completas —
`config_custos.py` traz só a fórmula e as tarifas já decididas para uso
neste app.

## Limitação nesta versão hospedada

O upload de `.stp` real (conversão ao vivo pra medir peso/diâmetro/3D da
peça) depende do pacote `cadquery` (kernel CAD), que não está incluído
neste deploy — é uma dependência pesada demais para build em nuvem
gratuita. A interface avisa isso quando alguém tenta subir um arquivo; as
demais funções (estimativa a partir de peso/diâmetro digitados, visor 3D
ilustrativo, faixa de tempo, custo) funcionam normalmente.

## Estimativa de apoio, não cotação

Os modelos explicam entre ~8% e ~53% da variação de tempo observada,
dependendo da família de peça — ver o bloco de metadados no rodapé do
próprio app (R², MAPE, tamanho da base de treino) para os números
validados de cada modelo.
