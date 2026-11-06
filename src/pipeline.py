"""Pipeline de análise do DataCo Supply Chain.

Uso: python src/pipeline.py --input data/DataCoSupplyChainDataset.csv --output outputs
"""
from pathlib import Path
import argparse
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--input", default="data/DataCoSupplyChainDataset.csv")
    parser.add_argument("--output", default="outputs")
    args=parser.parse_args()
    out=Path(args.output); out.mkdir(parents=True, exist_ok=True)
    df=pd.read_csv(args.input, encoding="latin-1")
    df.columns=df.columns.str.strip().str.lower()
    required=["delivery status","late_delivery_risk","days for shipping (real)","days for shipment (scheduled)","order region","sales"]
    missing=set(required)-set(df.columns)
    if missing: raise ValueError(f"Colunas ausentes: {sorted(missing)}")
    # Remover linhas sem métricas essenciais; datas/valores inválidos não entram no resumo.
    for col in ["late_delivery_risk","days for shipping (real)","days for shipment (scheduled)","sales"]:
        df[col]=pd.to_numeric(df[col],errors="coerce")
    df=df.dropna(subset=["delivery status","late_delivery_risk","days for shipping (real)","days for shipment (scheduled)","sales"])
    df=df.drop_duplicates()
    df=df[df["sales"]>=0]
    df["atraso_dias"]=(df["days for shipping (real)"]-df["days for shipment (scheduled)"]).clip(lower=0)
    df["risco_atraso"]=df["late_delivery_risk"].astype(bool)
    resumo=df.groupby("order region",dropna=False).agg(pedidos=("order region","size"),vendas=("sales","sum"),atraso_medio_dias=("atraso_dias","mean"),risco_atraso_pct=("risco_atraso","mean")).reset_index()
    resumo["risco_atraso_pct"]*=100
    resumo.to_csv(out/"resumo_por_regiao.csv",index=False)
    # Gráfico 1: risco registrado por região
    risco=df.groupby("order region")["risco_atraso"].mean().sort_values(ascending=False)*100
    fig,ax=plt.subplots(figsize=(10,6)); risco.plot.bar(ax=ax,color="#2563eb")
    ax.set(title="O risco de atraso varia entre regiões",ylabel="Pedidos com risco (%)",xlabel="Região"); fig.tight_layout(); fig.savefig(out/"risco_por_regiao.png",dpi=150); plt.close(fig)
    # Gráfico 2: atraso médio positivo por status de entrega
    atrasos=df.groupby("delivery status")["atraso_dias"].mean().sort_values(ascending=False)
    fig,ax=plt.subplots(figsize=(10,6)); atrasos.plot.bar(ax=ax,color="#ea580c")
    ax.set(title="Entregas marcadas como atrasadas acumulam mais dias de atraso",ylabel="Atraso médio (dias)",xlabel="Status de entrega"); fig.tight_layout(); fig.savefig(out/"atraso_por_status.png",dpi=150); plt.close(fig)
    print(f"Linhas analisadas: {len(df):,}")
    print(resumo.to_string(index=False))
    print(f"Saídas gravadas em: {out.resolve()}")
if __name__=="__main__": main()
