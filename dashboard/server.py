from functools import lru_cache
from pathlib import Path
import pandas as pd
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data' / 'DataCoSupplyChainDataset.csv'
MODEL_PATH = ROOT / 'modelo_atraso.joblib'

app = FastAPI(title='Smart Talent Logistics Dashboard')

REGION_GROUPS = {
    'North America': ['Canada', 'Caribbean', 'Central America', 'East of USA', 'West of USA', 'US Center', 'South of USA', 'South of  USA'],
    'América do Norte': ['Canada', 'Caribbean', 'Central America', 'East of USA', 'West of USA', 'US Center', 'South of USA', 'South of  USA'],
    'South America': ['South America'],
    'América do Sul': ['South America'],
    'Europe': ['Western Europe', 'Northern Europe', 'Southern Europe', 'Eastern Europe'],
    'Europa': ['Western Europe', 'Northern Europe', 'Southern Europe', 'Eastern Europe'],
    'Asia': ['Southeast Asia', 'South Asia', 'Eastern Asia', 'West Asia', 'Central Asia'],
    'Ásia': ['Southeast Asia', 'South Asia', 'Eastern Asia', 'West Asia', 'Central Asia'],
    'Oceania': ['Oceania'],
    'Africa': ['West Africa', 'East Africa', 'North Africa', 'Central Africa', 'Southern Africa'],
    'África': ['West Africa', 'East Africa', 'North Africa', 'Central Africa', 'Southern Africa'],
}

AVAILABLE_MACRO_REGIONS = [
    'Todas',
    'América do Norte',
    'Europa',
    'Ásia',
    'América do Sul',
    'Oceania',
    'África',
]

REGION_PT_BR = {
    'Canada': 'Canadá',
    'Caribbean': 'Caribe',
    'Central Africa': 'África Central',
    'Central America': 'América Central',
    'Central Asia': 'Ásia Central',
    'East Africa': 'África Oriental',
    'East of USA': 'Leste dos EUA',
    'Eastern Asia': 'Ásia Oriental',
    'Eastern Europe': 'Europa Oriental',
    'North Africa': 'Norte da África',
    'Northern Europe': 'Norte da Europa',
    'Oceania': 'Oceania',
    'South America': 'América do Sul',
    'South Asia': 'Sul da Ásia',
    'South of USA': 'Sul dos EUA',
    'Southeast Asia': 'Sudeste Asiático',
    'Southern Africa': 'África Austral',
    'Southern Europe': 'Sul da Europa',
    'US Center': 'Centro dos EUA',
    'West Africa': 'África Ocidental',
    'West Asia': 'Ásia Ocidental',
    'West of USA': 'Oeste dos EUA',
    'Western Europe': 'Europa Ocidental',
}

SHIPPING_MODE_PT_BR = {
    'First Class': 'Primeira Classe',
    'Same Day': 'Mesmo Dia',
    'Second Class': 'Segunda Classe',
    'Standard Class': 'Classe Padrão',
}

CATEGORY_PT_BR = {
    'Accessories': 'Acessórios',
    'As Seen on TV!': 'Visto na TV',
    'Baby': 'Bebê',
    'Baseball & Softball': 'Beisebol e Softbol',
    'Basketball': 'Basquete',
    'Books': 'Livros',
    'Boxing & MMA': 'Boxe e MMA',
    'CDs': 'CDs',
    'Cameras': 'Câmeras',
    'Camping & Hiking': 'Camping e Trilhas',
    'Cardio Equipment': 'Equipamentos de Cardio',
    "Children's Clothing": 'Roupas Infantis',
    'Cleats': 'Chuteiras e Travas',
    'Computers': 'Computadores',
    'Consumer Electronics': 'Eletrônicos de Consumo',
    'Crafts': 'Artesanato',
    'DVDs': 'DVDs',
    'Electronics': 'Eletrônicos',
    'Fishing': 'Pesca',
    'Fitness Accessories': 'Acessórios Fitness',
    'Garden': 'Jardinagem',
    "Girls' Apparel": 'Moda Infantil Feminina',
    'Golf Apparel': 'Vestuário de Golfe',
    'Golf Bags & Carts': 'Bolsas e Carrinhos de Golfe',
    'Golf Balls': 'Bolas de Golfe',
    'Golf Gloves': 'Luvas de Golfe',
    'Golf Shoes': 'Sapatos de Golfe',
    'Health and Beauty': 'Saúde e Beleza',
    'Hockey': 'Hóquei',
    'Hunting & Shooting': 'Caça e Tiro',
    'Indoor/Outdoor Games': 'Jogos Internos e Externos',
    "Kids' Golf Clubs": 'Tacos de Golfe Infantis',
    'Lacrosse': 'Lacrosse',
    "Men's Clothing": 'Moda Masculina',
    "Men's Footwear": 'Calçados Masculinos',
    "Men's Golf Clubs": 'Tacos de Golfe Masculinos',
    'Music': 'Música',
    'Pet Supplies': 'Artigos para Pets',
    'Shop By Sport': 'Artigos por Esporte',
    'Soccer': 'Futebol',
    'Sporting Goods': 'Artigos Esportivos',
    'Strength Training': 'Musculação',
    'Tennis & Racquet': 'Tênis e Raquetes',
    'Toys': 'Brinquedos',
    'Trade-In': 'Troca (Trade-In)',
    'Video Games': 'Videogames',
    'Water Sports': 'Esportes Aquáticos',
    "Women's Apparel": 'Vestuário Feminino',
    "Women's Clothing": 'Moda Feminina',
    "Women's Golf Clubs": 'Tacos de Golfe Femininos',
}

