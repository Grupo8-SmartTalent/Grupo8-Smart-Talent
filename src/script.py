"""
Script de Padronização e Normalização dos Datasets — Grupo 8 Smart Talent
=========================================================================
Realiza a limpeza estrutural, padronização de esquema/tipos/strings/datas e
aplica normalização (Min-Max [0, 1]) e padronização estatística (Z-Score)
diretamente nas colunas (in-place), gerando um único CSV final por dataset:
  1. data/processed/dataco_supply_chain_processed.csv
  2. data/processed/tokenized_access_logs_processed.csv
"""

from pathlib import Path
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = DATA_DIR / "processed"


# Colunas 100% redundantes (valores idênticos em todas as 180.519 linhas)
REDUNDANT_COLUMNS = [
    "Order Profit Per Order",    # Duplicata exata de 'Benefit per order'
    "Sales per customer",        # Duplicata exata de 'Order Item Total'
    "Product Category Id",       # Duplicata exata de 'Category Id'
    "Order Customer Id",         # Duplicata exata de 'Customer Id'
    "Order Item Cardprod Id",    # Duplicata exata de 'Product Card Id'
    "Order Item Product Price",  # Duplicata exata de 'Product Price'
]

# Colunas nulas (86%-100%) ou de variância zero (constantes/mascaradas)
USELESS_COLUMNS = [
    "Product Description",  # 100% nulo (180.519 NaNs)
    "Order Zipcode",        # 86,24% nulo (155.679 NaNs)
    "Customer Email",       # Constante ('XXXXXXXXX')
    "Customer Password",    # Constante ('XXXXXXXXX')
    "Product Status",       # Constante (0 em 100% das linhas)
]

# Mapeamento explícito para padronização dos nomes de colunas em snake_case
DATACO_COLUMN_RENAME = {
    "Type": "payment_type",
    "Days for shipping (real)": "days_for_shipping_real",
    "Days for shipment (scheduled)": "days_for_shipment_scheduled",
    "Benefit per order": "benefit_per_order",
    "Delivery Status": "delivery_status",
    "Late_delivery_risk": "late_delivery_risk",
    "Category Id": "category_id",
    "Category Name": "category_name",
    "Customer City": "customer_city",
    "Customer Country": "customer_country",
    "Customer Fname": "customer_fname",
    "Customer Id": "customer_id",
    "Customer Lname": "customer_lname",
    "Customer Segment": "customer_segment",
    "Customer State": "customer_state",
    "Customer Street": "customer_street",
    "Customer Zipcode": "customer_zipcode",
    "Department Id": "department_id",
    "Department Name": "department_name",
    "Latitude": "latitude",
    "Longitude": "longitude",
    "Market": "market",
    "Order City": "order_city",
    "Order Country": "order_country",
    "order date (DateOrders)": "order_date",
    "Order Id": "order_id",
    "Order Item Discount": "order_item_discount",
    "Order Item Discount Rate": "order_item_discount_rate",
    "Order Item Id": "order_item_id",
    "Order Item Profit Ratio": "order_item_profit_ratio",
    "Order Item Quantity": "order_item_quantity",
    "Sales": "sales",
    "Order Item Total": "order_item_total",
    "Order Region": "order_region",
    "Order State": "order_state",
    "Order Status": "order_status",
    "Product Card Id": "product_card_id",
    "Product Image": "product_image",
    "Product Name": "product_name",
    "Product Price": "product_price",
    "shipping date (DateOrders)": "shipping_date",
    "Shipping Mode": "shipping_mode",
}

LOGS_COLUMN_RENAME = {
    "Product": "product_name",
    "Category": "category_name",
    "Date": "access_date",
    "Month": "access_month",
    "Hour": "access_hour",
    "Department": "department_name",
    "ip": "client_ip",
    "url": "request_url",
}

# Variáveis discretas/limitadas não-negativas -> Normalização Min-Max [0, 1]
MINMAX_COLUMNS = [
    "days_for_shipping_real",       # Intervalo discreto [0, 6] dias
    "days_for_shipment_scheduled",  # Intervalo discreto [0, 4] dias
    "order_item_quantity",          # Intervalo discreto [1, 5] unidades
    "order_item_discount_rate",     # Taxa percentual limitada [0, 0.25]
]

# Variáveis financeiras contínuas (com valores negativos e outliers) -> Padronização Z-Score (média=0, std=1)
ZSCORE_COLUMNS = [
    "benefit_per_order",
    "order_item_discount",
    "order_item_profit_ratio",
    "sales",
    "order_item_total",
    "product_price",
]


