from flask import Flask, request, jsonify
import redis
import uuid
import requests
import json

app = Flask(__name__)
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

USER_MANAGER_URL = 'http://user-manager:5000/username/' 

# Helper to get username from uuid
def get_username(user_uuid):
    try:
        resp = requests.get(f"{USER_MANAGER_URL}{user_uuid}")
        if resp.status_code == 200:
            return resp.json().get('username', user_uuid)
    except Exception:
        pass
    return user_uuid

# Add a new match (POST /match)
@app.route('/match', methods=['POST'])
def add_match():
    data = request.json
    match_id = str(uuid.uuid4())
    
    serialized_log = "[]"
    if 'log' in data and data['log']:
        serialized_log = json.dumps(data['log'])

    match = {
        'id': match_id,
        'player1': data['player1'],
        'player2': data['player2'],
        'winner': data['winner'],
        'log': serialized_log,
        'points1': data['points1'],
        'points2': data['points2']
    }
    
    r.hset(f"match:{match_id}", mapping=match) 

    r.lpush(f"matches:{data['player1']}", match_id)
    r.lpush(f"matches:{data['player2']}", match_id)
    r.lpush("all_matches", match_id)
    return jsonify({'status': 'ok', 'match_id': match_id}), 201


# List all matches for a user (GET /matches/<player_uuid>)
@app.route('/matches/<player_uuid>', methods=['GET'])
def list_matches(player_uuid):
    match_ids = r.lrange(f"matches:{player_uuid}", 0, -1)
    matches = [r.hgetall(f"match:{mid}") for mid in match_ids]
    for m in matches:
        m['player1_name'] = get_username(m['player1'])
        m['player2_name'] = get_username(m['player2'])
        # Deserializza la stringa 'log' in una lista
        if 'log' in m and m['log']:
            try:
                m['log'] = json.loads(m['log'])
            except json.JSONDecodeError:
                m['log'] = "Error: Invalid log format"
    return jsonify(matches)

# Get details of a match (GET /match/<match_id>)
@app.route('/match/<match_id>', methods=['GET'])
def match_details(match_id):
    match = r.hgetall(f"match:{match_id}")
    if not match:
        return jsonify({'error': 'Match not found'}), 404
    match['player1_name'] = get_username(match['player1'])
    match['player2_name'] = get_username(match['player2'])
    # Deserializza la stringa 'log' in una lista
    if 'log' in match and match['log']:
        try:
            match['log'] = json.loads(match['log'])
        except json.JSONDecodeError:
            match['log'] = "Error: Invalid log format"
    return jsonify(match)

# Get leaderboard (GET /leaderboard)
@app.route('/leaderboard', methods=['GET'])
def leaderboard():
    player_stats = {}
    match_ids = r.lrange("all_matches", 0, -1)
    for mid in match_ids:
        m = r.hgetall(f"match:{mid}")
        # Gestione robusta nel caso i punti non siano presenti
        try:
            p1_points = int(m.get('points1', 0))
            p2_points = int(m.get('points2', 0))
        except ValueError:
            p1_points = 0
            p2_points = 0
            
        for i, p in enumerate([m['player1'], m['player2']]):
            if p not in player_stats:
                player_stats[p] = {'uuid': p, 'username': get_username(p), 'wins': 0, 'losses': 0, 'draws': 0, 'points': 0}
        
        if m['winner'] == '1':
            player_stats[m['player1']]['wins'] += 1
            player_stats[m['player2']]['losses'] += 1
        elif m['winner'] == '2':
            player_stats[m['player2']]['wins'] += 1
            player_stats[m['player1']]['losses'] += 1
        else: # draw
            player_stats[m['player1']]['draws'] += 1
            player_stats[m['player2']]['draws'] += 1
            
        player_stats[m['player1']]['points'] += p1_points
        player_stats[m['player2']]['points'] += p2_points
        
    leaderboard = list(player_stats.values())
    leaderboard.sort(key=lambda x: (-x['wins'], -x['points']))
    return jsonify(leaderboard)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)