COUNTRY_PT_BR = {
    'Afganistán': 'Afeganistão',
    'Albania': 'Albânia',
    'Alemania': 'Alemanha',
    'Angola': 'Angola',
    'Arabia Saudí': 'Arábia Saudita',
    'Argelia': 'Argélia',
    'Argentina': 'Argentina',
    'Armenia': 'Armênia',
    'Australia': 'Austrália',
    'Austria': 'Áustria',
    'Azerbaiyán': 'Azerbaijão',
    'Bangladés': 'Bangladesh',
    'Barbados': 'Barbados',
    'Baréin': 'Bahrein',
    'Belice': 'Belize',
    'Benín': 'Benin',
    'Bielorrusia': 'Bielorrússia',
    'Bolivia': 'Bolívia',
    'Bosnia y Herzegovina': 'Bósnia e Herzegovina',
    'Botsuana': 'Botsuana',
    'Brasil': 'Brasil',
    'Bulgaria': 'Bulgária',
    'Burkina Faso': 'Burkina Faso',
    'Burundi': 'Burundi',
    'Bután': 'Butão',
    'Bélgica': 'Bélgica',
    'Camboya': 'Camboja',
    'Camerún': 'Camarões',
    'Canada': 'Canadá',
    'Chad': 'Chade',
    'Chile': 'Chile',
    'China': 'China',
    'Chipre': 'Chipre',
    'Colombia': 'Colômbia',
    'Corea del Sur': 'Coreia do Sul',
    'Costa Rica': 'Costa Rica',
    'Costa de Marfil': 'Costa do Marfim',
    'Croacia': 'Croácia',
    'Cuba': 'Cuba',
    'Dinamarca': 'Dinamarca',
    'Ecuador': 'Equador',
    'Egipto': 'Egito',
    'El Salvador': 'El Salvador',
    'Emiratos Árabes Unidos': 'Emirados Árabes Unidos',
    'Eritrea': 'Eritreia',
    'Eslovaquia': 'Eslováquia',
    'Eslovenia': 'Eslovênia',
    'España': 'Espanha',
    'Estados Unidos': 'Estados Unidos',
    'Estonia': 'Estônia',
    'Etiopía': 'Etiópia',
    'Filipinas': 'Filipinas',
    'Finlandia': 'Finlândia',
    'Francia': 'França',
    'Gabón': 'Gabão',
    'Georgia': 'Geórgia',
    'Ghana': 'Gana',
    'Grecia': 'Grécia',
    'Guadalupe': 'Guadalupe',
    'Guatemala': 'Guatemala',
    'Guayana Francesa': 'Guiana Francesa',
    'Guinea': 'Guiné',
    'Guinea Ecuatorial': 'Guiné Equatorial',
    'Guinea-Bissau': 'Guiné-Bissau',
    'Guyana': 'Guiana',
    'Haití': 'Haiti',
    'Honduras': 'Honduras',
    'Hong Kong': 'Hong Kong',
    'Hungría': 'Hungria',
    'India': 'Índia',
    'Indonesia': 'Indonésia',
    'Irak': 'Iraque',
    'Irlanda': 'Irlanda',
    'Irán': 'Irã',
    'Israel': 'Israel',
    'Italia': 'Itália',
    'Jamaica': 'Jamaica',
    'Japón': 'Japão',
    'Jordania': 'Jordânia',
    'Kazajistán': 'Cazaquistão',
    'Kenia': 'Quênia',
    'Kirguistán': 'Quirguistão',
    'Kuwait': 'Kuwait',
    'Laos': 'Laos',
    'Lesoto': 'Lesoto',
    'Liberia': 'Libéria',
    'Libia': 'Líbia',
    'Lituania': 'Lituânia',
    'Luxemburgo': 'Luxemburgo',
    'Líbano': 'Líbano',
    'Macedonia': 'Macedônia',
    'Madagascar': 'Madagascar',
    'Malasia': 'Malásia',
    'Mali': 'Mali',
    'Marruecos': 'Marrocos',
    'Martinica': 'Martinica',
    'Mauritania': 'Mauritânia',
    'Moldavia': 'Moldávia',
    'Mongolia': 'Mongólia',
    'Montenegro': 'Montenegro',
    'Mozambique': 'Moçambique',
    'Myanmar (Birmania)': 'Mianmar',
    'México': 'México',
    'Namibia': 'Namíbia',
    'Nepal': 'Nepal',
    'Nicaragua': 'Nicarágua',
    'Nigeria': 'Nigéria',
    'Noruega': 'Noruega',
    'Nueva Zelanda': 'Nova Zelândia',
    'Níger': 'Níger',
    'Omán': 'Omã',
    'Pakistán': 'Paquistão',
    'Panamá': 'Panamá',
    'Papúa Nueva Guinea': 'Papua-Nova Guiné',
    'Paraguay': 'Paraguai',
    'Países Bajos': 'Países Baixos',
    'Perú': 'Peru',
    'Polonia': 'Polônia',
    'Portugal': 'Portugal',
    'Qatar': 'Catar',
    'Reino Unido': 'Reino Unido',
    'República Centroafricana': 'República Centro-Africana',
    'República Checa': 'República Tcheca',
    'República Democrática del Congo': 'República Democrática do Congo',
    'República Dominicana': 'República Dominicana',
    'República de Gambia': 'Gâmbia',
    'República del Congo': 'República do Congo',
    'Ruanda': 'Ruanda',
    'Rumania': 'Romênia',
    'Rusia': 'Rússia',
    'Senegal': 'Senegal',
    'Serbia': 'Sérvia',
    'Sierra Leona': 'Serra Leoa',
    'Singapur': 'Singapura',
    'Siria': 'Síria',
    'Somalia': 'Somália',
    'Sri Lanka': 'Sri Lanka',
    'Suazilandia': 'Essuatíni',
    'SudAfrica': 'África do Sul',
    'Sudán': 'Sudão',
    'Sudán del Sur': 'Sudão do Sul',
    'Suecia': 'Suécia',
    'Suiza': 'Suíça',
    'Surinam': 'Suriname',
    'Sáhara Occidental': 'Saara Ocidental',
    'Tailandia': 'Tailândia',
    'Taiwán': 'Taiwan',
    'Tanzania': 'Tanzânia',
    'Tayikistán': 'Tajiquistão',
    'Togo': 'Togo',
    'Trinidad y Tobago': 'Trinidad e Tobago',
    'Turkmenistán': 'Turcomenistão',
    'Turquía': 'Turquia',
    'Túnez': 'Tunísia',
    'Ucrania': 'Ucrânia',
    'Uganda': 'Uganda',
    'Uruguay': 'Uruguai',
    'Uzbekistán': 'Uzbequistão',
    'Venezuela': 'Venezuela',
    'Vietnam': 'Vietnã',
    'Yemen': 'Iêmen',
    'Yibuti': 'Djibuti',
    'Zambia': 'Zâmbia',
    'Zimbabue': 'Zimbábue',
}

