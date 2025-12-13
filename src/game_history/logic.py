import uuid
from database import get_matches_collection, get_leaderboard_collection
from config import PAGE_SIZE

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

    # Validate types to prevent NoSQL injection 
    if not isinstance(data['player1'], str) or not isinstance(data['player2'], str) or not isinstance(data['winner'], str):
        print("Error: Invalid data types in match data", flush=True)
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


def get_matches(player_uuid, page):
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


def get_leaderboard(page):
    pipeline = [
        # 1. Sort by higher points
        { '$sort': { 'points': -1 } },
        
        # 2. Pagination
        { '$skip': page * PAGE_SIZE },
        { '$limit': PAGE_SIZE }
    ]
    leaderboard_collection = get_leaderboard_collection()
    cursor = leaderboard_collection.aggregate(pipeline)
    return list(cursor)
