FROM python:3.12.12-slim
WORKDIR /app



COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5000
CMD flask run --cert=/run/secrets/collection_cert --key=/run/secrets/collection_key --host=0.0.0.0 --port=5000