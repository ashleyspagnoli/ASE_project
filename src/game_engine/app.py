from flask import Flask
from routes import game_blueprint

def create_app():
    app = Flask(__name__)
    app.register_blueprint(game_blueprint, url_prefix="/game")
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
