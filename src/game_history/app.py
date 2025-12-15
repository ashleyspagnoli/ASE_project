from flask import Flask
from routes import history_blueprint
from consumer import start_consumer

app = Flask(__name__)
app.register_blueprint(history_blueprint)

# Start consumer
start_consumer()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)