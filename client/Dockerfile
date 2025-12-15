# Usa un'immagine base leggera di Python
FROM python:3.11-slim

# Imposta la directory di lavoro nel container
WORKDIR /app

# Variabili d'ambiente per evitare file .pyc e buffer output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Installa le dipendenze di sistema (necessarie se usi librerie compilate, altrimenti opzionale ma consigliato)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copia prima solo il file dei requisiti (per sfruttare la cache di Docker)
COPY requirements.txt .

# Installa le dipendenze Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia tutto il resto del codice sorgente nel container
COPY . .

# Comando di default all'avvio del container.
# Scegline UNO in base a cosa è il tuo client:

# OPZIONE A: Se è uno script che fa una cosa e poi esce (es. test_client.py)
CMD ["python", "client.py"]

# OPZIONE B: Se è un'app interattiva o che deve rimanere in attesa (es. loop infinito)
# CMD ["python", "-u", "main.py"]