SORT_ALIASES = {
    'impact': 'impact',
    'risk': 'risk',
    'risk_pct': 'risk',
    'volume': 'volume',
    'orders': 'volume',
    'loss': 'loss',
    'negative_profit': 'loss',
    'avg_delay': 'avg_delay',
}


def _norm_key(value: str | None) -> str:
    return ' '.join(str(value or '').split()).lower()


def _build_forward_lookup(mapping: dict[str, str]) -> dict[str, str]:
    return {_norm_key(orig): pt for orig, pt in mapping.items()}


def _build_reverse_lookup(mapping: dict[str, str]) -> dict[str, str]:
    rev: dict[str, str] = {}
    for orig, pt in mapping.items():
        rev[_norm_key(orig)] = orig
        rev[_norm_key(pt)] = orig
    return rev


_FWD_REGION = _build_forward_lookup(REGION_PT_BR)
_FWD_MODE = _build_forward_lookup(SHIPPING_MODE_PT_BR)
_FWD_CATEGORY = _build_forward_lookup(CATEGORY_PT_BR)
_FWD_COUNTRY = _build_forward_lookup(COUNTRY_PT_BR)

_REV_REGION = _build_reverse_lookup(REGION_PT_BR)
_REV_MODE = _build_reverse_lookup(SHIPPING_MODE_PT_BR)
_REV_CATEGORY = _build_reverse_lookup(CATEGORY_PT_BR)
_REV_COUNTRY = _build_reverse_lookup(COUNTRY_PT_BR)


def tr_region(value: str | None) -> str:
    clean = ' '.join(str(value or '').split())
    return _FWD_REGION.get(clean.lower(), clean)


def tr_shipping_mode(value: str | None) -> str:
    clean = ' '.join(str(value or '').split())
    return _FWD_MODE.get(clean.lower(), clean)


def tr_category(value: str | None) -> str:
    clean = ' '.join(str(value or '').split())
    return _FWD_CATEGORY.get(clean.lower(), clean)


def tr_country(value: str | None) -> str:
    clean = ' '.join(str(value or '').split())
    return _FWD_COUNTRY.get(clean.lower(), clean)


def to_raw_region(value: str | None) -> str:
    clean = ' '.join(str(value or '').split())
    return _REV_REGION.get(clean.lower(), clean)


def to_raw_shipping_mode(value: str | None) -> str:
    clean = ' '.join(str(value or '').split())
    return _REV_MODE.get(clean.lower(), clean)


def to_raw_category(value: str | None) -> str:
    clean = ' '.join(str(value or '').split())
    return _REV_CATEGORY.get(clean.lower(), clean)


def to_raw_country(value: str | None) -> str:
    clean = ' '.join(str(value or '').split())
    return _REV_COUNTRY.get(clean.lower(), clean)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    fields = {str(err.get('loc', [''])[-1]) for err in errors}
    if 'delay_reduction_days' in fields:
        message = 'Quantidade de dias inválida. Revise o valor informado e tente novamente.'
    elif 'eu_demand_share' in fields:
        message = 'Percentual de demanda inválido. Revise o valor informado e tente novamente.'
    elif 'cost_per_order' in fields:
        message = 'Custo por pedido inválido. Revise o valor informado e tente novamente.'
    elif 'scheduled_days' in fields:
        message = 'Prazo programado inválido (use entre 0 e 30 dias).'
    elif 'quantity' in fields:
        message = 'Quantidade inválida (informe ao menos 1 unidade).'
    elif 'product_price' in fields:
        message = 'Preço do produto inválido (informe um valor maior ou igual a zero).'
    elif 'order_month' in fields:
        message = 'Mês do pedido inválido (use um valor entre 1 e 12).'
    elif 'order_weekday' in fields:
        message = 'Dia da semana inválido (use 0 para segunda-feira até 6 para domingo).'
    elif request.url.path.startswith('/api/predict'):
        message = 'Dados inválidos para previsão. Revise os campos informados e tente novamente.'
    else:
        message = 'Não foi possível executar a simulação. Revise os valores informados e tente novamente.'
    return JSONResponse(status_code=400, content={'error': {'code': 'invalid_input', 'message': message}})


