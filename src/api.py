"""HTTP API for the late-delivery baseline. Run after training."""
from pathlib import Path
import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
MODEL_PATH=Path(__file__).resolve().parents[1]/"modelo_atraso.joblib"
app=FastAPI(title="Smart Talent - Risco de atraso")
class OrderFeatures(BaseModel):
    shipping_mode:str
    order_region:str
    order_country:str
    category_name:str
    product_name:str
    scheduled_days:float
    quantity:float
    product_price:float
    order_month:int
    order_weekday:int
def load_model():
    if not MODEL_PATH.exists(): raise RuntimeError("Modelo ausente; execute python src/train_baseline.py")
    return joblib.load(MODEL_PATH)
@app.get("/health")
def health(): return {"status":"ok","model_exists":MODEL_PATH.exists()}
@app.post("/predict")
def predict(x:OrderFeatures):
    try:
        bundle=load_model()
        row=pd.DataFrame([{"Shipping Mode":x.shipping_mode,"Order Region":x.order_region,"Order Country":x.order_country,"Category Name":x.category_name,"Product Name":x.product_name,"Days for shipment (scheduled)":x.scheduled_days,"Order Item Quantity":x.quantity,"Product Price":x.product_price,"order_month":x.order_month,"order_weekday":x.order_weekday}])
        pipe=bundle["pipeline"]; pred=int(pipe.predict(row)[0]); prob=float(pipe.predict_proba(row)[0][1])
        return {"late_delivery_risk":pred,"probability":prob,"interpretation":"risco histórico estimado; não é garantia de atraso"}
    except RuntimeError as e: raise HTTPException(status_code=503,detail=str(e))
