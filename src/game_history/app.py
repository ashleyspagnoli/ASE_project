from flask import Flask, request, jsonify
from pymongo import MongoClient
import uuid
import requests
import json
import os
import pika
import threading
import time

app = Flask(__name__)

PAGE_SIZE = 10

# --- User Service ---
USER_MANAGER_URL = os.environ.get('USER_MANAGER_URL', 'https://user-manager:5000')
USERNAMES_BY_IDS_URL = f'{USER_MANAGER_URL}/utenti/usernames-by-ids'
USER_MANAGER_CERT = os.environ.get('USER_MANAGER_CERT', '/run/secrets/history_key')

# --- RabbitMQ broker ---
RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "rabbitmq")

# --- MongoDB Connection ---
_db = None
def get_db(): # Lazily load DB, this function will never be called if get_leaderboard and get_matches get mocked
    global _db
    if _db is None:
        try:
            client = MongoClient(f"mongodb://db-history:27017/", serverSelectionTimeoutMS=5000)
            _db = client.history
            print(f"Successfully connected to MongoDB", flush=True)
        except Exception as e:
            print(f"Error: Could not connect to MongoDB, {e}", flush=True)
            exit()
        return _db

def get_matches_collection():
    db = get_db()
    return db.matches

def get_leaderboard_collection():
    db = get_db()
    coll = db.leaderboard
    coll.create_index([("points", -1)]) #For improved efficiency, should do at least once, done at each startup since microservices are immutable
    return coll


# Helper to get usernames for a list of UUIDs in one request
mock_usernames_by_ids = None
def get_usernames_by_ids(user_ids):
    """
    Fetch usernames for a list of user IDs via the user-manager endpoint
    GET /utenti/usernames-by-ids?id_list=<id>&id_list=<id2> ...
    Returns a dict {id: username}
    """
    if not user_ids:
        return {}
    # Turn input into list
    user_ids = list(user_ids)
    
    if mock_usernames_by_ids:
        data = mock_usernames_by_ids(user_ids)
    else:
        try:
            # requests will serialize list params as repeated query params
            resp = requests.get(
                USERNAMES_BY_IDS_URL,
                params={'id_list': user_ids},
                timeout=3,
                verify=USER_MANAGER_CERT
            )
            if resp.status_code == 200:
                data = resp.json() or []
            else:
                print(f"Error: usernames-by-ids returned {resp.status_code}: {resp.text}", flush=True)
                data = []
        except requests.exceptions.ConnectionError as e:
            print(f"Warning: Could not connect to user-manager at {USERNAMES_BY_IDS_URL}. {e}", flush=True)
            data = []
        except Exception as e:
            print(f"Warning: Error fetching usernames for ids {user_ids}. {e}", flush=True)
            data = []

    mapping = {item.get('id'): item.get('username') for item in data if isinstance(item, dict)}
    # Ensure all ids present in mapping
    for uid in user_ids:
        mapping.setdefault(uid, "Unknown user")
    return mapping

# Helper for atomic leaderboard updates
def update_leaderboard_stats(player_uuid, points, is_win, is_loss, is_draw):
    """
    Atomically updates a single player's stats in the leaderboard collection.
    """
    try:
        query = {'_id': player_uuid}
        update = {
            '$inc': {
                'points': points,
                'wins': 1 if is_win else 0,
                'losses': 1 if is_loss else 0,
                'draws': 1 if is_draw else 0
            }
        }
        # upsert=True creates the document if it doesn't exist, default numbers are 0
        leaderboard_collection = get_leaderboard_collection()
        leaderboard_collection.update_one(query, update, upsert=True)
    except Exception as e:
        print(f"Error: Failed to update leaderboard for {player_uuid}. {e}", flush=True)


