"""
analise.py - Auditoria e análise do dataset de logística (Smart Logistics)
===========================================================================

O QUE ESTE SCRIPT FAZ
---------------------
1. Carrega o CSV com segurança (confere se o arquivo existe, se é mesmo um
   CSV e não uma página HTML, detecta separador e codificação).
2. Audita a qualidade dos dados em 4 níveis:
     - formato    : nulos, vazios, duplicados, tipos, datas, padrões
     - conteúdo   : categorias, faixas, outliers, distribuições
     - lógica     : coerência entre colunas, vazamento de alvo, regras fixas
     - integridade: chave da entrega, trajetos dos caminhões, realismo
3. Analisa os atrasos (geral, por trânsito, motivo, caminhão e mês), com
   teste estatístico para separar diferenças reais de acaso.
4. Avalia riscos para BI e para Machine Learning.
5. Dá notas de 0 a 10 para seis dimensões de qualidade.
6. Gera arquivos na pasta outputs/ (relatório, dataset tratado, registros
   problemáticos, dicionário de dados e qualidade por coluna).

Toda a saída é em português, com a explicação de cada etapa.

RELAÇÃO COM A AUDITORIA
-----------------------
Cada verificação tem um código (E1 a E10) igual ao do relatório de auditoria
"Auditoria de Qualidade de Dados: Smart Logistics". Assim, quem lê o código
sabe qual problema da auditoria cada trecho resolve.

COMO RODAR (a partir de qualquer pasta, com o venv ativado)
-----------------------------------------------------------
    python src/analise.py
    python src/analise.py --arquivo outro.csv
    python src/analise.py --sem-arquivos          (só mostra no terminal)
    python src/analise.py --falhar-em-critico     (código de saída 1 se houver
                                                   problema crítico)

DEPENDÊNCIAS: apenas pandas e numpy (já estão no requirements.txt).
Os testes estatísticos foram implementados aqui mesmo, sem SciPy, para não
exigir instalar mais nada.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

# =============================================================================
# 1. CONFIGURAÇÃO
# =============================================================================
# Todas as regras ficam reunidas aqui, no topo do arquivo.
# Motivo: na versão anterior, as regras estavam espalhadas pelo código, e para
# mudar um limite era preciso caçar a linha certa (problema de manutenção).

# O CSV de entrada fica junto deste script; assim, o padrão funciona de
# qualquer diretório de onde o script seja executado.
RAIZ = Path(__file__).resolve().parents[1]
ARQUIVO_PADRAO = Path(__file__).resolve().parent / "smart_logistics_dataset.csv"
PASTA_SAIDA = RAIZ / "outputs"

# Arquivos maiores que isso geram um aviso de desempenho.
LIMITE_TAMANHO_MB = 200

# Textos que costumam representar "sem valor" em bases de dados.
# Motivo (E4): o pandas transforma alguns deles em nulo automaticamente,
# e quem analisa acha que há dados faltando quando não há.
TEXTOS_PSEUDO_NULOS = {"na", "n/a", "nan", "null", "none", "-", "?", "--", "sem dados"}

# Velocidade máxima plausível de um caminhão, em km/h.
# Usada para detectar trajetos impossíveis (E5).
VELOCIDADE_MAXIMA_KMH = 120

# Latitude a partir da qual a região é polar (círculos polares).
# Usada para detectar localizações improváveis para caminhões (E6).
LATITUDE_POLAR = 66.5
TEMPERATURA_IMPROVAVEL_NOS_POLOS = 15.0

# Tamanho mínimo de um grupo para que uma taxa de 0% ou 100% seja tratada como
# regra fixa, e não como acaso de um grupo pequeno (E2, E3).
GRUPO_MINIMO_REGRA_FIXA = 30

# Nível de significância dos testes estatísticos.
# p-valor abaixo disso = diferença provavelmente real; acima = pode ser acaso.
NIVEL_SIGNIFICANCIA = 0.05

# Correlação mínima (em módulo) para considerar que duas colunas se relacionam.
CORRELACAO_RELEVANTE = 0.10

# Curtose de uma distribuição uniforme é -1,2. Valores perto disso, junto com
# assimetria perto de zero, indicam números gerados aleatoriamente (E7).
CURTOSE_UNIFORME = -1.2
TOLERANCIA_CURTOSE = 0.20
TOLERANCIA_ASSIMETRIA = 0.20

# Campos que todo registro de entrega deveria ter (E8).
# Cada item tem nomes alternativos que, se existirem, contam como presentes.
CAMPOS_ESSENCIAIS = {
    "ID da entrega": ["Shipment_ID", "Delivery_ID", "Order_ID"],
    "Origem": ["Origin", "Origem", "Source"],
    "Destino": ["Destination", "Destino"],
    "Prazo prometido": ["Promised_Date", "Due_Date", "Deadline", "Prazo"],
    "Data real de entrega": ["Delivery_Date", "Delivered_At", "Data_Entrega"],
}

# Pares de colunas que, em dados reais, deveriam ter alguma relação.
# Se a correlação for próxima de zero, isso é um sinal de dado suspeito (E7).
RELACOES_ESPERADAS = [
    ("Inventory_Level", "Asset_Utilization", "mais carga deveria significar mais uso do caminhão"),
    ("Inventory_Level", "Demand_Forecast", "o estoque deveria acompanhar a demanda prevista"),
    ("Temperature", "Latitude", "a temperatura deveria variar com a distância do equador"),
]

# Esquema da base: o que cada coluna significa, seu tipo, unidade e limites.
# Motivo (E9): a base original não documenta unidades nem significados.
# Este dicionário serve de documentação e de regra de validação ao mesmo tempo.
#   tipo        : data, categoria, inteiro, decimal ou binario
#   unidade     : None quando o arquivo não permite saber a unidade
#   min / max   : limites físicos (fora deles, o valor é impossível)
#   positivo    : True quando zero ou negativo não faz sentido
#   valores     : categorias permitidas
#   pos_evento  : True quando a coluna só é conhecida depois do resultado
#                 (risco de vazamento de alvo, E2)
#   grupo       : assunto da coluna (caminhão, ambiente, operação, cliente)
ESQUEMA = {
    "Timestamp": dict(
        nome="Data e hora", tipo="data", grupo="identificação",
        descricao="momento do registro", unidade="data/hora sem fuso",
        formato=r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"),
    "Asset_ID": dict(
        nome="Caminhão", tipo="categoria", grupo="identificação",
        descricao="identificação do veículo", unidade=None, formato=r"Truck_\d+"),
    "Latitude": dict(
        nome="Latitude", tipo="decimal", grupo="ambiente",
        descricao="posição norte-sul", unidade="graus", min=-90, max=90),
    "Longitude": dict(
        nome="Longitude", tipo="decimal", grupo="ambiente",
        descricao="posição leste-oeste", unidade="graus", min=-180, max=180),
    "Inventory_Level": dict(
        nome="Nível de estoque", tipo="inteiro", grupo="operação",
        descricao="quantidade de carga no momento", unidade=None, positivo=True),
    "Shipment_Status": dict(
        nome="Situação da entrega", tipo="categoria", grupo="operação",
        descricao="atrasada, entregue ou em trânsito", unidade=None,
        valores={"Delayed", "Delivered", "In Transit"}, pos_evento=True),
    "Temperature": dict(
        nome="Temperatura", tipo="decimal", grupo="ambiente",
        descricao="temperatura (provavelmente °C)", unidade=None, min=-60, max=60),
    "Humidity": dict(
        nome="Umidade (%)", tipo="decimal", grupo="ambiente",
        descricao="umidade do ar", unidade="%", min=0, max=100),
    "Traffic_Status": dict(
        nome="Trânsito", tipo="categoria", grupo="ambiente",
        descricao="condição do trânsito", unidade=None,
        valores={"Clear", "Detour", "Heavy"}),
    "Waiting_Time": dict(
        nome="Tempo de espera", tipo="inteiro", grupo="operação",
        descricao="quanto o caminhão ficou esperando", unidade=None, positivo=True),
    "User_Transaction_Amount": dict(
        nome="Valor da compra", tipo="inteiro", grupo="cliente",
        descricao="quanto o cliente gastou", unidade=None, positivo=True),
    "User_Purchase_Frequency": dict(
        nome="Frequência de compra", tipo="inteiro", grupo="cliente",
        descricao="quantas vezes o cliente compra", unidade=None, positivo=True),
    "Logistics_Delay_Reason": dict(
        nome="Motivo do atraso", tipo="categoria", grupo="operação",
        descricao="causa registrada para o atraso", unidade=None,
        valores={"None", "Weather", "Traffic", "Mechanical Failure"}),
    "Asset_Utilization": dict(
        nome="Uso do caminhão (%)", tipo="decimal", grupo="operação",
        descricao="parte da capacidade em uso", unidade="%", min=0, max=100),
    "Demand_Forecast": dict(
        nome="Previsão de demanda", tipo="inteiro", grupo="operação",
        descricao="demanda esperada", unidade=None, positivo=True),
    "Logistics_Delay": dict(
        nome="Atrasou?", tipo="binario", grupo="alvo",
        descricao="1 = houve atraso, 0 = não houve", unidade=None, valores={0, 1}),
}

ALVO = "Logistics_Delay"

# Traduções usadas só na exibição. A base nunca é alterada por elas.
TRADUCOES = {
    "Shipment_Status": {"Delayed": "Atrasada", "Delivered": "Entregue", "In Transit": "Em trânsito"},
    "Traffic_Status": {"Clear": "Livre", "Detour": "Desvio", "Heavy": "Pesado"},
    "Logistics_Delay_Reason": {"None": "Sem motivo", "Weather": "Clima", "Traffic": "Trânsito",
                               "Mechanical Failure": "Falha mecânica"},
}

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

# Ordem e símbolo dos níveis de gravidade.
GRAVIDADES = {"CRÍTICO": 0, "ALTO": 1, "MÉDIO": 2, "BAIXO": 3, "INFO": 4}


# =============================================================================
# 2. ESTRUTURAS DE APOIO
# =============================================================================

@dataclass
class Alerta:
    """
    Um problema encontrado na auditoria.

    Objetivo: guardar, para cada problema, as cinco informações que a auditoria
    exige (onde, como foi identificado, por que é problema, impacto e correção).
    Problema evitado: na versão anterior, os resultados eram só números soltos
    no terminal, sem explicação nem gravidade, e ninguém era alertado.
    """
    gravidade: str
    codigo: str
    titulo: str
    onde: str
    causa: str
    impacto: str
    correcao: str
    areas: tuple = ()          # BI, ML, Relatórios, Geografia...
    registros: int = 0         # quantos registros são afetados


@dataclass
class Relatorio:
    """
    Junta tudo o que é exibido, para mostrar no terminal e salvar em arquivo.

    Problema evitado: antes, o resultado só existia no terminal e se perdia
    ao fechar a janela.
    """
    linhas: list = field(default_factory=list)
    alertas: list = field(default_factory=list)

    def escrever(self, texto: str = "") -> None:
        print(texto)
        self.linhas.append(texto)

    def titulo(self, numero, texto: str, explicacao: str) -> None:
        self.escrever()
        self.escrever("=" * 78)
        self.escrever(f"{numero}. {texto.upper()}")
        self.escrever(f"   O que é: {explicacao}")
        self.escrever("=" * 78)

    def ok(self, texto: str) -> None:
        self.escrever(f"   [OK] {texto}")

    def aviso(self, texto: str) -> None:
        self.escrever(f"   [!]  {texto}")

    def alertar(self, alerta: Alerta) -> None:
        """Registra o alerta e mostra uma linha curta no ponto onde surgiu."""
        self.alertas.append(alerta)
        self.escrever(f"   [{alerta.gravidade}] {alerta.codigo}: {alerta.titulo}")

    def tabela(self, cabecalho: list, linhas: list, larguras: list) -> None:
        """Imprime uma tabela de texto alinhada."""
        def formatar(valores):
            partes = []
            for valor, largura in zip(valores, larguras):
                texto = str(valor)
                partes.append(texto[:largura].ljust(largura) if largura > 0
                              else texto.rjust(-largura))
            return "   " + " ".join(partes)
        self.escrever(formatar(cabecalho))
        self.escrever("   " + " ".join("-" * abs(l) for l in larguras))
        for linha in linhas:
            self.escrever(formatar(linha))

    def salvar(self, caminho: Path) -> None:
        caminho.write_text("\n".join(self.linhas) + "\n", encoding="utf-8")


# =============================================================================
# 3. FORMATAÇÃO
# =============================================================================

def numero(valor, casas: int = 0) -> str:
    """Formata no padrão brasileiro: 1.000 e 56,6."""
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return "-"
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def pct(proporcao: float, casas: int = 1) -> str:
    """Formata uma proporção (0 a 1) como porcentagem: 0.566 -> 56,6%."""
    return numero(proporcao * 100, casas) + "%"


def p_valor(p: float) -> str:
    """Formata um p-valor e diz em palavras o que ele significa."""
    texto = "p < 0,001" if p < 0.001 else f"p = {numero(p, 3)}"
    leitura = "diferença provavelmente real" if p < NIVEL_SIGNIFICANCIA else "pode ser acaso"
    return f"{texto} ({leitura})"


def nome_pt(coluna: str) -> str:
    return ESQUEMA.get(coluna, {}).get("nome", coluna)


def traduzir(coluna: str, valor) -> str:
    return TRADUCOES.get(coluna, {}).get(valor, str(valor))


# =============================================================================
# 4. ESTATÍSTICA (sem SciPy)
# =============================================================================
# Motivo: a versão anterior só comparava médias "a olho", sem testar se as
# diferenças eram reais. A auditoria mostrou que diferenças por caminhão e por
# mês pareciam grandes, mas eram acaso. Os testes abaixo resolvem isso.

def _gama_regularizada_superior(a: float, x: float) -> float:
    """
    Calcula Q(a, x), usada para obter o p-valor do teste qui-quadrado.
    Usa série para x pequeno e fração contínua para x grande (métodos clássicos
    de cálculo numérico), com precisão suficiente para decisões estatísticas.
    """
    if x <= 0:
        return 1.0
    log_fator = -x + a * math.log(x) - math.lgamma(a)
    if x < a + 1:
        termo = soma = 1.0 / a
        n = a
        for _ in range(500):
            n += 1
            termo *= x / n
            soma += termo
            if abs(termo) < abs(soma) * 1e-12:
                break
        return max(0.0, 1.0 - soma * math.exp(log_fator))
    minimo = 1e-300
    b = x + 1 - a
    c = 1 / minimo
    d = 1 / b
    h = d
    for i in range(1, 500):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = minimo if abs(d) < minimo else d
        c = b + an / c
        c = minimo if abs(c) < minimo else c
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-12:
            break
    return min(1.0, math.exp(log_fator) * h)


def qui_quadrado(tabela: pd.DataFrame) -> float:
    """
    Teste qui-quadrado de independência. Devolve o p-valor.

    Pergunta que responde: "a taxa de atraso muda de verdade entre os grupos,
    ou a diferença observada pode ser acaso?"
    """
    observado = tabela.to_numpy(dtype=float)
    if observado.shape[0] < 2 or observado.shape[1] < 2:
        return 1.0
    esperado = observado.sum(axis=1, keepdims=True) * observado.sum(axis=0, keepdims=True) / observado.sum()
    with np.errstate(divide="ignore", invalid="ignore"):
        estatistica = np.nansum((observado - esperado) ** 2 / esperado)
    graus = (observado.shape[0] - 1) * (observado.shape[1] - 1)
    return _gama_regularizada_superior(graus / 2, estatistica / 2)


def ks_uniforme(serie: pd.Series) -> float:
    """
    Teste de Kolmogorov-Smirnov contra a distribuição uniforme. Devolve o p-valor.

    Um p-valor alto significa que os dados são compatíveis com números sorteados
    por igual entre o mínimo e o máximo, um sinal de dado gerado (E7).
    Só faz sentido para colunas com muitos valores distintos.
    """
    valores = np.sort(serie.dropna().to_numpy(dtype=float))
    n = len(valores)
    if n < 20 or valores.max() == valores.min():
        return float("nan")
    u = (valores - valores.min()) / (valores.max() - valores.min())
    acumulada = np.arange(1, n + 1) / n
    d = max(np.max(acumulada - u), np.max(u - (acumulada - 1 / n)))
    raiz = math.sqrt(n)
    lam = (raiz + 0.12 + 0.11 / raiz) * d
    p = 2 * sum((-1) ** (j - 1) * math.exp(-2 * j * j * lam * lam) for j in range(1, 101))
    return float(min(1.0, max(0.0, p)))


def haversine_km(lat1, lon1, lat2, lon2):
    """Distância em km entre dois pontos da Terra (fórmula de Haversine)."""
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))


# =============================================================================
# 5. CARREGAMENTO SEGURO
# =============================================================================

def detectar_formato(caminho: Path) -> tuple:
    """
    Descobre a codificação e o separador do arquivo antes de lê-lo.

    Problemas evitados:
    - Arquivo inexistente: mensagem clara em vez de um erro técnico longo.
    - Página HTML salva como .csv (aconteceu com um download do GitHub): a
      versão anterior leria a página como uma tabela de 1 coluna sem avisar.
    - CSV do Excel brasileiro, que usa ";" e acentos em latin-1.
    """
    if not caminho.exists():
        sys.exit(f"ERRO: arquivo não encontrado: {caminho}\n"
                 f"Confira se o CSV está em {caminho.parent} com esse nome exato "
                 f"(maiúsculas e minúsculas fazem diferença no Linux).")
    if caminho.stat().st_size == 0:
        sys.exit(f"ERRO: o arquivo {caminho.name} está vazio.")

    inicio = caminho.read_bytes()[:4096]
    if inicio.lstrip().lower().startswith((b"<!doctype", b"<html")):
        sys.exit(f"ERRO: {caminho.name} é uma página HTML, não um CSV.\n"
                 f"Provavelmente foi baixado pelo link errado. Baixe pelo botão "
                 f"'Raw' ou 'Download' do GitHub.")

    for codificacao in ("utf-8-sig", "latin-1"):
        try:
            texto = inicio.decode(codificacao)
            break
        except UnicodeDecodeError:
            continue
    primeira_linha = texto.splitlines()[0] if texto else ""
    try:
        separador = csv.Sniffer().sniff(primeira_linha, delimiters=",;\t|").delimiter
    except csv.Error:
        separador = ","
    return codificacao, separador


def carregar(caminho: Path, rel: Relatorio) -> tuple:
    """
    Lê o CSV duas vezes:
      - bruto: tudo como texto, exatamente como está no arquivo. Serve para
        checar formatos, espaços e textos pseudo-nulos sem que o pandas
        "corrija" nada escondido.
      - tipado: cada coluna convertida para o tipo do ESQUEMA. Valores que não
        convertem viram nulo e são contados como erro de tipo.

    Por que ler como texto primeiro: com a leitura padrão, o pandas
    transforma o texto "None" em nulo (E4) e números mal formatados podem
    passar despercebidos.
    """
    codificacao, separador = detectar_formato(caminho)
    tamanho_mb = caminho.stat().st_size / 1024 ** 2

    rel.titulo(1, "Carregamento do arquivo",
               "confere se o arquivo existe, se é um CSV válido e como ele está codificado.")
    rel.escrever(f"   Arquivo:      {caminho.name}")
    rel.escrever(f"   Tamanho:      {numero(tamanho_mb, 2)} MB")
    rel.escrever(f"   Codificação:  {codificacao}")
    rel.escrever(f"   Separador:    '{separador}'")
    if tamanho_mb > LIMITE_TAMANHO_MB:
        rel.aviso(f"arquivo grande (> {LIMITE_TAMANHO_MB} MB). A leitura pode ficar lenta e "
                  f"usar muita memória; considere ler só as colunas necessárias.")

    # Se a amostra inicial parecia UTF-8 mas há acentos em latin-1 mais adiante,
    # a leitura falharia no meio do arquivo. Nesse caso, tenta de novo em latin-1.
    try:
        bruto = pd.read_csv(caminho, dtype=str, keep_default_na=False, sep=separador,
                            encoding=codificacao)
    except UnicodeDecodeError:
        codificacao = "latin-1"
        rel.aviso("acentos fora do padrão UTF-8 encontrados; arquivo relido como latin-1.")
        bruto = pd.read_csv(caminho, dtype=str, keep_default_na=False, sep=separador,
                            encoding=codificacao)
    bruto.columns = [c.strip().casefold() for c in bruto.columns]
    nomes_normalizados = {c.casefold(): c for c in ESQUEMA}
    bruto = bruto.rename(columns={c: nomes_normalizados.get(c, c) for c in bruto.columns})

    # Confere se as colunas esperadas existem.
    faltando = [c for c in ESQUEMA if c not in bruto.columns]
    extras = [c for c in bruto.columns if c not in ESQUEMA]
    if len(bruto.columns) == 1:
        sys.exit("ERRO: o arquivo foi lido com uma única coluna. O separador ou o "
                 "formato do arquivo não é o esperado.")
    if faltando:
        sys.exit(f"ERRO: faltam colunas obrigatórias: {', '.join(faltando)}")
    if extras:
        rel.aviso(f"colunas não previstas no esquema (não serão validadas): {', '.join(extras)}")
    rel.ok(f"todas as {len(ESQUEMA)} colunas esperadas estão presentes.")

    tipado = pd.DataFrame(index=bruto.index)
    falhas_conversao = {}
    for coluna, regra in ESQUEMA.items():
        texto = bruto[coluna].str.strip()
        if regra["tipo"] == "data":
            convertido = pd.to_datetime(texto, format="%Y-%m-%d %H:%M:%S", errors="coerce")
        elif regra["tipo"] in ("inteiro", "decimal", "binario"):
            convertido = pd.to_numeric(texto, errors="coerce")
        else:
            convertido = texto
        # Conta só as falhas reais: o texto existia, mas não pôde ser convertido.
        if regra["tipo"] != "categoria":
            falhas_conversao[coluna] = int((convertido.isna() & (texto != "")).sum())
        tipado[coluna] = convertido
    for coluna in extras:
        tipado[coluna] = bruto[coluna]

    # Colunas de categoria guardadas como 'category' ocupam menos memória.
    # Isso ajuda a escalar para bases maiores.
    for coluna, regra in ESQUEMA.items():
        if regra["tipo"] == "categoria":
            tipado[coluna] = tipado[coluna].astype("category")

    return bruto, tipado, falhas_conversao


# =============================================================================
# 6. VERIFICAÇÕES DE QUALIDADE
# =============================================================================
# Cada função recebe a base, escreve no relatório e devolve uma série booleana
# (uma por linha) marcando os registros com problema. Essas marcas formam a
# análise por registro (seção de registros problemáticos).

def verificar_estrutura(df: pd.DataFrame, rel: Relatorio) -> None:
    """Mostra tamanho, período e o dicionário de colunas (Etapa 1 da auditoria)."""
    rel.titulo(2, "Estrutura e dicionário de dados",
               "tamanho da base e o significado, tipo e unidade de cada coluna.")
    rel.escrever(f"   Linhas (registros):   {numero(len(df))}")
    rel.escrever(f"   Colunas:              {numero(df.shape[1])}")
    datas = df["Timestamp"].dropna()
    if len(datas):
        rel.escrever(f"   Período:              {datas.min():%d/%m/%Y} a {datas.max():%d/%m/%Y}")
    rel.escrever(f"   Caminhões distintos:  {df['Asset_ID'].nunique()}")
    rel.escrever()
    linhas = []
    for coluna, regra in ESQUEMA.items():
        if regra["unidade"]:
            unidade = regra["unidade"]
        elif regra["tipo"] in ("categoria", "binario"):
            unidade = "não se aplica"
        else:
            unidade = "NÃO DOCUMENTADA"
        linhas.append([regra["nome"], regra["tipo"], unidade, regra["descricao"]])
    rel.tabela(["Coluna", "Tipo", "Unidade", "Descrição"], linhas, [24, 10, 18, 46])


def verificar_nulos(bruto: pd.DataFrame, rel: Relatorio) -> pd.Series:
    """
    Detecta células vazias, células só com espaços e textos pseudo-nulos.

    Regra: um texto como "None" ou "NA" não é vazio no arquivo, mas é lido
    como nulo por muitas ferramentas. Ele precisa ser tratado de forma
    explícita para não sumir com dados válidos (E4).
    """
    rel.titulo(3, "Valores nulos e vazios",
               "células vazias, só com espaços ou com textos que significam 'sem valor'.")
    vazio = bruto.apply(lambda c: c.str.strip() == "")
    espacos = bruto.apply(lambda c: (c != c.str.strip()) & (c.str.strip() != ""))
    pseudo = bruto.apply(lambda c: c.str.strip().str.casefold().isin(TEXTOS_PSEUDO_NULOS))

    total_vazio, total_espacos = int(vazio.sum().sum()), int(espacos.sum().sum())
    (rel.ok if total_vazio == 0 else rel.aviso)(f"células vazias: {numero(total_vazio)}")
    (rel.ok if total_espacos == 0 else rel.aviso)(f"células com espaços sobrando: {numero(total_espacos)}")

    for coluna in pseudo.columns[pseudo.any()]:
        qtd = int(pseudo[coluna].sum())
        exemplos = sorted(bruto.loc[pseudo[coluna], coluna].unique())
        rel.alertar(Alerta(
            "ALTO", "E4", f"texto pseudo-nulo em '{nome_pt(coluna)}'",
            onde=f"coluna {coluna}, {numero(qtd)} registros (valores: {', '.join(exemplos)})",
            causa="o arquivo usa um texto para dizer 'sem valor'; a leitura padrão do pandas "
                  "converte esse texto em nulo",
            impacto=f"quem não souber disso vê {pct(qtd / len(bruto))} de dados 'faltando' e pode "
                    "apagá-los; contagens do BI ficam erradas",
            correcao="este script lê o arquivo como texto e trata o valor como categoria; no "
                     "dataset tratado, o motivo é reescrito de forma explícita (ver E1)",
            areas=("BI", "Relatórios", "Limpeza"), registros=qtd))
    if not pseudo.any().any():
        rel.ok("nenhum texto pseudo-nulo encontrado.")
    if total_vazio:
        for coluna in vazio.columns[vazio.any()]:
            rel.alertar(Alerta(
                "ALTO", "NULO", f"valores vazios em '{nome_pt(coluna)}'",
                onde=f"coluna {coluna}, {numero(int(vazio[coluna].sum()))} registros",
                causa="dado não preenchido na origem",
                impacto="médias e contagens deixam de considerar esses registros",
                correcao="verificar com o responsável; não substituir por média sem justificativa",
                areas=("BI", "ML"), registros=int(vazio[coluna].sum())))
    return vazio.any(axis=1) | espacos.any(axis=1)


def verificar_duplicados(df: pd.DataFrame, rel: Relatorio) -> pd.Series:
    """
    Procura duplicidades em três níveis:
      - linha inteira repetida;
      - linha repetida ignorando o horário (mesmo registro gravado duas vezes);
      - mesmo caminhão no mesmo horário (impossível ter dois registros).
    """
    rel.titulo(4, "Duplicidades",
               "registros repetidos, que inflam contagens e distorcem médias.")
    regras = {
        "linhas idênticas": df.duplicated(keep=False),
        "idênticas exceto o horário": df.drop(columns="Timestamp").duplicated(keep=False),
        "mesmo caminhão no mesmo horário": df.duplicated(["Asset_ID", "Timestamp"], keep=False),
        "mesma coordenada repetida": df.duplicated(["Latitude", "Longitude"], keep=False),
    }
    marcados = pd.Series(False, index=df.index)
    for nome, mascara in regras.items():
        qtd = int(mascara.sum())
        if qtd == 0:
            rel.ok(f"{nome}: nenhum")
        else:
            marcados |= mascara
            rel.alertar(Alerta(
                "ALTO", "DUP", f"duplicidade: {nome}", onde=f"{numero(qtd)} registros",
                causa="registro gravado mais de uma vez ou erro na coleta",
                impacto="contagens e taxas infladas",
                correcao="manter só uma ocorrência após confirmar com o responsável",
                areas=("BI", "ML"), registros=qtd))
    return marcados


def verificar_tipos_formatos(bruto: pd.DataFrame, df: pd.DataFrame, falhas: dict,
                             rel: Relatorio) -> pd.Series:
    """
    Confere tipos, datas e padrões de escrita.

    - Tipos: um número escrito com vírgula ou com letra não converte.
    - Datas: precisam existir, estar no formato esperado e não estar no futuro.
    - Padrões: o Asset_ID deve seguir 'Truck_<número>'.
    - Casas decimais: uma coluna com 1 casa em umas linhas e 3 em outras indica
      origens diferentes ou arredondamentos inconsistentes.
    """
    rel.titulo(5, "Tipos de dados e formatos",
               "valores que não convertem para o tipo certo, datas inválidas e padrões quebrados.")
    marcados = pd.Series(False, index=df.index)

    # Tipos
    total_falhas = sum(falhas.values())
    if total_falhas == 0:
        rel.ok("todos os valores numéricos e de data convertem para o tipo esperado.")
    for coluna, qtd in falhas.items():
        if qtd:
            mascara = df[coluna].isna() & (bruto[coluna].str.strip() != "")
            marcados |= mascara
            exemplos = ", ".join(bruto.loc[mascara, coluna].head(3))
            rel.alertar(Alerta(
                "ALTO", "TIPO", f"valores com tipo errado em '{nome_pt(coluna)}'",
                onde=f"coluna {coluna}, {numero(qtd)} registros (ex.: {exemplos})",
                causa="número ou data escrito fora do padrão",
                impacto="o valor vira nulo e sai dos cálculos",
                correcao="corrigir a escrita na origem", areas=("BI", "ML"), registros=qtd))

    # Padrões de texto (datas e IDs)
    for coluna, regra in ESQUEMA.items():
        if "formato" not in regra:
            continue
        fora = ~bruto[coluna].str.strip().str.fullmatch(regra["formato"])
        qtd = int(fora.sum())
        if qtd == 0:
            rel.ok(f"'{regra['nome']}': todos no padrão esperado.")
        else:
            marcados |= fora
            rel.alertar(Alerta(
                "MÉDIO", "FORMATO", f"formato inconsistente em '{regra['nome']}'",
                onde=f"coluna {coluna}, {numero(qtd)} registros",
                causa="valores escritos de formas diferentes",
                impacto="agrupamentos e filtros separam o que deveria estar junto",
                correcao="padronizar a escrita", areas=("BI",), registros=qtd))

    # Datas futuras ou anteriores a 2000
    datas = df["Timestamp"]
    hoje = pd.Timestamp.now()
    futuras = datas > hoje
    antigas = datas < pd.Timestamp("2000-01-01")
    if futuras.any() or antigas.any():
        marcados |= futuras | antigas
        rel.alertar(Alerta(
            "ALTO", "DATA", "datas fora do período possível",
            onde=f"{numero(int(futuras.sum()))} futuras e {numero(int(antigas.sum()))} antes de 2000",
            causa="erro de digitação ou de fuso", impacto="análises por período distorcidas",
            correcao="corrigir ou excluir as datas", areas=("BI", "Previsões"),
            registros=int((futuras | antigas).sum())))
    else:
        rel.ok("nenhuma data futura ou implausível.")

    # Casas decimais
    for coluna, regra in ESQUEMA.items():
        if regra["tipo"] not in ("decimal", "inteiro"):
            continue
        preenchidos = bruto[coluna].str.strip()
        preenchidos = preenchidos[preenchidos != ""]   # vazios já são tratados na seção 3
        casas = preenchidos.map(lambda s: len(s.split(".")[1]) if "." in s else 0)
        distintas = sorted(casas.unique())
        if len(distintas) > 1:
            rel.alertar(Alerta(
                "BAIXO", "FORMATO", f"casas decimais variadas em '{regra['nome']}'",
                onde=f"coluna {coluna}, casas encontradas: {distintas}",
                causa="dados de origens diferentes ou arredondamento inconsistente",
                impacto="pequenas diferenças de precisão entre registros",
                correcao="padronizar a precisão", areas=("Relatórios",)))
    rel.ok("casas decimais conferidas coluna a coluna.")
    return marcados


def verificar_categorias(bruto: pd.DataFrame, df: pd.DataFrame, rel: Relatorio) -> pd.Series:
    """
    Confere as colunas de texto contra as categorias permitidas.

    - Variações de escrita: 'Heavy', 'heavy ' e 'HEAVY' viram grupos diferentes
      num gráfico, embora sejam a mesma coisa.
    - Valores desconhecidos: indicam erro de digitação ou categoria nova não
      documentada.
    - Distribuição: mostra o tamanho de cada grupo.
    """
    rel.titulo(6, "Categorias",
               "variações de escrita, erros de digitação e tamanho de cada grupo.")
    marcados = pd.Series(False, index=df.index)
    for coluna, regra in ESQUEMA.items():
        if "valores" not in regra or regra["tipo"] == "binario":
            continue
        texto = bruto[coluna]
        normalizado = texto.str.strip().str.casefold()
        variantes = texto.groupby(normalizado).nunique()
        variantes = variantes[variantes > 1]
        permitidos = {v.casefold() for v in regra["valores"]}
        desconhecidos = ~normalizado.isin(permitidos)

        if len(variantes):
            rel.alertar(Alerta(
                "MÉDIO", "CATEG", f"mesma categoria escrita de formas diferentes em '{regra['nome']}'",
                onde=f"coluna {coluna}: {', '.join(variantes.index)}",
                causa="diferença de maiúsculas ou espaços",
                impacto="um mesmo grupo aparece dividido em gráficos e contagens",
                correcao="padronizar a escrita", areas=("BI", "Segmentação"),
                registros=int(normalizado.isin(variantes.index).sum())))
        if desconhecidos.any():
            marcados |= desconhecidos
            rel.alertar(Alerta(
                "MÉDIO", "CATEG", f"valores não previstos em '{regra['nome']}'",
                onde=f"coluna {coluna}: {', '.join(sorted(texto[desconhecidos].unique())[:5])}",
                causa="erro de digitação ou categoria não documentada",
                impacto="grupos inesperados nos relatórios",
                correcao="corrigir ou incluir a categoria no dicionário",
                areas=("BI",), registros=int(desconhecidos.sum())))
        if not len(variantes) and not desconhecidos.any():
            rel.ok(f"'{regra['nome']}': sem variações nem valores desconhecidos.")

        rel.escrever(f"\n   {regra['nome']}:")
        for valor, qtd in df[coluna].value_counts().items():
            rel.escrever(f"     - {traduzir(coluna, valor):<16} {numero(qtd):>6}  ({pct(qtd / len(df))})")
        rel.escrever()

    distintos = df["Asset_ID"].value_counts()
    rel.escrever(f"   Registros por caminhão: de {distintos.min()} a {distintos.max()}")
    return marcados


def verificar_faixas(df: pd.DataFrame, rel: Relatorio) -> pd.Series:
    """
    Procura valores impossíveis:
      - abaixo ou acima dos limites físicos (latitude > 90, umidade > 100%);
      - zero ou negativos onde isso não faz sentido (estoque, espera);
      - alvo diferente de 0 ou 1.
    """
    rel.titulo(7, "Valores impossíveis",
               "números que não podem existir na prática.")
    marcados = pd.Series(False, index=df.index)
    for coluna, regra in ESQUEMA.items():
        serie = df[coluna]
        if "min" in regra:
            fora = ~serie.between(regra["min"], regra["max"]) & serie.notna()
            texto = f"fora de {regra['min']} a {regra['max']}"
        elif regra.get("positivo"):
            fora = (serie <= 0) & serie.notna()
            texto = "menor ou igual a zero"
        elif regra["tipo"] == "binario":
            fora = ~serie.isin(list(regra["valores"])) & serie.notna()
            texto = "diferente de 0 ou 1"
        else:
            continue
        qtd = int(fora.sum())
        if qtd == 0:
            rel.ok(f"{regra['nome']:<22} nenhum valor {texto}")
        else:
            marcados |= fora
            rel.alertar(Alerta(
                "ALTO", "FAIXA", f"valores impossíveis em '{regra['nome']}' ({texto})",
                onde=f"coluna {coluna}, {numero(qtd)} registros",
                causa="erro de coleta ou digitação",
                impacto="médias e modelos distorcidos por valores que não existem",
                correcao="corrigir na origem ou excluir após confirmação",
                areas=("BI", "ML"), registros=qtd))
    return marcados


def verificar_outliers_distribuicao(df: pd.DataFrame, rel: Relatorio) -> dict:
    """
    Analisa a forma dos números em cada coluna numérica.

    - Outliers: pela regra do IQR (1,5 x intervalo interquartil) e pelo
      z-score (mais de 3 desvios da média).
    - Sinais de dado sintético (E7): curtose perto de -1,2 e assimetria perto de
      zero (assinatura da distribuição uniforme), teste KS que não rejeita a
      uniformidade e ausência total de outliers. Dados reais quase nunca são
      assim: têm concentrações, caudas e valores extremos.
    """
    rel.titulo(8, "Outliers, valores extremos e distribuições",
               "valores muito distantes do resto e o formato geral de cada coluna.")
    numericas = [c for c, r in ESQUEMA.items() if r["tipo"] in ("inteiro", "decimal")]
    linhas, uniformes, sem_outliers = [], [], []
    outliers_por_linha = pd.Series(False, index=df.index)

    for coluna in numericas:
        x = df[coluna].dropna()
        q1, q3 = x.quantile([0.25, 0.75])
        iqr = q3 - q1
        mask_iqr = (df[coluna] < q1 - 1.5 * iqr) | (df[coluna] > q3 + 1.5 * iqr)
        desvio = x.std()
        mask_z = ((df[coluna] - x.mean()).abs() / desvio > 3) if desvio > 0 else pd.Series(False, index=df.index)
        outliers_por_linha |= mask_iqr | mask_z
        n_out = int((mask_iqr | mask_z).sum())
        curtose, assimetria = x.kurt(), x.skew()
        ks = ks_uniforme(x) if x.nunique() > 50 else float("nan")
        parece_uniforme = (abs(curtose - CURTOSE_UNIFORME) <= TOLERANCIA_CURTOSE
                           and abs(assimetria) <= TOLERANCIA_ASSIMETRIA)
        if parece_uniforme:
            uniformes.append(coluna)
        if n_out == 0:
            sem_outliers.append(coluna)
        linhas.append([nome_pt(coluna), numero(x.min(), 1), numero(x.max(), 1),
                       numero(x.mean(), 1), numero(n_out), numero(assimetria, 2),
                       numero(curtose, 2), "-" if math.isnan(ks) else numero(ks, 2),
                       "sim" if parece_uniforme else "não"])

    rel.tabela(["Coluna", "Mín", "Máx", "Média", "Outl.", "Assim.", "Curt.", "KS p", "Uniforme?"],
               linhas, [22, -7, -7, -7, -5, -6, -6, -5, 9])
    rel.escrever("   Leitura: curtose perto de -1,2 e assimetria perto de 0 = números espalhados")
    rel.escrever("   por igual entre o mínimo e o máximo, típico de geração aleatória.")
    rel.escrever()

    if outliers_por_linha.any():
        rel.alertar(Alerta(
            "MÉDIO", "OUTLIER", "valores extremos encontrados",
            onde=f"{numero(int(outliers_por_linha.sum()))} registros",
            causa="eventos raros reais ou erros de registro",
            impacto="médias puxadas para cima ou para baixo",
            correcao="investigar cada caso antes de remover", areas=("BI", "ML"),
            registros=int(outliers_por_linha.sum())))
    else:
        rel.ok("nenhum outlier pela regra do IQR nem pelo z-score.")

    if len(uniformes) >= len(numericas) / 2:
        rel.alertar(Alerta(
            "ALTO", "E7", "distribuições artificiais (sinal de dado sintético)",
            onde=f"{len(uniformes)} de {len(numericas)} colunas numéricas: "
                 f"{', '.join(nome_pt(c) for c in uniformes)}",
            causa="os números parecem sorteados por igual entre limites redondos; "
                  f"{len(sem_outliers)} colunas não têm nenhum outlier",
            impacto="conclusões não valem para operações reais; modelos não terão padrões a aprender",
            correcao="declarar a base como sintética em qualquer apresentação; usar para estudo",
            areas=("Estatística", "ML", "Previsões", "Agrupamentos")))
    return {"uniformes": uniformes, "sem_outliers": sem_outliers, "numericas": numericas}


def verificar_coerencia(df: pd.DataFrame, rel: Relatorio) -> dict:
    """
    Compara colunas entre si. É aqui que estão os problemas mais graves.

    Regras de negócio aplicadas:
      E1. Um motivo de atraso só existe quando houve atraso, e todo atraso
          deveria ter um motivo.
      E2. Uma coluna que só é conhecida depois do resultado (status 'Delayed')
          não pode explicar o resultado: é vazamento de alvo.
      E3. Nenhuma condição do mundo real garante 100% de atraso; um grupo grande
          com 0% ou 100% indica regra fixa no gerador dos dados.
      Extra: motivo 'Traffic' com trânsito livre e status ambíguos.
    """
    rel.titulo(9, "Coerência entre colunas",
               "combinações de valores que não fazem sentido juntas.")
    marcas = {}
    motivo = df["Logistics_Delay_Reason"].astype(str)
    atraso = df[ALVO]

    # E1 - motivo x atraso
    motivo_sem_atraso = (atraso == 0) & (motivo != "None")
    atraso_sem_motivo = (atraso == 1) & (motivo == "None")
    contraditorio = motivo_sem_atraso | atraso_sem_motivo
    marcas["motivo_contraditorio"] = contraditorio
    if contraditorio.any():
        rel.alertar(Alerta(
            "CRÍTICO", "E1", "motivo do atraso contradiz o atraso",
            onde=f"{numero(int(motivo_sem_atraso.sum()))} registros com motivo e sem atraso; "
                 f"{numero(int(atraso_sem_motivo.sum()))} com atraso e sem motivo "
                 f"(total {numero(int(contraditorio.sum()))}, {pct(contraditorio.mean())})",
            causa="a regra 'motivo só existe se houver atraso' não foi respeitada na geração dos dados",
            impacto="relatórios de 'principais causas de atraso' ficam errados; modelos aprendem ruído",
            correcao="o dataset tratado cria a coluna Motivo_Tratado: 'Sem atraso' quando o atraso "
                     "é 0 e 'Desconhecido' quando há atraso sem motivo; a coluna original é mantida",
            areas=("BI", "Dashboards", "ML", "Relatórios"), registros=int(contraditorio.sum())))
    else:
        rel.ok("motivo e atraso são coerentes.")

    # E2 e E3 - grupos com taxa de 0% ou 100% (regra fixa ou vazamento)
    deterministicas = []
    for coluna, regra in ESQUEMA.items():
        if regra["tipo"] != "categoria" or coluna == "Asset_ID":
            continue
        taxas = df.groupby(coluna, observed=True)[ALVO].agg(["mean", "count"])
        fixos = taxas[(taxas["count"] >= GRUPO_MINIMO_REGRA_FIXA) & taxas["mean"].isin([0, 1])]
        for valor, linha in fixos.iterrows():
            mascara = df[coluna] == valor
            marcas[f"regra_fixa_{coluna}"] = mascara
            deterministicas.append(coluna)
            if regra.get("pos_evento"):
                rel.alertar(Alerta(
                    "CRÍTICO", "E2", f"vazamento de alvo: '{nome_pt(coluna)}' = "
                                     f"'{traduzir(coluna, valor)}' tem {pct(linha['mean'], 0)} de atraso",
                    onde=f"coluna {coluna}, {numero(int(linha['count']))} registros",
                    causa="a coluna descreve o resultado da entrega; ela só é conhecida depois que o "
                          "atraso aconteceu",
                    impacto="um modelo que use essa coluna 'cola' a resposta e mostra acurácia falsa",
                    correcao="a coluna é marcada como proibida para modelos na seção de riscos de ML; "
                             "use-a só para descrever o passado",
                    areas=("ML", "Previsões"), registros=int(linha["count"])))
            else:
                rel.alertar(Alerta(
                    "CRÍTICO", "E3", f"regra fixa: '{nome_pt(coluna)}' = "
                                     f"'{traduzir(coluna, valor)}' tem {pct(linha['mean'], 0)} de atraso",
                    onde=f"coluna {coluna}, {numero(int(linha['count']))} registros",
                    causa="no mundo real essa condição aumenta a chance de atraso, mas não a "
                          "garante; um resultado perfeito indica regra escrita no gerador",
                    impacto="modelos aprendem só essa regra e ela esconde o efeito das demais colunas",
                    correcao="a análise de atrasos é repetida sem esses registros (seção 11)",
                    areas=("ML", "Estatística", "Previsões"), registros=int(linha["count"])))

    # Motivo 'Traffic' com trânsito livre
    transito_incoerente = (motivo == "Traffic") & (df["Traffic_Status"] == "Clear")
    marcas["motivo_transito_incoerente"] = transito_incoerente
    if transito_incoerente.any():
        rel.alertar(Alerta(
            "MÉDIO", "E1", "motivo 'Trânsito' com trânsito livre",
            onde=f"{numero(int(transito_incoerente.sum()))} registros",
            causa="as colunas de motivo e de trânsito foram preenchidas de forma independente",
            impacto="análises de causa misturam situações incompatíveis",
            correcao="confirmar qual das duas colunas está certa", areas=("BI",),
            registros=int(transito_incoerente.sum())))

    # Status 'Delayed' sem motivo
    atrasada_sem_motivo = (df["Shipment_Status"] == "Delayed") & (motivo == "None")
    marcas["atrasada_sem_motivo"] = atrasada_sem_motivo
    if atrasada_sem_motivo.any():
        rel.alertar(Alerta(
            "MÉDIO", "E1", "entregas 'Atrasada' sem motivo registrado",
            onde=f"{numero(int(atrasada_sem_motivo.sum()))} registros",
            causa="motivo não preenchido quando o status indica atraso",
            impacto="parte dos atrasos fica sem explicação nos relatórios",
            correcao="preencher o motivo ou marcar como 'Desconhecido'", areas=("BI", "Relatórios"),
            registros=int(atrasada_sem_motivo.sum())))

    # Status ambíguos (informativo: não é erro certo, mas precisa de definição)
    ambiguos = df["Shipment_Status"].isin(["Delivered", "In Transit"]) & (atraso == 1)
    if ambiguos.any():
        rel.alertar(Alerta(
            "BAIXO", "E2", "status 'Entregue' ou 'Em trânsito' com atraso = 1",
            onde=f"{numero(int(ambiguos.sum()))} registros",
            causa="não está documentado se significa 'entregue com atraso' ou 'vai atrasar'",
            impacto="interpretações diferentes entre pessoas do grupo",
            correcao="documentar o significado de cada combinação", areas=("Relatórios",),
            registros=int(ambiguos.sum())))
    return {"marcas": marcas, "deterministicas": sorted(set(deterministicas))}


def verificar_integridade(df: pd.DataFrame, rel: Relatorio) -> dict:
    """
    Verifica se os dados respeitam a realidade física e se é possível
    identificar cada entrega.

      E5. Trajetos: ordena os registros de cada caminhão no tempo, calcula a
          distância entre posições consecutivas e a velocidade necessária.
          Velocidades acima do limite de um caminhão são impossíveis.
      E6. Localização e clima: regiões polares não têm malha rodoviária
          relevante, e temperaturas altas nelas são improváveis.
      E8. Chave e campos essenciais: sem ID da entrega, prazo e data de entrega,
          não dá para conferir se o atraso está correto.
      Relações esperadas: colunas que deveriam andar juntas e não andam.
    """
    rel.titulo(10, "Integridade e realismo",
               "trajetos possíveis, localizações plausíveis e campos essenciais.")
    marcas = {}

    # E5 - trajetos
    ordem = df.sort_values(["Asset_ID", "Timestamp"])
    grupo = ordem.groupby("Asset_ID", observed=True)
    lat_ant, lon_ant = grupo["Latitude"].shift(), grupo["Longitude"].shift()
    horas = grupo["Timestamp"].diff().dt.total_seconds() / 3600
    km = haversine_km(lat_ant, lon_ant, ordem["Latitude"], ordem["Longitude"])
    velocidade = (km / horas.where(horas > 0)).reindex(df.index)
    impossivel = velocidade > VELOCIDADE_MAXIMA_KMH
    marcas["trajeto_impossivel"] = impossivel.fillna(False)
    deslocamentos = int(velocidade.notna().sum())
    taxa_impossivel = impossivel.sum() / deslocamentos if deslocamentos else 0.0
    rel.escrever(f"   Deslocamentos analisados:  {numero(deslocamentos)}")
    rel.escrever(f"   Distância mediana:         {numero(km.median())} km em "
                 f"{numero(horas.median(), 1)} horas")
    rel.escrever(f"   Velocidade mediana:        {numero(velocidade.median())} km/h")
    if impossivel.any():
        rel.alertar(Alerta(
            "ALTO", "E5", "trajetos fisicamente impossíveis",
            onde=f"{numero(int(impossivel.sum()))} de {numero(deslocamentos)} deslocamentos "
                 f"({pct(taxa_impossivel)}) exigem mais de {VELOCIDADE_MAXIMA_KMH} km/h; "
                 f"máximo de {numero(velocidade.max())} km/h",
            causa="as coordenadas não seguem o movimento real dos caminhões",
            impacto="mapas, rotas, distâncias e análises por região ficam sem sentido",
            correcao="não usar as coordenadas em análises geográficas até haver dados reais",
            areas=("Geografia", "BI", "Dashboards"), registros=int(impossivel.sum())))
    else:
        rel.ok("todos os trajetos são compatíveis com a velocidade de um caminhão.")

    # E6 - localização e clima
    polar = df["Latitude"].abs() > LATITUDE_POLAR
    polar_quente = polar & (df["Temperature"] >= TEMPERATURA_IMPROVAVEL_NOS_POLOS)
    marcas["local_improvavel"] = polar
    if polar.any():
        rel.alertar(Alerta(
            "ALTO", "E6", "localizações improváveis (regiões polares)",
            onde=f"{numero(int(polar.sum()))} registros além de {numero(LATITUDE_POLAR, 1)}° de latitude; "
                 f"{numero(int(polar_quente.sum()))} deles com {numero(TEMPERATURA_IMPROVAVEL_NOS_POLOS)} °C ou mais",
            causa="coordenadas e temperaturas geradas sem relação com a geografia real",
            impacto="cruzamentos entre clima e localização perdem o sentido",
            correcao="não cruzar clima com localização", areas=("Geografia", "Estatística"),
            registros=int(polar.sum())))

    # Relações esperadas
    for col_a, col_b, motivo in RELACOES_ESPERADAS:
        a = df[col_a].abs() if col_b == "Latitude" else df[col_a]
        b = df[col_b].abs() if col_b == "Latitude" else df[col_b]
        r = a.corr(b)
        if abs(r) < CORRELACAO_RELEVANTE:
            rel.alertar(Alerta(
                "MÉDIO", "E7", f"relação esperada ausente: {nome_pt(col_a)} x {nome_pt(col_b)}",
                onde=f"correlação de {numero(r, 3)}",
                causa=f"{motivo}, mas as colunas variam de forma independente",
                impacto="indica dado gerado ou coluna mal definida",
                correcao="confirmar a definição das colunas com o responsável",
                areas=("Estatística", "ML")))

    # E8 - campos essenciais
    ausentes = [nome for nome, alternativas in CAMPOS_ESSENCIAIS.items()
                if not any(a in df.columns for a in alternativas)]
    if ausentes:
        rel.alertar(Alerta(
            "ALTO", "E8", "campos essenciais ausentes",
            onde=", ".join(ausentes),
            causa="a base registra o caminhão, mas não a entrega",
            impacto="não dá para seguir uma entrega do início ao fim nem conferir se o 'atraso' "
                    "está correto; indicadores de prazo ficam impossíveis",
            correcao="solicitar esses campos ao responsável pela base",
            areas=("BI", "Relatórios", "ML")))

    # E9 - documentação e mistura de assuntos
    sem_unidade = [c for c, r in ESQUEMA.items()
                   if r["tipo"] in ("inteiro", "decimal") and r["unidade"] is None]
    if sem_unidade:
        rel.alertar(Alerta(
            "MÉDIO", "E9", "colunas sem unidade documentada",
            onde=", ".join(nome_pt(c) for c in sem_unidade),
            causa="o arquivo não informa unidades (minutos? reais? kg?)",
            impacto="cada pessoa pode interpretar os números de um jeito",
            correcao="o script gera outputs/dicionario_dados.csv marcando as unidades a confirmar",
            areas=("Relatórios", "BI")))
    cliente = [c for c, r in ESQUEMA.items() if r["grupo"] == "cliente"]
    if cliente and not any(c in df.columns for c in ("Customer_ID", "User_ID")):
        rel.alertar(Alerta(
            "MÉDIO", "E9", "dados de cliente sem identificação do cliente",
            onde=", ".join(cliente),
            causa="um caminhão atende vários clientes, mas não se sabe de qual são os valores",
            impacto="segmentação de clientes fica impossível",
            correcao="mover os dados de cliente para uma tabela própria com Customer_ID",
            areas=("Segmentação", "BI")))
    return {"marcas": marcas, "taxa_trajeto_impossivel": taxa_impossivel, "ausentes": ausentes,
            "sem_unidade": sem_unidade}


# =============================================================================
# 7. ANÁLISE DOS ATRASOS
# =============================================================================

def taxas_por_grupo(df: pd.DataFrame, coluna, rel: Relatorio, rotulo=None) -> float:
    """
    Mostra a taxa de atraso de cada grupo e testa se a diferença é real.
    Devolve o p-valor do teste qui-quadrado.
    """
    chave = df[coluna] if isinstance(coluna, str) else coluna
    tabela = pd.crosstab(chave, df[ALVO])
    resumo = df.groupby(chave, observed=True)[ALVO].agg(["mean", "count"]).sort_values("mean", ascending=False)
    for valor, linha in resumo.iterrows():
        nome = rotulo(valor) if rotulo else traduzir(coluna if isinstance(coluna, str) else "", valor)
        rel.escrever(f"     {nome:<18} {pct(linha['mean']):>7} de atraso  ({numero(linha['count'])} registros)")
    p = qui_quadrado(tabela)
    rel.escrever(f"     Teste qui-quadrado: {p_valor(p)}")
    return p


def analisar_atrasos(df: pd.DataFrame, deterministicas: list, rel: Relatorio) -> dict:
    """
    Responde: quanto atrasa e o que está ligado ao atraso?

    Melhorias em relação à versão anterior:
    - testa se cada diferença é real (antes, diferenças por acaso pareciam
      descobertas);
    - analisa por caminhão e por mês (antes, não analisados);
    - repete a análise sem os grupos com regra fixa (E3), para revelar o efeito
      das demais colunas;
    - mede a relação das colunas numéricas com o atraso;
    - calcula a acurácia de referência que qualquer modelo precisa superar.
    """
    rel.titulo(11, "Análise dos atrasos",
               "quanto as entregas atrasam e o que está de fato ligado ao atraso.")
    taxa = df[ALVO].mean()
    rel.escrever(f"   Taxa geral: {numero(int(df[ALVO].sum()))} de {numero(len(df))} registros "
                 f"atrasaram ({pct(taxa)}).")
    rel.escrever("   Como 'Atrasou?' vale 1 ou 0, a média da coluna é a taxa de atraso.")
    resultados = {}

    for coluna in ["Traffic_Status", "Logistics_Delay_Reason", "Shipment_Status"]:
        rel.escrever(f"\n   Por {nome_pt(coluna).lower()}:")
        resultados[coluna] = taxas_por_grupo(df, coluna, rel)
        if ESQUEMA[coluna].get("pos_evento"):
            rel.escrever("     Atenção: coluna com vazamento de alvo (E2). Serve só para descrever.")

    rel.escrever("\n   Por caminhão:")
    resultados["Asset_ID"] = taxas_por_grupo(df, "Asset_ID", rel,
                                             rotulo=lambda v: str(v).replace("Truck_", "Caminhão "))
    rel.escrever("\n   Por mês:")
    meses = df["Timestamp"].dt.month.rename("Mês")
    resultados["Mês"] = taxas_por_grupo(df, meses, rel, rotulo=lambda m: MESES[int(m) - 1])

    # Sem as regras fixas (E3)
    regras_fixas = [c for c in deterministicas if not ESQUEMA[c].get("pos_evento")]
    sem_regra = df
    for coluna in regras_fixas:
        taxas = df.groupby(coluna, observed=True)[ALVO].mean()
        fixos = taxas[taxas.isin([0, 1])].index
        sem_regra = sem_regra[~sem_regra[coluna].isin(fixos)]
    if regras_fixas:
        rel.escrever(f"\n   Sem os registros com regra fixa ({', '.join(nome_pt(c) for c in regras_fixas)}):")
        rel.escrever(f"     {numero(len(sem_regra))} registros, taxa de atraso de {pct(sem_regra[ALVO].mean())}")

    # Colunas numéricas x atraso
    rel.escrever("\n   Relação das colunas numéricas com o atraso (correlação, de -1 a +1):")
    numericas = [c for c, r in ESQUEMA.items() if r["tipo"] in ("inteiro", "decimal")]
    correlacoes = sem_regra[numericas].corrwith(sem_regra[ALVO]).sort_values(key=abs, ascending=False)
    uteis = []
    for coluna, r in correlacoes.items():
        relevante = abs(r) >= CORRELACAO_RELEVANTE
        if relevante:
            uteis.append(coluna)
        rel.escrever(f"     {nome_pt(coluna):<24} {numero(r, 3):>7}  {'relevante' if relevante else 'sem relação'}")

    # Tempo de espera (E10): relação contrária ao esperado
    quartis = pd.qcut(sem_regra["Waiting_Time"], 4, duplicates="drop")
    por_espera = sem_regra.groupby(quartis, observed=True)[ALVO].mean()
    if len(por_espera) >= 2 and por_espera.iloc[0] > por_espera.iloc[-1] + 0.05:
        rel.alertar(Alerta(
            "MÉDIO", "E10", "tempo de espera com relação invertida",
            onde=f"menor espera: {pct(por_espera.iloc[0])} de atraso; maior espera: "
                 f"{pct(por_espera.iloc[-1])}",
            causa="esperar mais deveria aumentar o atraso, mas os dados mostram o contrário",
            impacto="a coluna pode estar mal definida ou medir outra coisa",
            correcao="confirmar a definição e a unidade com o responsável",
            areas=("Estatística", "ML")))

    # Grupos que só parecem diferentes
    for chave, nome in [("Asset_ID", "caminhão"), ("Mês", "mês"), ("Logistics_Delay_Reason", "motivo")]:
        if resultados[chave] >= NIVEL_SIGNIFICANCIA:
            rel.escrever(f"\n   Leitura: as diferenças por {nome} não passam no teste estatístico; "
                         f"não devem ser apresentadas como descoberta.")

    referencia = max(taxa, 1 - taxa)
    rel.escrever(f"\n   Acurácia de referência: {pct(referencia)} (chutar sempre a resposta mais comum).")
    rel.escrever("   Qualquer modelo de previsão precisa superar esse número para ter valor.")

    categoricas_uteis = [c for c in ("Traffic_Status", "Logistics_Delay_Reason")
                         if resultados[c] < NIVEL_SIGNIFICANCIA]
    return {"taxa": taxa, "p_valores": resultados, "uteis_numericas": uteis,
            "uteis_categoricas": categoricas_uteis, "referencia": referencia,
            "sem_regra": len(sem_regra)}


# =============================================================================
# 8. QUALIDADE POR COLUNA E POR REGISTRO
# =============================================================================

def qualidade_por_coluna(df: pd.DataFrame, bruto: pd.DataFrame, dist: dict, coer: dict,
                         integ: dict, rel: Relatorio) -> pd.DataFrame:
    """
    Junta, para cada coluna, os problemas encontrados e dá uma situação geral.
    Objetivo: mostrar de forma direta quais colunas merecem confiança.
    """
    rel.titulo(12, "Qualidade por coluna",
               "quais colunas são confiáveis e quais têm problemas.")
    problemas = {c: [] for c in ESQUEMA}
    for c in dist["uniformes"]:
        problemas[c].append("distribuição artificial")
    for c in coer["deterministicas"]:
        problemas[c].append("vazamento de alvo" if ESQUEMA[c].get("pos_evento") else "regra fixa com o alvo")
    if coer["marcas"]["motivo_contraditorio"].any():
        problemas["Logistics_Delay_Reason"].append("contradiz o alvo")
    pseudo = bruto["Logistics_Delay_Reason"].str.strip().str.casefold().isin(TEXTOS_PSEUDO_NULOS)
    if pseudo.any():
        problemas["Logistics_Delay_Reason"].append("texto pseudo-nulo")
    if integ["marcas"]["trajeto_impossivel"].any():
        problemas["Latitude"].append("trajeto impossível")
        problemas["Longitude"].append("trajeto impossível")
    if integ["marcas"]["local_improvavel"].any():
        problemas["Latitude"].append("regiões polares")
    for c in integ["sem_unidade"]:
        problemas[c].append("sem unidade")
    for c, r in ESQUEMA.items():
        if r["grupo"] == "cliente":
            problemas[c].append("sem ID do cliente")
    if "Timestamp" in ESQUEMA:
        problemas["Timestamp"].append("fuso não informado")
    if integ["ausentes"]:
        problemas[ALVO].append("critério de atraso não documentado")

    linhas, registros = [], []
    for coluna, lista in problemas.items():
        graves = [p for p in lista if p in ("contradiz o alvo", "vazamento de alvo",
                                            "regra fixa com o alvo", "trajeto impossível")]
        situacao = "CRÍTICA" if graves else ("ATENÇÃO" if lista else "BOA")
        linhas.append([nome_pt(coluna), situacao, "; ".join(lista) or "nenhum problema"])
        registros.append({"coluna": coluna, "nome": nome_pt(coluna), "situacao": situacao,
                          "problemas": "; ".join(lista)})
    rel.tabela(["Coluna", "Situação", "Problemas"], linhas, [24, 9, 70])
    return pd.DataFrame(registros)


def registros_problematicos(df: pd.DataFrame, marcas: dict, rel: Relatorio) -> pd.DataFrame:
    """
    Marca, em cada linha, quais regras ela quebrou.
    Objetivo: permitir corrigir ou investigar registro a registro, não só ver
    totais (análise que não existia na versão anterior).
    """
    rel.titulo(13, "Registros problemáticos",
               "quantas linhas quebram ao menos uma regra e quais regras mais aparecem.")
    flags = pd.DataFrame({f"problema_{nome}": m.reindex(df.index).fillna(False).astype(bool)
                          for nome, m in marcas.items()})
    flags["qtd_problemas"] = flags.sum(axis=1)
    com_problema = flags["qtd_problemas"] > 0
    rel.escrever(f"   Registros com pelo menos um problema: {numero(int(com_problema.sum()))} "
                 f"de {numero(len(df))} ({pct(com_problema.mean())})")
    rel.escrever(f"   Registros sem nenhum problema:         {numero(int((~com_problema).sum()))}")
    rel.escrever()
    contagem = flags.drop(columns="qtd_problemas").sum().sort_values(ascending=False)
    for nome, qtd in contagem.items():
        if qtd:
            rel.escrever(f"     {nome.replace('problema_', '').replace('_', ' '):<38} {numero(int(qtd)):>6}")
    distribuicao = flags["qtd_problemas"].value_counts().sort_index()
    rel.escrever("\n   Problemas por registro:")
    for qtd, n in distribuicao.items():
        rel.escrever(f"     {qtd} problema(s): {numero(n)} registros")
    return flags


# =============================================================================
# 9. RISCOS, NOTAS E RELATÓRIO FINAL
# =============================================================================

def riscos(rel: Relatorio, coer: dict, atrasos: dict) -> None:
    """
    Agrupa os alertas por área de uso (BI e Machine Learning) e lista as
    colunas que podem e as que não podem ser usadas em modelos.
    """
    rel.titulo(14, "Riscos para BI e Machine Learning",
               "o que pode dar errado em painéis, relatórios e modelos de previsão.")
    for area, titulo in [(("BI", "Dashboards", "Relatórios"), "BI e relatórios"),
                         (("ML", "Previsões"), "Machine Learning e previsões")]:
        rel.escrever(f"\n   {titulo}:")
        lista = sorted({(a.gravidade, a.codigo, a.titulo) for a in rel.alertas
                        if set(a.areas) & set(area)}, key=lambda x: GRAVIDADES[x[0]])
        for gravidade, codigo, titulo_alerta in lista:
            rel.escrever(f"     [{gravidade}] {codigo}: {titulo_alerta}")

    proibidas = [c for c in coer["deterministicas"] if ESQUEMA[c].get("pos_evento")]
    cuidado = [c for c in coer["deterministicas"] if not ESQUEMA[c].get("pos_evento")]
    candidatas = [c for c, r in ESQUEMA.items()
                  if c not in proibidas and c not in ("Timestamp", ALVO) and r["grupo"] != "identificação"]
    rel.escrever("\n   Uso das colunas em modelos de previsão do atraso:")
    rel.escrever(f"     Proibidas (vazamento):        {', '.join(nome_pt(c) for c in proibidas) or 'nenhuma'}")
    rel.escrever(f"     Usar com cuidado (regra fixa): {', '.join(nome_pt(c) for c in cuidado) or 'nenhuma'}")
    rel.escrever(f"     Candidatas:                    {', '.join(nome_pt(c) for c in candidatas if c not in cuidado)}")
    rel.escrever(f"     Colunas numéricas com relação real ao atraso: "
                 f"{', '.join(nome_pt(c) for c in atrasos['uteis_numericas']) or 'nenhuma'}")


def notas_qualidade(df: pd.DataFrame, bruto: pd.DataFrame, dist: dict, coer: dict, integ: dict,
                    atrasos: dict, flags: pd.DataFrame, rel: Relatorio) -> dict:
    """
    Calcula notas de 0 a 10 com fórmulas fixas e documentadas, para que a nota
    seja reproduzível e não uma opinião.

      Completude     = 10 x (células preenchidas) - 2 se faltarem campos essenciais
      Consistência   = 10 x (registros sem incoerência lógica) - 1 por regra fixa
      Integridade    = 10 - 10 x (duplicados) - 5 x (trajetos impossíveis)
                       - 1 se faltar a chave da entrega
      Confiabilidade = 10 - 2 por sinal de dado sintético (distribuições
                       uniformes, zero outliers, geografia impossível, regra fixa)
      Padronização   = 10 - 10 x (falhas de formato) - 2 se houver colunas sem
                       unidade - 1 se houver texto pseudo-nulo
      Utilidade      = 2 + 8 x (colunas com relação real ao atraso / candidatas),
                       com regras fixas contando metade
    """
    rel.titulo(15, "Notas de qualidade",
               "avaliação de 0 a 10 em seis dimensões, calculada por fórmulas fixas.")
    total = len(df)
    preenchidas = 1 - (bruto.apply(lambda c: c.str.strip() == "").to_numpy().mean())
    completude = 10 * preenchidas - (2 if integ["ausentes"] else 0)

    logicas = ["motivo_contraditorio", "motivo_transito_incoerente", "atrasada_sem_motivo"]
    incoerentes = flags[[f"problema_{n}" for n in logicas if f"problema_{n}" in flags]].any(axis=1)
    consistencia = 10 * (1 - incoerentes.mean()) - len(coer["deterministicas"])

    duplicados = df.duplicated().mean()
    integridade = (10 - 10 * duplicados - 5 * integ["taxa_trajeto_impossivel"]
                   - (1 if "ID da entrega" in integ["ausentes"] else 0))

    sinais = sum([len(dist["uniformes"]) >= len(dist["numericas"]) / 2,
                  len(dist["sem_outliers"]) == len(dist["numericas"]),
                  integ["taxa_trajeto_impossivel"] > 0.2,
                  bool(coer["deterministicas"])])
    confiabilidade = 10 - 2 * sinais

    pseudo = bruto.apply(lambda c: c.str.strip().str.casefold().isin(TEXTOS_PSEUDO_NULOS)).any().any()
    falhas_formato = flags["problema_formato"].mean() if "problema_formato" in flags else 0
    padronizacao = 10 - 10 * falhas_formato - (2 if integ["sem_unidade"] else 0) - (1 if pseudo else 0)

    candidatas = [c for c, r in ESQUEMA.items()
                  if r["grupo"] not in ("identificação", "alvo") and not r.get("pos_evento")]
    uteis = len(atrasos["uteis_numericas"]) + sum(
        0.5 if c in coer["deterministicas"] else 1 for c in atrasos["uteis_categoricas"])
    utilidade = 2 + 8 * uteis / len(candidatas)

    notas = {"Completude": completude, "Consistência": consistencia, "Integridade": integridade,
             "Confiabilidade": confiabilidade, "Padronização": padronizacao,
             "Utilidade analítica": utilidade}
    notas = {k: round(min(10, max(0, v)), 1) for k, v in notas.items()}
    for nome, valor in notas.items():
        barra = "#" * int(round(valor)) + "." * (10 - int(round(valor)))
        rel.escrever(f"   {nome:<20} {numero(valor, 1):>4}  [{barra}]")
    media = round(sum(notas.values()) / len(notas), 1)
    rel.escrever(f"   {'NOTA GERAL':<20} {numero(media, 1):>4}")
    notas["Geral"] = media
    return notas


def alertas_detalhados(rel: Relatorio) -> None:
    """
    Explica cada problema com as cinco informações exigidas pela auditoria:
    onde está, a causa, o impacto, a correção e os registros afetados.
    """
    rel.titulo(16, "Alertas detalhados",
               "cada problema encontrado, do mais grave ao menos grave, com causa, impacto e correção.")
    contagem = {g: 0 for g in GRAVIDADES}
    for alerta in sorted(rel.alertas, key=lambda a: (GRAVIDADES[a.gravidade], a.codigo)):
        contagem[alerta.gravidade] += 1
        rel.escrever(f"\n   [{alerta.gravidade}] {alerta.codigo} - {alerta.titulo}")
        rel.escrever(f"     Onde:     {alerta.onde}")
        rel.escrever(f"     Causa:    {alerta.causa}")
        rel.escrever(f"     Impacto:  {alerta.impacto}")
        rel.escrever(f"     Correção: {alerta.correcao}")
        if alerta.areas:
            rel.escrever(f"     Afeta:    {', '.join(alerta.areas)}")
    rel.escrever("\n   Resumo: " + ", ".join(f"{numero(n)} {g.lower()}" for g, n in contagem.items() if n))


# =============================================================================
# 10. ARQUIVOS DE SAÍDA
# =============================================================================

def proteger_para_planilha(df: pd.DataFrame) -> pd.DataFrame:
    """
    Evita "injeção de fórmula" ao abrir o CSV no Excel ou no Google Sheets.

    Problema evitado (segurança): um texto que começa com =, +, - ou @ é
    interpretado como fórmula pela planilha e pode executar comandos. Esses
    textos recebem um apóstrofo no início, que a planilha mostra como texto.
    Só colunas de texto são tratadas, para não alterar números negativos.
    """
    seguro = df.copy()
    for coluna in seguro.columns:
        if seguro[coluna].dtype == object or str(seguro[coluna].dtype) in ("str", "string", "category"):
            texto = seguro[coluna].astype(str)
            perigoso = texto.str.match(r"^[=+\-@\t\r]")
            seguro[coluna] = texto.where(~perigoso, "'" + texto)
    return seguro


def dataset_tratado(df: pd.DataFrame, flags: pd.DataFrame) -> pd.DataFrame:
    """
    Cria uma versão tratada da base, sem alterar o arquivo original.

    Correções aplicadas:
      - Motivo_Tratado (E1, E4): 'Sem atraso' quando o atraso é 0;
        'Desconhecido' quando há atraso sem motivo; motivo original nos demais.
      - Colunas de tradução para exibição em português.
      - Marcas de problema por registro, para filtrar ou investigar.
    A coluna original é mantida para que a correção possa ser conferida.
    """
    tratado = df.copy()
    motivo = tratado["Logistics_Delay_Reason"].astype(str)
    tratado["Motivo_Tratado"] = np.select(
        [tratado[ALVO] == 0, motivo == "None"],
        ["Sem atraso", "Desconhecido"],
        default=motivo.map(TRADUCOES["Logistics_Delay_Reason"]).fillna(motivo))
    for coluna, mapa in TRADUCOES.items():
        tratado[f"{coluna}_PT"] = tratado[coluna].astype(str).map(mapa)
    return pd.concat([tratado, flags], axis=1)


def salvar_saidas(pasta: Path, rel: Relatorio, df: pd.DataFrame, flags: pd.DataFrame,
                  colunas: pd.DataFrame) -> list:
    """Grava os arquivos de resultado na pasta outputs/."""
    pasta.mkdir(parents=True, exist_ok=True)
    arquivos = []

    caminho = pasta / "dataset_tratado.csv"
    proteger_para_planilha(dataset_tratado(df, flags)).to_csv(caminho, index=False, encoding="utf-8-sig")
    arquivos.append((caminho, "base com motivo corrigido, traduções e marcas de problema"))

    caminho = pasta / "registros_problematicos.csv"
    problematicos = pd.concat([df, flags], axis=1)
    problematicos = problematicos[problematicos["qtd_problemas"] > 0]
    proteger_para_planilha(problematicos).to_csv(caminho, index=False, encoding="utf-8-sig")
    arquivos.append((caminho, f"{numero(len(problematicos))} registros com pelo menos um problema"))

    caminho = pasta / "dicionario_dados.csv"
    dicionario = pd.DataFrame([{
        "coluna": c, "nome_pt": r["nome"], "tipo": r["tipo"], "grupo": r["grupo"],
        "descricao": r["descricao"], "unidade": r["unidade"] or "A CONFIRMAR",
        "minimo": r.get("min", ""), "maximo": r.get("max", ""),
        "valores_permitidos": ", ".join(sorted(map(str, r.get("valores", [])))),
        "pos_evento": "sim" if r.get("pos_evento") else "não"} for c, r in ESQUEMA.items()])
    proteger_para_planilha(dicionario).to_csv(caminho, index=False, encoding="utf-8-sig")
    arquivos.append((caminho, "significado, tipo, unidade e limites de cada coluna"))

    caminho = pasta / "qualidade_colunas.csv"
    proteger_para_planilha(colunas).to_csv(caminho, index=False, encoding="utf-8-sig")
    arquivos.append((caminho, "situação e problemas de cada coluna"))

    caminho = pasta / "relatorio_auditoria.txt"
    arquivos.append((caminho, "este relatório completo"))
    return arquivos


# =============================================================================
# 11. PROGRAMA PRINCIPAL
# =============================================================================

def argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Auditoria e análise do dataset de logística (saída em português).")
    parser.add_argument("--arquivo", type=Path, default=ARQUIVO_PADRAO,
                        help="caminho do CSV (padrão: smart_logistics_dataset.csv ao lado deste script)")
    parser.add_argument("--saida", type=Path, default=PASTA_SAIDA,
                        help="pasta onde os arquivos de resultado serão gravados (padrão: outputs/)")
    parser.add_argument("--sem-arquivos", action="store_true",
                        help="só mostra no terminal, sem gravar arquivos")
    parser.add_argument("--falhar-em-critico", action="store_true",
                        help="termina com código 1 se houver problema crítico (útil em automações)")
    return parser.parse_args()


def main() -> None:
    args = argumentos()
    rel = Relatorio()
    rel.escrever("AUDITORIA E ANÁLISE DO DATASET DE LOGÍSTICA")
    rel.escrever(f"Gerado em {pd.Timestamp.now():%d/%m/%Y %H:%M}")

    caminho = args.arquivo.expanduser().resolve()
    bruto, df, falhas = carregar(caminho, rel)

    verificar_estrutura(df, rel)
    marcas = {"vazio_ou_espaco": verificar_nulos(bruto, rel),
              "duplicado": verificar_duplicados(df, rel),
              "formato": verificar_tipos_formatos(bruto, df, falhas, rel),
              "categoria_invalida": verificar_categorias(bruto, df, rel),
              "fora_da_faixa": verificar_faixas(df, rel)}
    dist = verificar_outliers_distribuicao(df, rel)
    coer = verificar_coerencia(df, rel)
    integ = verificar_integridade(df, rel)
    marcas.update(coer["marcas"])
    marcas.update(integ["marcas"])
    # Regras fixas não são erro do registro em si; ficam fora da contagem por linha.
    marcas = {k: v for k, v in marcas.items() if not k.startswith("regra_fixa_")}

    atrasos = analisar_atrasos(df, coer["deterministicas"], rel)
    colunas = qualidade_por_coluna(df, bruto, dist, coer, integ, rel)
    flags = registros_problematicos(df, marcas, rel)
    riscos(rel, coer, atrasos)
    notas = notas_qualidade(df, bruto, dist, coer, integ, atrasos, flags, rel)
    alertas_detalhados(rel)

    criticos = [a for a in rel.alertas if a.gravidade == "CRÍTICO"]
    rel.titulo(17, "Conclusão", "o resumo do que a auditoria e a análise mostraram.")
    rel.escrever(f"   - Nota geral de qualidade: {numero(notas['Geral'], 1)} de 10.")
    rel.escrever(f"   - Problemas críticos: {len(criticos)}; total de alertas: {len(rel.alertas)}.")
    rel.escrever(f"   - {pct(atrasos['taxa'])} dos registros têm atraso.")
    if coer["deterministicas"]:
        rel.escrever("   - Colunas que determinam o atraso por regra fixa ou vazamento: "
                     + ", ".join(nome_pt(c) for c in coer["deterministicas"]) + ".")
    rel.escrever(f"   - Colunas numéricas com relação real ao atraso: "
                 f"{', '.join(nome_pt(c) for c in atrasos['uteis_numericas']) or 'nenhuma'}.")
    if dist["uniformes"]:
        rel.escrever("   - Os dados têm sinais de serem sintéticos: use-os para estudo, não para "
                     "decisões reais.")

    if not args.sem_arquivos:
        arquivos = salvar_saidas(args.saida.expanduser().resolve(), rel, df, flags, colunas)
        rel.escrever("\n   Arquivos gerados:")
        for caminho_saida, descricao in arquivos:
            rel.escrever(f"     - {caminho_saida.name:<28} {descricao}")
        rel.escrever(f"   Pasta: {args.saida.expanduser().resolve()}")
        rel.salvar(args.saida.expanduser().resolve() / "relatorio_auditoria.txt")

    if args.falhar_em_critico and criticos:
        sys.exit(1)


# Só executa quando o arquivo é rodado diretamente (python src/analise.py),
# e não quando é importado por outro script ou por testes.
if __name__ == "__main__":
    main()