def _is_all_filter(value: str | None, all_tokens: tuple[str, ...]) -> bool:
    if not value:
        return True
    return value.strip() in all_tokens


def filter_region(df: pd.DataFrame, region: str | None) -> pd.DataFrame:
    if _is_all_filter(region, ('Todas', 'All', 'Todas as regiões')):
        return df
    clean = region.strip()
    if clean in REGION_GROUPS:
        names = REGION_GROUPS[clean]
    else:
        raw = to_raw_region(clean)
        names = [raw, 'South of  USA'] if raw == 'South of USA' else [raw]
    return df[df['order region'].str.strip().isin(names)]


@lru_cache(maxsize=1)
def dataset() -> pd.DataFrame:
    wanted = {
        'order region', 'order country', 'order city', 'order state', 'shipping mode',
        'late_delivery_risk', 'days for shipping (real)', 'days for shipment (scheduled)',
        'sales', 'order profit per order', 'order item total', 'order item product price',
        'product name', 'product card id', 'category name', 'product price',
        'order item quantity', 'order item gross weight (kg)', 'order item volume (cm3)',
        'order id',
    }
    df = pd.read_csv(DATA, encoding='latin-1', usecols=lambda c: c.strip().lower() in wanted)
    df.columns = df.columns.str.strip().str.lower()
    numeric_cols = [
        'late_delivery_risk', 'days for shipping (real)', 'days for shipment (scheduled)',
        'sales', 'order profit per order', 'order item total', 'order item product price',
        'product price', 'order item quantity',
    ]
    for col in numeric_cols:
        if col in df:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=['order region', 'late_delivery_risk', 'days for shipping (real)', 'days for shipment (scheduled)']).copy()
    df['delay_days'] = (df['days for shipping (real)'] - df['days for shipment (scheduled)']).clip(lower=0)
    return df


@app.get('/api/overview')
def overview(region: str = 'Todas'):
    d = filter_region(dataset(), region)
    if d.empty:
        return {
            'rows': 0,
            'unique_orders': 0,
            'late_risk_pct': 0.0,
            'avg_delay_days': 0.0,
            'late_rows': 0,
            'regions': [],
            'available_regions': AVAILABLE_MACRO_REGIONS,
        }
    regions_table = (
        d.groupby('order region')
        .agg(
            orders=('order region', 'size'),
            risk_pct=('late_delivery_risk', 'mean'),
            avg_delay=('delay_days', 'mean'),
            sales=('sales', 'sum'),
        )
        .sort_values('orders', ascending=False)
        .reset_index()
        .assign(
            risk_pct=lambda x: (x.risk_pct * 100).round(2),
            avg_delay=lambda x: x.avg_delay.round(2),
            sales=lambda x: x.sales.round(2),
        )
    )
    regions_table['order region'] = regions_table['order region'].map(tr_region)
    return {
        'rows': int(len(d)),
        'unique_orders': int(d['order id'].nunique()),
        'late_risk_pct': round(float(d['late_delivery_risk'].mean() * 100), 2),
        'avg_delay_days': round(float(d['delay_days'].mean()), 2),
        'late_rows': int(d['late_delivery_risk'].sum()),
        'regions': regions_table.to_dict('records'),
        'available_regions': AVAILABLE_MACRO_REGIONS,
    }


def _apply_route_volume_floor(grouped: pd.DataFrame, sort_key: str, min_orders: int) -> tuple[pd.DataFrame, int]:
    if grouped.empty or min_orders <= 1 or sort_key == 'volume':
        return grouped, 0
    for floor in (min_orders, 15):
        if floor <= 1:
            continue
        eligible = grouped[grouped['orders'] >= floor]
        if len(eligible) >= min(5, len(grouped)):
            return eligible, int(floor)
    return grouped, 0


