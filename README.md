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

## Sobre o upload de `.stp`

O upload ao vivo (converte o desenho, mede peso/diâmetro e gera o visor
3D real da peça) depende do `cadquery` (kernel CAD), incluído no
`requirements.txt`. Se o build da nuvem gratuita não conseguir instalar
essa dependência (é pesada — kernel CAD completo), a interface degrada
sozinha: mostra um aviso educado em vez de quebrar, e as demais funções
(peso/diâmetro digitados, visor 3D ilustrativo por família, faixa de
tempo, custo) continuam funcionando normalmente.

## Estimativa de apoio, não cotação

Os modelos explicam entre ~8% e ~53% da variação de tempo observada,
dependendo da família de peça — ver o bloco de metadados no rodapé do
próprio app (R², MAPE, tamanho da base de treino) para os números
validados de cada modelo.
