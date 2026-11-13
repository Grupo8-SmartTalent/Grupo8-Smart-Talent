from pathlib import Path
from functools import lru_cache
import pandas as pd
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'/'DataCoSupplyChainDataset.csv'
app=FastAPI(title='Smart Talent Logistics Dashboard')

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    errors=exc.errors()
    fields={str(err.get('loc', [''])[-1]) for err in errors}
    if 'delay_reduction_days' in fields:
        message='Quantidade de dias inválida. Revise o valor informado e tente novamente.'
    elif 'eu_demand_share' in fields:
        message='Percentual de demanda inválido. Revise o valor informado e tente novamente.'
    elif 'cost_per_order' in fields:
        message='Custo por pedido inválido. Revise o valor informado e tente novamente.'
    else:
        message='Não foi possível executar a simulação. Revise os valores informados e tente novamente.'
    return JSONResponse(status_code=400, content={'error': {'code':'invalid_input', 'message':message}})


REGION_GROUPS={'North America':['Canada','Caribbean','Central America','East of USA','West of USA','US Center','South of USA'],'América do Norte':['Canada','Caribbean','Central America','East of USA','West of USA','US Center','South of USA'],'Europe':['Western Europe','Northern Europe','Southern Europe','Eastern Europe'],'Europa':['Western Europe','Northern Europe','Southern Europe','Eastern Europe'],'Asia':['Southeast Asia','South Asia','Eastern Asia','West Asia','Central Asia'],'Ásia':['Southeast Asia','South Asia','Eastern Asia','West Asia','Central Asia']}
def filter_region(df, region):
    if not region or region in ('Todas','All'): return df
    names=REGION_GROUPS.get(region,[region])
    return df[df['order region'].str.strip().isin(names)]

@lru_cache(maxsize=1)
def dataset():
    df=pd.read_csv(DATA,encoding='latin-1',usecols=lambda c:c.strip().lower() in {
      'order region','order country','order city','order state','shipping mode','late_delivery_risk',
      'days for shipping (real)','days for shipment (scheduled)','sales','order profit per order','order item total','order item product price','product name','product card id','order item quantity','order item gross weight (kg)','order item volume (cm3)','order id'
    })
    df.columns=df.columns.str.strip().str.lower()
    for c in ['late_delivery_risk','days for shipping (real)','days for shipment (scheduled)','sales','order profit per order','order item total','order item product price']:
      if c in df: df[c]=pd.to_numeric(df[c],errors='coerce')
    df=df.dropna(subset=['order region','late_delivery_risk','days for shipping (real)','days for shipment (scheduled)']).copy()
    df['delay_days']=(df['days for shipping (real)']-df['days for shipment (scheduled)']).clip(lower=0)
    return df

@app.get('/api/overview')
def overview(region:str='Todas'):
    d=dataset()
    d=filter_region(d,region)
    return {'rows':int(len(d)),'late_risk_pct':round(float(d['late_delivery_risk'].mean()*100),2),'avg_delay_days':round(float(d['delay_days'].mean()),2),'late_rows':int(d['late_delivery_risk'].sum()),'regions':d.groupby('order region').agg(orders=('order region','size'),risk_pct=('late_delivery_risk','mean'),avg_delay=('delay_days','mean'),sales=('sales','sum')).sort_values('orders',ascending=False).reset_index().assign(risk_pct=lambda x:(x.risk_pct*100).round(2),avg_delay=lambda x:x.avg_delay.round(2),sales=lambda x:x.sales.round(2)).to_dict('records')}

@app.get('/api/routes')
def routes(region:str='Todas',mode:str='Todas'):
    d=dataset()
    d=filter_region(d,region)
    if mode!='Todas': d=d[d['shipping mode'].eq(mode)]
    g=d.groupby(['order region','order country'],dropna=False).agg(orders=('order id','count'),risk_pct=('late_delivery_risk','mean'),avg_delay=('delay_days','mean'),sales=('sales','sum'),profit=('order profit per order','sum')).reset_index().sort_values(['risk_pct','orders'],ascending=False).head(15)
    g['risk_pct']=(g.risk_pct*100).round(1);g['avg_delay']=g.avg_delay.round(2)
    return {'routes':g.fillna(0).to_dict('records'),'shipping_modes':sorted(d['shipping mode'].dropna().unique().tolist())}