@app.get('/api/routes')
def routes(region: str = 'Todas', mode: str = 'Todas', sort_by: str = 'impact', min_orders: int = 50):
    base = dataset()
    d_region = filter_region(base, region)
    mode_source = d_region if not d_region.empty else base
    raw_modes = mode_source['shipping mode'].dropna().astype(str).str.strip().unique().tolist()
    shipping_modes = sorted({tr_shipping_mode(m) for m in raw_modes})

    d = d_region
    if not _is_all_filter(mode, ('Todas', 'All', 'Todas as modalidades')):
        raw_mode = to_raw_shipping_mode(mode)
        d = d[d['shipping mode'].astype(str).str.strip().eq(raw_mode)]

    if d.empty:
        return {
            'routes': [],
            'summary': {
                'lines': 0,
                'orders': 0,
                'risk_lines': 0,
                'risk_pct': 0.0,
                'avg_delay_days': 0.0,
                'sales_usd': 0.0,
                'profit_usd': 0.0,
                'negative_profit_loss_usd': 0.0,
            },
            'shipping_modes': shipping_modes,
            'available_regions': AVAILABLE_MACRO_REGIONS,
            'sort_by': SORT_ALIASES.get(sort_by.strip().lower(), 'impact'),
            'applied_min_orders': 0,
            'total_routes': 0,
        }

    neg_loss = d['order profit per order'].clip(upper=0).abs()
    summary = {
        'lines': int(len(d)),
        'orders': int(d['order id'].nunique()),
        'risk_lines': int(d['late_delivery_risk'].sum()),
        'risk_pct': round(float(d['late_delivery_risk'].mean() * 100), 2),
        'avg_delay_days': round(float(d['delay_days'].mean()), 2),
        'sales_usd': round(float(d['sales'].sum()), 2),
        'profit_usd': round(float(d['order profit per order'].sum()), 2),
        'negative_profit_loss_usd': round(float(neg_loss.sum()), 2),
    }

    work = d.assign(_neg_loss=neg_loss)
    g = (
        work.groupby(['order region', 'order country'], dropna=False)
        .agg(
            orders=('order id', 'count'),
            unique_orders=('order id', 'nunique'),
            risk_pct=('late_delivery_risk', 'mean'),
            avg_delay=('delay_days', 'mean'),
            sales=('sales', 'sum'),
            profit=('order profit per order', 'sum'),
            negative_profit_loss_usd=('_neg_loss', 'sum'),
        )
        .reset_index()
    )
    g['impact_score'] = g['orders'] * g['risk_pct']

    sort_key = SORT_ALIASES.get(sort_by.strip().lower(), 'impact')
    filtered_g, applied_floor = _apply_route_volume_floor(g, sort_key, max(0, int(min_orders)))

    sort_columns = {
        'impact': (['impact_score', 'orders'], [False, False]),
        'risk': (['risk_pct', 'orders'], [False, False]),
        'volume': (['orders', 'risk_pct'], [False, False]),
        'loss': (['negative_profit_loss_usd', 'orders'], [False, False]),
        'avg_delay': (['avg_delay', 'orders'], [False, False]),
    }
    cols, asc = sort_columns[sort_key]
    top = filtered_g.sort_values(cols, ascending=asc).head(15).drop(columns=['impact_score']).copy()
    top['order region'] = top['order region'].map(tr_region)
    top['order country'] = top['order country'].map(tr_country)
    top['risk_pct'] = (top['risk_pct'] * 100).round(1)
    top['avg_delay'] = top['avg_delay'].round(2)
    top['sales'] = top['sales'].round(2)
    top['profit'] = top['profit'].round(2)
    top['negative_profit_loss_usd'] = top['negative_profit_loss_usd'].round(2)

    return {
        'routes': top.fillna(0).to_dict('records'),
        'summary': summary,
        'shipping_modes': shipping_modes,
        'available_regions': AVAILABLE_MACRO_REGIONS,
        'sort_by': sort_key,
        'applied_min_orders': applied_floor,
        'total_routes': int(len(g)),
    }


@lru_cache(maxsize=1)
def bi_supporting_data():
    data_dir = DATA.parent
    dimensions = pd.read_csv(data_dir / 'product_dimensions.csv', encoding='latin-1')
    dimensions['Product Card Id'] = pd.to_numeric(dimensions['Product Card Id'], errors='coerce')
    dimensions['Package Volume (cm3)'] = (
        dimensions['Package Length (cm)'] * dimensions['Package Width (cm)'] * dimensions['Package Height (cm)']
    )
    logs = pd.read_csv(data_dir / 'tokenized_access_logs.csv', encoding='latin-1', usecols=['Product', 'Category'])
    return dimensions, {
        'events': int(len(logs)),
        'products': int(logs['Product'].nunique()),
        'categories': int(logs['Category'].nunique()),
    }


