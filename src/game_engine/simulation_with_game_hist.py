from logic import (
    start_new_game,
    select_deck,
    submit_card,
)
import random
import time
import uuid

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

    # --- MODIFICA 1: Definisci UUID e Nomi ---
    ALICE_UUID = str(uuid.uuid4())
    ALICE_NAME = "Alice"
    BOB_UUID = str(uuid.uuid4())
    BOB_NAME = "Bob"
    # --- Fine Modifica 1 ---

    # 1. Start a new game
    # --- MODIFICA 2: Passa UUID e Nomi ---
    game_id = start_new_game(ALICE_UUID, ALICE_NAME, BOB_UUID, BOB_NAME, games)
    print(f"\n🎮 New Game Started (ID: {game_id}) between {ALICE_NAME} and {BOB_NAME}")
    # --- Fine Modifica 2 ---

    # 2. Both players select a deck
    deck_alice = make_valid_deck()
    deck_bob = make_valid_deck()
    
    # Alice selects the deck
    # --- MODIFICA 3: Passa l'UUID di Alice ---
    select_deck(game_id, ALICE_UUID, deck_alice, games)
    print(f"{ALICE_NAME} has selected the deck. Waiting for {BOB_NAME}...")
    # --- Fine Modifica 3 ---
    
    # Bob selects the deck. THIS STARTS THE GAME!
    # --- MODIFICA 4: Passa l'UUID di Bob ---
    result_deck = select_deck(game_id, BOB_UUID, deck_bob, games)
    print(f"{BOB_NAME} has selected the deck. {result_deck['message']}")
    # --- Fine Modifica 4 ---

    game = games[game_id]
    
    # Initial check: both should have 3 cards
    print(f"Initial hands: {ALICE_NAME} ({len(game.player1.hand)} cards), {BOB_NAME} ({len(game.player2.hand)} cards)")

    # 3. Match loop until someone wins
    while not game.winner:

        # Safety check
        if not game.player1.hand or not game.player2.hand:
            print("\n🚫 Entrambi i giocatori hanno finito le carte! La partita termina in pareggio.")
            # Nota: questo stato non verrebbe salvato in Game History 
            # perché non è un "vincitore" gestito.
            game.winner = "Draw (Decks Exhausted)" 
            break

        # 3a. Each player chooses a random card from their hand
        card_a = random.choice(game.player1.hand)
        card_b = random.choice(game.player2.hand)

        print(f"\n--- Turn {game.turn_number + 1} ---")
        print(f"🟥 {ALICE_NAME} plays: {card_a.rank} of {card_a.suit} (Hand: {len(game.player1.hand)} cards)")
        print(f"🟦 {BOB_NAME} plays:   {card_b.rank} of {card_b.suit} (Hand: {len(game.player2.hand)} cards)")

        # 3b. Submit the cards
        # Alice (the first player) submits. The state becomes "waiting"
        # --- MODIFICA 5: Passa l'UUID di Alice ---
        submit_card(game_id, ALICE_UUID, {"rank": card_a.rank, "suit": card_a.suit}, games)
        
        # Bob (the second) submits. The turn resolves AND players draw 1 card.
        # --- MODIFICA 6: Passa l'UUID di Bob ---
        result = submit_card(game_id, BOB_UUID, {"rank": card_b.rank, "suit": card_b.suit}, games)
        # --- Fine Modifica 6 ---

        # 3c. Print the turn result
        print(f"RESULT: {result['message']}")
        # Usiamo i nomi per recuperare gli score dal dizionario
        print(f"SCORES → {ALICE_NAME}: {result['scores'][ALICE_NAME]}, {BOB_NAME}: {result['scores'][BOB_NAME]}")
        
        # Post-draw check print
        if not game.winner:
            print(f"Updated hands: {ALICE_NAME} ({len(game.player1.hand)} cards), {BOB_NAME} ({len(game.player2.hand)} cards)")

        # Small delay for readability
        time.sleep(0.5)

    # 4. End of match
    print("\n🏆🏆🏆 Match Ended! 🏆🏆🏆")
    print(f"Final Winner: {game.winner}")
    print(f"Final Scores → {ALICE_NAME}: {game.player1.score}, {BOB_NAME}: {game.player2.score}")

    # Print the full match history
    print("\n📜 Match History:")
    for t in game.turns:
        print(f"  Turn {t['turn']}: (Winner: {t['winner']})")
        # --- MODIFICA 7: Aggiornato il nome della chiave (da 'cards' a 'cards_played') ---
        # Questo corrisponde all'aggiornamento che abbiamo fatto in 'models.py' (resolve_round)
        print(f"    Cards: {t['cards']}")
        # --- Fine Modifica 7 ---

# ------------------------------------------------------------------
# ⚡ Run the simulation
# ------------------------------------------------------------------
if __name__ == "__main__":
    # Importante:
    # Per eseguire questo test, assicurati che il microservizio 
    # 'game-history' (in Python) sia in esecuzione sulla porta 5001,
    # altrimenti la chiamata
    # _save_match_to_history (all'interno di submit_card) fallirà.
    print("Avvio simulazione... (Assicurati che Game History sia in ascolto su localhost:5001)")
    simulate_match()