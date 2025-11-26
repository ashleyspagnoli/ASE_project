from flask import request
from flask_socketio import emit, join_room
from extensions import socketio
from routes import controller
from logic import validate_user_token, handle_socket_join, handle_socket_disconnect, submit_card

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    handle_socket_disconnect(request.sid)
    print(f"Client disconnected: {request.sid}")

@socketio.on('join_queue')
def on_join_queue(data):
    token = data.get('token')
    if not token:
        emit('error', {'message': 'Token missing'})
        return

    try:
        user_uuid, username = validate_user_token(token)
    except ValueError as e:
        emit('error', {'message': str(e)})
        return

    match_found, result = handle_socket_join(
        user_uuid, username, request.sid, controller.games
    )

    if match_found:
        game_id = result['match_data']['game_id']
        
        # IMPORTANTE: Uniamo il socket corrente alla stanza
        join_room(game_id)
        
        # Notifichiamo l'avversario (specificando il suo SID)
        socketio.emit('match_start', result['match_data'], room=result['player1_sid'])
        # Notifichiamo noi stessi
        emit('match_start', result['match_data'])
    else:
        emit('queue_status', {'status': 'waiting', 'message': 'Sei in coda...'})


@socketio.on('play_card')
def on_play_card(data):
    """
    Riceve: { 'token': '...', 'game_id': '...', 'card': {'value': 'K', 'suit': 'hearts'} }
    """
    token = data.get('token')
    game_id = data.get('game_id')
    card_data = data.get('card')

    if not all([token, game_id, card_data]):
        emit('error', {'message': 'Dati mancanti (token, game_id o card)'})
        return

    try:
        # 1. Validiamo l'utente
        user_uuid, username = validate_user_token(token)

        # 2. Eseguiamo la logica di gioco (la stessa usata nelle rotte HTTP)
        # result conterrà: status ('waiting', 'resolved', 'finished'), scores, winner, ecc.
        result = submit_card(game_id, user_uuid, card_data, controller.games)

        # 3. Gestiamo la risposta
        if result['status'] == 'waiting':
            # Solo uno ha giocato, notifichiamo solo lui
            emit('round_status', {'message': 'Carta giocata. In attesa dell\'avversario...'})
        
        elif result['status'] in ['resolved', 'finished']:
            # Il turno è finito o la partita è finita!
            # Manda il risultato a TUTTI nella stanza (room=game_id)
            socketio.emit('round_result', result, room=game_id)

    except ValueError as e:
        emit('error', {'message': str(e)})
    except Exception as e:
        emit('error', {'message': f"Errore server: {str(e)}"})