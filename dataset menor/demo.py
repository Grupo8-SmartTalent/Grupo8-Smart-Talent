"""
Análise do dataset de logística (smart_logistics_dataset.csv).

O script faz duas coisas:
  1. Verifica se os dados são confiáveis (tamanho, tipos, faltantes,
     duplicados e valores impossíveis).
  2. Mostra quanto as entregas atrasam e em que situações.

Toda a saída é em português, com uma breve explicação de cada etapa.
Como rodar (a partir da pasta do projeto, com o venv ativado):
    python src/analise.py
"""

from pathlib import Path

import pandas as pd

# ----------------------------------------------------------------------
# Configuração
# ----------------------------------------------------------------------

# Caminho do CSV calculado a partir da localização deste arquivo.
# Assim o script funciona de qualquer pasta em que o terminal estiver.
RAIZ = Path(__file__).resolve().parents[1]
ARQUIVO = RAIZ / "data" / "smart_logistics_dataset.csv"

# Nome de cada coluna em português e o que ela significa.
COLUNAS = {
    "Timestamp": ("Data e hora", "momento em que o registro foi feito"),
    "Asset_ID": ("Caminhão", "identificação do veículo"),
    "Latitude": ("Latitude", "posição norte-sul do caminhão"),
    "Longitude": ("Longitude", "posição leste-oeste do caminhão"),
    "Inventory_Level": ("Nível de estoque", "quantidade de carga no momento"),
    "Shipment_Status": ("Situação da entrega", "atrasada, entregue ou em trânsito"),
    "Temperature": ("Temperatura", "temperatura no momento do registro"),
    "Humidity": ("Umidade (%)", "umidade do ar no momento do registro"),
    "Traffic_Status": ("Trânsito", "condição do trânsito: livre, desvio ou pesado"),
    "Waiting_Time": ("Tempo de espera", "quanto o caminhão ficou esperando"),
    "User_Transaction_Amount": ("Valor da compra", "quanto o cliente gastou"),
    "User_Purchase_Frequency": ("Frequência de compra", "quantas vezes o cliente compra"),
    "Logistics_Delay_Reason": ("Motivo do atraso", "causa registrada para o atraso"),
    "Asset_Utilization": ("Uso do caminhão (%)", "quanto da capacidade está sendo usada"),
    "Demand_Forecast": ("Previsão de demanda", "demanda esperada para o período"),
    "Logistics_Delay": ("Atrasou?", "1 = houve atraso, 0 = não houve"),
}

# Tradução dos valores de texto que aparecem nas colunas.
VALORES = {
    "Shipment_Status": {
        "Delayed": "Atrasada",
        "Delivered": "Entregue",
        "In Transit": "Em trânsito",
    },
    "Traffic_Status": {
        "Clear": "Livre",
        "Detour": "Desvio",
        "Heavy": "Pesado",
    },
    "Logistics_Delay_Reason": {
        "None": "Sem motivo",
        "Weather": "Clima",
        "Traffic": "Trânsito",
        "Mechanical Failure": "Falha mecânica",
    },
}

# Tradução dos tipos de dado do pandas.
TIPOS = {
    "int64": "número inteiro",
    "float64": "número decimal",
    "object": "texto",
    "str": "texto",
    "string": "texto",
}

# ----------------------------------------------------------------------
# Funções de apoio
# ----------------------------------------------------------------------


def numero(valor, casas=0):
    """Formata um número no padrão brasileiro: 1.000 e 56,6."""
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def porcentagem(valor):
    """Formata uma proporção (0 a 1) como porcentagem: 0.566 -> 56,6%."""
    return numero(valor * 100, 1) + "%"


def tipo_em_portugues(tipo):
    """Traduz o tipo de dado do pandas."""
    nome = str(tipo)
    if nome.startswith("datetime"):
        return "data e hora"
    return TIPOS.get(nome, nome)


def titulo(numero_etapa, texto, explicacao):
    """Imprime o título de uma etapa e uma linha explicando o que ela faz."""
    print()
    print("=" * 70)
    print(f"{numero_etapa}. {texto.upper()}")
    print(f"   O que é: {explicacao}")
    print("=" * 70)


