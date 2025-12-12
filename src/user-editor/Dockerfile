FROM python:3.11-slim

WORKDIR /app
# ---------------------------------------------------------------
COPY ./user-editor/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# -----------------------------------------------------------------------

# ---------------------------------------------------------------

RUN apt-get update && \
    apt-get install -y ca-certificates && \
    rm -rf /var/lib/apt/lists/* # Pulizia della cache APT

COPY ./certs/user-manager/user-manager.crt /usr/local/share/ca-certificates/user-manager.crt 

RUN chmod 644 /usr/local/share/ca-certificates/user-manager.crt && \
    update-ca-certificates

ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
# ---------------------------------------------------------------

COPY . .
# ---------------------------------------------------------------