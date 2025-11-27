from flask import Flask, request, jsonify
from pymongo import MongoClient
import uuid
import requests
import json
import os

app = Flask(__name__)

# --- MongoDB Connection ---
try:
    client = MongoClient(f"mongodb://db-history:27017/", serverSelectionTimeoutMS=5000)
    client.server_info() # Force connection check
    db = client.history
    matches_collection = db.matches
    leaderboard_collection = db.leaderboard
    leaderboard_collection.create_index([("points", -1)])
    print(f"Successfully connected to MongoDB", flush=True)
except Exception as e:
    print(f"Error: Could not connect to MongoDB, {e}", flush=True)
    exit()

PAGE_SIZE = 10

# --- User Service Connection ---
# Use environment variables or default to 'user-manager'
USER_MANAGER_URL = os.environ.get('USER_MANAGER_URL', 'https://user-manager:5000')
USERNAMES_BY_IDS_URL = f'{USER_MANAGER_URL}/utenti/usernames-by-ids'


# Helper to get usernames for a list of UUIDs in one request
def get_usernames_by_ids(user_ids):
    """
    Fetch usernames for a list of user IDs via the user-manager endpoint
    GET /utenti/usernames-by-ids?id_list=<id>&id_list=<id2> ...
    Returns a dict {id: username}
    """
    if not user_ids:
        return {}

    # Deduplicate and drop falsy values while preserving order
    user_ids = list(user_ids)
    try:
        # requests will serialize list params as repeated query params
        resp = requests.get(
            USERNAMES_BY_IDS_URL,
            params={'id_list': user_ids},
            timeout=3,
            verify=False
        )
        if resp.status_code == 200:
            data = resp.json() or []
            mapping = {item.get('id'): item.get('username') for item in data if isinstance(item, dict)}
            # Ensure all ids present in mapping
            for uid in user_ids:
                mapping.setdefault(uid, "Unknown user")
            return mapping
        else:
            print(f"Warning: usernames-by-ids returned {resp.status_code}: {resp.text}", flush=True)
    except requests.exceptions.ConnectionError as e:
        print(f"Warning: Could not connect to user-manager at {USERNAMES_BY_IDS_URL}. {e}", flush=True)
    except Exception as e:
        print(f"Warning: Error fetching usernames for ids {deduped_ids}. {e}", flush=True)

    return {uid: "Unknown user" for uid in deduped_ids}

# Helper for atomic leaderboard updates
def update_leaderboard_stats(player_uuid, points, is_win, is_loss, is_draw):
    """
    Atomically updates a single player's stats in the leaderboard collection.
    """
    if leaderboard_collection is None:
        print(f"Error: leaderboard_collection not initialized. Skipping update for {player_uuid}.", flush=True)
        return

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
        leaderboard_collection.update_one(query, update, upsert=True)
    except Exception as e:
        print(f"Error: Failed to update leaderboard for {player_uuid}. {e}", flush=True)


# Add a new match (POST /match)
@app.route('/addmatch', methods=['POST'])
def add_match():
    data = request.json
    if not data or 'player1' not in data or 'player2' not in data or 'winner' not in data:
        return jsonify({'error': 'Missing required match data'}), 400

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

        return jsonify({'status': 'ok', 'match_id': match_id}), 201
    
    except Exception as e:
        print(f"Error in add_match: {e}", flush=True)
        return jsonify({'error': 'Failed to add match'}), 500


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
        pipeline = [
            # 1. Filter by player
            { '$match': { '$or': [{ 'player1': player_uuid }, { 'player2': player_uuid }] } },

            # 2. Sort by starting time
            { '$sort': { 'started_at': -1 } },
            
            # 3. Pagination
            { '$skip': page * PAGE_SIZE },
            { '$limit': PAGE_SIZE }
        ]
        cursor = matches_collection.aggregate(pipeline)

        start_rank = (page * PAGE_SIZE) + 1
        matches = []
        for index, doc in enumerate(cursor):
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


# Get leaderboard (GET /leaderboard)
@app.route('/leaderboard', methods=['GET'])
def leaderboard():
    """
    Retrieves the pre-computed leaderboard, replacing player UUID '_id' with 'username'.
    """
    page = request.args.get('page', default=0, type=int) #It's a int -> doesn't need to be sanitized
    try:
        # Fetch all entries sorted by points desc

        pipeline = [
            # 1. Sort by starting time
            { '$sort': { 'points': -1 } },
            
            # 2. Pagination
            { '$skip': page * PAGE_SIZE },
            { '$limit': PAGE_SIZE }
        ]
        cursor = leaderboard_collection.aggregate(pipeline)
        raw_entries = list(cursor)

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

# Get leaderboard page where user is located and redirects to leaderboard (GET /myleaderboard)
# @app.route('/myleaderboard', methods=['GET'])
# def my_leaderboard():
#     """
#     Finds the rank of the user and redirects to the correct leaderboard page.
#     """

#     token_header = request.headers.get("Authorization")
#     try:
#         player_uuid, username = validate_user_token(token_header)
#     except ValueError as e:
#         return jsonify({"error": str(e)}), 401

#     try:
#         # 1. Get the current user's stats to find their score
#         user_doc = leaderboard_collection.find_one({'_id': player_uuid})
        
#         if not user_doc:
#             return jsonify({'error': 'User not found in leaderboard'}), 404
            
#         user_points = user_doc.get('points', 0)

#         # 2. Calculate Rank (Count how many people are ahead of this user)
#         # We must use the SAME sorting logic as the main leaderboard.
#         # Logic: Count documents where points are strictly greater than user_points
#         # OR points are equal, but _id is "smaller" (for tie-breaking).
        
#         count_query = {
#             '$or': [
#                 {'points': {'$gt': user_points}},
#                 {
#                     'points': user_points,
#                     '_id': {'$lt': user_id} # Secondary sort key (deterministic tie-breaker)
#                 }
#             ]
#         }
        
#         # This count is the number of people BEFORE the user. 
#         # e.g., if 5 people are better, the user is at index 5 (0-indexed).
#         position_index = leaderboard_collection.count_documents(count_query)

#         # 3. Calculate Page
#         # integer division finds the page index (0-based)
#         target_page = position_index // PAGE_SIZE

#         # 4. Redirect
#         return redirect(url_for('leaderboard', page=target_page))

#     except Exception as e:
#         print(f"Error in myleaderboard: {e}", flush=True)
#         return jsonify({'error': 'Failed to calculate rank'}), 500

if __name__ == '__main__':
    # Check if DB is connected before running
    if not db:
        print("Fatal: MongoDB connection not established. Exiting.", flush=True)
    else:
        app.run(host='0.0.0.0', port=5001, debug=True)



# ------------------------------------------------------------
# 🔐 User Token Validation (copied from game_engine)
#------------------------------------------------------------
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
            verify=False  # <-- IMPORTANTE: Ignora la verifica del certificato SSL
        )

        # Se l'user-manager risponde 401, 403, 404, ecc., solleva un errore
        response.raise_for_status()

        user_data = response.json()

        # L'endpoint /users/validate-token restituisce 'id' e 'username'
        user_uuid = user_data.get("id")
        username = user_data.get("username")

        if not user_uuid or not username:
            raise ValueError("Dati utente incompleti dal servizio di validazione")

        print(f"[Game-Engine] Token validato con successo per l'utente: {username} ({user_uuid})")
        return user_uuid, username

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