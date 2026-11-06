# Grupo 8 — Smart Talent

Análise exploratória do dataset DataCo Smart Supply Chain com Pandas: limpeza reproduzível, tabela-resumo por região e gráficos para apoiar decisões sobre risco e atraso de entrega.

## Rodar localmente

Requer Python 3.11+.

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python src/pipeline.py --input data/DataCoSupplyChainDataset.csv --output outputs
```

O dataset DataCo é disponibilizado em `data/DataCoSupplyChainDataset.csv`. Para manter o Git leve, CSVs ficam fora do versionamento; obtenha o dataset da fonte do projeto e coloque-o nesse caminho. A saída inclui `resumo_por_regiao.csv`, `risco_por_regiao.png` e `atraso_por_status.png`.

## Decisões de limpeza

1. Cabeçalhos são convertidos para minúsculas: facilita acesso consistente às colunas sem depender de capitalização.
2. Métricas numéricas são convertidas com valores inválidos como ausentes, e linhas sem os campos essenciais são removidas: evita que registros incompletos distorçam taxas e médias.
3. Duplicatas exatas são removidas para não contar o mesmo registro duas vezes.
4. Vendas negativas são excluídas por não representarem venda válida para o resumo comercial.
5. Atraso é calculado como dias reais menos dias programados e limitado a zero: entregas adiantadas não contam como atraso.

## Docker

Monte o diretório contendo o CSV em `/data` no container. Execute na raiz:

```bash
docker build -t grupo8-pipeline .
docker run --rm -v "${PWD}/data:/data" -v "${PWD}/outputs:/outputs" grupo8-pipeline --input /data/DataCoSupplyChainDataset.csv --output /outputs
```

No PowerShell, use `-v "${PWD}/data:/data"` e `-v "${PWD}/outputs:/outputs"` igualmente.

## Saída

- `resumo_por_regiao.csv`: volume, vendas, atraso médio e percentual com risco por região.
- `risco_por_regiao.png`: comparação do percentual de risco por região.
- `atraso_por_status.png`: atraso médio por status de entrega.

## Checklist externo da atividade

A conclusão de EADs, instalação/teste de Node.js/npm, atualização do board, publicação da imagem e execução em máquina de outro grupo precisam ser realizados e comprovados pelos integrantes. Anexar também a captura da execução Docker na entrega. Cada integrante deve abrir/revisar PRs conforme solicitado pela atividade.
