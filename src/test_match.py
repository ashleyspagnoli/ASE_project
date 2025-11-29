import requests
import time
import threading
import urllib3
import random
import string
from datetime import datetime

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# API Gateway URL
GATEWAY_URL = "https://localhost:8443"

# Global game stats
game_stats = {
    "game_id": None,
    "players": {},
    "rounds": [],
    "start_time": None,
    "end_time": None
}
    
def generate_random_user():
    rand_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"user_{rand_str}", "Password123!"

def register_and_login(username, password):
    print(f"\n{'='*60}")
    print(f"👤 [{username}] Registration & Authentication")
    print(f"{'='*60}")
    try:
        # 1. Registration
        reg_resp = requests.post(f"{GATEWAY_URL}/users/register", json={
            "username": username, "email": f"{username}@test.com", "password": password
        }, verify=False)
        
        if reg_resp.status_code not in [200, 201]:
            print(f"⚠️  [{username}] User might already exist ({reg_resp.status_code}), trying login...")
        else:
            print(f"✅ [{username}] Successfully registered!")

        # 2. Login
        login_resp = requests.post(f"{GATEWAY_URL}/users/login", json={
            "username": username, "password": password
        }, verify=False)
        
        if login_resp.status_code != 200:
            print(f"❌ [{username}] Login failed: {login_resp.text}")
            return None
            
        token = login_resp.json().get("token")
        print(f"🔑 [{username}] Authentication token obtained!")
        return token
    except Exception as e:
        print(f"❌ [{username}] Authentication error: {e}")
        return None

def create_deck(username, token, deck_slot, user_id):
    headers = {"Authorization": f"Bearer {token}"}
    
    print(f"\n{'='*60}")
    print(f"🎴 [{username}] Deck Creation Process")
    print(f"{'='*60}")
    
    # 1. Get available cards from collection
    print(f"✨ [{username}] Fetching available cards...")
    try:
        cards_resp = requests.get(f"{GATEWAY_URL}/collection/cards", verify=False)
        if cards_resp.status_code != 200:
            print(f"❌ [{username}] Failed to get cards: {cards_resp.text}")
            return False
        
        cards_data = cards_resp.json()
        available_cards = cards_data.get('data', [])
        
        if len(available_cards) < 8:
            print(f"⚠️  [{username}] Not enough cards available.")
            return False

        print(f"✅ [{username}] Found {len(available_cards)} available cards")

    except Exception as e:
        print(f"❌ [{username}] Exception fetching cards: {e}")
        return False

    # 2. Get full card details and select 8 cards (2 per suit, max 15 points per suit)
    print(f"\n🎯 [{username}] Selecting cards for deck...")
    try:
        all_cards_details = []
        for card_info in available_cards:
            card_detail_resp = requests.get(f"{GATEWAY_URL}/collection/cards/{card_info['id']}", verify=False)
            if card_detail_resp.status_code == 200:
                all_cards_details.append(card_detail_resp.json()['data'])
        
        # Organize by suit
        suits = {'hearts': [], 'diamonds': [], 'clubs': [], 'spades': []}
        for card in all_cards_details:
            if card['suit'] in suits:
                suits[card['suit']].append(card)
        
        # Select 2 cards per suit with max 15 points
        selected_cards = []
        for suit_name, suit_cards in suits.items():
            # Sort by points to make selection easier
            suit_cards.sort(key=lambda x: x['points'])
            
            # Try to find 2 cards that sum to <= 15 points
            found = False
            for i in range(len(suit_cards)):
                for j in range(i + 1, len(suit_cards)):
                    if suit_cards[i]['points'] + suit_cards[j]['points'] <= 15:
                        selected_cards.append(suit_cards[i]['id'])
                        selected_cards.append(suit_cards[j]['id'])
                        found = True
                        break
                if found:
                    break
            
            if not found:
                # Fallback: take the two lowest point cards
                if len(suit_cards) >= 2:
                    selected_cards.append(suit_cards[0]['id'])
                    selected_cards.append(suit_cards[1]['id'])
        
        if len(selected_cards) != 8:
            print(f"⚠️  [{username}] Could not select proper deck (got {len(selected_cards)} cards)")
            return False
        
        print(f"✅ [{username}] Selected 8 cards: {', '.join(selected_cards)}")

    except Exception as e:
        print(f"❌ [{username}] Exception during card selection: {e}")
        return False

    # 3. Create deck
    deck_name = f"{username}'s Deck"
    print(f"\n🛠️  [{username}] Creating deck '{deck_name}' in slot {deck_slot}...")
    try:
        create_deck_resp = requests.post(f"{GATEWAY_URL}/collection/decks", headers=headers, json={
            "userId": user_id,
            "deckName": deck_name,
            "cards": selected_cards,
            "deckSlot": deck_slot
        }, verify=False)

        if create_deck_resp.status_code not in [200, 201]:
            print(f"❌ [{username}] Deck creation failed: {create_deck_resp.text}")
            return False
        
        print(f"✅ [{username}] Deck successfully created in slot {deck_slot}!")
        return True
    except Exception as e:
        print(f"❌ [{username}] Exception during deck creation: {e}")
        return False

