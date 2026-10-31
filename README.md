# Grupo 8 — Smart Talent (DataCo Supply Chain & Access Logs)

Projeto de preparação, padronização e normalização dos datasets de cadeia de suprimentos (**DataCo Smart Supply Chain**) e logs de acesso tokenizados (**Tokenized Access Logs**).

---

## Estrutura do Projeto

```text
Grupo8-Smart-Talent/
├── data/
│   ├── DataCoSupplyChainDataset.csv       # Dataset bruto de pedidos e logística (180.519 linhas x 53 colunas)
│   ├── DescriptionDataCoSupplyChain.csv   # Dicionário de dados oficial das colunas
│   ├── tokenized_access_logs.csv          # Dataset bruto de logs de acesso (469.977 linhas x 8 colunas)
│   └── processed/                         # Datasets finais padronizados e normalizados (1 CSV por base, UTF-8)
├── src/
│   └── script.py                          # Pipeline de limpeza, padronização e normalização in-place
├── requirements.txt                       # Dependências do projeto (codificado em UTF-8)
└── README.md                              # Documentação e instruções de execução
```

---

## Pré-requisitos

- **Python 3.11+** (ambiente configurado com Python 3.13)
- **pip** atualizado

---

## Como Configurar e Rodar o Projeto

### 1. Ativar o Ambiente Virtual (`venv`)

Caso esteja na pasta raiz `Grupo8-Smart-Talent` no **Windows (PowerShell)**:

```powershell
.\venv\Scripts\Activate.ps1
```

Ou via **Prompt de Comando (CMD)**:

```cmd
.\venv\Scripts\activate.bat
```

*(Caso ainda não possua um ambiente virtual criado, crie-o com `python -m venv venv` e ative-o com o comando acima).*

### 2. Instalar as Dependências

Entre no diretório do repositório e instale os pacotes listados no `requirements.txt`:

```powershell
cd Grupo8-Smart-Talent
pip install -r requirements.txt
```

### 3. Executar o Script de Padronização e Normalização

Execute o script principal:

```powershell
python src/script.py
```

---

## Arquivos Gerados

Após a execução de `python src/script.py`, é gerado **1 único CSV final por dataset** em `data/processed/` (em codificação **UTF-8**), já com todas as limpezas, padronizações e normalizações aplicadas diretamente nas colunas:

1. `data/processed/dataco_supply_chain_processed.csv` — Dataset principal padronizado e normalizado (`180.519` linhas × `42` colunas).
2. `data/processed/tokenized_access_logs_processed.csv` — Dataset de logs de acesso sem duplicatas, padronizado e normalizado (`466.728` linhas × `8` colunas).
