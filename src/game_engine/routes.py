from flask import Blueprint, jsonify, request
from .logic import (
    submit_card,
    get_game_state,
    select_deck,
    start_new_game,
    get_player_hand,
    validate_user_token,
    process_matchmaking_request,
    check_matchmaking_status,
)

game_blueprint = Blueprint("game_engine", __name__)


class GameController:
    def __init__(self):
        self.games = {}

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
        try:
            user_uuid, _ = validate_user_token(request.headers.get("Authorization"))
            # Nota: select_deck deve esistere in logic.py
            deck_slot = request.get_json().get("deck_slot")
            return jsonify(select_deck(game_id, user_uuid, deck_slot, self.games)), 200
        except ValueError as e: return jsonify({"error": str(e)}), 401
        except Exception as e: return jsonify({"error": str(e)}), 400

    def play_turn(self, game_id):
        try:
            user_uuid, _ = validate_user_token(request.headers.get("Authorization"))
            card = request.get_json().get("card")
            return jsonify(submit_card(game_id, user_uuid, card, self.games)), 200
        except ValueError as e: return jsonify({"error": str(e)}), 400
        
    def get_hand(self, game_id):
        try:
            user_uuid, _ = validate_user_token(request.headers.get("Authorization"))
            return jsonify(get_player_hand(game_id, user_uuid, self.games)), 200
        except ValueError as e: return jsonify({"error": str(e)}), 400
    
    def get_state(self, game_id):
        # State potrebbe essere pubblico o protetto, qui lo proteggiamo per sicurezza
        try:
            user_uuid, _ = validate_user_token(request.headers.get("Authorization"))
            return jsonify(get_game_state(game_id, self.games)), 200
        except ValueError as e: return jsonify({"error": str(e)}), 400

    def join_matchmaking(self):
        try:
            user_uuid, username = validate_user_token(request.headers.get("Authorization"))
            result = process_matchmaking_request(user_uuid, username, self.games)
            return jsonify(result), 200
        except ValueError as e: return jsonify({"error": str(e)}), 401
        except Exception as e: return jsonify({"error": str(e)}), 500

    def status_matchmaking(self):
        try:
            user_uuid, username = validate_user_token(request.headers.get("Authorization"))
            result = check_matchmaking_status(user_uuid)
            return jsonify(result), 200
        except ValueError as e: return jsonify({"error": str(e)}), 401

controller = GameController()

game_blueprint.add_url_rule("/match/join", view_func=controller.join_matchmaking, methods=["POST"])
game_blueprint.add_url_rule("/match/status", view_func=controller.status_matchmaking, methods=["GET"])
game_blueprint.add_url_rule("/deck/<game_id>", view_func=controller.choose_deck, methods=["POST"])
game_blueprint.add_url_rule("/play/<game_id>", view_func=controller.play_turn, methods=["POST"])
game_blueprint.add_url_rule("/hand/<game_id>", view_func=controller.get_hand, methods=["GET"])
game_blueprint.add_url_rule("/state/<game_id>", view_func=controller.get_state, methods=["GET"])