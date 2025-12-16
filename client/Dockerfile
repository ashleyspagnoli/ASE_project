FROM python:3.12.12-slim

# Imposta la directory di lavoro dentro il container
WORKDIR /app

# Copia i requisiti e installali
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia tutto il codice del client dentro il container
COPY . .

# Copia il certificato (Assumiamo che il file .pem sia nella cartella del client o sottocartella)
# Se il certificato è fuori dalla cartella client, dovrai spostarlo o copiarlo durante la build
# Esempio: Copiamo un file fittizio, assicurati che il file esista nella cartella di build
# COPY gateway_cert.pem /app/certs/gateway_cert.pem

# Definisce le variabili d'ambiente di default (sovrascrivibili da docker run)
ENV PYTHONUNBUFFERED=1

# Comando di avvio
CMD ["python", "client.py"]