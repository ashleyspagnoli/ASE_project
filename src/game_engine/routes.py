from flask import Blueprint, jsonify, request
from logic import (
    submit_card,
    get_game_state,
    select_deck,
    matchmaking_connect,
    matchmaking_match,
    start_new_game,
    get_player_hand
)

game_blueprint = Blueprint("game_engine", __name__)


class GameController:
    def __init__(self):
        self.games = {}
        # online_players ora è un dizionario {uuid: nome}
        self.online_players = {}

    def start_game(self):
        """ Avvio manuale (per testing?) """
        data = request.get_json()
        p1_uuid = data.get("player1_uuid")
        p1_name = data.get("player1_name")
        p2_uuid = data.get("player2_uuid")
        p2_name = data.get("player2_name")
        
        if not all([p1_uuid, p1_name, p2_uuid, p2_name]):
            return jsonify({"error": "Missing player data (uuid and name)"}), 400

        game_id = start_new_game(p1_uuid, p1_name, p2_uuid, p2_name, self.games)
        return jsonify({"game_id": game_id, "status": "started"}), 201

    def choose_deck(self, game_id):
        data = request.get_json()
        player_uuid = data.get("player_uuid") 
        deck_slot = data.get("deck_slot")
        
        print(f"Received deck selection: player_uuid={player_uuid}, deck_slot={deck_slot}")
        
        if player_uuid is None or deck_slot is None:
            return jsonify({"error": "player_uuid and deck_slot are required"}), 400

        try:
            # Passa lo slot, non il mazzo
            result = select_deck(game_id, player_uuid, deck_slot, self.games) 
            return jsonify(result), 200
        except ValueError as e:
            # Cattura sia l'int() fallito sia gli errori da select_deck
            # (es. "Deck not found" o "Could not reach collection service")
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            # Altri errori imprevisti
            return jsonify({"error": f"An unexpected error occurred: {e}"}), 500

    def play_turn(self, game_id):
        data = request.get_json()
        # Il client deve inviare 'player_uuid'
        player_uuid = data.get("player_uuid") 
        card = data.get("card")
        
        if not player_uuid or not card:
            return jsonify({"error": "player_uuid and card are required"}), 400

        try:
            result = submit_card(game_id, player_uuid, card, self.games)
            return jsonify(result), 200
        except ValueError as e:
            return jsonify({"error": str(e)}), 404 # 404 se game_id non valido, 400 per altro
        
    def get_hand(self, game_id):
        """
        Endpoint GET per recuperare la mano di un giocatore.
        Usa un query parameter ?player_uuid=...
        """
        # Per le richieste GET, i parametri si leggono da request.args
        player_uuid = request.args.get("player_uuid")
        
        if not player_uuid:
            return jsonify({"error": "player_uuid query parameter is required"}), 400
            
        try:
            hand = get_player_hand(game_id, player_uuid, self.games)
            # Ritorna la mano come lista di oggetti
            return jsonify(hand), 200 
        except ValueError as e:
            return jsonify({"error": str(e)}), 404

    def get_state(self, game_id):
        try:
            state = get_game_state(game_id, self.games)
            return jsonify(state)
        except ValueError as e:
            return jsonify({"error": str(e)}), 404

    def connect_player(self):
        data = request.get_json()
        # Il client deve inviare 'uuid' e 'username'
        username = data.get("username")
        user_uuid = data.get("uuid") 
        
        if not username or not user_uuid:
            return jsonify({"error": "uuid and username are required"}), 400
            
        result = matchmaking_connect(user_uuid, username, self.online_players)
        return jsonify(result), 200

    def find_match(self):
        match = matchmaking_match(self.online_players, self.games)
        return jsonify(match), 200


controller = GameController()

game_blueprint.add_url_rule("/start", view_func=controller.start_game, methods=["POST"])
game_blueprint.add_url_rule("/deck/<game_id>", view_func=controller.choose_deck, methods=["POST"])
game_blueprint.add_url_rule("/play/<game_id>", view_func=controller.play_turn, methods=["POST"])
game_blueprint.add_url_rule("/hand/<game_id>", view_func=controller.get_hand, methods=["GET"])
game_blueprint.add_url_rule("/state/<game_id>", view_func=controller.get_state, methods=["GET"])
game_blueprint.add_url_rule("/connect", view_func=controller.connect_player, methods=["POST"])
game_blueprint.add_url_rule("/matchmake", view_func=controller.find_match, methods=["POST"])