def player_routine(username, password, deck_slot):
    """Main player routine - handles full game flow for one player"""
    global game_stats
    
    print(f"\n{'#'*60}")
    print(f"#  PLAYER: {username}")
    print(f"{'#'*60}")
    
    # Step 1: Authentication
    token = register_and_login(username, password)
    if not token:
        print(f"\n❌ [{username}] Failed to authenticate. Exiting.")
        return

    # Extract user_id from token (decode JWT to get user info)
    try:
        import base64
        import json as json_lib
        # JWT format: header.payload.signature
        payload = token.split('.')[1]
        # Add padding if needed
        payload += '=' * (4 - len(payload) % 4)
        decoded = base64.b64decode(payload)
        user_data = json_lib.loads(decoded)
        user_id = user_data.get('user_id') or user_data.get('sub')
        print(f"🔍 [{username}] Extracted user_id: {user_id}")
    except Exception as e:
        print(f"⚠️  [{username}] Could not decode token: {e}")
        user_id = username  # Fallback to username

    # Step 2: Deck Creation
    if not create_deck(username, token, deck_slot, user_id):
        print(f"\n❌ [{username}] Failed to create deck. Exiting.")
        return

    headers = {"Authorization": f"Bearer {token}"}
    game_id = None

    # Step 3: Matchmaking
    print(f"\n{'='*60}")
    print(f"🔵 [{username}] Joining Matchmaking Queue")
    print(f"{'='*60}")
    
    while True:
        try:
            resp = requests.post(f"{GATEWAY_URL}/game/match/join", headers=headers, verify=False)
            if resp.status_code == 401:
                print(f"❌ [{username}] Unauthorized by Game Engine!")
                return
            
            data = resp.json()
            if data.get("status") == "matched":
                game_id = data["game_id"]
                if game_stats["game_id"] is None:
                    game_stats["game_id"] = game_id
                    game_stats["start_time"] = datetime.now()
                print(f"✅ [{username}] MATCH FOUND! Game ID: {game_id}")
                break
            elif data.get("status") == "waiting":
                print(f"⏳ [{username}] Waiting for opponent...")
                time.sleep(2)
                # Poll for match status
                while True:
                    stat_resp = requests.get(f"{GATEWAY_URL}/game/match/status", headers=headers, verify=False)
                    stat_data = stat_resp.json()
                    if stat_data.get("status") == "matched":
                        game_id = stat_data["game_id"]
                        if game_stats["game_id"] is None:
                            game_stats["game_id"] = game_id
                            game_stats["start_time"] = datetime.now()
                        print(f"✅ [{username}] Match confirmed! Game ID: {game_id}")
                        break
                    time.sleep(1.5)
                break
        except Exception as e:
            print(f"❌ [{username}] Matchmaking error: {e}")
            return

    # Step 4: Deck Selection
    print(f"\n{'='*60}")
    print(f"🎴 [{username}] Selecting Deck for Battle")
    print(f"{'='*60}")
    try:
        res = requests.post(f"{GATEWAY_URL}/game/deck/{game_id}", json={"deck_slot": deck_slot}, headers=headers, verify=False)
        if res.status_code != 200:
            print(f"⚠️  [{username}] Deck selection issue: {res.text}")
        else:
            print(f"✅ [{username}] Deck selected successfully!")
    except Exception as e:
        print(f"⚠️  [{username}] Deck selection exception: {e}")

    time.sleep(1)
    
    # Initialize player stats
    game_stats["players"][username] = {
        "cards_played": [],
        "score": 0
    }

    # Step 5: Game Loop
    print(f"\n{'='*60}")
    print(f"⚔️  [{username}] ENTERING BATTLE")
    print(f"{'='*60}")
    
    round_num = 0
    
    while True:
        try:
            # Get current hand
            hand_resp = requests.get(f"{GATEWAY_URL}/game/hand/{game_id}", headers=headers, verify=False)
            hand = hand_resp.json()
            
            # Check game state
            state_resp = requests.get(f"{GATEWAY_URL}/game/state/{game_id}", headers=headers, verify=False)
            state = state_resp.json()
            
            if state.get("winner"):
                game_stats["end_time"] = datetime.now()
                print(f"\n{'='*60}")
                print(f"🏆 [{username}] GAME OVER!")
                print(f"{'='*60}")
                print(f"Winner: {state['winner']}")
                print(f"Final Scores: {state.get('scores', {})}")
                print(f"{'='*60}")
                break

            if not hand or len(hand) == 0:
                print(f"⏸️  [{username}] Hand empty, waiting...")
                time.sleep(2)
                continue

            # Play a card
            round_num += 1
            card = random.choice(hand)
            
            print(f"\n🎯 [{username}] Round {round_num}")
            print(f"   Hand size: {len(hand)} cards")
            print(f"   Playing: {card['value']} of {card['suit']}")
            
            # Record the move
            game_stats["players"][username]["cards_played"].append({
                "round": round_num,
                "card": f"{card['value']} of {card['suit']}"
            })
            
            play_resp = requests.post(f"{GATEWAY_URL}/game/play/{game_id}", json={"card": card}, headers=headers, verify=False)
            play_data = play_resp.json()
            
            # Update score if available
            if "scores" in play_data:
                scores = play_data["scores"]
                if username in scores:
                    game_stats["players"][username]["score"] = scores[username]
                print(f"   Current Scores: {scores}")
            
            if play_data.get("status") == "finished":
                game_stats["end_time"] = datetime.now()
                print(f"\n🏁 [{username}] Match finished!")
                break
            elif play_data.get("status") == "resolved":
                if "message" in play_data:
                    print(f"   Result: {play_data['message']}")
            
            time.sleep(1.5)

        except Exception as e:
            print(f"❌ [{username}] Game loop error: {e}")
            break