@lru_cache(maxsize=1)
def bi_supporting_data():
    data_dir=DATA.parent
    dimensions=pd.read_csv(data_dir/'product_dimensions.csv',encoding='latin-1')
    dimensions['Product Card Id']=pd.to_numeric(dimensions['Product Card Id'],errors='coerce')
    dimensions['Package Volume (cm3)']=dimensions['Package Length (cm)']*dimensions['Package Width (cm)']*dimensions['Package Height (cm)']
    logs=pd.read_csv(data_dir/'tokenized_access_logs.csv',encoding='latin-1',usecols=['Product','Category'])
    return dimensions, {'events':int(len(logs)),'products':int(logs['Product'].nunique()),'categories':int(logs['Category'].nunique())}

@app.get('/api/bi')
def bi():
    d=dataset().copy()
    # “Order Profit Per Order” varies by product line. Sum line values rather
    # than deduplicating by order. Negative values are gross negative entries,
    # not the company's net loss and not necessarily caused by a delivery delay.
    d['negative_profit']=d['order profit per order'].clip(upper=0).abs()
    d['delayed_negative_profit']=d['negative_profit'].where(d['late_delivery_risk']==1,0)
    d['late_delay_days']=d['delay_days'].where(d['late_delivery_risk']==1)
    dimensions,logs=bi_supporting_data()
    modes=d.groupby('shipping mode').agg(lines=('order id','size'),orders=('order id','nunique'),risk_pct=('late_delivery_risk','mean'),avg_late_delay=('late_delay_days','mean'),sales=('sales','sum'),negative_profit_loss_usd=('negative_profit','sum'),delayed_negative_profit_usd=('delayed_negative_profit','sum')).reset_index()
    regions=d.groupby('order region').agg(lines=('order id','size'),orders=('order id','nunique'),risk_pct=('late_delivery_risk','mean'),avg_late_delay=('late_delay_days','mean'),sales=('sales','sum'),negative_profit_loss_usd=('negative_profit','sum'),delayed_negative_profit_usd=('delayed_negative_profit','sum')).reset_index()
    products=d.groupby(['product card id','product name'],dropna=False).agg(lines=('order id','size'),orders=('order id','nunique'),risk_pct=('late_delivery_risk','mean'),avg_late_delay=('late_delay_days','mean'),sales=('sales','sum'),negative_profit_loss_usd=('negative_profit','sum'),delayed_negative_profit_usd=('delayed_negative_profit','sum'),units=('order item quantity','sum')).reset_index()
    products=products.merge(dimensions[['Product Card Id','Package Gross Weight (kg)','Package Volume (cm3)','Estimate Basis']],left_on='product card id',right_on='Product Card Id',how='left')
    for table in (modes,regions,products):
        table['risk_pct']=(table['risk_pct']*100).round(2)
        table['avg_late_delay']=table['avg_late_delay'].round(2)
        for col in ('sales','negative_profit_loss_usd','delayed_negative_profit_usd'):
            table[col]=table[col].round(2)
    delayed=d[d['late_delivery_risk']==1]
    total_negative=float(d['negative_profit'].sum())
    delayed_negative=float(delayed['negative_profit'].sum())
    eu=d[d['order region'].str.strip().isin(['Western Europe','Northern Europe','Southern Europe','Eastern Europe'])]
    western_eu=d[d['order region'].str.strip().eq('Western Europe')]
    first_class=modes[modes['shipping mode'].eq('First Class')]
    first_risk=float(first_class.iloc[0]['risk_pct']) if len(first_class) else 0
    first_lines=int(first_class.iloc[0]['lines']) if len(first_class) else 0
    fmt_pt=lambda value,decimals=0:f'{float(value):,.{decimals}f}'.replace(',','@').replace('.',',').replace('@','.')
    top_products=products.sort_values('negative_profit_loss_usd',ascending=False).head(8).copy()
    top8_share=float(top_products['negative_profit_loss_usd'].sum()/total_negative*100) if total_negative else 0
    top_products=top_products.rename(columns={'product name':'product_name','product card id':'product_id','avg_late_delay':'avg_delay_when_risk','Package Gross Weight (kg)':'package_gross_weight_kg','Package Volume (cm3)':'package_volume_cm3','Estimate Basis':'dimension_estimate_basis'})
    top_products=top_products.astype(object).where(pd.notna(top_products),None)
    return {'observed':{'lines':int(len(d)),'orders':int(d['order id'].nunique()),'risk_lines':int(d['late_delivery_risk'].sum()),'risk_orders':int(delayed['order id'].nunique()),'risk_pct':round(float(d['late_delivery_risk'].mean()*100),2),'avg_delay_days_all':round(float(d['delay_days'].mean()),2),'avg_delay_days_late':round(float(delayed['delay_days'].mean()),2),'sales_usd':round(float(d['sales'].sum()),2),'negative_profit_loss_usd':round(total_negative,2),'delayed_negative_profit_usd':round(delayed_negative,2),'delayed_negative_profit_share_pct':round(delayed_negative/total_negative*100,2) if total_negative else 0,'late_negative_lines':int(((d['negative_profit']>0)&(d['late_delivery_risk']==1)).sum()),'late_negative_orders':int(d.loc[(d['negative_profit']>0)&(d['late_delivery_risk']==1),'order id'].nunique()),'top8_negative_loss_share_pct':round(top8_share,2),'modes':modes.sort_values('delayed_negative_profit_usd',ascending=False).to_dict('records'),'regions':regions.sort_values('delayed_negative_profit_usd',ascending=False).to_dict('records'),'top_products':top_products.to_dict('records'),'europe':{'lines':int(len(eu)),'risk_pct':round(float(eu['late_delivery_risk'].mean()*100),2) if len(eu) else 0,'risk_lines':int(eu['late_delivery_risk'].sum()),'negative_profit_loss_usd':round(float(eu['negative_profit'].sum()),2)}},'data_sources':{'transactions':{'rows':int(len(d)),'orders':int(d['order id'].nunique()),'late_negative_lines':int(((d['negative_profit']>0)&(d['late_delivery_risk']==1)).sum()),'file':'DataCoSupplyChainDataset.csv'},'product_dimensions':{'products':int(dimensions['Product Card Id'].nunique()),'file':'product_dimensions.csv','note':'Peso bruto e volume são estimativas da tabela auxiliar; volume calculado por comprimento × largura × altura.'},'web_logs':{'events':logs['events'],'products':logs['products'],'categories':logs['categories'],'file':'tokenized_access_logs.csv','note':'Eventos de navegação não são pedidos e não estão ligados às transações.'}},'recommendations':[{'title':'Investigar promessa First Class','evidence':f'First Class tem {fmt_pt(first_risk,2)}% de linhas com risco em {fmt_pt(first_lines)} linhas. Revisar promessa e capacidade por produto e rota.','kind':'observado'},{'title':'Dimensionar piloto na Europa Ocidental','evidence':f'A região tem {fmt_pt(len(western_eu))} linhas e US$ {fmt_pt(western_eu["sales"].sum())} em vendas históricas; validar estoque, cobertura e custo do CD.','kind':'hipótese'},{'title':'Definir SLA de parceiros nos EUA e China','evidence':'Comparar prazo, custo total, cobertura e penalidades por rota antes de terceirizar a operação.','kind':'dado faltante'}],'warning':'Prejuízo bruto registrado = soma do valor absoluto das linhas negativas de “Order Profit Per Order”; não é prejuízo líquido da empresa. Associação com atraso não prova causalidade. Cenários são hipóteses, sem custos reais de CD/3PL.'}

