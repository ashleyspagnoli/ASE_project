from datetime import datetime
from models import Game, Player, Card, Deck
import random
import requests
import uuid
import json
import os
import urllib3
import pika

# Disabilita warning per certificati self-signed interni
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

GAME_HISTORY_URL = os.environ.get("GAME_HISTORY_URL", "https://game_history:5000/addmatch")
COLLECTION_URL = os.environ.get("COLLECTION_URL", "https://collection:5000/collection")
USER_MANAGER_URL = os.environ.get("USER_MANAGER_URL", "https://user_manager:5000")
RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.environ.get("RABBITMQ_PORT", "5671"))
RABBITMQ_CERT_PATH = "/run/secrets/rabbitmq_cert"


# --- STRUTTURE DATI PER MATCHMAKING REST ---
matchmaking_queue = []
pending_matches = {}
games = {}

# ------------------------------------------------------------
# 🂡 Utility: Create a full deck (for testing or reference)
# ------------------------------------------------------------
def generate_full_deck():
    suits = ["hearts", "diamonds", "clubs", "spades"]
    values = [str(n) for n in range(2, 11)] + ["J", "Q", "K", "A"]
    deck = [Card(value, suit) for suit in suits for value in values]
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
    joker_found = False

    for card in deck_cards:
        # Controlla che la carta stessa sia un dizionario valido
        if not isinstance(card, dict):
            raise ValueError("Invalid card data received (not a dictionary)")

        value = card.get("value")
        suit = card.get("suit")

        # Controlla che value e suit esistano e non siano None
        if value is None or suit is None:
            raise ValueError(f"Invalid card data: value or suit is null/missing. Card: {card}")

        if value == "JOKER":
            joker_found = True
            continue

        value_map = {"J": 11, "Q": 12, "K": 13, "A": 7}
        
        try:
            if value in value_map:
                val = value_map[value]
            else:
                val = int(value) 
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid value {value}. Must be a number or J,Q,K,A. Error: {e}")
        suits.setdefault(suit, []).append(val)

    if not joker_found:
        raise ValueError("Deck must contain one Joker.")

    if len(suits) != 4:
         raise ValueError("Deck must contain exactly 4 suits (plus Joker).")

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


# ------------------------------------------------------------
# 🔗 Matchmaking REST (Logica Aggiornata)
# ------------------------------------------------------------
def process_matchmaking_request(user_uuid, user_name, games_dict):
    global matchmaking_queue, pending_matches

    # 1. Controllo match pendente
    if user_uuid in pending_matches:
        return {"status": "matched", "game_id": pending_matches[user_uuid], "message": "Partita trovata!"}

    # 2. Pulizia coda
    matchmaking_queue = [p for p in matchmaking_queue if p['uuid'] != user_uuid]

    # 3. Matching
    if len(matchmaking_queue) > 0:
        opponent = matchmaking_queue.pop(0)
        
        # IMPORTANTE: start_new_game deve essere importata o definita sopra
        # Usa la tua funzione start_new_game esistente
        game_id = start_new_game(opponent['uuid'], opponent['name'], user_uuid, user_name, games_dict)

        pending_matches[opponent['uuid']] = game_id
        
        return {"status": "matched", "game_id": game_id, "opponent": opponent['name'], "role": "player2"}
    else:
        matchmaking_queue.append({'uuid': user_uuid, 'name': user_name})
        return {"status": "waiting", "message": "In attesa di avversario..."}

def check_matchmaking_status(user_uuid):
    global pending_matches, matchmaking_queue
    if user_uuid in pending_matches:
        game_id = pending_matches.pop(user_uuid)
        return {"status": "matched", "game_id": game_id}
    
    if any(p['uuid'] == user_uuid for p in matchmaking_queue):
        return {"status": "waiting"}

    return {"status": "error", "message": "Non sei in coda."}