def clean_string_series(series: pd.Series) -> pd.Series:
    """Remove espaços nas extremidades e colapsa múltiplos espaços internos."""
    return (
        series.astype(str)
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
    )


def process_dataco(input_path: Path) -> pd.DataFrame:
    """Limpa, padroniza e normaliza in-place o dataset DataCoSupplyChainDataset.csv."""
    print(f"[1/2] Carregando {input_path.name}...")
    df = pd.read_csv(input_path, encoding="latin-1")
    print(f"      Formato original: {df.shape[0]:,} linhas x {df.shape[1]} colunas")

    # 1. Remoção de colunas 100% redundantes e colunas nulas/constantes
    cols_to_drop = REDUNDANT_COLUMNS + USELESS_COLUMNS
    df = df.drop(columns=cols_to_drop)
    print(f"      Removidas {len(REDUNDANT_COLUMNS)} colunas duplicadas e {len(USELESS_COLUMNS)} colunas nulas/constantes.")

    # 2. Renomeação de todas as colunas para snake_case padronizado
    df = df.rename(columns=DATACO_COLUMN_RENAME)

    # 3. Correção das 3 linhas com deslocamento de endereço (Street -> City -> State -> Zipcode)
    shifted_mask = df["customer_zipcode"].isna() & df["customer_state"].astype(str).str.isdigit()
    shifted_count = int(shifted_mask.sum())
    if shifted_count > 0:
        df.loc[shifted_mask, "customer_zipcode"] = df.loc[shifted_mask, "customer_state"].astype(float)
        df.loc[shifted_mask, "customer_state"] = df.loc[shifted_mask, "customer_city"]
        df.loc[shifted_mask, "customer_city"] = df.loc[shifted_mask, "customer_street"]
        df.loc[shifted_mask, "customer_street"] = "Unknown"
        print(f"      Corrigidas {shifted_count} linhas com deslocamento nas colunas de endereço do cliente.")

    # 4. Tratamento de valores nulos remanescentes em customer_lname
    lname_nulls = int(df["customer_lname"].isna().sum())
    df["customer_lname"] = df["customer_lname"].fillna("Unknown")
    print(f"      Preenchidos {lname_nulls} valores ausentes em 'customer_lname' com 'Unknown'.")

    # 5. Padronização do CEP (customer_zipcode) como string de 5 dígitos com zero à esquerda (ex.: 00725)
    df["customer_zipcode"] = (
        df["customer_zipcode"]
        .fillna(0)
        .astype(int)
        .astype(str)
        .str.zfill(5)
    )

    # 6. Limpeza de espaços extras em todas as colunas textuais
    text_columns = [
        "payment_type",
        "delivery_status",
        "category_name",
        "customer_city",
        "customer_country",
        "customer_fname",
        "customer_lname",
        "customer_segment",
        "customer_state",
        "customer_street",
        "department_name",
        "market",
        "order_city",
        "order_country",
        "order_region",
        "order_state",
        "order_status",
        "product_image",
        "product_name",
        "shipping_mode",
    ]
    for col in text_columns:
        df[col] = clean_string_series(df[col])

    # 7. Padronização de nome de país ('EE. UU.' -> 'United States')
    df["customer_country"] = df["customer_country"].replace({"EE. UU.": "United States"})

    # 8. Unificação de category_id inconsistente para 'Electronics' (IDs 13 e 37 -> 13)
    electronics_mask = (df["category_name"] == "Electronics") & (df["category_id"] == 37)
    electronics_fixed = int(electronics_mask.sum())
    df.loc[electronics_mask, "category_id"] = 13
    print(f"      Unificados {electronics_fixed} registros da categoria 'Electronics' (category_id 37 -> 13).")

    # 9. Padronização de datas para formato ISO 8601 (YYYY-MM-DD HH:MM:SS)
    df["order_date"] = pd.to_datetime(df["order_date"], format="%m/%d/%Y %H:%M").dt.strftime("%Y-%m-%d %H:%M:%S")
    df["shipping_date"] = pd.to_datetime(df["shipping_date"], format="%m/%d/%Y %H:%M").dt.strftime("%Y-%m-%d %H:%M:%S")

    # 10. Correção de ruído de ponto flutuante antes do escalonamento
    df[["latitude", "longitude"]] = df[["latitude", "longitude"]].round(6)
    df[["order_item_discount_rate", "order_item_profit_ratio"]] = df[
        ["order_item_discount_rate", "order_item_profit_ratio"]
    ].round(4)

    # 11. Normalização Min-Max [0, 1] in-place nas variáveis limitadas/discretas
    for col in MINMAX_COLUMNS:
        col_min = df[col].min()
        col_max = df[col].max()
        df[col] = ((df[col] - col_min) / (col_max - col_min)).round(6)

    # 12. Padronização Z-Score (média=0, desvio padrão=1) in-place nas variáveis financeiras contínuas
    for col in ZSCORE_COLUMNS:
        col_mean = df[col].mean()
        col_std = df[col].std()
        df[col] = ((df[col] - col_mean) / col_std).round(6)

    print(f"      Formato final processado: {df.shape[0]:,} linhas x {df.shape[1]} colunas")
    return df


