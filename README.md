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

O CSV DataCo não contém falhas de máquinas; por isso, o baseline prevê `Late_delivery_risk` (1 = risco de atraso), alinhado ao problema logístico do grupo. Foi treinada uma Random Forest com atributos disponíveis no pedido (modalidade de envio, região, país, categoria, produto, prazo prometido, quantidade, preço, mês e dia da semana). O split é cronológico e agrupado por `Order Id`: os 80% de pedidos mais antigos ficam no treino e os 20% mais recentes no teste, sem separar itens de um mesmo pedido entre os conjuntos.

### Métricas no conjunto de teste

| Métrica | Resultado | Interpretação |
|---|---:|---|
| Acurácia | 69,25% | Percentual de previsões corretas entre todos os pedidos de teste. |
| Precisão (classe 1) | 83,22% | Entre os pedidos sinalizados com risco, cerca de 83 em cada 100 tinham risco 1 no dataset. |
| Recall (classe 1) | 55,01% | O modelo identificou cerca de 55 em cada 100 pedidos que tinham risco 1. |

Avaliação feita em 22.778 linhas de teste (treino: 157.741 linhas). Para a operação, a precisão indica quanto confiar nos alertas emitidos; o recall indica quantos pedidos de risco o alerta consegue encontrar. O recall moderado significa que muitos casos de risco ainda passam sem alerta. Essas métricas medem associação preditiva no histórico, não causalidade, economia financeira nem garantia individual de atraso.

Para reproduzir o treinamento e salvar o modelo compactado abaixo do limite de 100 MB do GitHub:

```powershell
python src/train_baseline.py
```

O script salva `modelo_atraso.joblib` e `outputs/metricas_baseline.json`. O arquivo do modelo é persistido com compressão zlib sem reduzir componentes ou precisão do modelo.

### API e integração

Com o modelo treinado, inicie a API:

```powershell
uvicorn src.api:app --host 127.0.0.1 --port 8000
```

Verifique `http://127.0.0.1:8000/health` e envie POST JSON para `/predict`. A API responde com `late_delivery_risk` (0 ou 1), `probability` e uma interpretação. Para integrar com o React, a tela deve enviar os campos do schema `OrderFeatures` em `src/api.py`; a confirmação do consumo pela tela depende do projeto React do Sábado 3, que não está neste checkout.

### Roteiro do pitch (7 minutos + 3 minutos de perguntas)

Estrutura conforme o deck de orientação: **Entenda (2 min) → Construa (3 min) → Comprove (2 min)**. Cinco integrantes, cada um fala uma única vez. A lógica do pitch é problema → solução → valor → pedido; em cada etapa, mostrar o dado e a decisão que ele apoia.

| Tempo | Bloco e fala | Roteiro e apoio visual |
|---|---|---|
| 0:00–1:15 | **ENTENDA — Integrante 1: contexto e problema** | Abrir com a pergunta de negócio: “Onde os atrasos se concentram e como isso deve orientar decisões logísticas?” Contextualizar quem é afetado e a consequência para cliente e empresa. Exibir a evidência principal do CSV/dashboard e declarar a meta do projeto: tornar os padrões de atraso e risco mais visíveis para priorizar investigação. |
| 1:15–2:00 | **ENTENDA — Integrante 2: evidência e decisão** | Mostrar os recortes do dataset que sustentam o problema (produto, modalidade, região/rota), explicando população e medida. Distinguir associação de causalidade e mencionar limitações dos dados. Concluir qual decisão gerencial a análise ajuda a avaliar, sem afirmar que o CSV prova uma causa. |
| 2:00–3:30 | **CONSTRUA — Integrante 3: método e arquitetura** | Explicar o dataset e seu preparo; mostrar o caminho reproduzível no repositório (pipeline e Docker, quando aplicável), split temporal agrupado por pedido, baseline Random Forest e métricas. Diagrama do fluxo: CSV → Pandas/preparo → modelo → API → dashboard. Responder “como outra pessoa roda do zero?” com os comandos documentados. |
| 3:30–5:00 | **CONSTRUA — Integrante 4: o que foi criado e demonstração** | Demonstrar o dashboard e uma previsão pela API: dado de entrada, resposta e decisão que um gestor poderia investigar. Dizer com precisão o que foi testado. A API foi testada por HTTP; não apresentar consumo pelo React como concluído sem validação independente. Se a demo não subir em 30 segundos, usar vídeo/capturas de contingência. |
| 5:00–7:00 | **COMPROVE — Integrante 5: resultado, impacto, aprendizado e pedido** | Apresentar honestamente as métricas no teste cronológico: precisão 83,22%, recall 55,01% e acurácia 69,25% (22.778 linhas). Explicar o que mudou com a solução: visibilidade e priorização analítica, sem atribuir redução financeira ainda não medida. Limites: risco histórico não é causalidade nem garantia; recall deixa casos sem alerta. Fechar com aprendizados e pedido à banca: apoio para validar com dados operacionais recentes e medir impacto em um piloto. |

**Perguntas da banca — 3 minutos.** Preparar respostas para: como rodar do zero; o que o gestor faz com o resultado; o que mudariam com mais um mês; onde estimaram errado; e qual é a limitação mais importante. Se a demonstração falhar, usar vídeo ou capturas. O deck também recomenda mostrar dado entrando e decisão saindo.

A divisão acima dá uma fala a cada um dos cinco integrantes. A revisão do mentor e a confirmação de participação precisam ocorrer fora deste checkout.

### Pendências externas ao checkout

A conclusão do EAD de Machine Learning e GenAI, a revisão do deck pelo mentor, a integração efetiva com o projeto React e a confirmação de fala de todos os integrantes precisam ser realizadas/verificadas pelo grupo. Este texto e o modelo ainda não foram commitados.
## API e modelo no Docker para integração com React

A imagem inclui somente a API FastAPI, suas dependências e o modelo treinado. O avaliador pode usar a própria tela React para chamar a API; a imagem não contém a tela demonstrativa local.

```powershell
docker build -t smart-talent-api .
docker run --rm -p 8000:8000 -e "ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173" smart-talent-api
```

API: `http://localhost:8000`; documentação: `http://localhost:8000/docs`; saúde: `http://localhost:8000/health`. Configure `ALLOWED_ORIGINS` com a origem exata onde o frontend React estiver servido (esquema, host e porta). Para produção, informe o domínio real da tela. O React chama `POST http://localhost:8000/predict` enviando o JSON definido no schema `OrderFeatures` de `src/api.py`.

A imagem não inclui os CSVs, pois não são necessários para servir o modelo já treinado. Para retreinar, rode `python src/train_baseline.py` no checkout com os dados.