@app.get('/api/bi')
def bi():
    d = dataset().copy()
    # “Order Profit Per Order” varies by product line. Sum line values rather
    # than deduplicating by order. Negative values are gross negative entries,
    # not the company's net loss and not necessarily caused by a delivery delay.
    d['negative_profit'] = d['order profit per order'].clip(upper=0).abs()
    d['delayed_negative_profit'] = d['negative_profit'].where(d['late_delivery_risk'] == 1, 0)
    d['late_delay_days'] = d['delay_days'].where(d['late_delivery_risk'] == 1)
    dimensions, logs = bi_supporting_data()
    modes = d.groupby('shipping mode').agg(
        lines=('order id', 'size'),
        orders=('order id', 'nunique'),
        risk_pct=('late_delivery_risk', 'mean'),
        avg_late_delay=('late_delay_days', 'mean'),
        sales=('sales', 'sum'),
        negative_profit_loss_usd=('negative_profit', 'sum'),
        delayed_negative_profit_usd=('delayed_negative_profit', 'sum'),
    ).reset_index()
    regions = d.groupby('order region').agg(
        lines=('order id', 'size'),
        orders=('order id', 'nunique'),
        risk_pct=('late_delivery_risk', 'mean'),
        avg_late_delay=('late_delay_days', 'mean'),
        sales=('sales', 'sum'),
        negative_profit_loss_usd=('negative_profit', 'sum'),
        delayed_negative_profit_usd=('delayed_negative_profit', 'sum'),
    ).reset_index()
    products = d.groupby(['product card id', 'product name'], dropna=False).agg(
        lines=('order id', 'size'),
        orders=('order id', 'nunique'),
        risk_pct=('late_delivery_risk', 'mean'),
        avg_late_delay=('late_delay_days', 'mean'),
        sales=('sales', 'sum'),
        negative_profit_loss_usd=('negative_profit', 'sum'),
        delayed_negative_profit_usd=('delayed_negative_profit', 'sum'),
        units=('order item quantity', 'sum'),
    ).reset_index()
    products = products.merge(
        dimensions[['Product Card Id', 'Package Gross Weight (kg)', 'Package Volume (cm3)', 'Estimate Basis']],
        left_on='product card id',
        right_on='Product Card Id',
        how='left',
    )
    for table in (modes, regions, products):
        table['risk_pct'] = (table['risk_pct'] * 100).round(2)
        table['avg_late_delay'] = table['avg_late_delay'].round(2)
        for col in ('sales', 'negative_profit_loss_usd', 'delayed_negative_profit_usd'):
            table[col] = table[col].round(2)
    delayed = d[d['late_delivery_risk'] == 1]
    total_negative = float(d['negative_profit'].sum())
    delayed_negative = float(delayed['negative_profit'].sum())
    eu = filter_region(d, 'Europe')
    western_eu = d[d['order region'].str.strip().eq('Western Europe')]
    first_class = modes[modes['shipping mode'].eq('First Class')]
    first_risk = float(first_class.iloc[0]['risk_pct']) if len(first_class) else 0
    first_lines = int(first_class.iloc[0]['lines']) if len(first_class) else 0
    fmt_pt = lambda value, decimals=0: f'{float(value):,.{decimals}f}'.replace(',', '@').replace('.', ',').replace('@', '.')

    modes['shipping mode'] = modes['shipping mode'].map(tr_shipping_mode)
    regions['order region'] = regions['order region'].map(tr_region)

    top_products = products.sort_values('negative_profit_loss_usd', ascending=False).head(8).copy()
    top8_share = float(top_products['negative_profit_loss_usd'].sum() / total_negative * 100) if total_negative else 0
    top_products = top_products.rename(columns={
        'product name': 'product_name',
        'product card id': 'product_id',
        'avg_late_delay': 'avg_delay_when_risk',
        'Package Gross Weight (kg)': 'package_gross_weight_kg',
        'Package Volume (cm3)': 'package_volume_cm3',
        'Estimate Basis': 'dimension_estimate_basis',
    })
    top_products = top_products.astype(object).where(pd.notna(top_products), None)
    return {
        'observed': {
            'lines': int(len(d)),
            'orders': int(d['order id'].nunique()),
            'risk_lines': int(d['late_delivery_risk'].sum()),
            'risk_orders': int(delayed['order id'].nunique()),
            'risk_pct': round(float(d['late_delivery_risk'].mean() * 100), 2),
            'avg_delay_days_all': round(float(d['delay_days'].mean()), 2),
            'avg_delay_days_late': round(float(delayed['delay_days'].mean()), 2),
            'sales_usd': round(float(d['sales'].sum()), 2),
            'negative_profit_loss_usd': round(total_negative, 2),
            'delayed_negative_profit_usd': round(delayed_negative, 2),
            'delayed_negative_profit_share_pct': round(delayed_negative / total_negative * 100, 2) if total_negative else 0,
            'late_negative_lines': int(((d['negative_profit'] > 0) & (d['late_delivery_risk'] == 1)).sum()),
            'late_negative_orders': int(d.loc[(d['negative_profit'] > 0) & (d['late_delivery_risk'] == 1), 'order id'].nunique()),
            'top8_negative_loss_share_pct': round(top8_share, 2),
            'modes': modes.sort_values('delayed_negative_profit_usd', ascending=False).to_dict('records'),
            'regions': regions.sort_values('delayed_negative_profit_usd', ascending=False).to_dict('records'),
            'top_products': top_products.to_dict('records'),
            'europe': {
                'lines': int(len(eu)),
                'risk_pct': round(float(eu['late_delivery_risk'].mean() * 100), 2) if len(eu) else 0,
                'risk_lines': int(eu['late_delivery_risk'].sum()),
                'negative_profit_loss_usd': round(float(eu['negative_profit'].sum()), 2),
            },
        },
        'data_sources': {
            'transactions': {
                'rows': int(len(d)),
                'orders': int(d['order id'].nunique()),
                'late_negative_lines': int(((d['negative_profit'] > 0) & (d['late_delivery_risk'] == 1)).sum()),
                'file': 'DataCoSupplyChainDataset.csv',
            },
            'product_dimensions': {
                'products': int(dimensions['Product Card Id'].nunique()),
                'file': 'product_dimensions.csv',
                'note': 'Peso bruto e volume são estimativas da tabela auxiliar; volume calculado por comprimento × largura × altura.',
            },
            'web_logs': {
                'events': logs['events'],
                'products': logs['products'],
                'categories': logs['categories'],
                'file': 'tokenized_access_logs.csv',
                'note': 'Eventos de navegação não são pedidos e não estão ligados às transações.',
            },
        },
        'recommendations': [
            {
                'title': 'Investigar Promessa da Primeira Classe',
                'evidence': f'Primeira Classe tem {fmt_pt(first_risk, 2)}% de linhas com risco em {fmt_pt(first_lines)} linhas. Revisar promessa e capacidade por produto e rota.',
                'kind': 'Observado',
            },
            {
                'title': 'Dimensionar Piloto na Europa Ocidental',
                'evidence': f'A região tem {fmt_pt(len(western_eu))} linhas e US$ {fmt_pt(western_eu["sales"].sum())} em vendas históricas; validar estoque, cobertura e custo do CD.',
                'kind': 'Hipótese',
            },
            {
                'title': 'Definir Acordo de Prazo (SLA) de Parceiros nos EUA e China',
                'evidence': 'Comparar prazo, custo total, cobertura e penalidades por rota antes de terceirizar a operação.',
                'kind': 'Dado Faltante',
            },
        ],
        'warning': 'Prejuízo bruto registrado = soma do valor absoluto das linhas negativas de Lucro por Pedido; não é prejuízo líquido da empresa. Associação com atraso não prova causalidade. Cenários são hipóteses, sem custos reais de CD ou Operador Logístico (3PL).',
    }


