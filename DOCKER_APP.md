# Smart Talent API Docker

Build a imagem contendo FastAPI, dependências e `modelo_atraso.joblib`:

```powershell
docker build -t smart-talent-api .
```

Inicie a API:

```powershell
docker run --rm -p 8000:8000 -e "ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173" smart-talent-api
```

A API ficará em `http://localhost:8000`; documentação interativa em `http://localhost:8000/docs`. Teste `GET /health` e `POST /predict`.

## Consumir a partir de um frontend React separado

Com o container ativo e o React local em `http://localhost:5173`, o navegador pode chamar a API em `http://localhost:8000`. Configure `ALLOWED_ORIGINS` para a origem exata em que a tela React está sendo servida (incluindo esquema e porta). Em produção, substitua pelos domínios reais do frontend; não use `*` com credenciais.

```js
const response = await fetch('http://localhost:8000/predict', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    shipping_mode: 'First Class',
    order_region: 'Western Europe',
    order_country: 'Reino Unido',
    category_name: 'Cleats',
    product_name: "Nike Men's Free 5.0+ Running Shoe",
    scheduled_days: 1,
    quantity: 1,
    product_price: 190,
    order_month: 6,
    order_weekday: 2
  })
});
const prediction = await response.json();
```

A imagem não inclui o frontend de teste nem os CSVs. O avaliador usa sua própria aplicação React para chamar a API; a imagem inclui somente o serviço e o modelo treinado.
