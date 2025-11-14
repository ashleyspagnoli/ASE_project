from models import Game, Player, Card, Deck
import random
import requests
import uuid

# GAME_HISTORY_URL = "http://game-history:5001/match" # Per ambiente di produzione

GAME_HISTORY_URL = "http://localhost:5001/match" # Per test locale

# ------------------------------------------------------------
# 🂡 Utility: Create a full deck (for testing or reference)
# ------------------------------------------------------------
def generate_full_deck():
    suits = ["hearts", "diamonds", "clubs", "spades"]
    ranks = [str(n) for n in range(2, 11)] + ["J", "Q", "K", "A"]
    deck = [Card(rank, suit) for suit in suits for rank in ranks]
    deck.append(Card("JOKER", "none"))
    return deck


# ------------------------------------------------------------
# 🪄 Deck Validation Rules
# ------------------------------------------------------------
def validate_deck(deck_cards):
    """Enforce deck rules:
       - 8 cards + 1 Joker
       - 2 cards per suit
       - Sum of 2 cards per suit ≤ 15 points
    """
    if len(deck_cards) != 9:
        raise ValueError("Deck must contain exactly 9 cards (8 + 1 Joker).")

    suits = {}
    for card in deck_cards:
        rank, suit = card["rank"], card["suit"]
        if rank == "JOKER":
            continue

        value_map = {"J": 11, "Q": 12, "K": 13, "A": 7}
        try:
            if rank in value_map:
                val = value_map[rank]
            else:
                val = int(rank)
        except ValueError:
            raise ValueError(f"Invalid rank {rank}")

        suits.setdefault(suit, []).append(val)

    for suit, vals in suits.items():
        if len(vals) != 2:
            raise ValueError(f"Suit '{suit}' must have exactly 2 cards.")
        if sum(vals) > 15:
            raise ValueError(f"Suit '{suit}' exceeds 15 total points (got {sum(vals)}).")


# ------------------------------------------------------------
# ⚙️ Game Management
# ------------------------------------------------------------
def start_new_game(player1_uuid, player1_name, player2_uuid, player2_name, games):
    # Crea Players usando il modello aggiornato
    p1 = Player(uuid=player1_uuid, name=player1_name)
    p2 = Player(uuid=player2_uuid, name=player2_name)
    
    game = Game(p1, p2) # Game ora usa i nuovi Player
    games[game.game_id] = game
    return game.game_id

def select_deck(game_id, player_uuid, deck_cards, games):
    game = games.get(game_id)
    if not game:
        raise ValueError("Invalid game ID")

    validate_deck(deck_cards)

    # Identifica il giocatore tramite UUID
    player = game.player1 if game.player1.uuid == player_uuid else game.player2
    if player.uuid != player_uuid:
        raise ValueError("Player UUID not found in this game")

    player.deck.cards = [Card(c["rank"], c["suit"]) for c in deck_cards]
    player.deck.shuffle()
    
    opponent = game.player2 if game.player1.uuid == player_uuid else game.player1
    
    # Regola: 3 carte al primo turno
    if opponent.deck.cards:  
        for _ in range(3):
            game.player1.draw_card()
            game.player2.draw_card()
        
        return {"message": f"{player.name} deck selected. Both ready! Game started, 3 cards drawn."}
    else:
        return {"message": f"{player.name} deck selected. Waiting for opponent."}


# ------------------------------------------------------------
# 🧠 Card Comparison Logic
# ------------------------------------------------------------
def compare_cards(card1: Card, card2: Card):
    """Compare two cards according to the official rules."""
    suit_priority = {"hearts": 4, "diamonds": 3, "clubs": 2, "spades": 1, "none": 0}
    numeric_value = {
        "2": 2, "3": 3, "4": 4, "5": 5, "6": 6,
        "7": 7, "8": 8, "9": 9, "10": 10,
        "J": 11, "Q": 12, "K": 13, "A": 7, "JOKER": 99
    }

    # Joker beats everything
    if card1.rank == "JOKER" and card2.rank == "JOKER":
        return "double_win"
    elif card1.rank == "JOKER":
        return "player1"
    elif card2.rank == "JOKER":
        return "player2"

    # --- Ace special interactions ---
    if card1.rank == "A" and card2.rank in ["J", "Q", "K"]:
        return "player1"
    if card2.rank == "A" and card1.rank in ["J", "Q", "K"]:
        return "player2"
    if card1.rank == "A" and card2.rank.isdigit():
        return "player2"
    if card2.rank == "A" and card1.rank.isdigit():
        return "player1"

    # --- Normal numeric comparison ---
    v1, v2 = numeric_value[card1.rank], numeric_value[card2.rank]
    if v1 > v2:
        return "player1"
    elif v2 > v1:
        return "player2"
    else:
        # Same rank → suit priority
        if suit_priority[card1.suit] > suit_priority[card2.suit]:
            return "player1"
        elif suit_priority[card1.suit] < suit_priority[card2.suit]:
            return "player2"
        else:
            return "draw"