def process_logs(
    input_path: Path, canonical_categories: dict[str, str], canonical_departments: dict[str, str]
) -> pd.DataFrame:
    """Limpa, padroniza e normaliza in-place o dataset tokenized_access_logs.csv."""
    print(f"\n[2/2] Carregando {input_path.name}...")
    logs = pd.read_csv(input_path, encoding="latin-1")
    print(f"      Formato original: {logs.shape[0]:,} linhas x {logs.shape[1]} colunas")

    # 1. Renomeação das colunas para snake_case
    logs = logs.rename(columns=LOGS_COLUMN_RENAME)

    # 2. Limpeza de espaços em branco nas strings (ex.: 'fitness ' -> 'fitness')
    for col in ["product_name", "category_name", "access_month", "department_name", "client_ip", "request_url"]:
        logs[col] = clean_string_series(logs[col])

    # 3. Remoção de linhas exatas duplicadas
    before_dedup = len(logs)
    logs = logs.drop_duplicates().reset_index(drop=True)
    removed_dups = before_dedup - len(logs)
    print(f"      Removidas {removed_dups:,} linhas duplicadas exatas.")

    # 4. Padronização de category_name e department_name com os nomes canônicos do dataset principal
    cat_lookup = {
        **canonical_categories,
        "indoor outdoor games": "Indoor/Outdoor Games",
        "featured shops": "Featured Shops",
    }
    logs["category_name"] = logs["category_name"].str.lower().map(cat_lookup).fillna(logs["category_name"].str.title())
    logs["department_name"] = (
        logs["department_name"].str.lower().map(canonical_departments).fillna(logs["department_name"].str.title())
    )

    # 5. Padronização de nomes de produtos com ano divergente (2017 -> 2014) para permitir join com DataCo
    product_fixes = {
        "adidas Brazuca 2017 Official Match Ball": "adidas Brazuca 2014 Official Match Ball",
        "Top Flite Women's 2017 XL Hybrid": "Top Flite Women's 2014 XL Hybrid",
        "TaylorMade 2017 Purelite Stand Bag": "TaylorMade 2014 Purelite Stand Bag",
    }
    logs["product_name"] = logs["product_name"].replace(product_fixes)

    # 6. Padronização de access_date para ISO 8601 (YYYY-MM-DD HH:MM:SS)
    parsed_dt = pd.to_datetime(logs["access_date"], format="%m/%d/%Y %H:%M")
    logs["access_date"] = parsed_dt.dt.strftime("%Y-%m-%d %H:%M:%S")

    # 7. Normalização Min-Max [0, 1] in-place em access_hour (intervalo [0, 23])
    logs["access_hour"] = (logs["access_hour"].astype(float) / 23.0).round(6)

    print(f"      Formato final processado: {logs.shape[0]:,} linhas x {logs.shape[1]} colunas")
    return logs


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    dataco_path = DATA_DIR / "DataCoSupplyChainDataset.csv"
    logs_path = DATA_DIR / "tokenized_access_logs.csv"

    df_processed = process_dataco(dataco_path)

    # Dicionários canônicos para padronizar os logs de acordo com a base principal
    canonical_categories = {c.lower(): c for c in df_processed["category_name"].unique()}
    canonical_departments = {d.lower(): d for d in df_processed["department_name"].unique()}

    logs_processed = process_logs(logs_path, canonical_categories, canonical_departments)

    print("\nSalvando 1 CSV unificado por dataset em 'data/processed/' (UTF-8)...")
    dataco_out = OUTPUT_DIR / "dataco_supply_chain_processed.csv"
    logs_out = OUTPUT_DIR / "tokenized_access_logs_processed.csv"

    df_processed.to_csv(dataco_out, index=False, encoding="utf-8")
    logs_processed.to_csv(logs_out, index=False, encoding="utf-8")

    print("Concluído com sucesso!")
    for p in [dataco_out, logs_out]:
        size_mb = p.stat().st_size / (1024 * 1024)
        print(f"  - {p.relative_to(BASE_DIR)} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    main()
