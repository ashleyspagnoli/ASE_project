from flask import Flask, request, jsonify
import redis
import uuid
import requests

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
    match = {
        'id': match_id,
        'player1': data['player1'],
        'player2': data['player2'],
        'winner': data['winner'],
        'log': data['log'],
        'points1': data['points1'],
        'points2': data['points2']
    }
    r.hmset(f"match:{match_id}", match)
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
    return jsonify(matches)

# Get details of a match (GET /match/<match_id>)
@app.route('/match/<match_id>', methods=['GET'])
def match_details(match_id):
    match = r.hgetall(f"match:{match_id}")
    if not match:
        return jsonify({'error': 'Match not found'}), 404
    match['player1_name'] = get_username(match['player1'])
    match['player2_name'] = get_username(match['player2'])
    return jsonify(match)

# Get leaderboard (GET /leaderboard)
@app.route('/leaderboard', methods=['GET'])
def leaderboard():
    player_stats = {}
    match_ids = r.lrange("all_matches", 0, -1)
    for mid in match_ids:
        m = r.hgetall(f"match:{mid}")
        for i, p in enumerate([m['player1'], m['player2']]):
            if p not in player_stats:
                player_stats[p] = {'uuid': p, 'username': get_username(p), 'wins': 0, 'losses': 0, 'draws': 0, 'points': 0}
        if m['winner'] == '1':
            player_stats[m['player1']]['wins'] += 1
            player_stats[m['player2']]['losses'] += 1
        elif m['winner'] == '2':
            player_stats[m['player2']]['wins'] += 1
            player_stats[m['player1']]['losses'] += 1
        else:
            player_stats[m['player1']]['draws'] += 1
            player_stats[m['player2']]['draws'] += 1
        player_stats[m['player1']]['points'] += int(m['points1'])
        player_stats[m['player2']]['points'] += int(m['points2'])
    leaderboard = list(player_stats.values())
    leaderboard.sort(key=lambda x: (-x['wins'], -x['points']))
    return jsonify(leaderboard)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