def process_match_data(data):
    if not data or 'player1' not in data or 'player2' not in data or 'winner' not in data:
        print("Error: Missing required match data", flush=True)
        return False

    match_id = str(uuid.uuid4())
    match = {
        '_id': match_id,
        'player1': data['player1'],
        'player2': data['player2'],
        'winner': data['winner'], # '1', '2', or 'draw'
        'log': data.get('log', []),
        'points1': data.get('points1', 0),
        'points2': data.get('points2', 0),
        'started_at': data.get('started_at', 0),
        'ended_at': data.get('ended_at', 0)
    }
    
    try:
        # --- 1. Insert the new match ---
        matches_collection = get_matches_collection()
        matches_collection.insert_one(match)

        # --- 2. Atomically update leaderboard ---
        winner = match['winner']
        
        # Update Player 1
        update_leaderboard_stats(
            player_uuid=match['player1'],
            points=match['points1'],
            is_win=(winner == '1'),
            is_loss=(winner == '2'),
            is_draw=(winner == 'draw')
        )
        
        # Update Player 2
        update_leaderboard_stats(
            player_uuid=match['player2'],
            points=match['points2'],
            is_win=(winner == '2'),
            is_loss=(winner == '1'),
            is_draw=(winner == 'draw')
        )
        print(f"Match {match_id} processed successfully.", flush=True)
        return True
    
    except Exception as e:
        print(f"Error processing match: {e}", flush=True)
        return False

def consume_game_history():
    print("Starting RabbitMQ consumer thread...", flush=True)
    while True:
        try:
            print(f"Connecting to RabbitMQ at {RABBITMQ_HOST}...", flush=True)
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
            channel = connection.channel()
            channel.queue_declare(queue='game_history_queue', durable=True)

            def callback(ch, method, properties, body):
                print("Received match data from RabbitMQ", flush=True)
                try:
                    data = json.loads(body)
                    if process_match_data(data):
                        ch.basic_ack(delivery_tag=method.delivery_tag)
                    else:
                        # Log error but ack to avoid infinite loop if data is bad
                        print("Failed to process match data, acking anyway to clear queue", flush=True)
                        ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as e:
                    print(f"Error processing message: {e}", flush=True)
                    ch.basic_ack(delivery_tag=method.delivery_tag)

            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue='game_history_queue', on_message_callback=callback)

            print('Waiting for messages. To exit press CTRL+C', flush=True)
            channel.start_consuming()
        except pika.exceptions.AMQPConnectionError as e:
            print(f"RabbitMQ connection failed: {e}. Retrying in 5 seconds...", flush=True)
            time.sleep(5)
        except Exception as e:
            print(f"Error in RabbitMQ consumer: {e}. Retrying in 5 seconds...", flush=True)
            time.sleep(5)

# Start consumer in a background thread
threading.Thread(target=consume_game_history, daemon=True).start()

# Add a new match (POST /match)
# @app.route('/addmatch', methods=['POST'])
# def add_match():
#     data = request.json
#     if process_match_data(data):
#         return jsonify({'status': 'ok'}), 201
#     else:
#         return jsonify({'error': 'Failed to add match'}), 500

mock_matches = None
def get_matches(player_uuid, page):
    if mock_matches:
        return mock_matches(player_uuid, page)
    pipeline = [
        # 1. Filter by player
        { '$match': { '$or': [{ 'player1': player_uuid }, { 'player2': player_uuid }] } },

        # 2. Sort by starting time
        { '$sort': { 'started_at': -1 } },
        
        # 3. Pagination
        { '$skip': page * PAGE_SIZE },
        { '$limit': PAGE_SIZE }
    ]
    matches_collection = get_matches_collection()
    cursor = matches_collection.aggregate(pipeline)
    return list(cursor)
    
    

# List all matches for a user (GET /matches/<player_uuid>)
@app.route('/matches', methods=['GET'])
def list_matches():
    page = request.args.get('page', default=0, type=int) #It's a int -> doesn't need to be sanitized
    token_header = request.headers.get("Authorization")
    try:
        player_uuid, username = validate_user_token(token_header)
    except ValueError as e:
        return jsonify({"error": str(e)}), 401
    
    try:
        raw_entries = get_matches(player_uuid, page)
        start_rank = (page * PAGE_SIZE) + 1
        matches = []
        for index, doc in enumerate(raw_entries):
            doc['row_number'] = start_rank + index
            matches.append(doc)
        
        # Batch fetch usernames for all involved players
        all_ids = {}
        for m in matches:
            all_ids.update({m.get('player1'), m.get('player2')})
        id_to_username = get_usernames_by_ids(all_ids)
        
        for m in matches:
            p1 = m.get('player1')
            p2 = m.get('player2')
            m['player1'] = id_to_username.get(p1, p1 or "Unknown user")
            m['player2'] = id_to_username.get(p2, p2 or "Unknown user")
            
        return jsonify(matches)
    except Exception as e:
        print(f"Error in list_matches: {e}", flush=True)
        return jsonify({'error': 'Failed to retrieve matches'}), 500


