# Grupo 8 — Smart Talent

Projeto de análise logística com o dataset DataCo Supply Chain. O trabalho reúne um pipeline exploratório em Pandas e um baseline de aprendizado de máquina que estima o risco histórico de atraso de um pedido. O modelo é exposto por uma API FastAPI.

## Conteúdo do repositório

- `data/`: datasets usados pelo projeto (já versionados no repositório).
- `src/pipeline.py`: análise exploratória, tabelas e gráficos (Remoto 02).
- `src/train_baseline.py`: treino e avaliação temporal do baseline (Remoto 03).
- `src/api.py`: endpoints HTTP `/health` e `/predict`.
- `modelo_atraso.joblib`: modelo treinado, persistido com compressão zlib.
- `outputs/`: tabelas, gráficos e métricas gerados localmente; ignorado pelo Git.

## Requisitos

- Python 3.11 ou superior e pip.
- Para executar a API em container: Docker Desktop ou Docker Engine.

## Instalação e execução local

Na raiz do repositório:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

No Linux/macOS, ative o ambiente com `source .venv/bin/activate`.

Execute a análise exploratória:

```powershell
python src/pipeline.py --input data/DataCoSupplyChainDataset.csv --output outputs
```

Para treinar e reavaliar o baseline, com o CSV disponível em `data/`:

```powershell
python src/train_baseline.py
```

O treino gera/atualiza `modelo_atraso.joblib` e `outputs/metricas_baseline.json`.

## Decisões de limpeza do pipeline analítico

O pipeline documenta e aplica tratamentos para padronizar nomes de colunas, converter campos numéricos, remover registros sem valores essenciais, remover duplicatas exatas e excluir valores de venda negativos. O atraso é calculado como dias reais de envio menos dias programados, com valores negativos limitados a zero. Essas regras mantêm as saídas comparáveis e evitam tratar entregas adiantadas como dias de atraso.

## Saídas da análise exploratória

A execução de `src/pipeline.py` salva em `outputs/` uma tabela-resumo por região e gráficos de risco por região e atraso por status de entrega.

## Baseline de risco de atraso

O dataset não descreve falhas de máquinas. Portanto, o alvo deste projeto é `Late_delivery_risk` (1 = risco de atraso), relacionado ao problema logístico do grupo. O baseline é uma Random Forest com atributos disponíveis no pedido: modalidade de envio, região, país, categoria, produto, prazo prometido, quantidade, preço, mês e dia da semana.

O split é cronológico e agrupado por `Order Id`: os 80% de pedidos mais antigos são usados no treino e os 20% mais recentes no teste. Itens do mesmo pedido não são separados entre treino e teste.

### Métricas registradas

| Métrica | Teste | Significado |
|---|---:|---|
| Acurácia | 69,25% | Proporção de previsões corretas entre as observações de teste. |
| Precisão, classe 1 | 83,22% | Entre as observações previstas como risco, proporção que tinha rótulo de risco no dataset. |
| Recall, classe 1 | 55,01% | Proporção dos casos com rótulo de risco que o modelo identificou. |

A avaliação usou 22.778 linhas de teste e 157.741 de treino. O recall indica que o modelo não identifica todos os casos de risco. As métricas descrevem desempenho preditivo nesse recorte histórico; não demonstram causalidade, economia financeira ou garantia de atraso para um pedido individual.

## API e integração com uma aplicação React

A API recebe JSON com os campos definidos em `OrderFeatures`, valida os tipos e retorna classe de risco, probabilidade estimada e interpretação. A API foi chamada por HTTP; a integração com uma tela React de demonstração local também foi exercitada, retornando HTTP 200 e uma previsão. O projeto React original do Sábado 3 não está neste checkout.

### Executar localmente

```powershell
uvicorn src.api:app --host 127.0.0.1 --port 8000
```

Endpoints: `GET http://127.0.0.1:8000/health`, `POST http://127.0.0.1:8000/predict` e documentação interativa em `http://127.0.0.1:8000/docs`.

