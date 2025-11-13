from logic import (
    start_new_game,
    select_deck,
    submit_card,
)
import random
import time

# ------------------------------------------------------------------
# 🂡 Helper: create a valid deck
# ------------------------------------------------------------------
def make_valid_deck():
    """8 cards + 1 Joker, 2 per suit, total ≤15 each"""
    return [
        {"rank": "9", "suit": "hearts"},
        {"rank": "6", "suit": "hearts"},   # total 15
        {"rank": "A", "suit": "diamonds"}, # Ace is worth 7
        {"rank": "8", "suit": "diamonds"}, # total 15
        {"rank": "J", "suit": "clubs"},    # Jack is worth 11
        {"rank": "4", "suit": "clubs"},    # total 15
        {"rank": "10", "suit": "spades"},
        {"rank": "5", "suit": "spades"},   # total 15
        {"rank": "JOKER", "suit": "none"},
    ]

# ------------------------------------------------------------------
# 🕹️ Match Simulation
# ------------------------------------------------------------------
def simulate_match():
    games = {} # Simulate our in-memory "database"

    # 1. Start a new game
    game_id = start_new_game("Alice", "Bob", games)
    print(f"\n🎮 New Game Started (ID: {game_id}) between Alice and Bob")

    # 2. Both players select a deck
    deck_alice = make_valid_deck()
    deck_bob = make_valid_deck()
    
    # Alice selects the deck
    select_deck(game_id, "Alice", deck_alice, games)
    print("Alice has selected the deck. Waiting for Bob...")
    
    # Bob selects the deck. THIS STARTS THE GAME!
    result_deck = select_deck(game_id, "Bob", deck_bob, games)
    print(f"Bob has selected the deck. {result_deck['message']}")

    game = games[game_id]
    
    # Initial check: both should have 3 cards
    print(f"Initial hands: Alice ({len(game.player1.hand)} cards), Bob ({len(game.player2.hand)} cards)")

    # 3. Match loop until someone wins
    while not game.winner:

        # Safety check: if players run out of cards (very rare)
        if not game.player1.hand or not game.player2.hand:
            print("\n🚫 Both players have run out of cards! The match ends.")
            game.winner = "Draw (Decks Exhausted)"
            break

        # 3a. Each player chooses a random card from their hand
        card_a = random.choice(game.player1.hand)
        card_b = random.choice(game.player2.hand)

        print(f"\n--- Turn {game.turn_number + 1} ---")
        print(f"🟥 Alice plays: {card_a.rank} of {card_a.suit} (Hand: {len(game.player1.hand)} cards)")
        print(f"🟦 Bob plays:   {card_b.rank} of {card_b.suit} (Hand: {len(game.player2.hand)} cards)")

        # 3b. Submit the cards
        # Alice (the first player) submits. The state becomes "waiting"
        submit_card(game_id, "Alice", {"rank": card_a.rank, "suit": card_a.suit}, games)
        
        # Bob (the second) submits. The turn resolves AND players draw 1 card.
        result = submit_card(game_id, "Bob", {"rank": card_b.rank, "suit": card_b.suit}, games)

        # 3c. Print the turn result
        print(f"RESULT: {result['message']}")
        print(f"SCORES → Alice: {result['scores']['Alice']}, Bob: {result['scores']['Bob']}")
        
        # Post-draw check print
        if not game.winner:
            print(f"Updated hands: Alice ({len(game.player1.hand)} cards), Bob ({len(game.player2.hand)} cards)")

        # Small delay for readability
        time.sleep(0.5)

        # The 'while' loop will check game.winner to terminate

    # 4. End of match
    print("\n🏆🏆🏆 Match Ended! 🏆🏆🏆")
    print(f"Final Winner: {game.winner}")
    print(f"Final Scores → Alice: {game.player1.score}, Bob: {game.player2.score}")

    # Print the full match history
    print("\n📜 Match History:")
    for t in game.turns:
        print(f"  Turn {t['turn']}: (Winner: {t['winner']})")
        print(f"    Cards: {t['cards']}")

# ------------------------------------------------------------------
# ⚡ Run the simulation
# ------------------------------------------------------------------
if __name__ == "__main__":
    simulate_match()