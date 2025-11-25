# Usa un'immagine Python base
FROM python:3.11-slim

# Imposta la directory di lavoro nel container
WORKDIR /app

# Copia i requisiti e installa le dipendenze
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia il resto del codice dell'applicazione
COPY . .
# Comando per avviare il server (usando Uvicorn per FastAPI)
CMD ["uvicorn", "gateway:app", "--host", "0.0.0.0", "--port", "5000"]