### Executar a API e o modelo no Docker

A imagem inclui a API, suas dependências e o modelo. Ela não inclui a tela React de demonstração nem os CSVs, pois não são necessários para servir previsões.

```powershell
docker build -t smart-talent-api .
docker run --rm -p 8000:8000 -e "ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173" smart-talent-api
```

A API ficará em `http://localhost:8000`; documentação em `/docs` e saúde em `/health`. Configure `ALLOWED_ORIGINS` para a origem exata da aplicação React, incluindo protocolo, host e porta. Para outra origem, substitua os exemplos no comando. O avaliador pode executar sua própria tela React e apontá-la para `POST http://localhost:8000/predict`.

Exemplo de chamada em React:

```js
const response = await fetch('http://localhost:8000/predict', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    shipping_mode: 'First Class',
    order_region: 'Western Europe',
    order_country: 'Reino Unido',
    category_name: 'Cleats',
    product_name: "Nike Men's Free 5.0+ Running Shoe",
    scheduled_days: 1,
    quantity: 1,
    product_price: 190,
    order_month: 6,
    order_weekday: 2
  })
});
const prediction = await response.json();
```

## Roteiro do pitch — 7 minutos e 3 minutos de perguntas

Estrutura do deck de orientação: **Entenda (2 min) → Construa (3 min) → Comprove (2 min)**. São cinco falas, uma por integrante, seguindo problema → solução → valor → pedido.

| Tempo | Pessoa e etapa | Conteúdo |
|---|---|---|
| 0:00–1:15 | Integrante 1 — Entenda | Contexto, quem é afetado e pergunta de negócio: onde os atrasos se concentram e como isso pode orientar decisões logísticas? Apresentar a meta do projeto. |
| 1:15–2:00 | Integrante 2 — Entenda | Mostrar evidências do CSV/dashboard por produto, modalidade ou região. Explicar população e medidas, limitações e que associação não prova causa. Relacionar evidência à decisão que merece investigação. |
| 2:00–3:30 | Integrante 3 — Construa | Explicar dados e preparação; mostrar arquitetura CSV → Pandas → split temporal por pedido → Random Forest → API → aplicação React. Demonstrar como instalar e executar conforme este README. |
| 3:30–5:00 | Integrante 4 — Construa | Demonstrar a API com dado de entrada e resposta, e o dashboard do projeto. Explicitar o que foi testado: a API e uma tela React demonstrativa local; não alegar integração com o React original do Sábado 3, que não está disponível. Ter vídeo/capturas de contingência se a demonstração não iniciar rapidamente. |
| 5:00–7:00 | Integrante 5 — Comprove | Apresentar precisão 83,22%, recall 55,01% e acurácia 69,25%; explicar falsos alertas e riscos não encontrados. Mostrar o valor já demonstrado — visibilidade e priorização — sem atribuir economia ainda não medida. Encerrar com limites, aprendizados e pedido de apoio para validar em piloto com dados operacionais recentes. |

Reservar 3 minutos para perguntas. Preparar respostas sobre execução do zero, decisão gerencial apoiada, limitações, estimativas que podem estar erradas e o que seria feito com mais tempo. Mostrar o dado entrando e a decisão saindo; usar vídeo ou capturas se a demonstração falhar.

## Itens de entrega e validações externas

O artefato local do modelo, a API e a documentação foram preparados nesta branch e publicados no PR #4. A chamada da API e o consumo por uma tela React de demonstração foram verificados localmente. A tela React original do Sábado 3 não estava disponível para teste.

A conclusão do EAD de Machine Learning e GenAI e a revisão do deck por mentor dependem dos integrantes/plataforma do curso; não são verificáveis neste repositório. Antes da entrega, o grupo deve confirmar esses itens e a participação dos cinco integrantes na apresentação. A imagem Docker deve ser construída e executada pelo avaliador/grupo no ambiente-alvo; os comandos acima reproduzem o serviço localmente.
