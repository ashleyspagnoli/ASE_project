from flask import Blueprint, jsonify, request
from logic import (
    start_new_game,
    submit_card,
    get_game_state,
    select_deck,
    matchmaking_connect,
    matchmaking_match,
)

game_blueprint = Blueprint("game_engine", __name__)


class GameController:
    def __init__(self):
        self.games = {}
        self.online_players = []

    def start_game(self):
        data = request.get_json()
        player1 = data.get("player1")
        player2 = data.get("player2")
        game_id = start_new_game(player1, player2, self.games)
        return jsonify({"game_id": game_id, "status": "started"}), 201

    def choose_deck(self, game_id):
        data = request.get_json()
        player = data.get("player")
        deck = data.get("deck")
        result = select_deck(game_id, player, deck, self.games)
        return jsonify(result), 200

    def play_turn(self, game_id):
        data = request.get_json()
        player = data.get("player")
        card = data.get("card")
        result = submit_card(game_id, player, card, self.games)
        return jsonify(result), 200

    def get_state(self, game_id):
        state = get_game_state(game_id, self.games)
        return jsonify(state)

    def connect_player(self):
        data = request.get_json()
        username = data.get("username")
        result = matchmaking_connect(username, self.online_players)
        return jsonify(result), 200

    def find_match(self):
        match = matchmaking_match(self.online_players, self.games)
        return jsonify(match), 200


controller = GameController()

game_blueprint.add_url_rule("/start", view_func=controller.start_game, methods=["POST"])
game_blueprint.add_url_rule("/deck/<game_id>", view_func=controller.choose_deck, methods=["POST"])
game_blueprint.add_url_rule("/play/<game_id>", view_func=controller.play_turn, methods=["POST"])
game_blueprint.add_url_rule("/state/<game_id>", view_func=controller.get_state, methods=["GET"])
game_blueprint.add_url_rule("/connect", view_func=controller.connect_player, methods=["POST"])
game_blueprint.add_url_rule("/matchmake", view_func=controller.find_match, methods=["POST"])