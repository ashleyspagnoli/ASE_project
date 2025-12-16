FROM python:3.12.12-slim

WORKDIR /history

COPY requirements.txt .

RUN pip install -r requirements.txt
COPY . .

EXPOSE 5000

CMD flask run --cert=/run/secrets/history_cert --key=/run/secrets/history_key --host=0.0.0.0 --port=5000
