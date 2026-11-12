# Grupo 8 — Smart Talent

Projeto de análise exploratória, pré-processamento e modelagem do dataset **DataCo Smart Supply Chain** e **Tokenized Access Logs**, incluindo pipeline analítico reproduzível e conteinerização via Docker (Atividade Remoto 02).

---

## Estrutura do Repositório

```text
Grupo8-Smart-Talent/
├── data/
│   ├── DataCoSupplyChainDataset.csv       # Dataset principal de pedidos e logística (180.519 linhas)
│   ├── DescriptionDataCoSupplyChain.csv   # Dicionário de dados oficial das colunas
│   ├── product_dimensions.csv             # Dimensões e pesos estimados da embalagem de cada produto (118 produtos)
│   ├── tokenized_access_logs.csv          # Dataset de logs de acesso tokenizados (469.977 linhas)
│   └── processed/                         # Datasets limpos e normalizados (gerados por src/script.py)
├── src/
│   ├── pipeline.py                        # Pipeline analítico com geração de resumo e gráficos (Remoto 02)
│   └── script.py                          # Pipeline de padronização, limpeza e normalização dos dados
├── outputs/                               # Saídas analíticas do pipeline (tabelas e gráficos)
├── Dockerfile                             # Configuração da imagem Docker (python:3.11-slim)
├── .dockerignore                          # Arquivos e pastas excluídos da build Docker
├── .gitignore                             # Arquivos e pastas ignorados pelo Git
├── requirements.txt                       # Dependências do projeto
└── README.md                              # Documentação e instruções de execução
```

---

## 1. Execução Local

### Pré-requisitos
- Python 3.11+
- Gerenciador de pacotes `pip`

### Passo a passo

```bash
# 1. Criar e ativar o ambiente virtual
python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

# 2. Instalar as dependências
pip install -r requirements.txt

# 3. Executar o pipeline analítico
python src/pipeline.py --input data/DataCoSupplyChainDataset.csv --output outputs
```

Caso queira executar a padronização e normalização completa dos datasets:
```bash
python src/script.py
```

As dimensões e os pesos estimados das embalagens já estão incluídos no dataset principal.

---

## 2. Execução via Docker (Atividade Remoto 02)

O pipeline foi conteinerizado com imagem base `python:3.11-slim`. Monte os diretórios contendo os dados de entrada e a pasta de saída desejada:

```bash
# Construir a imagem Docker
docker build -t grupo8-pipeline .

# Executar o container montando volumes locais
# Linux / macOS (Bash)
docker run --rm -v "${PWD}/data:/data" -v "${PWD}/outputs:/outputs" grupo8-pipeline --input /data/DataCoSupplyChainDataset.csv --output /outputs

# Windows (PowerShell)
docker run --rm -v "${PWD}/data:/data" -v "${PWD}/outputs:/outputs" grupo8-pipeline --input /data/DataCoSupplyChainDataset.csv --output /outputs
```

---

## 3. Decisões de Limpeza no Pipeline Analítico

1. **Padronização de cabeçalhos:** Nomes de colunas convertidos para minúsculas e sem espaços nas pontas (`str.strip().str.lower()`), garantindo acesso uniforme.
2. **Conversão de tipos e tratamento de nulos:** Colunas essenciais (`sales`, `late_delivery_risk`, dias de envio) convertidas numericamente; registros incompletos são descartados para não distorcer médias.
3. **Desduplicação:** Remoção de registros 100% duplicados.
4. **Filtro de vendas:** Exclusão de vendas negativas (`sales >= 0`) para refletir apenas faturamento comercial válido.
5. **Cálculo de atraso:** `atraso_dias` definido como a diferença entre dias reais e programados (`Days for shipping (real) - Days for shipment (scheduled)`), com piso em zero (`clip(lower=0)`), de modo que entregas adiantadas não contem como atraso.

---

## 4. Saídas Geradas pelo Pipeline

Ao rodar `src/pipeline.py` (localmente ou no Docker), os seguintes artefatos são salvos no diretório `--output` (padrão `outputs/`):

- `resumo_por_regiao.csv`: Tabela agregada com volume de pedidos, faturamento de vendas, atraso médio em dias e percentual de risco de atraso por região geográfica (`order region`).
- `risco_por_regiao.png`: Gráfico de barras comparando o percentual de pedidos com risco de entrega por região.
- `atraso_por_status.png`: Gráfico de barras ilustrando o atraso médio em dias de acordo com o status da entrega (`delivery status`).

---

## 5. Checklist Externo da Atividade

A conclusão de EADs, instalação/teste de Node.js/npm, atualização do board, publicação da imagem e execução em máquina de outro grupo precisam ser realizados e comprovados pelos integrantes. Anexar também a captura da execução Docker na entrega. Cada integrante deve abrir/revisar PRs conforme solicitado pela atividade.


## Baseline de risco de atraso (Remoto 03)

O CSV DataCo não contém falhas de máquinas; este projeto usa como alvo `Late_delivery_risk` (1 = risco de atraso), alinhado à análise logística do grupo. O treino usa split temporal: 80% mais antigos para treino e 20% mais recentes para teste, evitando misturar períodos. Não use campos conhecidos somente após a entrega.

Instale dependências com `pip install -r requirements.txt` e rode `python src/train_baseline.py`. O script salva `modelo_atraso.joblib` e `outputs/metricas_baseline.json`. Precisão mede, entre os pedidos previstos como risco, a fração que realmente tem risco; recall mede a fração dos pedidos com risco que o modelo identifica. Os valores devem ser preenchidos a partir do JSON após executar o treino; não foram inventados.

API: após treinar, rode `uvicorn src.api:app --reload`. Consulte `/health` e envie POST a `/predict` com as features documentadas no schema. A tela React do Sábado 3 e o ambiente local precisam ser conectados/testados pelo grupo.

### Roteiro preliminar (5 minutos)

- **0:00–0:30 — Problema:** atrasos logísticos afetam experiência e rentabilidade; pergunta: como identificar pedidos com risco antes de concluir a promessa operacional?
- **0:30–1:15 — Arquitetura:** CSV DataCo → preparação e split temporal → Random Forest baseline → API FastAPI → dashboard.
- **1:15–3:15 — Demonstração:** mostrar dashboard por modalidade/produto/região, previsão de risco via API e resposta consumível pela tela.
- **3:15–4:15 — Resultado e limites:** apresentar precisão e recall do JSON de teste; explicar falso positivo/falso negativo. É risco histórico, não causalidade nem garantia individual.
- **4:15–5:00 — Processo/aprendizado:** ciclo dados–modelo–API–interface, divisão de tarefas e próximos passos: validar com operação real e monitorar drift.

Cada integrante deve falar. Rascunho sujeito à revisão do mentor; EAD, integração React e execução no ambiente da equipe precisam ser confirmados pelo grupo.
