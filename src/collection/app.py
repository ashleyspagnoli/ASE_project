from flask import Flask, jsonify, request
from pymongo import MongoClient
from bson import ObjectId
import json
from utilities import require_auth, validate_user_token

app = Flask(__name__)

mock_db_conn = None
_decks_collection = None

# Funzione per ottenere i decks dell'utente
def get_decks_collection():
    global _decks_collection
    
    if mock_db_conn:
        return mock_db_conn()
    
    # connessione a MongoDB
    if _decks_collection is None:
        try:
            client = MongoClient('mongodb://db-decks:27017/')
            db = client['card_game']
            _decks_collection = db['decks']
            print("Connected to MongoDB")
        except Exception as e:
            print(f"MongoDB connection error: {e}")
            raise
    
    return _decks_collection

# load cards from JSON file
def load_cards():
    with open('cards/cards.json', 'r') as f:
        return json.load(f)

# serialize ObjectId to string
def serialize_deck(deck):
    if deck and '_id' in deck:
        deck['_id'] = str(deck['_id'])
    return deck

# PUBLIC ROUTES 

# GET /collection/cards - Get all cards ids
@app.route('/collection/cards', methods=['GET'])
def get_collection():
    """
    Ottiene tutte le carte disponibili.
    """
    try:
        cards = load_cards()
        filtered_cards = [ {'id': card['id']} for card in cards ]
        return jsonify({
            'success': True,
            'data': filtered_cards,
            'total': len(filtered_cards)
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# GET /collection/{cardId} - Get details of a single card
@app.route('/collection/cards/<card_id>', methods=['GET'])
def get_card(card_id):
    """
    Ottiene tutti i dettagli di una singola carta.
    """
    try:
        cards = load_cards()
        card = next((c for c in cards if c['id'] == card_id), None)
        if card:
            return jsonify({'success': True, 'data': card}), 200
        else:
            return jsonify({'success': False, 'error': 'Card not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# PROTECTED ROUTES

# GET /decks - Get all user's decks
@app.route('/collection/decks', methods=['GET'])
@require_auth
def get_decks(user_id, username):
    """
    Ottiene tutti i mazzi dell'utente autenticato.
    """
    try:
        decks_collection = get_decks_collection()
        user_decks = list(decks_collection.find({'userId': user_id}))
        for deck in user_decks:
            serialize_deck(deck)
        return jsonify({
            'success': True,
            'data': user_decks,
            'total': len(user_decks)
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# POST /collection/decks - Create a new deck - PROTETTA
@app.route('/collection/decks', methods=['POST'])
@require_auth
def create_deck(user_id, username):
    """
    Crea un nuovo mazzo per l'utente autenticato.
    """
    try:
        decks_collection = get_decks_collection()
        data = request.json
        deck_slot = data.get('deckSlot')
        deck_name = data.get('deckName')
        selected_cards = data.get('cards', [])

        # validazioni (slot, name, card count)
        if not deck_slot or deck_slot not in [1, 2, 3, 4, 5]:
            return jsonify({'success': False, 'error': 'Deck slot must be between 1 and 5'}), 400
        if not deck_name or len(deck_name.strip()) == 0:
            return jsonify({'success': False, 'error': 'Deck name is required'}), 400
        if len(selected_cards) != 8:
            return jsonify({'success': False, 'error': 'You must select exactly 8 cards'}), 400

        # carica e valida le carte selezionate
        all_cards = load_cards()
        cards_dict = {c['id']: c for c in all_cards}
        suits_count = {'hearts': [], 'diamonds': [], 'clubs': [], 'spades': []}

        # id corretti
        for card_id in selected_cards:
            if card_id not in cards_dict:
                return jsonify({'success': False, 'error': f'Invalid card: {card_id}'}), 400
            card = cards_dict[card_id]
            suits_count[card['suit']].append(card)

        # 2 carte per seme e max 15 punti per seme
        for suit, cards in suits_count.items():
            if len(cards) != 2:
                return jsonify({'success': False, 'error': f'Must select exactly 2 cards per suit (suit {suit}: {len(cards)} cards)'}), 400
            total_points = sum(c['points'] for c in cards)
            if total_points > 15:
                return jsonify({'success': False, 'error': f'Suit {suit} has {total_points} points (max 15)'}), 400

        # rimpiazza il mazzo esistente nello slot se presente
        decks_collection.delete_one({'userId': user_id, 'slot': deck_slot})

        new_deck = {
            'userId': user_id,
            'slot': deck_slot,
            'name': deck_name,
            'cards': selected_cards
        }
        result = decks_collection.insert_one(new_deck)
        new_deck['_id'] = str(result.inserted_id)

        return jsonify({'success': True, 'message': 'Deck created successfully', 'data': new_deck}), 201
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# DELETE /collection/decks/{deckId} - Delete a deck - PROTETTA
@app.route('/collection/decks/<deck_id>', methods=['DELETE'])
@require_auth
def delete_deck(user_id, username, deck_id):
    """
    Elimina un mazzo dell'utente autenticato.
    """
    try:
        # controllo sull'esistenza del deck e appartenenza all'utente
        deck = decks_collection.find_one({'_id': query_id, 'userId': user_id}) 
        if not deck:
            return jsonify({'success': False, 'error': 'Deck not found or access denied'}), 404
        
        # elimina il deck
        decks_collection.delete_one({'_id': query_id})
        return jsonify({'success': True, 'message': 'Deck deleted successfully'}), 200
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# GET /collection/decks/user/{user_id}/slot/{slot_number} - INTERNA (per game-engine)
@app.route('/collection/decks/user/<user_id>/slot/<int:slot_number>', methods=['GET'])
def get_deck_by_slot(user_id, slot_number):
    """
    Endpoint INTERNO usato dal game-engine per recuperare un mazzo.
    """
    try:
        decks_collection = get_decks_collection()
        all_cards = load_cards()
        cards_dict = {c['id']: c for c in all_cards}

        deck = decks_collection.find_one({
            'userId': user_id, 
            'slot': slot_number
        })

        if not deck:
            return jsonify({'success': False, 'error': 'Deck not found in this slot'}), 404

        populated_cards = []
        for card_id in deck.get('cards', []):
            if card_id in cards_dict:
                card_data = cards_dict[card_id]
                populated_cards.append({
                    "value": card_data.get("value"),
                    "suit": card_data.get("suit")
                })
        
        # aggiunta joker
        populated_cards.append({"value": "JOKER", "suit": "none"})

        if len(populated_cards) != 9:
            app.logger.error(f"Deck {deck['_id']} for user {user_id} is incomplete. Found {len(populated_cards)-1} cards.")
            return jsonify({'success': False, 'error': 'Deck data is corrupt or incomplete'}), 500

        return jsonify({'success': True, 'data': populated_cards}), 200

    except Exception as e:
        app.logger.error(f"Error in get_deck_by_slot: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)