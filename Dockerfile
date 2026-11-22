FROM python:3.11-slim

WORKDIR /app

# Bibliotecas de sistema necessárias para o WeasyPrint (geração de PDFs):
# pango/cairo/cgdk-pixbuf para renderização, libffi-dev para cffi, shared-mime-info
# e fontes para uma tipografia consistente nos PDFs.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Instala dependências primeiro para aproveitar o cache do Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código
COPY . .

# Comando para iniciar o servidor com auto-reload
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
