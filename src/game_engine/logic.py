from models import Game, Player, Card, Deck
import random


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
            val = value_map.get(rank, int(rank))
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
def start_new_game(player1_name, player2_name, games):
    p1 = Player(player1_name)
    p2 = Player(player2_name)
    game = Game(p1, p2)
    games[game.game_id] = game
    return game.game_id


def select_deck(game_id, player_name, deck_cards, games):
    game = games.get(game_id)
    if not game:
        raise ValueError("Invalid game ID")

    validate_deck(deck_cards)

    player = game.player1 if game.player1.name == player_name else game.player2
    player.deck.cards = [Card(c["rank"], c["suit"]) for c in deck_cards]
    player.deck.shuffle()

    return {"message": f"{player_name} deck selected", "deck_size": len(player.deck.cards)}


def draw_card_from_deck(game_id, player_name, games):
    game = games.get(game_id)
    player = game.player1 if game.player1.name == player_name else game.player2
    card = player.draw_card()
    if card:
        return {"card": {"rank": card.rank, "suit": card.suit}}
    else:
        return {"message": "No cards left in deck"}


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

    # --- Joker beats everything ---
    if card1.rank == "JOKER" and card2.rank == "JOKER":
        return "draw"
    elif card1.rank == "JOKER":
        return "player1"
    elif card2.rank == "JOKER":
        return "player2"

    # --- Ace special interactions ---
    # Ace beats face cards (J/Q/K)
    if card1.rank == "A" and card2.rank in ["J", "Q", "K"]:
        return "player1"
    if card2.rank == "A" and card1.rank in ["J", "Q", "K"]:
        return "player2"

    # Ace loses to numbers (2–10)
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
def submit_card(game_id, player_name, card_data, games):
    game = games.get(game_id)
    if not game:
        raise ValueError("Invalid game ID")

    player = game.player1 if game.player1.name == player_name else game.player2

    # Validate the card is in the player's hand
    matching_card = next(
        (c for c in player.hand if c.rank == card_data["rank"] and c.suit == card_data["suit"]),
        None
    )
    if not matching_card:
        raise ValueError(f"{player.name} tried to play a card not in hand.")

    # Play the card
    player.hand.remove(matching_card)
    game.current_round[player.name] = matching_card

    # Wait for both players
    if len(game.current_round) < 2:
        return {"status": "waiting"}

    # Compare cards and determine the round winner
    c1 = game.current_round.get(game.player1.name)
    c2 = game.current_round.get(game.player2.name)
    result = compare_cards(c1, c2)

    if result == "player1":
        game.player1.score += 1
        winner_name = game.player1.name
        message = f"{winner_name} wins round {game.turn_number + 1}!"
    elif result == "player2":
        game.player2.score += 1
        winner_name = game.player2.name
        message = f"{winner_name} wins round {game.turn_number + 1}!"
    else:
        winner_name = None
        message = f"Round {game.turn_number + 1} is a draw."

    game.resolve_round(winner_name)

    # Check for end condition (first to 5 points)
    match_winner = None
    if game.player1.score >= 5:
        match_winner = game.player1.name
    elif game.player2.score >= 5:
        match_winner = game.player2.name

    if match_winner:
        game.winner = match_winner

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
    return {
        "turn_number": game.turn_number,
        "scores": {game.player1.name: game.player1.score, game.player2.name: game.player2.score},
        "winner": game.winner,
        "turns": game.turns,
    }


# ------------------------------------------------------------
# 🔗 Matchmaking
# ------------------------------------------------------------
def matchmaking_connect(username, online_players):
    if username in online_players:
        return {"message": f"{username} is already online."}
    online_players.append(username)
    return {"message": f"{username} connected.", "players_online": online_players}


def matchmaking_match(online_players, games):
    if len(online_players) < 2:
        return {"message": "Waiting for more players...", "players_online": online_players}

    p1, p2 = random.sample(online_players, 2)
    game_id = start_new_game(p1, p2, games)
    online_players.remove(p1)
    online_players.remove(p2)
    return {"message": f"Match created between {p1} and {p2}", "game_id": game_id, "players": [p1, p2]}