class Scenario(BaseModel):
    eu_demand_share: float = Field(0.3, ge=0, le=1)
    delay_reduction_days: float = Field(1.0, ge=0, le=30)
    cost_per_order: float = Field(0, ge=0)
    orders_served: int | None = None


@app.post('/api/scenario')
def scenario(x: Scenario):
    try:
        eu = filter_region(dataset(), 'Europe')
        if eu.empty:
            return JSONResponse(status_code=422, content={'error': {'code': 'no_europe_data', 'message': 'Não há pedidos europeus disponíveis para simular.'}})
        n = int(x.orders_served if x.orders_served is not None else len(eu))
        delayed = int((eu['late_delivery_risk'] == 1).sum())
        observed_delay = float(eu['delay_days'].mean())
        reduction = min(x.delay_reduction_days, observed_delay)
        return {
            'scope': 'Simulação Hipotética (Não é Resultado Observado)',
            'europe_orders_in_csv': int(len(eu)),
            'orders_assumed': n,
            'risk_orders_historical': delayed,
            'observed_europe_avg_delay_days': round(observed_delay, 2),
            'delay_reduction_assumption_days': x.delay_reduction_days,
            'applied_delay_reduction_days': round(reduction, 2),
            'estimated_delay_days_avoided': round(n * x.eu_demand_share * reduction, 1),
            'assumed_cost': round(n * x.eu_demand_share * x.cost_per_order, 2),
            'roi': 'Não Calculado: Sem Dados Validados de Benefício e Custo',
            'note': 'Apenas simulação hipotética. O CSV não estabelece efeito causal de um novo centro de distribuição.',
        }
    except Exception:
        return JSONResponse(status_code=500, content={'error': {'code': 'simulation_failed', 'message': 'A simulação não pôde ser concluída. Confira os dados e tente novamente.'}})


@lru_cache(maxsize=1)
def load_prediction_bundle() -> dict:
    if not MODEL_PATH.exists():
        raise RuntimeError('Modelo preditivo (modelo_atraso.joblib) não encontrado no servidor.')
    try:
        import joblib
        import sklearn  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(f'Dependência de aprendizado de máquina ausente no ambiente ({exc.name}).') from exc
    try:
        bundle = joblib.load(MODEL_PATH)
    except Exception as exc:
        raise RuntimeError(f'Não foi possível carregar modelo_atraso.joblib: {exc}') from exc
    if not isinstance(bundle, dict) or 'pipeline' not in bundle:
        raise RuntimeError('Arquivo modelo_atraso.joblib em formato inválido.')
    return bundle


def check_model_availability() -> tuple[bool, str | None]:
    try:
        load_prediction_bundle()
        return True, None
    except RuntimeError as exc:
        return False, str(exc)


def _model_category_lookup(bundle: dict) -> dict[str, dict[str, str]]:
    feature_names = ['Shipping Mode', 'Order Region', 'Order Country', 'Category Name', 'Product Name']
    lookup: dict[str, dict[str, str]] = {col: {} for col in feature_names}
    try:
        ohe = bundle['pipeline'].named_steps['prep'].named_transformers_['cat'].named_steps['onehot']
        for col, categories in zip(feature_names, ohe.categories_):
            lookup[col] = {_norm_key(cat): str(cat) for cat in categories}
    except Exception:
        pass
    return lookup


