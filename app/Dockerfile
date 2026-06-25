# Base pinada por digest (supply-chain): reprodutível e imune a re-tag de 'slim'.
# Atualizar o digest junto com a versão do Python, conscientemente.
FROM python:3.11-slim@sha256:cdbd05fb6f457ca275ff51ce00d93d865ca0b6a25f5ffb08262d94f6835771e5
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app
# System deps do WeasyPrint (render HTML/CSS -> PDF vetorial) + fontes p/ acentos
# + Tesseract (OCR do brinco por foto, Fase 2).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangocairo-1.0-0 libpangoft2-1.0-0 \
        libcairo2 libgdk-pixbuf-2.0-0 libffi8 \
        fonts-dejavu-core \
        tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
# Processo não roda como root: limita o estrago de um eventual RCE na app.
# uid fixo alto (não colide com users do host); home p/ cache de fontes do WeasyPrint.
RUN useradd --create-home --uid 10001 appuser
USER appuser
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
