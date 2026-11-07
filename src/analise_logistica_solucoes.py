"""
Script de Diagnóstico Logístico, Rotas, Precificação e Demanda — Grupo 8 Smart Talent
=====================================================================================
Calcula métricas 100% baseadas nos dados reais dos datasets originais (sem valores
aleatórios ou constantes inventadas) para embasar a decisão entre:
  1. Construir/Contratar Centros de Distribuição (CDs) por Região e País comprador
  2. Otimizar Rotas e Reposicionar Itens no Estoque (Origem -> Destino)
  3. Mudar Meio de Transporte / Modalidade de Envio conforme Peso e Volume real
  4. Ajustar Preços e Descontos por Região e por Segmento de Consumidor
  5. Alinhar Estoque pela Demanda Real (Acessos/Cliques x Vendas x Toneladas)

Saídas salvas em: `outputs/solucoes_logisticas/`
"""

from pathlib import Path
import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
DATACO_PATH = BASE_DIR / "data" / "DataCoSupplyChainDataset.csv"
LOGS_PATH = BASE_DIR / "data" / "tokenized_access_logs.csv"
OUTPUT_DIR = BASE_DIR / "outputs" / "solucoes_logisticas"


def carregar_base_principal() -> pd.DataFrame:
    df = pd.read_csv(DATACO_PATH, encoding="latin-1")
    df["Product Name"] = df["Product Name"].astype(str).str.strip()
    df["Category Name"] = df["Category Name"].astype(str).str.strip()
    df["Department Name"] = df["Department Name"].astype(str).str.strip()
    df["Order Region"] = df["Order Region"].astype(str).str.strip()

    # Equação contábil exata presente nos dados: Receita Líquida - Lucro Líquido = Custo Operacional Total
    df["Custo_Operacional_Real"] = df["Order Item Total"] - df["Benefit per order"]
    df["Custo_Por_Kg"] = df["Custo_Operacional_Real"] / df["Order Item Gross Weight (kg)"]
    df["Pedido_Com_Prejuizo"] = df["Benefit per order"] < 0
    df["Atraso_Dias"] = (df["Days for shipping (real)"] - df["Days for shipment (scheduled)"]).clip(lower=0)

    # Classificação empírica baseada nos quartis/faixas reais de peso bruto do catálogo
    df["Classe_Peso_Volume"] = pd.cut(
        df["Package Gross Weight (kg)"],
        bins=[0, 1.0, 5.0, 20.0, 200.0],
        labels=[
            "1. Leve (<=1 kg)",
            "2. Medio (1-5 kg)",
            "3. Grande/Volumoso (5-20 kg)",
            "4. Extra-Pesado (>20 kg)",
        ],
    )
    return df


def analisar_transporte_e_porte(df: pd.DataFrame) -> pd.DataFrame:
    """1. Analisa o impacto do porte físico e modalidade de transporte nos custos e atrasos."""
    resumo = (
        df.groupby(["Classe_Peso_Volume", "Shipping Mode"], observed=False)
        .agg(
            pedidos=("Order Id", "count"),
            peso_bruto_medio_kg=("Order Item Gross Weight (kg)", "mean"),
            volume_medio_litros=("Order Item Volume (cm3)", lambda x: x.mean() / 1000.0),
            toneladas_totais=("Order Item Gross Weight (kg)", lambda x: x.sum() / 1000.0),
            volume_total_m3=("Order Item Volume (cm3)", lambda x: x.sum() / 1e6),
            preco_medio_produto=("Order Item Product Price", "mean"),
            receita_liquida_media=("Order Item Total", "mean"),
            custo_operacional_medio=("Custo_Operacional_Real", "mean"),
            lucro_liquido_medio=("Benefit per order", "mean"),
            prejuizo_acumulado=("Benefit per order", lambda x: x[x < 0].sum()),
            pct_pedidos_prejuizo=("Pedido_Com_Prejuizo", lambda x: x.mean() * 100.0),
            dias_prometidos=("Days for shipment (scheduled)", "mean"),
            dias_reais_media=("Days for shipping (real)", "mean"),
            pct_atraso=("Late_delivery_risk", lambda x: x.mean() * 100.0),
        )
        .reset_index()
        .round(2)
    )
    return resumo


