from flask import Flask, jsonify, request
from pymongo import MongoClient
from bson import ObjectId
import json

app = Flask(__name__)

# connect to MongoDB
try:
    client = MongoClient('mongodb://db-decks:27017/')
    db = client['card_game']
    decks_collection = db['decks']
    print("Connected to MongoDB")

except Exception as e:
    print(f"MongoDB connection error: {e}")

# load cards from JSON file
def load_cards():
    with open('cards/cards.json', 'r') as f:
        return json.load(f)

# serialize ObjectId to string
def serialize_deck(deck):
    if deck and '_id' in deck:
        deck['_id'] = str(deck['_id'])
    return deck

# GET /collection - Get all cards (id and image)
@app.route('/collection/cards', methods=['GET'])
def get_collection():
    try:
        cards = load_cards()
        filtered_cards = [
            {'id': card['id'], 'image': card['image']}
            for card in cards
        ]
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
    try:
        cards = load_cards()
        card = next((c for c in cards if c['id'] == card_id), None)
        if card:
            return jsonify({'success': True, 'data': card}), 200
        else:
            return jsonify({'success': False, 'error': 'Card not found'}), 404
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# GET /decks - Get all user's decks
@app.route('/collection/decks', methods=['GET'])
def get_decks():
    try:
        user_id = request.args.get('userId')
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

# POST /collection/create - Create a new deck
@app.route('/collection/decks', methods=['POST'])
def create_deck():
    try:
        data = request.json
        user_id = data.get('userId')
        deck_slot = data.get('deckSlot')
        deck_name = data.get('deckName')
        selected_cards = data.get('cards', [])

        # validations (slot, name, card count)
        if not deck_slot or deck_slot not in [1, 2, 3, 4, 5]:
            return jsonify({'success': False, 'error': 'Deck slot must be between 1 and 5'}), 400
        if not deck_name or len(deck_name.strip()) == 0:
            return jsonify({'success': False, 'error': 'Deck name is required'}), 400
        if len(selected_cards) != 8:
            return jsonify({'success': False, 'error': 'You must select exactly 8 cards'}), 400

        # load and validate selected cards
        all_cards = load_cards()
        cards_dict = {c['id']: c for c in all_cards}
        suits_count = {'hearts': [], 'diamonds': [], 'clubs': [], 'spades': []}

        # correct ids
        for card_id in selected_cards:
            if card_id not in cards_dict:
                return jsonify({'success': False, 'error': f'Invalid card: {card_id}'}), 400
            card = cards_dict[card_id]
            suits_count[card['suit']].append(card)

        # 2 cards per suit and max 15 points per suit
        for suit, cards in suits_count.items():
            if len(cards) != 2:
                return jsonify({'success': False, 'error': f'Must select exactly 2 cards per suit (suit {suit}: {len(cards)} cards)'}), 400
            total_points = sum(c['points'] for c in cards)
            if total_points > 15:
                return jsonify({'success': False, 'error': f'Suit {suit} has {total_points} points (max 15)'}), 400

        # replace existing deck in the same slot
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

# DELETE /collection/{deckId} - Delete a deck
@app.route('/collection/decks/<deck_id>', methods=['DELETE'])
def delete_deck(deck_id):
    try:
        user_id = request.args.get('userId')
        
        # check if deck exists
        deck = decks_collection.find_one({'_id': ObjectId(deck_id), 'userId': user_id})
        if not deck:
            return jsonify({'success': False, 'error': 'Deck not found'}), 404
        
        # delete the deck
        decks_collection.delete_one({'_id': ObjectId(deck_id)})
        return jsonify({'success': True, 'message': 'Deck deleted successfully'}), 200
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    
    
    
@app.route('/collection/decks/user/<user_id>/slot/<int:slot_number>', methods=['GET'])
def get_deck_by_slot(user_id, slot_number):
    """
    Restituisce un singolo mazzo per un utente e uno slot, 
    popolando i dati delle carte e aggiungendo il Joker.
    Questo endpoint è pensato per essere usato dal Game Engine.
    """
    try:
        # 1. Carica il dizionario di tutte le carte per una ricerca veloce
        all_cards = load_cards()
        cards_dict = {c['id']: c for c in all_cards}

        # 2. Trova il mazzo nel database
        deck = decks_collection.find_one({
            'userId': user_id, 
            'slot': slot_number
        })

        if not deck:
            return jsonify({'success': False, 'error': 'Deck not found in this slot'}), 404

        # 3. "Popola" le carte: trasforma la lista di ID in una lista di oggetti carta
        populated_cards = []
        for card_id in deck.get('cards', []): # deck['cards'] è una lista di 8 ID
            if card_id in cards_dict:
                # Aggiungi solo i campi che servono al game-engine (value, suit)
                card_data = cards_dict[card_id]
                populated_cards.append({
                    "value": card_data.get("value"), #
                    "suit": card_data.get("suit")
                })
            
        # 4. Aggiungi il Joker (richiesto dal game-engine)
        populated_cards.append({"value": "JOKER", "suit": "none"})

        # 5. Verifica che il mazzo sia completo (8 + 1 Joker)
        if len(populated_cards) != 9:
            app.logger.error(f"Deck {deck['_id']} for user {user_id} is incomplete. Found {len(populated_cards)-1} cards.")
            return jsonify({'success': False, 'error': 'Deck data is corrupt or incomplete'}), 500

        return jsonify({'success': True, 'data': populated_cards}), 200

    except Exception as e:
        app.logger.error(f"Error in get_deck_by_slot: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
