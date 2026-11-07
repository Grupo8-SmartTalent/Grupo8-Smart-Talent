"""
Script de Estatísticas Descritivas por Categoria — Grupo 8 Smart Talent
========================================================================
Calcula métricas detalhadas (média, mediana, moda, desvio padrão, quartis,
contagem de nulos e valores negativos) sobre o DATASET ORIGINAL da DataCo,
preservando valores reais, negativos e ausentes para apoiar a análise crítica.

Uso:
    python src/metricas_por_categoria.py
    python src/metricas_por_categoria.py --input data/DataCoSupplyChainDataset.csv --output-dir outputs/metricas_categoria
"""

from pathlib import Path
import argparse
import numpy as np
import pandas as pd


# Diretórios padrão
BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = BASE_DIR / "data" / "DataCoSupplyChainDataset.csv"
DEFAULT_OUTPUT_DIR = BASE_DIR / "outputs" / "metricas_categoria"

# Colunas numéricas essenciais do dataset original para análise por categoria
COLUNAS_ANALISE = [
    "Benefit per order",             # Lucro líquido por pedido (contém negativos críticos)
    "Order Item Profit Ratio",       # Margem de lucro (taxa percentual, contém negativos)
    "Sales",                         # Vendas brutas
    "Order Item Total",              # Venda líquida faturada (pós-desconto)
    "Order Item Discount",           # Valor de desconto em $
    "Order Item Discount Rate",      # Taxa de desconto concedida
    "Order Item Product Price",      # Preço unitário do produto
    "Order Item Quantity",           # Quantidade de itens por pedido
    "Days for shipping (real)",      # Dias reais de envio
    "Days for shipment (scheduled)", # Dias agendados para entrega
    "Late_delivery_risk",            # Risco de atraso (0 ou 1)
]


def calcular_moda(series: pd.Series):
    """Calcula a moda principal da série, lidando com nulos e séries vazias."""
    valid = series.dropna()
    if valid.empty:
        return np.nan
    m = valid.mode()
    return m.iloc[0] if not m.empty else np.nan


def calcular_metricas_serie(series: pd.Series) -> dict:
    """Calcula todas as métricas descritivas para uma série numérica."""
    total = len(series)
    valid = series.dropna()
    valid_count = len(valid)
    nulls = total - valid_count
    nulls_pct = (nulls / total * 100.0) if total > 0 else 0.0

    if valid_count == 0:
        return {
            "total_registros": total,
            "qtd_nulos": nulls,
            "pct_nulos": nulls_pct,
            "qtd_negativos": 0,
            "pct_negativos": 0.0,
            "qtd_zeros": 0,
            "pct_zeros": 0.0,
            "media": np.nan,
            "mediana": np.nan,
            "moda": np.nan,
            "desvio_padrao": np.nan,
            "minimo": np.nan,
            "q25": np.nan,
            "q75": np.nan,
            "iqr": np.nan,
            "maximo": np.nan,
            "assimetria_skew": np.nan,
            "soma_total": np.nan,
        }

    negativos = (valid < 0).sum()
    negativos_pct = (negativos / valid_count * 100.0)
    zeros = (valid == 0).sum()
    zeros_pct = (zeros / valid_count * 100.0)

    q25 = valid.quantile(0.25)
    q75 = valid.quantile(0.75)

    return {
        "total_registros": total,
        "qtd_nulos": nulls,
        "pct_nulos": round(nulls_pct, 2),
        "qtd_negativos": int(negativos),
        "pct_negativos": round(negativos_pct, 2),
        "qtd_zeros": int(zeros),
        "pct_zeros": round(zeros_pct, 2),
        "media": round(float(valid.mean()), 2),
        "mediana": round(float(valid.median()), 2),
        "moda": round(float(calcular_moda(valid)), 2),
        "desvio_padrao": round(float(valid.std()), 2) if valid_count > 1 else 0.0,
        "minimo": round(float(valid.min()), 2),
        "q25": round(float(q25), 2),
        "q75": round(float(q75), 2),
        "iqr": round(float(q75 - q25), 2),
        "maximo": round(float(valid.max()), 2),
        "assimetria_skew": round(float(valid.skew()), 2) if valid_count > 2 else 0.0,
        "soma_total": round(float(valid.sum()), 2),
    }


def gerar_relatorio_completo(df: pd.DataFrame, colunas: list[str]) -> pd.DataFrame:
    """Gera tabela completa com métricas de cada coluna numérica por Categoria."""
    linhas = []
    
    # Preserva o nome original da categoria removendo apenas espaços soltos nas pontas
    df["Categoria"] = df["Category Name"].astype(str).str.strip()
    
    # Adiciona Departamento associado para contexto adicional
    dept_map = df.groupby("Categoria")["Department Name"].agg(lambda x: x.str.strip().mode().iloc[0]).to_dict()

    grupos = df.groupby("Categoria")

    for cat_name, grupo in grupos:
        dept = dept_map.get(cat_name, "N/A")
        for col in colunas:
            if col not in grupo.columns:
                continue
            metricas = calcular_metricas_serie(grupo[col])
            registro = {
                "Categoria": cat_name,
                "Departamento": dept,
                "Variavel": col,
                **metricas,
            }
            linhas.append(registro)

    return pd.DataFrame(linhas)