def tabela_de_taxas(df, coluna):
    """Imprime, para cada grupo da coluna, quantas entregas e quantos % atrasaram."""
    grupos = df.groupby(coluna)["Atrasou?"].agg(["count", "mean"])
    grupos = grupos.sort_values("mean", ascending=False)
    for nome, linha in grupos.iterrows():
        print(f"   {nome:<16} {porcentagem(linha['mean']):>7} de atraso"
              f"  ({numero(linha['count'])} entregas)")
    return grupos


# ----------------------------------------------------------------------
# Leitura dos dados
# ----------------------------------------------------------------------

# keep_default_na=False: sem isso, o pandas leria o texto "None"
# (sem motivo de atraso) como valor faltando.
df = pd.read_csv(
    ARQUIVO,
    keep_default_na=False,
    na_values=[""],
    parse_dates=["Timestamp"],
)

# Traduz os valores de texto e depois os nomes das colunas.
for coluna, traducao in VALORES.items():
    df[coluna] = df[coluna].replace(traducao)
df["Asset_ID"] = df["Asset_ID"].str.replace("Truck_", "Caminhão ", regex=False)

tipos_originais = df.dtypes
df = df.rename(columns={original: pt for original, (pt, _) in COLUNAS.items()})

print("ANÁLISE DO DATASET DE LOGÍSTICA")
print(f"Arquivo: {ARQUIVO.name}")

# ----------------------------------------------------------------------
# 1. Tamanho
# ----------------------------------------------------------------------
titulo(1, "Tamanho do dataset",
       "quantas linhas (entregas) e colunas (informações) existem.")
print(f"   Linhas (entregas):       {numero(df.shape[0])}")
print(f"   Colunas (informações):   {numero(df.shape[1])}")
inicio = df["Data e hora"].min().strftime("%d/%m/%Y")
fim = df["Data e hora"].max().strftime("%d/%m/%Y")
print(f"   Período coberto:         {inicio} a {fim}")
print(f"   Caminhões diferentes:    {df['Caminhão'].nunique()}")

# ----------------------------------------------------------------------
# 2. Colunas e tipos
# ----------------------------------------------------------------------
titulo(2, "Colunas e tipos de dado",
       "o significado de cada coluna e o tipo de valor que ela guarda.")
print(f"   {'Coluna':<22} {'Tipo':<16} Descrição")
print(f"   {'-' * 22} {'-' * 16} {'-' * 28}")
for original, (pt, descricao) in COLUNAS.items():
    tipo = tipo_em_portugues(tipos_originais[original])
    print(f"   {pt:<22} {tipo:<16} {descricao}")

# ----------------------------------------------------------------------
# 3. Valores faltando
# ----------------------------------------------------------------------
titulo(3, "Valores faltando",
       "células vazias. Muitas delas tornam a análise menos confiável.")
faltando = df.isna().sum()
total_faltando = int(faltando.sum())
print(f"   Total de células vazias: {numero(total_faltando)}")
if total_faltando:
    for coluna, qtd in faltando[faltando > 0].items():
        print(f"   - {coluna}: {numero(qtd)}")
else:
    print("   Resultado: nenhuma célula vazia. Os dados estão completos.")

# ----------------------------------------------------------------------
# 4. Linhas duplicadas
# ----------------------------------------------------------------------
titulo(4, "Linhas duplicadas",
       "entregas registradas mais de uma vez, que distorcem as contagens.")
duplicadas = int(df.duplicated().sum())
print(f"   Linhas repetidas: {numero(duplicadas)}")
if duplicadas == 0:
    print("   Resultado: nenhuma repetição.")

# ----------------------------------------------------------------------
# 5. Valores impossíveis
# ----------------------------------------------------------------------
titulo(5, "Valores impossíveis",
       "números que não podem existir na prática, como estoque negativo.")

# Estas colunas não podem ter zero nem valores negativos.
positivas = ["Nível de estoque", "Tempo de espera", "Valor da compra",
             "Frequência de compra", "Previsão de demanda"]