# ------------------------------------------------------------
# 🃏 Deck Selection
# ------------------------------------------------------------
def select_deck(game_id, player_uuid, deck_slot, games):
    game = games.get(game_id)
    if not game:
        raise ValueError("Invalid game ID")

    try:
        # 1. Contatta il microservizio 'collection' per ottenere il mazzo
        deck_url = f"{COLLECTION_URL}/decks/user/{player_uuid}/slot/{deck_slot}"
        response = requests.get(deck_url, timeout=5, verify=False)
        
        # Lancia un errore se la richiesta fallisce (es. 404 Deck non trovato)
        response.raise_for_status() 
        
        deck_data = response.json()
        
        if not deck_data.get('success') or 'data' not in deck_data:
            raise ValueError("Invalid response from collection service")
            
        # deck_cards è ora la lista di 9 carte (8 + 1 Joker)
        deck_cards = deck_data['data'] 
    
    except requests.RequestException as e:
        # Errore di connessione, timeout, o status code >= 400
        if e.response:
            try:
                error_msg = e.response.json().get('error', 'Unknown error')
            except json.JSONDecodeError:
                error_msg = e.response.text
            raise ValueError(f"Collection Service error: {error_msg}")
        else:
            raise ValueError(f"Could not reach collection service: {e}")
    except (KeyError, json.JSONDecodeError):
        raise ValueError("Failed to parse deck data from collection service")

    validate_deck(deck_cards) # Valida il mazzo ricevuto dal servizio

    # Identifica il giocatore tramite UUID
    player = game.player1 if game.player1.uuid == player_uuid else game.player2
    if player.uuid != player_uuid:
        raise ValueError("Player UUID not found in this game")

    player.deck.cards = [Card(c["value"], c["suit"]) for c in deck_cards]
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
    if card1.value == "JOKER" and card2.value == "JOKER":
        return "double_win"
    elif card1.value == "JOKER":
        return "player1"
    elif card2.value == "JOKER":
        return "player2"

    # --- Ace special interactions ---
    if card1.value == "A" and card2.value in ["J", "Q", "K"]:
        return "player1"
    if card2.value == "A" and card1.value in ["J", "Q", "K"]:
        return "player2"
    if card1.value == "A" and card2.value.isdigit():
        return "player2"
    if card2.value == "A" and card1.value.isdigit():
        return "player1"

    # --- Normal numeric comparison ---
    v1, v2 = numeric_value[card1.value], numeric_value[card2.value]
    if v1 > v2:
        return "player1"
    elif v2 > v1:
        return "player2"
    else:
        # Same value → suit priority
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
        (c for c in player.hand if c.value == card_data["value"] and c.suit == card_data["suit"]),
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
    
    # 1. Controllo Punteggio (Vittoria o Pareggio immediato)
    p1_wins_points = game.player1.score >= 5
    p2_wins_points = game.player2.score >= 5

    if p1_wins_points and p2_wins_points:
        match_winner = "Draw" # Entrambi hanno raggiunto il target nello stesso turno
    elif p1_wins_points:
        match_winner = game.player1.name
    elif p2_wins_points:
        match_winner = game.player2.name
    else:
        # 2. Controllo Esaurimento Carte (se nessuno ha ancora vinto)
        # Se entrambi i giocatori non hanno carte in mano E il mazzo è vuoto
        p1_finished = len(game.player1.hand) == 0 and len(game.player1.deck.cards) == 0
        p2_finished = len(game.player2.hand) == 0 and len(game.player2.deck.cards) == 0

        if p1_finished and p2_finished:
            # La partita finisce per esaurimento carte, controlliamo chi ha più punti
            if game.player1.score > game.player2.score:
                match_winner = game.player1.name
            elif game.player2.score > game.player1.score:
                match_winner = game.player2.name
            else:
                match_winner = "Draw" # Punteggio identico e carte finite

    # --- GESTIONE FINE PARTITA ---
    if match_winner:
        game.winner = match_winner
        game.ended_at = datetime.now()
        
        _save_match_to_history(game)
        
        return {
            "status": "finished",
            "match_winner": match_winner,
            "message": f"Game Over! Result: {match_winner}",
            "scores": {game.player1.name: game.player1.score, game.player2.name: game.player2.score}
        }
        
    else:
        # La partita continua: pescano se hanno carte nel mazzo
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
# 💾 History Saving
# ------------------------------------------------------------
def _save_match_to_history(game: Game):
    """
    Invia l'esito della partita al servizio Game History in modo Asincrono tramite RabbitMQ.
    """
    
    winner_index = "draw" # Default
    if game.winner == game.player1.name:
        winner_index = "1"
    elif game.winner == game.player2.name:
        winner_index = "2"
    elif game.winner == "Draw":
        winner_index = "draw"

    # Il log (game.turns) è già stato serializzato 
    # dalla funzione game.resolve_round()
    
    payload = {
        "player1": game.player1.uuid,
        "player2": game.player2.uuid,
        "winner": winner_index,
        "log": game.turns,
        "points1": game.player1.score,
        "points2": game.player2.score,
        "started_at": game.started_at.isoformat() if game.started_at else None,
        "ended_at": game.ended_at.isoformat() if game.ended_at else None
    }

    try:
        # Configure SSL connection (always enabled)
        import ssl
        ssl_context = ssl.create_default_context(cafile=RABBITMQ_CERT_PATH)
        ssl_context.check_hostname = True
        ssl_options = pika.SSLOptions(ssl_context, RABBITMQ_HOST)
        connection_params = pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            port=RABBITMQ_PORT,
            ssl_options=ssl_options
        )
        
        connection = pika.BlockingConnection(connection_params)
        channel = connection.channel()
        channel.queue_declare(queue='game_history_queue', durable=True)
        
        channel.basic_publish(
            exchange='',
            routing_key='game_history_queue',
            body=json.dumps(payload),
            properties=pika.BasicProperties(
                delivery_mode=2,  # make message persistent
            ))
        connection.close()
        print(f"Match {game.game_id} inviato a RabbitMQ via SSL.", flush=True)
    
    except Exception as e:
        print(f"ERRORE CRITICO: Impossibile inviare la partita {game.game_id} a RabbitMQ: {e}", flush=True)
        
        