mock_leaderboard = None
def get_leaderboard(page):
    if mock_leaderboard:
        return mock_leaderboard(page)
    pipeline = [
        # 1. Sort by starting time
        { '$sort': { 'points': -1 } },
        
        # 2. Pagination
        { '$skip': page * PAGE_SIZE },
        { '$limit': PAGE_SIZE }
    ]
    leaderboard_collection = get_leaderboard_collection()
    cursor = leaderboard_collection.aggregate(pipeline)
    return list(cursor)

# Get leaderboard (GET /leaderboard)
@app.route('/leaderboard', methods=['GET'])
def leaderboard():
    """
    Retrieves the pre-computed leaderboard, replacing player UUID '_id' with 'username'.
    """
    page = request.args.get('page', default=0, type=int) #It's a int -> doesn't need to be sanitized
    try:
        # Fetch all entries sorted by points desc
        raw_entries = get_leaderboard(page)
        start_rank = (page * PAGE_SIZE) + 1
        matches = []
        for index, doc in raw_entries:
            doc['row_number'] = start_rank + index
            matches.append(doc)
        
        # Batch fetch usernames for all involved players
        all_ids = {}
        for m in matches:
            all_ids.add(m.get('_id'))
        id_to_username = get_usernames_by_ids(all_ids)


        # Build response replacing _id with username
        response = []
        for doc in raw_entries:
            entry = {k: v for k, v in doc.items() if k != '_id'}  # keep all other stats
            entry['username'] = id_to_username.get(doc.get('_id'))
            response.append(entry)
        
        return jsonify(response)
    except Exception as e:
        print(f"Error in leaderboard: {e}", flush=True)
        return jsonify({'error': 'Failed to retrieve leaderboard'}), 500



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)


# ------------------------------------------------------------
# 🔐 User Token Validation
#------------------------------------------------------------
mock_user_validator = None
def validate_user_token(token_header: str):
    """
    Contatta l'user-manager (in HTTPS) per validare un token JWT.
    
    Ignora la verifica del certificato SSL (verify=False) per permettere
    la comunicazione tra container con certificati auto-firmati.

    Restituisce (user_uuid, username) se il token è valido.
    Solleva ValueError se il token non è valido o il servizio non risponde.
    """
    if not token_header:
        raise ValueError("Header 'Authorization' mancante.")

    if mock_user_validator:
        return mock_user_validator(token_header)
    
    # Il token_header è "Bearer eyJ...". Dobbiamo estrarre solo il token "eyJ..."
    try:
        token_type, token = token_header.split(" ")
        if token_type.lower() != "bearer":
            raise ValueError("Tipo di token non valido, richiesto 'Bearer'.")
    except Exception:
        raise ValueError("Formato 'Authorization' header non valido. Usare 'Bearer <token>'.")

    # Questo è l'endpoint che hai definito nel tuo user-manager
    validate_url = f"{USER_MANAGER_URL}/users/validate-token"

    try:
        # Invia la richiesta GET con il token come query parameter
        response = requests.get(
            validate_url,
            params={"token_str": token},
            timeout=5,
            verify=USER_MANAGER_CERT  # <-- IMPORTANTE: Ignora la verifica del certificato SSL
        )

        # Se l'user-manager risponde 401, 403, 404, ecc., solleva un errore
        response.raise_for_status()

        user_data = response.json()

        # L'endpoint /users/validate-token restituisce 'id' e 'username'
        user_uuid = user_data.get("id")
        #username = user_data.get("username")

        if not user_uuid:
            raise ValueError("Dati utente incompleti dal servizio di validazione")

        print(f"Token validato con successo per l'utente: {user_uuid}", flush=True)
        return user_uuid

    except requests.RequestException as e:
        # Errore di connessione o risposta 4xx/5xx dal servizio utenti
        error_detail = f"Impossibile validare l'utente. Errore di connessione a {validate_url}."
        if e.response:
            try:
                # Prova a leggere il 'detail' dall'errore FastAPI
                error_detail = e.response.json().get('detail', 'Errore sconosciuto da User-Manager')
            except json.JSONDecodeError:
                error_detail = e.response.text

        print(f"ERRORE validazione token: {error_detail}")
        # Solleva un ValueError che il controller (routes.py) convertirà in 401
        raise ValueError(f"Servizio Utenti: {error_detail}")