print("   Valores menores ou iguais a zero (não deveriam existir):")
total_invalidos = 0
for coluna in positivas:
    qtd = int((df[coluna] <= 0).sum())
    total_invalidos += qtd
    print(f"   - {coluna:<22} {numero(qtd)}")

# Estas colunas têm limites físicos.
print("\n   Valores fora do limite possível:")
limites = [
    ("Latitude", -90, 90),
    ("Longitude", -180, 180),
    ("Umidade (%)", 0, 100),
    ("Uso do caminhão (%)", 0, 100),
]
for coluna, minimo, maximo in limites:
    qtd = int((~df[coluna].between(minimo, maximo)).sum())
    total_invalidos += qtd
    print(f"   - {coluna:<22} {numero(qtd)}  (limite: {minimo} a {maximo})")

qtd = int((~df["Atrasou?"].isin([0, 1])).sum())
total_invalidos += qtd
print(f"   - {'Atrasou?':<22} {numero(qtd)}  (só pode ser 0 ou 1)")

if total_invalidos == 0:
    print("\n   Resultado: nenhum valor impossível encontrado.")

# ----------------------------------------------------------------------
# 6. Categorias
# ----------------------------------------------------------------------
titulo(6, "Distribuição das categorias",
       "quantas entregas existem em cada grupo das colunas de texto.")
for coluna in ["Situação da entrega", "Trânsito", "Motivo do atraso"]:
    print(f"\n   {coluna}:")
    contagem = df[coluna].value_counts()
    for nome, qtd in contagem.items():
        print(f"   - {nome:<16} {numero(qtd):>5} entregas"
              f"  ({porcentagem(qtd / len(df))})")

# ----------------------------------------------------------------------
# 7. Taxa geral de atraso
# ----------------------------------------------------------------------
titulo(7, "Taxa geral de atraso",
       "a porcentagem de entregas que atrasaram no total.")
taxa_geral = df["Atrasou?"].mean()
atrasos = int(df["Atrasou?"].sum())
print(f"   {numero(atrasos)} de {numero(len(df))} entregas atrasaram:"
      f" {porcentagem(taxa_geral)}")
print("   Como 'Atrasou?' vale 1 ou 0, a média da coluna é a taxa de atraso.")

# ----------------------------------------------------------------------
# 8. Atraso por trânsito
# ----------------------------------------------------------------------
titulo(8, "Atraso por condição do trânsito",
       "se o tipo de trânsito muda a chance de a entrega atrasar.")
por_transito = tabela_de_taxas(df, "Trânsito")
pior = por_transito.index[0]
print(f"\n   Leitura: com trânsito '{pior}', a taxa de atraso é"
      f" {porcentagem(por_transito['mean'].iloc[0])}, contra"
      f" {porcentagem(por_transito['mean'].iloc[-1])} no melhor caso.")

# ----------------------------------------------------------------------
# 9. Atraso por motivo registrado
# ----------------------------------------------------------------------
titulo(9, "Atraso por motivo registrado",
       "se o motivo anotado ajuda a explicar os atrasos.")
por_motivo = tabela_de_taxas(df, "Motivo do atraso")
diferenca = por_motivo["mean"].max() - por_motivo["mean"].min()
print(f"\n   Leitura: a diferença entre o maior e o menor motivo é de apenas"
      f" {numero(diferenca * 100, 1)} pontos percentuais.")
print("   Ou seja, o motivo registrado praticamente não explica os atrasos.")

# ----------------------------------------------------------------------
# Conclusão
# ----------------------------------------------------------------------
titulo(10, "Conclusão", "o resumo do que a análise mostrou.")
problemas = total_faltando + duplicadas + total_invalidos
if problemas == 0:
    print("   - Os dados estão limpos: sem faltantes, duplicados ou valores impossíveis.")
else:
    print(f"   - Foram encontrados {numero(problemas)} problemas nos dados (ver acima).")
print(f"   - {porcentagem(taxa_geral)} das entregas atrasaram.")
print(f"   - O fator que mais pesa é o trânsito '{pior}'"
      f" ({porcentagem(por_transito['mean'].iloc[0])} de atraso).")
print("   - O motivo registrado não explica os atrasos.")
