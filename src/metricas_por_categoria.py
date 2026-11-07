"""
Script de Estatísticas Descritivas por Categoria — Grupo 8 Smart Talent
========================================================================
Calcula métricas detalhadas (média, mediana, moda, desvio padrão, quartis,
contagem de nulos e valores negativos) sobre o DATASET ORIGINAL da DataCo,
incluindo as 8 novas variáveis de peso e dimensões das embalagens.

Uso:
    python src/metricas_por_categoria.py
"""

from pathlib import Path
import argparse
import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = BASE_DIR / "data" / "DataCoSupplyChainDataset.csv"
DEFAULT_OUTPUT_DIR = BASE_DIR / "outputs" / "metricas_categoria"

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
    "Package Length (cm)",           # Comprimento da embalagem (cm)
    "Package Width (cm)",            # Largura da embalagem (cm)
    "Package Height (cm)",           # Altura da embalagem (cm)
    "Package Volume (cm3)",          # Volume unitário da embalagem (cm³)
    "Product Net Weight (kg)",       # Peso líquido do produto (kg)
    "Package Gross Weight (kg)",     # Peso bruto unitário com embalagem (kg)
    "Order Item Gross Weight (kg)",  # Peso bruto total do item no pedido (kg)
    "Order Item Volume (cm3)",       # Volume total do item no pedido (cm³)
]


def calcular_moda(series: pd.Series):
    valid = series.dropna()
    if valid.empty:
        return np.nan
    m = valid.mode()
    return m.iloc[0] if not m.empty else np.nan


def calcular_metricas_serie(series: pd.Series) -> dict:
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
    linhas = []
    df["Categoria"] = df["Category Name"].astype(str).str.strip()
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
    return sub[colunas_exibir].sort_values(ordenar_por, ascending=ascending)


def main():
    parser = argparse.ArgumentParser(description="Calcula métricas estatísticas por categoria sobre o dataset original DataCo.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Caminho do CSV DataCo original.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Diretório onde salvar os relatórios CSV.")
    parser.add_argument("--top", type=int, default=10, help="Quantidade de categorias para destacar no terminal.")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_path, encoding="latin-1")
    print(f"Total de registros carregados: {len(df):,} linhas x {df.shape[1]} colunas")

    df_metricas = gerar_relatorio_completo(df, COLUNAS_ANALISE)
    arquivo_completo = output_dir / "metricas_completas_por_categoria.csv"
    df_metricas.to_csv(arquivo_completo, index=False, encoding="utf-8-sig")

    resumo_lucro = gerar_tabela_resumo_especifica(df_metricas, "Benefit per order", "pct_negativos", False)
    resumo_lucro.to_csv(output_dir / "resumo_lucro_negativos_por_categoria.csv", index=False, encoding="utf-8-sig")

    resumo_vendas = gerar_tabela_resumo_especifica(df_metricas, "Sales", "soma_total", False)
    resumo_vendas.to_csv(output_dir / "resumo_vendas_por_categoria.csv", index=False, encoding="utf-8-sig")

    resumo_desconto = gerar_tabela_resumo_especifica(df_metricas, "Order Item Discount", "media", False)
    resumo_desconto.to_csv(output_dir / "resumo_descontos_por_categoria.csv", index=False, encoding="utf-8-sig")

    resumo_envio = gerar_tabela_resumo_especifica(df_metricas, "Days for shipping (real)", "media", False)
    resumo_envio.to_csv(output_dir / "resumo_dias_envio_por_categoria.csv", index=False, encoding="utf-8-sig")

    resumo_peso = gerar_tabela_resumo_especifica(df_metricas, "Order Item Gross Weight (kg)", "soma_total", False)
    resumo_peso.to_csv(output_dir / "resumo_peso_por_categoria.csv", index=False, encoding="utf-8-sig")

    print("Relatórios CSV atualizados com sucesso em:", output_dir.resolve())


if __name__ == "__main__":
    main()
