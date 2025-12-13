FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

ENV FLASK_APP=app.py

CMD flask run --cert=/run/secrets/game_engine_cert --key=/run/secrets/game_engine_key --host=0.0.0.0 --port=5000