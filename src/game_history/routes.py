from flask import Blueprint, request, jsonify
from logic import get_matches, get_leaderboard
from utils import validate_user_token, get_usernames_by_ids
from config import PAGE_SIZE

history_blueprint = Blueprint('game_history', __name__)

# List all matches for a user (GET /matches/<player_uuid>)
@history_blueprint.route('/matches', methods=['GET'])
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
        all_ids = set()
        for m in matches:
            if m.get('player1'): all_ids.add(m.get('player1'))
            if m.get('player2'): all_ids.add(m.get('player2'))
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
@history_blueprint.route('/leaderboard', methods=['GET'])
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
        for index, doc in enumerate(raw_entries):
            doc['row_number'] = start_rank + index
            matches.append(doc)
        
        # Batch fetch usernames for all involved players
        all_ids = set()
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