def print_game_summary():
    """Print a comprehensive summary of the game"""
    print(f"\n\n{'#'*60}")
    print(f"#  GAME SIMULATION SUMMARY")
    print(f"{'#'*60}")
    
    if game_stats["game_id"]:
        print(f"\n📊 Game Information:")
        print(f"   Game ID: {game_stats['game_id']}")
        
        if game_stats["start_time"] and game_stats["end_time"]:
            duration = game_stats["end_time"] - game_stats["start_time"]
            print(f"   Duration: {duration.seconds} seconds")
    
    print(f"\n👥 Player Statistics:")
    for player_name, stats in game_stats["players"].items():
        print(f"\n   Player: {player_name}")
        print(f"   Final Score: {stats['score']}")
        print(f"   Cards Played: {len(stats['cards_played'])}")
        
        if stats['cards_played']:
            print(f"   Move History:")
            for move in stats['cards_played'][:5]:  # Show first 5 moves
                print(f"      Round {move['round']}: {move['card']}")
            if len(stats['cards_played']) > 5:
                print(f"      ... and {len(stats['cards_played']) - 5} more moves")
    
    print(f"\n{'#'*60}")
    print(f"#  SIMULATION COMPLETE")
    print(f"{'#'*60}\n")


if __name__ == "__main__":
    print("\n")
    print("="*60)
    print("  🎮 CARD GAME SIMULATION - TWO PLAYER MATCH")
    print("="*60)
    print("\nInitializing game simulation...")
    print("Creating two random players for the match...\n")
    
    # Generate two random players
    u1, p1 = generate_random_user()
    u2, p2 = generate_random_user()
    
    print(f"Player 1: {u1}")
    print(f"Player 2: {u2}\n")

    # Create threads for each player
    t1 = threading.Thread(target=player_routine, args=(u1, p1, 1), name=u1)
    t2 = threading.Thread(target=player_routine, args=(u2, p2, 2), name=u2)

    # Start player threads with a delay
    print("Starting Player 1...")
    t1.start()
    
    time.sleep(2)  # Delay to let first player enter queue
    
    print("Starting Player 2...")
    t2.start()

    # Wait for both players to finish
    t1.join()
    t2.join()
    
    # Print comprehensive game summary
    print_game_summary()