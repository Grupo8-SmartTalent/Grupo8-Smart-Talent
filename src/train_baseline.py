"""Train chronological baseline for late-delivery risk."""
from pathlib import Path
import argparse, json
import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, precision_score, recall_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"/"DataCoSupplyChainDataset.csv"
MODEL=ROOT/"modelo_atraso.joblib"
METRICS=ROOT/"outputs"/"metricas_baseline.json"
CATEGORICAL=["Shipping Mode","Order Region","Order Country","Category Name","Product Name"]
NUMERIC=["Days for shipment (scheduled)","Order Item Quantity","Product Price","order_month","order_weekday"]
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--data",type=Path,default=DATA)
    ap.add_argument("--model",type=Path,default=MODEL)
    ap.add_argument("--metrics",type=Path,default=METRICS)
    a=ap.parse_args()
    df=pd.read_csv(a.data,encoding="latin-1")
    required=CATEGORICAL+["Days for shipment (scheduled)","Order Item Quantity","Product Price","Late_delivery_risk","order date (DateOrders)"]
    missing=[c for c in required if c not in df.columns]
    if missing: raise ValueError(f"Colunas ausentes: {missing}")
    df["order date (DateOrders)"]=pd.to_datetime(df["order date (DateOrders)"],format="%m/%d/%Y %H:%M",errors="coerce")
    df["Late_delivery_risk"]=pd.to_numeric(df["Late_delivery_risk"],errors="coerce")
    df=df.dropna(subset=["order date (DateOrders)","Late_delivery_risk"]).copy()
    df["order_month"]=df["order date (DateOrders)"].dt.month
    df["order_weekday"]=df["order date (DateOrders)"].dt.weekday
    df=df.sort_values("order date (DateOrders)")
    # Keep every line item from one order on the same side of the split.
    order_dates=df.groupby("Order Id")["order date (DateOrders)"].min().sort_values()
    cut=int(len(order_dates)*0.8)
    train_ids=set(order_dates.index[:cut])
    train=df[df["Order Id"].isin(train_ids)]
    test=df[~df["Order Id"].isin(train_ids)]
    if train["Late_delivery_risk"].nunique()<2 or test["Late_delivery_risk"].nunique()<2: raise ValueError("Split cronológico sem ambas as classes; verifique o período/dados.")
    prep=ColumnTransformer([("cat",Pipeline([("impute",SimpleImputer(strategy="most_frequent")),("onehot",OneHotEncoder(handle_unknown="ignore"))]),CATEGORICAL),("num",Pipeline([("impute",SimpleImputer(strategy="median"))]),NUMERIC)])
    model=Pipeline([("prep",prep),("classifier",RandomForestClassifier(n_estimators=150,min_samples_leaf=3,class_weight="balanced",random_state=42,n_jobs=-1))])
    model.fit(train[CATEGORICAL+NUMERIC],train["Late_delivery_risk"].astype(int))
    pred=model.predict(test[CATEGORICAL+NUMERIC])
    metrics={"target":"Late_delivery_risk","split":"primeiros 80% do período para treino; últimos 20% para teste","train_rows":len(train),"test_rows":len(test),"accuracy":accuracy_score(test["Late_delivery_risk"],pred),"precision_positive":precision_score(test["Late_delivery_risk"],pred,zero_division=0),"recall_positive":recall_score(test["Late_delivery_risk"],pred,zero_division=0),"positive_label":"1 = risco de atraso"}
    a.model.parent.mkdir(parents=True,exist_ok=True); a.metrics.parent.mkdir(parents=True,exist_ok=True)
    joblib.dump({"pipeline":model,"features":CATEGORICAL+NUMERIC},a.model)
    a.metrics.write_text(json.dumps(metrics,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(metrics,indent=2,ensure_ascii=False))
if __name__=="__main__": main()
