import utilities as utils
import app as main_app
import mongomock

# Mock del token validator
def mock_token_validator():
    return "testUser123", "testUser"

# Setup mongomock
mock_client = mongomock.MongoClient()
mock_db = mock_client['card_game']
mock_collection = mock_db['decks']

# Funzione che restituisce il mock
def mock_db_conn():
    return mock_collection

# Imposta i mock
utils.mock_token_validator = mock_token_validator
main_app.mock_db_conn = mock_db_conn

# Configura l'app per i test
flask_app = main_app.app


# Per test: 
# docker build -f collection/Dockerfile_test -t collection-test .
# docker run -d -p 5006:5000 collection-test