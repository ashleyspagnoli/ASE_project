from flask import request, jsonify
import mongomock
import database
import consumer

# --- 1. Disable RabbitMQ Consumer (MUST be done before importing app) ---
# We replace the start_consumer function with a no-op.
# This prevents the thread from ever starting when app.py is imported.
consumer.start_consumer = lambda: None

# Now we can safely import app
import app as main_app
import logic
import utils

# --- 2. Setup Mongomock ---
mock_client = mongomock.MongoClient()
mock_db = mock_client.game_history_db

# --- 3. Inject the mock DB into the database module ---
# Instead of patching logic.py, we patch the lower-level database.get_db function.
# This ensures that ANY module calling database.get_db() gets our mock.

def mock_get_db():
    return mock_db

# Patch database.py function
database.mock_get_db = mock_get_db

# --- 4. Mock User Validation (Keep existing) ---
user_id_to_username = {}  # Store user_id -> username associations

def mock_get_usernames_by_ids(user_ids):
    """
    Simulates fetching usernames for a list of user IDs.
    Returns a list of dictionaries [{'id': user_id, 'username': username}, ...]
    """
    return [{'id': user_id, 'username': user_id_to_username.get(user_id, "Unknown user")} for user_id in user_ids]

def mock_validate_user_token(token_header):
    """The token IS the user_id for testing. Return the association."""
    user_id = token_header.replace("Bearer ", "").strip()
    return user_id, user_id_to_username.get(user_id, "Unknown user")

utils.mock_get_usernames_by_ids = mock_get_usernames_by_ids
utils.mock_validate_user_token = mock_validate_user_token

# --- 5. Setup Flask App ---
flask_app = main_app.app

@flask_app.route('/addusernames', methods=['POST'])
def add_usernames():
    """
    Test endpoint to populate the user_id -> username mapping.
    Expects a JSON object: { "user_id": "username", ... }
    """
    data = request.json
    if not isinstance(data, dict):
        return jsonify({'error': 'Expected dictionary of user_id: username'}), 400
    user_id_to_username.update(data)
    print("Received data for /addusernames:", data)
    return jsonify({'status': 'ok'}), 201

# Add the addmatches endpoint for testing
@flask_app.route('/addmatches', methods=['POST'])
def add_matches():
    """
    Test endpoint to add multiple matches directly, invoking the REAL logic.
    Expects a JSON array of match objects.
    """
    data = request.json
    if not isinstance(data, list):
        return jsonify({'error': 'Expected list of matches'}), 400
    
    success_count = 0
    for match in data:
        # Call the REAL logic function
        if logic.process_match_data(match):
            success_count += 1
            
    return jsonify({'status': 'ok', 'added': success_count}), 201