class Scenario(BaseModel):
    eu_demand_share:float=Field(0.3,ge=0,le=1)
    delay_reduction_days:float=Field(1.0,ge=0,le=30)
    cost_per_order:float=Field(0,ge=0)
    orders_served: int|None=None

@app.post('/api/scenario')
def scenario(x:Scenario):
    try:
        d=dataset(); eu=d[d['order region'].str.contains('Europe',case=False,na=False)]
        if eu.empty:
            return JSONResponse(status_code=422,content={'error':{'code':'no_europe_data','message':'Não há pedidos europeus disponíveis para simular.'}})
        n=int(x.orders_served if x.orders_served is not None else len(eu))
        delayed=int((eu['late_delivery_risk']==1).sum())
        observed_delay=float(eu['delay_days'].mean())
        reduction=min(x.delay_reduction_days,observed_delay)
        return {'scope':'simulation, not observed outcome','europe_orders_in_csv':int(len(eu)),'orders_assumed':n,'risk_orders_historical':delayed,'delay_reduction_assumption_days':x.delay_reduction_days,'applied_delay_reduction_days':reduction,'estimated_delay_days_avoided':round(n*x.eu_demand_share*reduction,1),'assumed_cost':round(n*x.eu_demand_share*x.cost_per_order,2),'roi':'not calculated: no validated benefit/cost data','note':'Simulation only. CSV does not establish causal impact of a new distribution center.'}
    except Exception:
        return JSONResponse(status_code=500,content={'error':{'code':'simulation_failed','message':'A simulação não pôde ser concluída. Confira os dados e tente novamente.'}})

app.mount('/',StaticFiles(directory=Path(__file__).parent,html=True),name='frontend')