def analisar_rotas_e_viabilidade_cd(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """2. Analisa as rotas (Origem -> Destino) e concentração por país comprador para decisão de CD."""
    rotas = (
        df.groupby(["Customer Country", "Customer State", "Market", "Order Region", "Order Country"])
        .agg(
            pedidos=("Order Id", "count"),
            unidades_vendidas=("Order Item Quantity", "sum"),
            toneladas_expedidas=("Order Item Gross Weight (kg)", lambda x: x.sum() / 1000.0),
            volume_m3=("Order Item Volume (cm3)", lambda x: x.sum() / 1e6),
            receita_liquida=("Order Item Total", "sum"),
            custo_operacional_total=("Custo_Operacional_Real", "sum"),
            lucro_liquido_total=("Benefit per order", "sum"),
            prejuizo_bruto=("Benefit per order", lambda x: x[x < 0].sum()),
            pct_pedidos_prejuizo=("Pedido_Com_Prejuizo", lambda x: x.mean() * 100.0),
            pct_atraso=("Late_delivery_risk", lambda x: x.mean() * 100.0),
            dias_envio_real=("Days for shipping (real)", "mean"),
        )
        .reset_index()
        .sort_values("pedidos", ascending=False)
        .round(2)
    )

    paises_cd = (
        df.groupby(["Market", "Order Region", "Order Country"])
        .agg(
            pedidos_totais=("Order Id", "count"),
            pedidos_vindos_de_porto_rico=("Customer Country", lambda x: (x == "Puerto Rico").sum()),
            toneladas_totais=("Order Item Gross Weight (kg)", lambda x: x.sum() / 1000.0),
            volume_total_m3=("Order Item Volume (cm3)", lambda x: x.sum() / 1e6),
            faturamento_bruto=("Sales", "sum"),
            receita_liquida=("Order Item Total", "sum"),
            custo_operacional=("Custo_Operacional_Real", "sum"),
            lucro_liquido=("Benefit per order", "sum"),
            prejuizo_bruto=("Benefit per order", lambda x: x[x < 0].sum()),
            pct_atraso=("Late_delivery_risk", lambda x: x.mean() * 100.0),
            pct_frete_expresso=(
                "Shipping Mode",
                lambda x: x.isin(["First Class", "Second Class", "Same Day"]).mean() * 100.0,
            ),
        )
        .reset_index()
        .sort_values("toneladas_totais", ascending=False)
        .round(2)
    )
    return rotas, paises_cd


def analisar_reposicionamento_itens(df: pd.DataFrame) -> pd.DataFrame:
    """3. Mapeia onde cada produto está estocado vs. onde é realmente demandado/comprado."""
    def top_val(s: pd.Series) -> str:
        vc = s.value_counts(normalize=True) * 100
        return f"{vc.index[0]} ({vc.iloc[0]:.1f}%)"

    prod_pos = (
        df.groupby(["Product Card Id", "Product Name", "Category Name", "Package Gross Weight (kg)", "Package Volume (cm3)"])
        .agg(
            pedidos=("Order Id", "count"),
            toneladas_totais=("Order Item Gross Weight (kg)", lambda x: x.sum() / 1000.0),
            volume_total_m3=("Order Item Volume (cm3)", lambda x: x.sum() / 1e6),
            pct_estoque_porto_rico=("Customer Country", lambda x: (x == "Puerto Rico").mean() * 100.0),
            principal_cidade_estoque=("Customer City", top_val),
            principal_mercado_comprador=("Market", top_val),
            principal_pais_comprador=("Order Country", top_val),
            vendas_brutas=("Sales", "sum"),
            custo_operacional=("Custo_Operacional_Real", "sum"),
            lucro_liquido=("Benefit per order", "sum"),
            prejuizo_bruto=("Benefit per order", lambda x: x[x < 0].sum()),
            pct_atraso=("Late_delivery_risk", lambda x: x.mean() * 100.0),
        )
        .reset_index()
        .sort_values("toneladas_totais", ascending=False)
        .round(2)
    )
    return prod_pos


def analisar_precos_regiao_consumidor(df: pd.DataFrame) -> pd.DataFrame:
    """4. Analisa preços, descontos, custos e rentabilidade por Mercado e Segmento de Consumidor."""
    precos_seg = (
        df.groupby(["Market", "Customer Segment"])
        .agg(
            pedidos=("Order Id", "count"),
            ticket_bruto_medio=("Sales", "mean"),
            desconto_medio_usd=("Order Item Discount", "mean"),
            taxa_desconto_media_pct=("Order Item Discount Rate", lambda x: x.mean() * 100.0),
            receita_liquida_media=("Order Item Total", "mean"),
            custo_operacional_medio=("Custo_Operacional_Real", "mean"),
            lucro_liquido_medio=("Benefit per order", "mean"),
            lucro_mediano=("Benefit per order", "median"),
            margem_liquida_media_pct=("Order Item Profit Ratio", lambda x: x.mean() * 100.0),
            pct_pedidos_prejuizo=("Pedido_Com_Prejuizo", lambda x: x.mean() * 100.0),
            prejuizo_acumulado=("Benefit per order", lambda x: x[x < 0].sum()),
            pct_atraso=("Late_delivery_risk", lambda x: x.mean() * 100.0),
        )
        .reset_index()
        .sort_values(["Market", "lucro_liquido_medio"], ascending=[True, False])
        .round(2)
    )
    return precos_seg


def analisar_demanda_acessos_vs_vendas(df: pd.DataFrame) -> pd.DataFrame:
    """5. Cruza a demanda de tráfego (tokenized_access_logs) com pedidos reais no período coincidente."""
    logs = pd.read_csv(LOGS_PATH, encoding="latin-1").drop_duplicates()
    logs["Product"] = logs["Product"].astype(str).str.strip().replace({
        "adidas Brazuca 2017 Official Match Ball": "adidas Brazuca 2014 Official Match Ball",
        "Top Flite Women's 2017 XL Hybrid": "Top Flite Women's 2014 XL Hybrid",
        "TaylorMade 2017 Purelite Stand Bag": "TaylorMade 2014 Purelite Stand Bag",
    })
    logs["add_to_cart"] = logs["url"].astype(str).str.contains("/add_to_cart", case=False, na=False)

    # Filtrar DataCo no exato período coberto pelos logs (01/09/2017 a 31/01/2018)
    df_dt = pd.to_datetime(df["order date (DateOrders)"], format="%m/%d/%Y %H:%M")
    df_periodo = df[(df_dt >= "2017-09-01") & (df_dt <= "2018-01-31 23:59:59")].copy()

    acessos_prod = (
        logs.groupby("Product")
        .agg(
            acessos_pagina=("url", "count"),
            cliques_add_to_cart=("add_to_cart", "sum"),
            ips_unicos=("ip", "nunique"),
        )
        .reset_index()
        .rename(columns={"Product": "Product Name"})
    )

    vendas_prod = (
        df_periodo.groupby(["Product Name", "Category Name", "Package Gross Weight (kg)"])
        .agg(
            pedidos_periodo=("Order Id", "count"),
            unidades_vendidas=("Order Item Quantity", "sum"),
            toneladas_demandadas=("Order Item Gross Weight (kg)", lambda x: x.sum() / 1000.0),
            receita_liquida=("Order Item Total", "sum"),
            lucro_liquido=("Benefit per order", "sum"),
            prejuizo_bruto=("Benefit per order", lambda x: x[x < 0].sum()),
            pct_atraso=("Late_delivery_risk", lambda x: x.mean() * 100.0),
        )
        .reset_index()
    )

    demanda = pd.merge(acessos_prod, vendas_prod, on="Product Name", how="inner")
    demanda["taxa_conversao_pedidos_por_100_acessos"] = (
        demanda["pedidos_periodo"] / demanda["acessos_pagina"] * 100.0
    ).round(2)
    demanda = demanda.sort_values("acessos_pagina", ascending=False).round(2)
    return demanda


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df = carregar_base_principal()

    df_transporte = analisar_transporte_e_porte(df)
    df_rotas, df_paises_cd = analisar_rotas_e_viabilidade_cd(df)
    df_repos = analisar_reposicionamento_itens(df)
    df_precos = analisar_precos_regiao_consumidor(df)
    df_demanda = analisar_demanda_acessos_vs_vendas(df)

    df_transporte.to_csv(OUTPUT_DIR / "01_transporte_por_porte_fisico.csv", index=False, encoding="utf-8-sig")
    df_rotas.to_csv(OUTPUT_DIR / "02_rotas_origem_destino.csv", index=False, encoding="utf-8-sig")
    df_paises_cd.to_csv(OUTPUT_DIR / "03_viabilidade_cd_por_pais.csv", index=False, encoding="utf-8-sig")
    df_repos.to_csv(OUTPUT_DIR / "04_reposicionamento_estoque_produtos.csv", index=False, encoding="utf-8-sig")
    df_precos.to_csv(OUTPUT_DIR / "05_precos_regiao_e_consumidor.csv", index=False, encoding="utf-8-sig")
    df_demanda.to_csv(OUTPUT_DIR / "06_demanda_acessos_vs_vendas.csv", index=False, encoding="utf-8-sig")

    print("=== 1. TRANSPORTE POR PORTE FISICO ===")
    print(df_transporte[["Classe_Peso_Volume", "Shipping Mode", "pedidos", "toneladas_totais", "volume_total_m3", "custo_operacional_medio", "lucro_liquido_medio", "prejuizo_acumulado", "pct_atraso"]].to_string(index=False))

    print("\n=== 2. TOP 10 PAISES POR TONELADAS E PREJUIZO (CANDIDATOS A CD) ===")
    print(df_paises_cd.head(10)[["Market", "Order Country", "pedidos_totais", "toneladas_totais", "volume_total_m3", "receita_liquida", "prejuizo_bruto", "pct_atraso"]].to_string(index=False))

    print("\n=== 3. TOP 10 PRODUTOS POR TONELADAS EXPEDIDAS (REPOSICIONAMENTO) ===")
    print(df_repos.head(10)[["Product Name", "Package Gross Weight (kg)", "pedidos", "toneladas_totais", "pct_estoque_porto_rico", "principal_mercado_comprador", "principal_pais_comprador", "prejuizo_bruto"]].to_string(index=False))

    print("\n=== 4. PRECOS E RENTABILIDADE POR MERCADO E SEGMENTO DE CONSUMIDOR ===")
    print(df_precos[["Market", "Customer Segment", "pedidos", "receita_liquida_media", "custo_operacional_medio", "lucro_liquido_medio", "lucro_mediano", "prejuizo_acumulado"]].to_string(index=False))

    print("\n=== 5. TOP 10 PRODUTOS MAIS DEMANDADOS NOS LOGS DE ACESSO (SET/2017 A JAN/2018) ===")
    print(df_demanda.head(10)[["Product Name", "acessos_pagina", "cliques_add_to_cart", "pedidos_periodo", "taxa_conversao_pedidos_por_100_acessos", "toneladas_demandadas", "prejuizo_bruto"]].to_string(index=False))


if __name__ == "__main__":
    main()
