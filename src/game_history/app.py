from flask import Flask, request, jsonify
from pymongo import MongoClient
import uuid
import requests
import json
import os
import traceback

app = Flask(__name__)

# --- MongoDB Connection ---
try:
    client = MongoClient(f"mongodb://db-history:27017/", serverSelectionTimeoutMS=5000)
    client.server_info() # Force connection check
    db = client.history
    matches_collection = db.matches
    leaderboard_collection = db.leaderboard
    print(f"Successfully connected to MongoDB")
except Exception as e:
    print(f"Error: Could not connect to MongoDB, {e}")
    exit()

# --- User Service Connection ---
# Use environment variables or default to 'user-manager'
USER_MANAGER_HOST = os.environ.get('USER_MANAGER_HOST', 'user-manager')
USER_MANAGER_PORT = int(os.environ.get('USER_MANAGER_PORT', 5000))
USER_MANAGER_BASE = f'http://{USER_MANAGER_HOST}:{USER_MANAGER_PORT}'
USERNAMES_BY_IDS_URL = f'{USER_MANAGER_BASE}/utenti/usernames-by-ids'


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
    deduped_ids = list(dict.fromkeys([uid for uid in user_ids if uid]))
    try:
        # requests will serialize list params as repeated query params
        resp = requests.get(
            USERNAMES_BY_IDS_URL,
            params={'id_list': deduped_ids},
            timeout=3
        )
        if resp.status_code == 200:
            data = resp.json() or []
            mapping = {item.get('id'): item.get('username') for item in data if isinstance(item, dict)}
            # Ensure all ids present in mapping
            for uid in deduped_ids:
                mapping.setdefault(uid, "Unknown user")
            return mapping
        else:
            print(f"Warning: usernames-by-ids returned {resp.status_code}: {resp.text}")
    except requests.exceptions.ConnectionError as e:
        print(f"Warning: Could not connect to user-manager at {USERNAMES_BY_IDS_URL}. {e}")
    except Exception as e:
        print(f"Warning: Error fetching usernames for ids {deduped_ids}. {e}")

    return {uid: "Unknown user" for uid in deduped_ids}

# Helper for atomic leaderboard updates
# Helper for atomic leaderboard updates
def update_leaderboard_stats(player_uuid, points, is_win, is_loss, is_draw):
    """
    Atomically updates a single player's stats in the leaderboard collection.
    """
    if not player_uuid:
        print("Warning: player_uuid is missing. Skipping leaderboard update.")
        return

    if leaderboard_collection is None:
        print(f"Error: leaderboard_collection not initialized. Skipping update for {player_uuid}.")
        raise RuntimeError("leaderboard_collection not initialized")

    try:
        query = {'_id': player_uuid}
        
        # Conversione di sicurezza per evitare errori se points arriva come stringa
        safe_points = int(points) if points is not None else 0
        
        update = {
            '$inc': {
                'points': safe_points,
                'wins': 1 if is_win else 0,
                'losses': 1 if is_loss else 0,
                'draws': 1 if is_draw else 0
            }
        }
        result = leaderboard_collection.update_one(query, update, upsert=True)
        if not result.acknowledged:
            raise RuntimeError(f"Leaderboard update not acknowledged for player {player_uuid}")
    except Exception as e:
        print(f"Error: Failed to update leaderboard for {player_uuid}. Details: {e}")
        raise


# Add a new match (POST /match)
@app.route('/match', methods=['POST'])
def add_match():
    try:
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
        
        # --- 1. Insert the new match ---
        matches_collection.insert_one(match)

        # --- 2. Atomically update leaderboard ---
        winner = match['winner']
        
        # Update Player 1
        print(f"Updating stats for Player 1: {match['player1']}")
        update_leaderboard_stats(
            player_uuid=match['player1'],
            points=match['points1'],
            is_win=(winner == '1'),
            is_loss=(winner == '2'),
            is_draw=(winner == 'draw')
        )
        
        # Update Player 2
        print(f"Updating stats for Player 2: {match['player2']}")
        update_leaderboard_stats(
            player_uuid=match['player2'],
            points=match['points2'],
            is_win=(winner == '2'),
            is_loss=(winner == '1'),
            is_draw=(winner == 'draw')
        )

        return jsonify({'status': 'ok', 'match_id': match_id}), 201
    
    except Exception as e:
        print("CRITICAL ERROR TRACEBACK:")
        traceback.print_exc() # Questo stampa TUTTO l'errore nei log
        return jsonify({'error': f'Failed to add match: {str(e)}'}), 500


# List all matches for a user (GET /matches/<player_uuid>)
@app.route('/matches/<player_uuid>', methods=['GET'])
def list_matches(player_uuid):
    try:
        # Find matches where the player is either player1 or player2
        query = { '$or': [ { 'player1': player_uuid }, { 'player2': player_uuid } ] }
        # Sort by timestamp
        cursor = matches_collection.find(query).sort('started_at', -1)
        matches = list(cursor)
        
        # Batch fetch usernames for all involved players
        all_ids = []
        for m in matches:
            all_ids.extend([m.get('player1'), m.get('player2')])
        id_to_username = get_usernames_by_ids(all_ids)
        
        for m in matches:
            p1 = m.get('player1')
            p2 = m.get('player2')
            m['player1_name'] = id_to_username.get(p1, p1 or "Unknown user")
            m['player2_name'] = id_to_username.get(p2, p2 or "Unknown user")
            
        return jsonify(matches)
    except Exception as e:
        print(f"Error in list_matches: {e}")
        return jsonify({'error': 'Failed to retrieve matches'}), 500


# Get details of a match (GET /match/<match_id>)
@app.route('/match/<match_id>', methods=['GET'])
def match_details(match_id):
    try:
        match = matches_collection.find_one({'_id': match_id})
        
        if not match:
            return jsonify({'error': 'Match not found'}), 404
        
        # Batch fetch the two usernames in one request
        ids = [match.get('player1'), match.get('player2')]
        id_to_username = get_usernames_by_ids(ids)
        
        match['player1_name'] = id_to_username.get(match.get('player1'), match.get('player1') or "Unknown user")
        match['player2_name'] = id_to_username.get(match.get('player2'), match.get('player2') or "Unknown user")
        
        return jsonify(match)
    except Exception as e:
        print(f"Error in match_details: {e}")
        return jsonify({'error': 'Failed to retrieve match details'}), 500


# Get leaderboard (GET /leaderboard)
@app.route('/leaderboard', methods=['GET'])
def leaderboard():
    """
    Retrieves the pre-computed leaderboard.
    """
    try:
        # Find all players, sort by points (desc)
        leaderboard_cursor = leaderboard_collection.find().sort('points', -1)
        
        # Convert cursor to a list of dictionaries
        leaderboard_data = list(leaderboard_cursor)
        
        # Batch fetch usernames
        all_player_ids = [p['_id'] for p in leaderboard_data]
        id_to_username = get_usernames_by_ids(all_player_ids)
        
        # Add usernames to the leaderboard data
        for player_stats in leaderboard_data:
            player_id = player_stats.get('_id')
            player_stats['username'] = id_to_username.get(player_id, "Unknown User")
            
        return jsonify(leaderboard_data)
    except Exception as e:
        print(f"Error in leaderboard: {e}")
        return jsonify({'error': 'Failed to retrieve leaderboard'}), 500


if __name__ == '__main__':
    # Check if DB is connected before running
    if not db:
        print("Fatal: MongoDB connection not established. Exiting.")
    else:
        app.run(host='0.0.0.0', port=5001, debug=True)