from flask import request, jsonify
import logic
import utils
import app as main_app
from config import PAGE_SIZE

# In-memory data stores
matches_store = {}
leaderboard_store = {}
match_counter = 0
user_id_to_username = {}  # Store user_id -> username associations

# Block the rabbitmq consumer
mock_consumer = True

# Mock functions to replace the real ones
def mock_get_matches(player_uuid, page):
    """
    Simulates retrieving matches for a specific player with pagination.
    Filters matches where the player is player1 or player2.
    """
    matches = []
    for match_id, match in matches_store.items():
        if match.get('player1') == player_uuid or match.get('player2') == player_uuid:
            matches.append(match.copy())
    
    # Sort by started_at descending
    matches.sort(key=lambda x: x.get('started_at', 0), reverse=True)
    
    # Apply pagination
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    return matches[start:end]


def mock_get_leaderboard(page):
    """
    Simulates retrieving the leaderboard with pagination.
    Returns leaderboard entries sorted by points descending.
    """
    entries = []
    for player_uuid, stats in leaderboard_store.items():
        entry = stats.copy()
        entry['_id'] = player_uuid
        entries.append(entry)
    
    # Sort by points descending
    entries.sort(key=lambda x: x.get('points', 0), reverse=True)
    
    # Apply pagination
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    return entries[start:end]


def mock_usernames_by_ids(user_ids):
    """
    Simulates fetching usernames for a list of user IDs.
    Returns a dictionary mapping IDs to usernames from the stored associations.
    """
    return {user_id: user_id_to_username.get(user_id, "Unknown user") for user_id in user_ids}


def mock_user_validator(token_header):
    """The token IS the user_id for testing. Store and return the association."""
    user_id = token_header.replace("Bearer ", "").strip()
    user_id_to_username.setdefault(user_id, f"User_{user_id[:8]}")
    return user_id, user_id_to_username[user_id]


def mock_process_match_data(data):
    """
    Simulates processing match data and storing it locally.
    Updates matches_store and leaderboard_store.
    """
    global match_counter
    
    if not data or 'player1' not in data or 'player2' not in data or 'winner' not in data:
        print("Error: Missing required match data", flush=True)
        return False
    
    match_counter += 1
    match_id = f"mock_match_{match_counter}"
    
    match = {
        '_id': match_id,
        'player1': data['player1'],
        'player2': data['player2'],
        'winner': data['winner'],  # '1', '2', or 'draw'
        'log': data.get('log', []),
        'points1': data.get('points1', 0),
        'points2': data.get('points2', 0),
        'started_at': data.get('started_at', 0),
        'ended_at': data.get('ended_at', 0)
    }
    
    try:
        # Store the match
        matches_store[match_id] = match
        
        # Update leaderboard for both players
        winner = match['winner']
        
        # Update Player 1
        if match['player1'] not in leaderboard_store:
            leaderboard_store[match['player1']] = {
                'points': 0,
                'wins': 0,
                'losses': 0,
                'draws': 0
            }
        
        leaderboard_store[match['player1']]['points'] += match['points1']
        if winner == '1':
            leaderboard_store[match['player1']]['wins'] += 1
        elif winner == '2':
            leaderboard_store[match['player1']]['losses'] += 1
        elif winner == 'draw':
            leaderboard_store[match['player1']]['draws'] += 1
        
        # Update Player 2
        if match['player2'] not in leaderboard_store:
            leaderboard_store[match['player2']] = {
                'points': 0,
                'wins': 0,
                'losses': 0,
                'draws': 0
            }
        
        leaderboard_store[match['player2']]['points'] += match['points2']
        if winner == '2':
            leaderboard_store[match['player2']]['wins'] += 1
        elif winner == '1':
            leaderboard_store[match['player2']]['losses'] += 1
        elif winner == 'draw':
            leaderboard_store[match['player2']]['draws'] += 1
        
        print(f"Match {match_id} processed successfully.", flush=True)
        return True
    
    except Exception as e:
        print(f"Error processing match: {e}", flush=True)
        return False


# Set the mocks in the modules
logic.mock_get_matches = mock_get_matches
logic.mock_get_leaderboard = mock_get_leaderboard
utils.mock_usernames_by_ids = mock_usernames_by_ids
utils.mock_user_validator = mock_user_validator

# Get the Flask app
flask_app = main_app.app

# Add the addmatch endpoint for testing
@flask_app.route('/addmatch', methods=['POST'])
def add_match():
    """
    Test endpoint to add a match directly without RabbitMQ.
    """
    data = request.json
    if mock_process_match_data(data):
        return jsonify({'status': 'ok'}), 201
    else:
        return jsonify({'error': 'Failed to add match'}), 500


# For test: 
# docker build -f game_history/Dockerfile_test -t game-history-test .
# docker run -d -p 5007:5000 game-history-test