# ------------------------------------------------------------
# 🎮 Turn Handling
# ------------------------------------------------------------
def submit_card(game_id, player_uuid, card_data, games):
    game = games.get(game_id)
    if not game:
        raise ValueError("Invalid game ID")
    
    # Se la partita è già finita, non fare nulla
    if game.winner:
        return {"status": "finished", "message": f"Game already won by {game.winner}"}

    # Identifica il giocatore tramite UUID
    player = game.player1 if game.player1.uuid == player_uuid else game.player2
    if player.uuid != player_uuid:
        raise ValueError("Player UUID not found in this game")

    matching_card = next(
        (c for c in player.hand if c.rank == card_data["rank"] and c.suit == card_data["suit"]),
        None
    )
    if not matching_card:
        raise ValueError(f"{player.name} tried to play a card not in hand.")

    player.hand.remove(matching_card)
    
    # Usa l'UUID del giocatore come chiave
    game.current_round[player.uuid] = matching_card

    if len(game.current_round) < 2:
        return {"status": "waiting"}

    # Entrambi i giocatori hanno giocato
    c1 = game.current_round.get(game.player1.uuid)
    c2 = game.current_round.get(game.player2.uuid)
    result = compare_cards(c1, c2)

    winner_name = None
    if result == "player1":
        game.player1.score += 1
        winner_name = game.player1.name
        message = f"{winner_name} wins round {game.turn_number + 1}!"
    elif result == "player2":
        game.player2.score += 1
        winner_name = game.player2.name
        message = f"{winner_name} wins round {game.turn_number + 1}!"
    elif result == "double_win": # Joker vs Joker
        game.player1.score += 1
        game.player2.score += 1
        winner_name = "both"
        message = f"Round {game.turn_number + 1} è un Double Win! 1 punto a entrambi."
    else: # "draw" (stessa identica carta)
        winner_name = "draw"
        message = f"Round {game.turn_number + 1} is a draw (stessa carta)."

    # Salva il log del turno (usa la funzione definita in models.py)
    game.resolve_round(winner_name)

    # Controlla la condizione di fine partita (Regola 5 punti)
    match_winner = None
    if game.player1.score >= 5:
        match_winner = game.player1.name
    elif game.player2.score >= 5:
        match_winner = game.player2.name

    if match_winner:
        game.winner = match_winner
        
        # <-- ⭐️ CHIAMATA SINCRONA AL GAME HISTORY ⭐️ -->
        _save_match_to_history(game)
        
    else:
        # Regola: 1 carta nei turni successivi
        game.player1.draw_card()
        game.player2.draw_card()

    return {
        "status": "resolved",
        "message": message,
        "scores": {game.player1.name: game.player1.score, game.player2.name: game.player2.score},
        "turn_number": game.turn_number,
        "match_winner": game.winner,
    }

# ------------------------------------------------------------
# 📊 Game State
# ------------------------------------------------------------
def get_game_state(game_id, games):
    game = games.get(game_id)
    if not game:
        raise ValueError("Invalid game ID")
    
    state = {
        "game_id": game.game_id,
        "turn_number": game.turn_number,
        "winner": game.winner,
        "scores": {
            game.player1.name: game.player1.score,
            game.player2.name: game.player2.score
        },
        "players": [
            {"uuid": game.player1.uuid, "name": game.player1.name, "hand_size": len(game.player1.hand)},
            {"uuid": game.player2.uuid, "name": game.player2.name, "hand_size": len(game.player2.hand)}
        ],
        "turn_history": game.turns,
    }
    return state

# ------------------------------------------------------------
# 🔗 Matchmaking
# ------------------------------------------------------------
def matchmaking_connect(user_uuid, username, online_players):
    if user_uuid in online_players:
        return {"message": f"{username} ({user_uuid}) is already online."}
    
    # Memorizza {uuid: nome}
    online_players[user_uuid] = username
    
    return {"message": f"{username} connected.", "players_online_count": len(online_players)}

def matchmaking_match(online_players, games):
    if len(online_players) < 2:
        return {"message": "Waiting for more players...", "players_online_count": len(online_players)}

    player_uuids = list(online_players.keys())
    p1_uuid, p2_uuid = random.sample(player_uuids, 2)
    
    p1_name = online_players[p1_uuid]
    p2_name = online_players[p2_uuid]

    # Avvia la partita con UUID e Nomi
    game_id = start_new_game(p1_uuid, p1_name, p2_uuid, p2_name, games)
    
    del online_players[p1_uuid]
    del online_players[p2_uuid]
    
    return {
        "message": f"Match created between {p1_name} and {p2_name}",
        "game_id": game_id,
        "players": [
            {"uuid": p1_uuid, "name": p1_name},
            {"uuid": p2_uuid, "name": p2_name}
        ]
    }

# ------------------------------------------------------------
# 💾 History Saving
# ------------------------------------------------------------
def _save_match_to_history(game: Game):
    """
    Invia l'esito della partita al servizio Game History in modo Sincrono.
    """
    
    winner_index = "draw" # Default
    if game.winner == game.player1.name:
        winner_index = "1"
    elif game.winner == game.player2.name:
        winner_index = "2"

    # Il log (game.turns) è già stato serializzato 
    # dalla funzione game.resolve_round()
    
    payload = {
        "player1": game.player1.uuid,
        "player2": game.player2.uuid,
        "winner": winner_index,
        "log": game.turns,             # <-- Usa il log serializzato
        "points1": game.player1.score,
        "points2": game.player2.score
    }

    try:
        # CHIAMATA SINCRONA
        response = requests.post(GAME_HISTORY_URL, json=payload, timeout=5)
        response.raise_for_status() 
        print(f"Match {game.game_id} salvato con successo su Game History.")
    
    except requests.RequestException as e:
        # La partita è finita, ma il salvataggio è fallito.
        # Il client riceverà comunque l'esito della partita.
        # Logga questo errore!
        print(f"ERRORE CRITICO: Impossibile salvare la partita {game.game_id} su Game History: {e}")