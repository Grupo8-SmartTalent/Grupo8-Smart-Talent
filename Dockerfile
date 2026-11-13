FROM python:3.11-slim
WORKDIR /app
COPY requirements-api.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY src/api.py ./src/api.py
COPY modelo_atraso.joblib ./modelo_atraso.joblib
EXPOSE 8000
CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]
