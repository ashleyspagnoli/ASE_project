# app.py
from flask import Flask
from routes import game_blueprint
from flask_swagger_ui import get_swaggerui_blueprint
from extensions import socketio
import events

def create_app():
    app = Flask(__name__)
    
    # Configurazione Swagger
    SWAGGER_URL = '/apidocs'  
    API_URL = '/static/openapi.yml'
    swaggerui_blueprint = get_swaggerui_blueprint(
        SWAGGER_URL,
        API_URL,
        config={'app_name': "Card Game API Documentation"}
    )
    app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

    # Registrazione Blueprint Gioco
    app.register_blueprint(game_blueprint, url_prefix="/game")
    
    # Inizializzazione SocketIO
    # cors_allowed_origins="*" è fondamentale in sviluppo se frontend e backend sono su porte diverse
    socketio.init_app(app, cors_allowed_origins="*") 
    
    return app

if __name__ == "__main__":
    app = create_app()
    # <--- 3. IMPORTANTE: Usa socketio.run, NON app.run
    # allow_unsafe_werkzeug=True serve se usi environments di sviluppo particolari, 
    # ma solitamente basta debug=True
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)