def gerar_tabela_resumo_especifica(df_completo: pd.DataFrame, variavel: str, ordenar_por: str = "media", ascending: bool = False) -> pd.DataFrame:
    """Extrai uma visão comparativa de uma variável específica entre as categorias."""
    sub = df_completo[df_completo["Variavel"] == variavel].copy()
    colunas_exibir = [
        "Categoria",
        "Departamento",
        "total_registros",
        "qtd_negativos",
        "pct_negativos",
        "media",
        "mediana",
        "moda",
        "desvio_padrao",
        "minimo",
        "q25",
        "q75",
        "maximo",
        "soma_total",
    ]
    sub = sub[colunas_exibir].sort_values(ordenar_por, ascending=ascending)
    return sub


def main():
    parser = argparse.ArgumentParser(description="Calcula métricas estatísticas por categoria sobre o dataset original DataCo.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Caminho do CSV DataCo original.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Diretório onde salvar os relatórios CSV.")
    parser.add_argument("--top", type=int, default=10, help="Quantidade de categorias para destacar no terminal.")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("ESTATÍSTICAS DESCRITIVAS POR CATEGORIA (DATASET ORIGINAL)")
    print("=" * 80)
    print(f"Lendo dataset bruto de: {input_path.resolve()}")
    if not input_path.exists():
        raise FileNotFoundError(f"Arquivo de dados não encontrado: {input_path}")

    df = pd.read_csv(input_path, encoding="latin-1")
    print(f"Total de registros carregados: {len(df):,} linhas x {df.shape[1]} colunas\n")

    # 1. Gerar tabela completa com todas as métricas
    print("Calculando média, mediana, moda, desvio padrão, nulos e valores negativos...")
    df_metricas = gerar_relatorio_completo(df, COLUNAS_ANALISE)

    # 2. Salvar tabela detalhada completa
    arquivo_completo = output_dir / "metricas_completas_por_categoria.csv"
    df_metricas.to_csv(arquivo_completo, index=False, encoding="utf-8-sig")
    print(f"-> Relatório completo salvo em: {arquivo_completo.resolve()}")

    # 3. Gerar e salvar resumos específicos para análise de negócio
    # A) Lucro Líquido (Benefit per order) — Crucial para identificar pedidos com prejuízo
    resumo_lucro = gerar_tabela_resumo_especifica(df_completo=df_metricas, variavel="Benefit per order", ordenar_por="pct_negativos", ascending=False)
    arquivo_lucro = output_dir / "resumo_lucro_negativos_por_categoria.csv"
    resumo_lucro.to_csv(arquivo_lucro, index=False, encoding="utf-8-sig")

    # B) Vendas Totais (Sales)
    resumo_vendas = gerar_tabela_resumo_especifica(df_completo=df_metricas, variavel="Sales", ordenar_por="soma_total", ascending=False)
    arquivo_vendas = output_dir / "resumo_vendas_por_categoria.csv"
    resumo_vendas.to_csv(arquivo_vendas, index=False, encoding="utf-8-sig")

    # C) Descontos Concedidos (Order Item Discount)
    resumo_desconto = gerar_tabela_resumo_especifica(df_completo=df_metricas, variavel="Order Item Discount", ordenar_por="media", ascending=False)
    arquivo_desconto = output_dir / "resumo_descontos_por_categoria.csv"
    resumo_desconto.to_csv(arquivo_desconto, index=False, encoding="utf-8-sig")

    # D) Dias de Envio Real (Days for shipping (real))
    resumo_envio = gerar_tabela_resumo_especifica(df_completo=df_metricas, variavel="Days for shipping (real)", ordenar_por="media", ascending=False)
    arquivo_envio = output_dir / "resumo_dias_envio_por_categoria.csv"
    resumo_envio.to_csv(arquivo_envio, index=False, encoding="utf-8-sig")

    print(f"-> Resumo de Lucro & Prejuízos salvo em: {arquivo_lucro.resolve()}")
    print(f"-> Resumo de Vendas Totais salvo em:     {arquivo_vendas.resolve()}")
    print(f"-> Resumo de Descontos salvo em:          {arquivo_desconto.resolve()}")
    print(f"-> Resumo de Prazos de Envio salvo em:   {arquivo_envio.resolve()}\n")

    # 4. Apresentação amigável dos principais insights no terminal
    print("=" * 80)
    print(f"TOP {args.top} CATEGORIAS COM MAIOR PERCENTUAL DE PREJUÍZO (Benefit per order < 0)")
    print("=" * 80)
    print("Por que a mediana difere da média? A média é puxada para baixo pelos prejuízos extremos.")
    cols_lucro_view = ["Categoria", "Departamento", "total_registros", "pct_negativos", "minimo", "q25", "mediana", "media", "moda"]
    print(resumo_lucro[cols_lucro_view].head(args.top).to_string(index=False))

    print("\n" + "=" * 80)
    print(f"TOP {args.top} CATEGORIAS COM MAIOR FATURAMENTO TOTAL (Sales)")
    print("=" * 80)
    cols_vendas_view = ["Categoria", "Departamento", "total_registros", "media", "mediana", "moda", "desvio_padrao", "maximo", "soma_total"]
    print(resumo_vendas[cols_vendas_view].head(args.top).to_string(index=False))

    print("\n" + "=" * 80)
    print(f"TOP {args.top} CATEGORIAS COM MAIOR DIAS MÉDIOS DE ENVIO (Days for shipping (real))")
    print("=" * 80)
    cols_envio_view = ["Categoria", "Departamento", "total_registros", "media", "mediana", "moda", "minimo", "maximo"]
    print(resumo_envio[cols_envio_view].head(args.top).to_string(index=False))
    print("=" * 80)


if __name__ == "__main__":
    main()
