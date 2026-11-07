"""
Geração de Gráficos das Métricas Estatísticas e de Negócio — Grupo 8 Smart Talent
==================================================================================
Gera visualizações gráficas de alta resolução sobre o dataset original da DataCo,
destacando as métricas estatísticas essenciais:
  1. Percentual de pedidos com prejuízo por categoria (Benefit < 0).
  2. Comparação Média vs. Mediana de Lucro (mostrando a assimetria dos negativos).
  3. Faturamento total acumulado pelas principais categorias de produtos.
  4. Dias reais vs. agendados de frete (gargalo logístico e quebra de SLA).
  5. Demonstração visual do Paradoxo de Simpson (Segmentos de clientes vs. Mercados).
  6. Frequência das taxas de desconto (destacando a moda em 0%).

Saídas salvas em: `outputs/graficos/`
"""

from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# Configurações de caminhos
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "DataCoSupplyChainDataset.csv"
OUTPUT_DIR = BASE_DIR / "outputs" / "graficos"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Estilo visual padronizado
plt.rcParams.update({
    "font.sans-serif": "DejaVu Sans",
    "font.family": "sans-serif",
    "figure.titlesize": 14,
    "axes.titlesize": 12,
    "axes.labelsize": 10,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "figure.autolayout": False,
})

# Paleta de cores semântica
COR_AZUL_PRINCIPAL = "#1d4ed8"
COR_AZUL_SECUNDARIO = "#60a5fa"
COR_VERMELHO_ALERTA = "#dc2626"
COR_VERDE_POSITIVO = "#16a34a"
COR_CINZA_NEUTRO = "#64748b"
COR_LARANJA = "#ea580c"


def carregar_dados():
    print(f"Carregando dataset de: {DATA_PATH.resolve()}")
    df = pd.read_csv(DATA_PATH, encoding="latin-1")
    df["Categoria"] = df["Category Name"].astype(str).str.strip()
    return df


def grafico_01_prejuizo_por_categoria(df):
    """Gráfico 1: Categorias com maior proporção de vendas no prejuízo."""
    taxa_neg = df.groupby("Categoria")["Benefit per order"].agg(
        total="count",
        pct_neg=lambda x: (x < 0).mean() * 100
    ).query("total >= 50").sort_values("pct_neg", ascending=True).tail(12)

    media_global = (df["Benefit per order"] < 0).mean() * 100

    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
    barras = ax.barh(taxa_neg.index, taxa_neg["pct_neg"], color=COR_VERMELHO_ALERTA, alpha=0.88, edgecolor="none", height=0.65)

    ax.axvline(media_global, color=COR_CINZA_NEUTRO, linestyle="--", linewidth=1.5, label=f"Média Geral da Empresa ({media_global:.1f}%)")

    # Valores nas barras
    for bar in barras:
        w = bar.get_width()
        ax.annotate(f"{w:.1f}%",
                    xy=(w, bar.get_y() + bar.get_height() / 2),
                    xytext=(5, 0), textcoords="offset points",
                    ha="left", va="center", fontsize=9, fontweight="bold", color="#1e293b")

    ax.set_xlim(0, max(taxa_neg["pct_neg"]) * 1.15)
    ax.set_title("Categorias com Maior Proporção de Pedidos com Prejuízo Líquido\n(Benefit per order < 0)", fontweight="bold", pad=12)
    ax.set_xlabel("Percentual de Pedidos com Prejuízo (%)")
    ax.legend(loc="lower right", frameon=True)
    ax.grid(axis="x", linestyle=":", alpha=0.6)

    fig.tight_layout()
    destino = OUTPUT_DIR / "01_prejuizo_por_categoria.png"
    fig.savefig(destino)
    plt.close(fig)
    print(f"  [OK] Gráfico 1 salvo: {destino.name}")


def grafico_02_media_vs_mediana_lucro(df):
    """Gráfico 2: Média vs Mediana de Lucro demonstrando a distorção das perdas."""
    analise = df.groupby("Categoria")["Benefit per order"].agg(
        total="count",
        pct_neg=lambda x: (x < 0).mean() * 100,
        media="mean",
        mediana="median"
    ).query("total >= 100").sort_values("pct_neg", ascending=False).head(10).iloc[::-1]

    y = np.arange(len(analise))
    altura = 0.35

    fig, ax = plt.subplots(figsize=(10, 6.5), dpi=150)
    b1 = ax.barh(y + altura/2, analise["mediana"], height=altura, color=COR_VERDE_POSITIVO, alpha=0.9, label="Mediana (Pedido Típico)")
    b2 = ax.barh(y - altura/2, analise["media"], height=altura, color=COR_AZUL_PRINCIPAL, alpha=0.85, label="Média (Puxada para baixo pelas perdas)")

    ax.set_yticks(y)
    ax.set_yticklabels(analise.index)
    ax.set_title("A Média Esconde o Prejuízo: Comparação Mediana vs. Média de Lucro por Pedido", fontweight="bold", pad=12)
    ax.set_xlabel("Lucro por Pedido (US$)")
    ax.legend(loc="lower right", frameon=True)
    ax.grid(axis="x", linestyle=":", alpha=0.6)

    # Rótulo de valores
    for bar in b1:
        w = bar.get_width()
        ax.annotate(f"${w:.1f}", xy=(w, bar.get_y() + bar.get_height()/2), xytext=(4, 0), textcoords="offset points", va="center", fontsize=8)
    for bar in b2:
        w = bar.get_width()
        ax.annotate(f"${w:.1f}", xy=(w, bar.get_y() + bar.get_height()/2), xytext=(4, 0), textcoords="offset points", va="center", fontsize=8, color="#1e3a8a", fontweight="bold")

    fig.tight_layout()
    destino = OUTPUT_DIR / "02_media_vs_mediana_lucro.png"
    fig.savefig(destino)
    plt.close(fig)
    print(f"  [OK] Gráfico 2 salvo: {destino.name}")


