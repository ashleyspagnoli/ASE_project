from logic import (
    start_new_game,
    select_deck,
    draw_card_from_deck,
    submit_card,
    get_game_state,
)
from models import Card
import random
import time

# ------------------------------------------------------------------
# 🂡 Helper: create a valid deck according to your deck rules
# ------------------------------------------------------------------
def make_valid_deck():
    """8 cards + 1 Joker, 2 per suit, total ≤15 each"""
    return [
        {"rank": "9", "suit": "hearts"},
        {"rank": "6", "suit": "hearts"},   # total 15
        {"rank": "8", "suit": "diamonds"},
        {"rank": "7", "suit": "diamonds"}, # total 15
        {"rank": "9", "suit": "clubs"},
        {"rank": "5", "suit": "clubs"},    # total 14
        {"rank": "10", "suit": "spades"},
        {"rank": "5", "suit": "spades"},   # total 15
        {"rank": "JOKER", "suit": "none"},
    ]


# ------------------------------------------------------------------
# 🕹️ Simulation Runner
# ------------------------------------------------------------------
def simulate_match():
    games = {}

    # Start a game between Alice and Bob
    game_id = start_new_game("Alice", "Bob", games)
    print(f"\n🎮 New Game Started (ID: {game_id})")

    # Both players select a deck
    deck = make_valid_deck()
    select_deck(game_id, "Alice", deck, games)
    select_deck(game_id, "Bob", deck, games)

    game = games[game_id]

    # Both players draw their opening hand (3 cards)
    for _ in range(3):
        draw_card_from_deck(game_id, "Alice", games)
        draw_card_from_deck(game_id, "Bob", games)

    # Continue until someone wins
    while not game.winner:
        # Draw one new card each turn (if available)
        draw_card_from_deck(game_id, "Alice", games)
        draw_card_from_deck(game_id, "Bob", games)

        # Each player randomly picks a card from hand
        card_a = random.choice(game.player1.hand)
        card_b = random.choice(game.player2.hand)

        print(f"\nTurn {game.turn_number + 1}")
        print(f"🟥 Alice plays: {card_a.rank} of {card_a.suit}")
        print(f"🟦 Bob plays:   {card_b.rank} of {card_b.suit}")

        # Submit cards
        submit_card(game_id, "Alice", {"rank": card_a.rank, "suit": card_a.suit}, games)
        result = submit_card(game_id, "Bob", {"rank": card_b.rank, "suit": card_b.suit}, games)

        # Print round result
        print(result["message"])
        print(f"Scores → Alice: {game.player1.score}, Bob: {game.player2.score}")

        # Small delay for readability
        time.sleep(0.5)

        # Check win condition
        if game.winner:
            print("\n🏆 Game Over!")
            print(f"Final Winner: {game.winner}")
            print(f"Final Scores → Alice: {game.player1.score}, Bob: {game.player2.score}")
            break

    # Optional: print full game history
    print("\n📜 Match History:")
    for t in game.turns:
        print(f" Turn {t['turn']}: {t['cards']} → Winner: {t['winner']}")


# ------------------------------------------------------------------
# 🧠 Run it!
# ------------------------------------------------------------------
if __name__ == "__main__":
    simulate_match()
