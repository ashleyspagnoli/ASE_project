from pymongo import MongoClient
from config import MONGO_URI

# --- MongoDB Connection ---
mock_get_db = None
_db = None
def get_db(): # Lazily load DB, this function will never be called if get_leaderboard and get_matches get mocked
    if mock_get_db:
        return mock_get_db()
    global _db
    if _db is None:
        try:
            client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
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