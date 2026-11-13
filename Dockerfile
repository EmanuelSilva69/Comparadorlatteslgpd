FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --system --uid 10001 --create-home app

# Apenas o código da aplicação. Dados pessoais entram por volume (ver compose),
# exceto academicData.ts, resumos_cache.json e indice_fontes.json, que fazem
# parte da entrega e são necessários para o site funcionar.
COPY api.py auth.py data_parser.py academicData.ts resumos_cache.json indice_fontes.json ./
COPY public/ ./public/

USER app

EXPOSE 8000

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