@lru_cache(maxsize=1)
def _build_predict_options() -> dict:
    d = dataset()
    raw_modes = d['shipping mode'].dropna().astype(str).str.strip().unique().tolist()
    shipping_modes = sorted({tr_shipping_mode(m) for m in raw_modes})

    region_series = d['order region'].dropna().astype(str).map(tr_region)
    country_series = d['order country'].dropna().astype(str).map(tr_country)
    regions = sorted(region_series.unique().tolist())
    countries = sorted(country_series.unique().tolist())

    rc_df = pd.DataFrame({'region': region_series, 'country': country_series}).dropna().drop_duplicates()
    regions_countries: dict[str, list[str]] = {
        reg: sorted(grp['country'].unique().tolist())
        for reg, grp in rc_df.groupby('region')
    }

    price_col = 'product price' if 'product price' in d.columns else 'order item product price'
    prod_df = d[['category name', 'product name', price_col]].dropna(subset=['category name', 'product name']).copy()
    prod_df['category_name'] = prod_df['category name'].astype(str).map(tr_category)
    prod_df['product_name'] = prod_df['product name'].astype(str).str.strip()
    prod_df['product_price'] = pd.to_numeric(prod_df[price_col], errors='coerce').fillna(0.0)

    grouped_products = (
        prod_df.groupby(['product_name', 'category_name'], as_index=False)
        .agg(lines=('product_price', 'size'), product_price=('product_price', 'median'))
        .sort_values(['lines', 'product_name'], ascending=[False, True])
    )
    grouped_products['product_price'] = grouped_products['product_price'].round(2)

    top_products = grouped_products.head(20)[['product_name', 'category_name', 'product_price', 'lines']].to_dict('records')
    categories = sorted(grouped_products['category_name'].unique().tolist())
    categories_products = {
        cat: grp[['product_name', 'product_price']].to_dict('records')
        for cat, grp in grouped_products.groupby('category_name')
    }

    presets = [
        {
            'id': 'critical_first_class_eu',
            'label': 'Caso Crítico: Primeira Classe · Europa',
            'description': 'Envio expresso (1 dia) para a França — alta probabilidade histórica de atraso.',
            'payload': {
                'shipping_mode': 'Primeira Classe',
                'order_region': 'Europa Ocidental',
                'order_country': 'França',
                'category_name': 'Pesca',
                'product_name': 'Field & Stream Sportsman 16 Gun Fire Safe',
                'scheduled_days': 1,
                'quantity': 1,
                'product_price': 399.98,
                'order_month': 11,
                'order_weekday': 2,
            },
        },
        {
            'id': 'standard_us',
            'label': 'Caso Padrão: Classe Padrão · EUA',
            'description': 'Envio padrão (4 dias) para o Leste dos EUA.',
            'payload': {
                'shipping_mode': 'Classe Padrão',
                'order_region': 'Leste dos EUA',
                'order_country': 'Estados Unidos',
                'category_name': 'Chuteiras e Travas',
                'product_name': 'Perfect Fitness Perfect Rip Deck',
                'scheduled_days': 4,
                'quantity': 2,
                'product_price': 59.99,
                'order_month': 5,
                'order_weekday': 1,
            },
        },
    ]

    return {
        'shipping_modes': shipping_modes,
        'regions': regions,
        'countries': countries,
        'regions_countries': regions_countries,
        'categories': categories,
        'products': top_products,
        'categories_products': categories_products,
        'presets': presets,
    }


@app.get('/api/predict-options')
@app.get('/api/predict/options')
def predict_options():
    available, reason = check_model_availability()
    options = _build_predict_options()
    return {
        'model_available': available,
        'model_message': reason,
        **options,
    }


class OrderFeatures(BaseModel):
    shipping_mode: str = Field(..., min_length=1)
    order_region: str = Field(..., min_length=1)
    order_country: str = Field(..., min_length=1)
    category_name: str = Field(..., min_length=1)
    product_name: str = Field(..., min_length=1)
    scheduled_days: float = Field(..., ge=0, le=30)
    quantity: float = Field(..., ge=1, le=1000)
    product_price: float = Field(..., ge=0)
    order_month: int = Field(..., ge=1, le=12)
    order_weekday: int = Field(..., ge=0, le=6)


def _classify_risk(probability: float) -> tuple[str, str]:
    if probability >= 0.65:
        return 'Alto', 'Alto Risco de Atraso'
    if probability >= 0.45:
        return 'Moderado', 'Risco Moderado de Atraso'
    return 'Baixo', 'Baixo Risco de Atraso'


@app.post('/api/predict')
def predict(x: OrderFeatures):
    try:
        bundle = load_prediction_bundle()
    except RuntimeError as exc:
        reason = str(exc)
        return JSONResponse(
            status_code=503,
            content={
                'detail': reason,
                'error': {'code': 'model_unavailable', 'message': reason},
            },
        )

    lookup = _model_category_lookup(bundle)
    raw_row = {
        'Shipping Mode': to_raw_shipping_mode(x.shipping_mode),
        'Order Region': to_raw_region(x.order_region),
        'Order Country': to_raw_country(x.order_country),
        'Category Name': to_raw_category(x.category_name),
        'Product Name': x.product_name.strip(),
    }
    normalized_row = {
        col: lookup.get(col, {}).get(_norm_key(val), val.strip())
        for col, val in raw_row.items()
    }
    normalized_row.update({
        'Days for shipment (scheduled)': x.scheduled_days,
        'Order Item Quantity': x.quantity,
        'Product Price': x.product_price,
        'order_month': x.order_month,
        'order_weekday': x.order_weekday,
    })

    row = pd.DataFrame([normalized_row])
    pipe = bundle['pipeline']
    pred = int(pipe.predict(row)[0])
    prob = float(pipe.predict_proba(row)[0][1])
    risk_level, risk_label = _classify_risk(prob)
    return {
        'available': True,
        'late_delivery_risk': pred,
        'probability': round(prob, 4),
        'probability_pct': round(prob * 100, 1),
        'risk_level': risk_level,
        'risk_label': risk_label,
        'interpretation': 'Probabilidade histórica estimada pelo modelo de referência; não é garantia de atraso nem mede efeito causal de mudança de CD.',
    }


app.mount('/', StaticFiles(directory=Path(__file__).parent, html=True), name='frontend')