def grafico_03_faturamento_top_categorias(df):
    """Gráfico 3: Top categorias por faturamento acumulado."""
    vendas = df.groupby("Categoria")["Sales"].sum().sort_values(ascending=False).head(10).iloc[::-1]
    vendas_milhoes = vendas / 1e6

    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
    barras = ax.barh(vendas_milhoes.index, vendas_milhoes.values, color=COR_AZUL_PRINCIPAL, height=0.65, alpha=0.9)

    for bar in barras:
        w = bar.get_width()
        ax.annotate(f"${w:.2f}M",
                    xy=(w, bar.get_y() + bar.get_height() / 2),
                    xytext=(5, 0), textcoords="offset points",
                    ha="left", va="center", fontsize=9, fontweight="bold")

    ax.set_xlim(0, max(vendas_milhoes.values) * 1.15)
    ax.set_title("Concentração de Receita: Top 10 Categorias com Maior Faturamento Bruto Acumulado", fontweight="bold", pad=12)
    ax.set_xlabel("Faturamento Total Acumulado (Milhões de US$)")
    ax.grid(axis="x", linestyle=":", alpha=0.6)

    fig.tight_layout()
    destino = OUTPUT_DIR / "03_faturamento_top_categorias.png"
    fig.savefig(destino)
    plt.close(fig)
    print(f"  [OK] Gráfico 3 salvo: {destino.name}")


def grafico_04_dias_envio_real_vs_agendado(df):
    """Gráfico 4: Descompasso entre prazo prometido e entrega real."""
    envio = df.groupby("Shipping Mode")[["Days for shipment (scheduled)", "Days for shipping (real)"]].mean().reset_index()

    x = np.arange(len(envio))
    largura = 0.35

    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=150)
    b_agendado = ax.bar(x - largura/2, envio["Days for shipment (scheduled)"], width=largura, color=COR_CINZA_NEUTRO, alpha=0.85, label="Prazo Agendado (Promessa)")
    b_real = ax.bar(x + largura/2, envio["Days for shipping (real)"], width=largura, color=COR_LARANJA, alpha=0.9, label="Prazo Real (Média Entregue)")

    ax.set_xticks(x)
    ax.set_xticklabels(envio["Shipping Mode"], fontweight="bold")
    ax.set_ylabel("Média de Dias")
    ax.set_title("Gargalo Logístico: Dias Reais vs. Dias Prometidos por Modalidade de Frete", fontweight="bold", pad=12)
    ax.legend(loc="upper left", frameon=True)
    ax.grid(axis="y", linestyle=":", alpha=0.6)
    ax.set_ylim(0, 5)

    for bar in b_agendado:
        h = bar.get_height()
        ax.annotate(f"{h:.1f}d", xy=(bar.get_x() + bar.get_width()/2, h), xytext=(0, 3), textcoords="offset points", ha="center", fontsize=9)
    for bar in b_real:
        h = bar.get_height()
        ax.annotate(f"{h:.2f}d", xy=(bar.get_x() + bar.get_width()/2, h), xytext=(0, 3), textcoords="offset points", ha="center", fontsize=9, fontweight="bold", color="#9a3412")

    fig.tight_layout()
    destino = OUTPUT_DIR / "04_dias_envio_real_vs_agendado.png"
    fig.savefig(destino)
    plt.close(fig)
    print(f"  [OK] Gráfico 4 salvo: {destino.name}")


