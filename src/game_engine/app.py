from flask import Flask
from routes import game_blueprint
from flask_swagger_ui import get_swaggerui_blueprint

def create_app():
    app = Flask(__name__)
    
    SWAGGER_URL = '/apidocs'  

    API_URL = '/static/openapi.yml'

    swaggerui_blueprint = get_swaggerui_blueprint(
        SWAGGER_URL,
        API_URL,
        config={
            'app_name': "Card Game API Documentation"
        }
    )
        
    app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

    app.register_blueprint(game_blueprint, url_prefix="/game")
    
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)