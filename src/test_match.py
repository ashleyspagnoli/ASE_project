import socketio
import time
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURAZIONE ---
GATEWAY_URL = 'https://localhost:8443'      # Per Auth
GAME_ENGINE_HTTP = 'http://localhost:5001'  # Per scaricare la mano (GET)
GAME_ENGINE_WS = 'http://localhost:5001'    # Per giocare (WebSocket)

# --- STATO GLOBALE DEI CLIENT ---
# Memorizziamo qui i dati per ogni giocatore (token, game_id, mano attuale)
players_state = {
    "Alice": {"token": None, "game_id": None, "hand": [], "client": socketio.Client()},
    "Bob":   {"token": None, "game_id": None, "hand": [], "client": socketio.Client()}
}

def get_real_token(username):
    """Ottiene il token dal Gateway."""
    # Password sicura (> 3 caratteri)
    PASSWORD = "password123" 
    
    try:
        # 1. Registrazione (ignoriamo il risultato se l'utente esiste già)
        # verify=False serve per i certificati self-signed del Gateway
        requests.post(
            f"{GATEWAY_URL}/users/register", 
            json={"username": username, "password": PASSWORD, "email": f"{username}@test.com"}, 
            verify=False
        )
        
        # 2. Login
        resp = requests.post(
            f"{GATEWAY_URL}/users/login", 
            json={"username": username, "password": PASSWORD}, 
            verify=False
        )
        
        if resp.status_code == 200:
            data = resp.json()
            token = data.get('token') or data.get('access_token')
            print(f"🔑 Token ottenuto per {username}")
            return f"Bearer {token}"
        else:
            print(f"❌ Errore Login {username}: {resp.status_code} - {resp.text}")
            
    except Exception as e:
        print(f"❌ Auth Exception {username}: {e}")
    return None

def fetch_hand(username):
    """Scarica la mano via HTTP per sapere cosa giocare."""
    p = players_state[username]
    headers = {"Authorization": p['token']}
    try:
        # Nota: Qui chiamiamo HTTP diretto al Game Engine perché il Gateway non ha ancora le rotte /game
        resp = requests.get(f"{GAME_ENGINE_HTTP}/game/hand/{p['game_id']}", headers=headers)
        if resp.status_code == 200:
            p['hand'] = resp.json()
            print(f"🃏 [{username}] Mano ricevuta: {len(p['hand'])} carte.")
        else:
            print(f"❌ Errore Hand {username}: {resp.text}")
    except Exception as e:
        print(f"❌ Errore Hand Req {username}: {e}")

def play_next_card(username):
    """Prende la prima carta dalla mano e la gioca via WebSocket."""
    p = players_state[username]
    if not p['hand']:
        print(f"⚠️  [{username}] Nessuna carta in mano!")
        return

    # Prendi la prima carta e rimuovila dalla lista locale (simulazione client)
    card_to_play = p['hand'].pop(0)
    
    print(f"🚀 [{username}] Gioca {card_to_play['value']} di {card_to_play['suit']} via Socket...")
    
    # EMETTE L'EVENTO PLAY_CARD
    p['client'].emit('play_card', {
        'token': p['token'],
        'game_id': p['game_id'],
        'card': card_to_play
    })

# --- SETUP SOCKET HANDLERS ---
def setup_client(username):
    sio = players_state[username]['client']

    @sio.event
    def connect():
        print(f"✅ [{username}] Connesso Socket.")
        sio.emit('join_queue', {'token': players_state[username]['token']})

    @sio.on('match_start')
    def on_match(data):
        print(f"⚔️  [{username}] MATCH START! Game ID: {data['game_id']}")
        players_state[username]['game_id'] = data['game_id']
        
        # Appena inizia il match, scarica la mano e gioca la prima carta
        fetch_hand(username)
        # Diamo un piccolo delay per realismo
        time.sleep(1)
        play_next_card(username)

    @sio.on('round_status')
    def on_status(data):
        print(f"⏳ [{username}] {data['message']}")

    @sio.on('round_result')
    def on_result(data):
        # Questo evento arriva a ENTRAMBI quando il turno è finito
        if data['status'] == 'finished':
            print(f"🏆 [{username}] PARTITA FINITA! Vincitore: {data['match_winner']}")
            sio.disconnect()
        else:
            print(f"R [{username}] Round finito. {data['message']} (Punteggi: {data['scores']})")
            # Gioca la carta successiva per il prossimo round
            time.sleep(1)
            play_next_card(username)

    @sio.on('error')
    def on_error(data):
        print(f"❌ [{username}] Errore Socket: {data}")

# --- MAIN ---
if __name__ == '__main__':
    print("--- 1. AUTENTICAZIONE ---")
    players_state['Alice']['token'] = get_real_token("Alice")
    players_state['Bob']['token'] = get_real_token("Bob")

    if not players_state['Alice']['token'] or not players_state['Bob']['token']:
        print("❌ Token mancanti.")
        exit(1)

    print("--- 2. START CLIENTS ---")
    setup_client("Alice")
    setup_client("Bob")

    try:
        # Connettiamo i socket
        players_state['Alice']['client'].connect(GAME_ENGINE_WS)
        players_state['Bob']['client'].connect(GAME_ENGINE_WS)
        
        # Mantiene vivo lo script
        players_state['Alice']['client'].wait()
    except Exception as e:
        # Intercetta la disconnessione pulita a fine partita
        pass
    
    print("--- TEST TERMINATO ---")