def grafico_05_paradoxo_simpson(df):
    """Gráfico 5: O Paradoxo de Simpson nos Segmentos de Cliente (Global vs LATAM e África)."""
    global_profit = df.groupby("Customer Segment")["Benefit per order"].mean()
    latam_profit = df[df["Market"] == "LATAM"].groupby("Customer Segment")["Benefit per order"].mean()
    africa_profit = df[df["Market"] == "Africa"].groupby("Customer Segment")["Benefit per order"].mean()

    segmentos = ["Consumer", "Corporate", "Home Office"]
    x = np.arange(len(segmentos))
    largura = 0.25

    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
    b_global = ax.bar(x - largura, [global_profit[s] for s in segmentos], width=largura, color=COR_AZUL_PRINCIPAL, alpha=0.9, label="Global (Consumer lidera: $22.18)")
    b_latam = ax.bar(x, [latam_profit[s] for s in segmentos], width=largura, color=COR_VERDE_POSITIVO, alpha=0.9, label="LATAM (Corporate lidera: $22.33)")
    b_africa = ax.bar(x + largura, [africa_profit[s] for s in segmentos], width=largura, color=COR_LARANJA, alpha=0.9, label="África (Home Office lidera: $22.47)")

    ax.set_xticks(x)
    ax.set_xticklabels(segmentos, fontweight="bold")
    ax.set_ylabel("Lucro Médio por Pedido (US$)")
    ax.set_title("Paradoxo de Simpson: O Segmento Mais Lucrativo Globalmente Inverte nos Mercados Locais", fontweight="bold", pad=12)
    ax.set_ylim(19, 23.5)
    ax.legend(loc="upper right", frameon=True)
    ax.grid(axis="y", linestyle=":", alpha=0.6)

    for bar in b_global:
        h = bar.get_height()
        ax.annotate(f"${h:.2f}", xy=(bar.get_x() + bar.get_width()/2, h), xytext=(0, 3), textcoords="offset points", ha="center", fontsize=8)
    for bar in b_latam:
        h = bar.get_height()
        ax.annotate(f"${h:.2f}", xy=(bar.get_x() + bar.get_width()/2, h), xytext=(0, 3), textcoords="offset points", ha="center", fontsize=8, fontweight="bold", color="#15803d")
    for bar in b_africa:
        h = bar.get_height()
        ax.annotate(f"${h:.2f}", xy=(bar.get_x() + bar.get_width()/2, h), xytext=(0, 3), textcoords="offset points", ha="center", fontsize=8, fontweight="bold", color="#c2410c")

    fig.tight_layout()
    destino = OUTPUT_DIR / "05_paradoxo_simpson_segmentos.png"
    fig.savefig(destino)
    plt.close(fig)
    print(f"  [OK] Gráfico 5 salvo: {destino.name}")


def grafico_06_prejuizo_acumulado_dolares(df):
    """Gráfico 6: Top categorias com maior prejuízo financeiro acumulado em dólares."""
    neg = df[df["Benefit per order"] < 0]
    perdas = neg.groupby("Categoria")["Benefit per order"].agg(
        total_prejuizo=lambda x: abs(x.sum()),
        pedidos_prejuizo="count"
    ).sort_values("total_prejuizo", ascending=False).head(10).iloc[::-1]

    perdas_milhares = perdas["total_prejuizo"] / 1e3

    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
    barras = ax.barh(perdas_milhares.index, perdas_milhares.values, color=COR_VERMELHO_ALERTA, alpha=0.9, height=0.65)

    for bar in barras:
        w = bar.get_width()
        ax.annotate(f"-${w:.1f}k",
                    xy=(w, bar.get_y() + bar.get_height() / 2),
                    xytext=(5, 0), textcoords="offset points",
                    ha="left", va="center", fontsize=9, fontweight="bold", color="#7f1d1d")

    ax.set_xlim(0, max(perdas_milhares.values) * 1.15)
    ax.set_title("Onde a Empresa Mais Queima Caixa: Top 10 Categorias por Prejuízo Acumulado\n(Total em Milhares de US$)", fontweight="bold", pad=12)
    ax.set_xlabel("Prejuízo Financeiro Total Acumulado (Milhares de US$)")
    ax.grid(axis="x", linestyle=":", alpha=0.6)

    fig.tight_layout()
    destino = OUTPUT_DIR / "06_prejuizo_acumulado_dolares.png"
    fig.savefig(destino)
    plt.close(fig)
    print(f"  [OK] Gráfico 6 salvo: {destino.name}")


def main():
    print("=" * 70)
    print("GERANDO GRÁFICOS DAS MÉTRICAS ESTATÍSTICAS E DE NEGÓCIO")
    print("=" * 70)
    df = carregar_dados()
    grafico_01_prejuizo_por_categoria(df)
    grafico_02_media_vs_mediana_lucro(df)
    grafico_03_faturamento_top_categorias(df)
    grafico_04_dias_envio_real_vs_agendado(df)
    grafico_05_paradoxo_simpson(df)
    grafico_06_prejuizo_acumulado_dolares(df)
    print("=" * 70)
    print(f"Todos os 6 gráficos foram gerados e salvos com sucesso em:\n{OUTPUT_DIR.resolve()}")
    print("=" * 70)


if __name__ == "__main__":
    main()
