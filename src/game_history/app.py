from flask import Flask, request, jsonify
from pymongo import MongoClient, DESCENDING
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
    print(f"Successfully connected to MongoDB")
except Exception as e:
    print(f"Error: Could not connect to MongoDB, {e}")
    exit()

# --- User Service Connection ---
# Use environment variables or default to 'user-manager'
USER_MANAGER_HOST = os.environ.get('USER_MANAGER_HOST', 'user-manager')
USER_MANAGER_PORT = os.environ.get('USER_MANAGER_PORT', 5000)
USER_MANAGER_URL = f'http://{USER_MANAGER_HOST}:{USER_MANAGER_PORT}/username/'


# Helper to get username from uuid
def get_username(user_uuid):
    """
    Fetches the username from the user-manager microservice.
    """
    try:
        resp = requests.get(f"{USER_MANAGER_URL}{user_uuid}")
        if resp.status_code == 200:
            return resp.json().get('username', user_uuid)
    except requests.exceptions.ConnectionError as e:
        print(f"Warning: Could not connect to user-manager at {USER_MANAGER_URL}{user_uuid}. {e}")
    except Exception as e:
        print(f"Warning: Error fetching username for {user_uuid}. {e}")
    return "Unknown user"

# Helper to process MongoDB documents (convert _id)
def mongo_doc_to_json(doc):
    """
    Converts a MongoDB document (with ObjectId) to a JSON-serializable dict.
    """
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc

# Helper for atomic leaderboard updates
def update_leaderboard_stats(player_uuid, points, is_win, is_loss, is_draw):
    """
    Atomically updates a single player's stats in the leaderboard collection.
    """
    if not leaderboard_collection:
        print(f"Error: leaderboard_collection not initialized. Skipping update for {player_uuid}.")
        return

    try:
        query = {'uuid': player_uuid}
        update = {
            '$inc': {
                'points': points,
                'wins': 1 if is_win else 0,
                'losses': 1 if is_loss else 0,
                'draws': 1 if is_draw else 0
            },
            '$setOnInsert': {
                'uuid': player_uuid,
                'username': get_username(player_uuid) # Get username on first insert
            }
        }
        # upsert=True creates the document if it doesn't exist, default numbers are 0
        leaderboard_collection.update_one(query, update, upsert=True)
    except Exception as e:
        print(f"Error: Failed to update leaderboard for {player_uuid}. {e}")


# Add a new match (POST /match)
@app.route('/match', methods=['POST'])
def add_match():
    data = request.json
    if not data or 'player1' not in data or 'player2' not in data or 'winner' not in data:
        return jsonify({'error': 'Missing required match data'}), 400

    match_id = str(uuid.uuid4())

    match = {
        'id': match_id,
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
        print(f"Error in add_match: {e}")
        return jsonify({'error': 'Failed to add match'}), 500


# List all matches for a user (GET /matches/<player_uuid>)
@app.route('/matches/<player_uuid>', methods=['GET'])
def list_matches(player_uuid):
    try:
        # Find matches where the player is either player1 or player2
        query = { '$or': [ { 'player1': player_uuid }, { 'player2': player_uuid } ] }
        # Sort by timestamp, newest first (if you add it)
        # user_matches_cursor = matches_collection.find(query).sort('timestamp', DESCENDING)
        user_matches_cursor = matches_collection.find(query)

        matches = [mongo_doc_to_json(m) for m in user_matches_cursor]
        
        # Get usernames for display
        for m in matches:
            m['player1_name'] = get_username(m['player1'])
            m['player2_name'] = get_username(m['player2'])
            
        return jsonify(matches)
    except Exception as e:
        print(f"Error in list_matches: {e}")
        return jsonify({'error': 'Failed to retrieve matches'}), 500


# Get details of a match (GET /match/<match_id>)
@app.route('/match/<match_id>', methods=['GET'])
def match_details(match_id):
    if not matches_collection:
        return jsonify({'error': 'Database not connected'}), 500
        
    try:
        # Find by 'id' field, not '_id'
        match = matches_collection.find_one({'id': match_id})
        
        if not match:
            return jsonify({'error': 'Match not found'}), 404
            
        match = mongo_doc_to_json(match)
        match['player1_name'] = get_username(match['player1'])
        match['player2_name'] = get_username(match['player2'])
        
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
        # Find all players, sort by wins (desc), then points (desc)
        leaderboard_cursor = leaderboard_collection.find().sort([
            ('wins', DESCENDING),
            ('points', DESCENDING)
        ])
        
        leaderboard = [mongo_doc_to_json(player) for player in leaderboard_cursor]
        
        return jsonify(leaderboard)
    except Exception as e:
        print(f"Error in leaderboard: {e}")
        return jsonify({'error': 'Failed to retrieve leaderboard'}), 500


if __name__ == '__main__':
    # Check if DB is connected before running
    if not db:
        print("Fatal: MongoDB connection not established. Exiting.")
    else:
        app.run(host='0.0.0.0', port=5001, debug=True)