# ------------------------------------------------------------
# 🃏 Get Player Hand
# ------------------------------------------------------------
def get_player_hand(game_id, player_uuid, games):
    """
    Recupera la mano attuale di un giocatore specifico in formato JSON.
    """
    game = games.get(game_id)
    if not game:
        raise ValueError("Invalid game ID")

    # Identifica il giocatore tramite UUID
    player = game.player1 if game.player1.uuid == player_uuid else game.player2
    if player.uuid != player_uuid:
        raise ValueError("Player UUID not found in this game")

    # Serializza le carte in un formato JSON-friendly
    # (Trasforma [Card(value='K', suit='hearts'), ...] 
    # in [{'value': 'K', 'suit': 'hearts'}, ...])
    hand_data = [{"value": card.value, "suit": card.suit} for card in player.hand]
    
    return hand_data


# ------------------------------------------------------------
# 🔐 User Token Validation (REALE con HTTPS bypass)
# ------------------------------------------------------------
def validate_user_token(token_header: str):
    if not token_header:
        raise ValueError("Header Authorization mancante.")
    try:
        token_type, token = token_header.split(" ")
        if token_type.lower() != "bearer": raise ValueError("Token non Bearer")
    except:
        raise ValueError("Formato header invalido")

    validate_url = f"{USER_MANAGER_URL}/users/validate-token"
    
    try:
        # VERIFY=FALSE è cruciale per i certificati self-signed interni a Docker
        response = requests.get(validate_url, headers={"Authorization": f"Bearer {token}"}, timeout=5, verify=False)
        response.raise_for_status()
        user_data = response.json()
        return user_data["id"], user_data["username"]
    except requests.RequestException as e:
        print(f"Errore validazione token: {e}")
        raise ValueError("Token non valido o servizio utenti irraggiungibile")