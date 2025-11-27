import requests
import time
import threading
import urllib3
import random
import string
from pymongo import MongoClient

# Disabilita warning SSL per chiamate al Gateway (self-signed)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# PUNTA ALL'API GATEWAY!
GATEWAY_URL = "https://localhost:8443"
COLLECTION_URL = "http://localhost:5003"


def inject_deck_db(username, deck_slot):
    print(f"💉 [{username}] Iniezione mazzo direttamente nel DB (Bypass API)...")
    
    # 1. LISTA DI ID CARTE VALIDI (DAI TUOI DATI REALI)
    # Devi mettere qui 8 ID che esistono sicuramente nel tuo cards.json.
    # Scegli carte con pochi punti per evitare problemi di logica successiva.
    # Esempio: 2 carte per seme.
    card_ids_to_inject = [
        "h_2", "h_3",  # Cuori (Hearts) 
        "d_2", "d_3",  # Quadri (Diamonds)
        "c_2", "c_3",  # Fiori (Clubs)
        "s_2", "s_3"   # Picche (Spades)
    ]
    
    # Se non conosci gli ID, puoi provare a leggere il file locale se il test è nella stessa cartella
    # o lasciare questi se i tuoi ID sono formattati così.
    
    try:
        # 2. Connessione a Mongo (assumendo che sia esposto su localhost)
        # Se usi Docker, assicurati che la porta 27017 sia mappata su localhost
        client = MongoClient('mongodb://localhost:27018/')
        db = client['card_game']
        decks_collection = db['decks']
        
        # 3. Creazione oggetto Deck
        deck_doc = {
            "userId": username,   # Lo username generato dal test
            "slot": deck_slot,
            "name": f"Mazzo Iniettato {username}",
            "cards": card_ids_to_inject
        }
        
        # 4. Upsert (Inserisci o Aggiorna se esiste già per questo utente/slot)
        decks_collection.replace_one(
            {"userId": username, "slot": deck_slot},
            deck_doc,
            upsert=True
        )
        
        print(f"✅ [{username}] Mazzo iniettato con successo nello slot {deck_slot}!")
        return True

    except Exception as e:
        print(f"❌ [{username}] Errore iniezione DB: {e}")
        print("   -> Assicurati che MongoDB sia raggiungibile da localhost:27017")
        return False
    
def generate_random_user():
    rand_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"user_{rand_str}", "Password123!"

def register_and_login(username, password):
    print(f"👤 [{username}] Registrazione...")
    try:
        # 1. Registrazione via Gateway -> User Manager
        reg_resp = requests.post(f"{GATEWAY_URL}/users/register", json={
            "username": username, "email": f"{username}@test.com", "password": password
        }, verify=False) # Verify False perché il gateway ha cert self-signed
        
        if reg_resp.status_code not in [200, 201]:
            # Se esiste già proviamo il login
            print(f"⚠️ [{username}] Utente forse esistente ({reg_resp.status_code}), provo login...")

        # 2. Login via Gateway -> User Manager
        # Il test ora usa l'endpoint /users/login che accetta JSON,
        # invece di /users/token che si aspetta form-data.
        login_resp = requests.post(f"{GATEWAY_URL}/users/login", json={
            "username": username, "password": password
        }, verify=False)
        
        if login_resp.status_code != 200:
            print(f"❌ [{username}] Login fallito: {login_resp.text}")
            return None
            
        token = login_resp.json().get("token")
        print(f"🔑 [{username}] Token ottenuto!")
        return token
    except Exception as e:
        print(f"❌ [{username}] Errore connessione Auth: {e}")
        return None

def create_deck(username, token, deck_slot):
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Aggiungi carte iniziali alla collezione del giocatore
    print(f"✨ [{username}] Assegnazione carte iniziali...")
    try:
        add_cards_resp = requests.post(f"{COLLECTION_URL}/collection/starter-pack", headers=headers, verify=False)
        if add_cards_resp.status_code not in [200, 201]:
            print(f"❌ [{username}] Errore nell'assegnare le carte iniziali: {add_cards_resp.text}")
            return False
        
        starter_cards = add_cards_resp.json()
        if not starter_cards or len(starter_cards) < 20:
            print(f"⚠️ [{username}] Non sono state ricevute abbastanza carte iniziali (ricevute: {len(starter_cards)}).")
            return False

        print(f"✅ [{username}] Carte iniziali assegnate.")
        card_ids = [card['id'] for card in starter_cards]

    except Exception as e:
        print(f"❌ [{username}] Eccezione durante l'assegnazione delle carte: {e}")
        return False

    # 2. Crea il mazzo con le carte iniziali
    deck_name = f"Mazzo Iniziale di {username}"
    print(f"🛠️ [{username}] Creazione del mazzo '{deck_name}'...")
    try:
        create_deck_resp = requests.post(f"{COLLECTION_URL}/collection/decks", headers=headers, json={
            "name": deck_name,
            "cards": card_ids,
            "slot": deck_slot
        }, verify=False)

        if create_deck_resp.status_code not in [200, 201]:
            print(f"❌ [{username}] Errore creazione mazzo: {create_deck_resp.text}")
            return False
        
        print(f"✅ [{username}] Mazzo creato con successo nello slot {deck_slot}!")
        return True
    except Exception as e:
        print(f"❌ [{username}] Eccezione creazione mazzo: {e}")
        return False

def player_routine(username, password, deck_slot):
    token = register_and_login(username, password)
    if not token: return

    # Aggiunta fase di creazione mazzo
    if not inject_deck_db(username, deck_slot):
        print(f"🛑 [{username}] Impossibile iniettare il mazzo. Esco.")
        return

    headers = {"Authorization": f"Bearer {token}"}
    game_id = None

    print(f"🔵 [{username}] Join Matchmaking...")
    
    # 3. Matchmaking Loop
    while True:
        try:
            # Chiamata al Game Engine via Gateway (/game/...)
            resp = requests.post(f"{GATEWAY_URL}/game/match/join", headers=headers, verify=False)
            if resp.status_code == 401:
                print(f"❌ [{username}] Non autorizzato dal Game Engine!")
                return
            
            data = resp.json()
            if data.get("status") == "matched":
                game_id = data["game_id"]
                print(f"✅ [{username}] PARTITA TROVATA! ID: {game_id}")
                break
            elif data.get("status") == "waiting":
                print(f"⏳ [{username}] Polling...")
                time.sleep(2)
                # Polling Status
                while True:
                    stat_resp = requests.get(f"{GATEWAY_URL}/game/match/status", headers=headers, verify=False)
                    stat_data = stat_resp.json()
                    if stat_data.get("status") == "matched":
                        game_id = stat_data["game_id"]
                        print(f"✅ [{username}] Match confermato! ID: {game_id}")
                        break
                    time.sleep(1.5)
                break
        except Exception as e:
            print(f"❌ [{username}] Errore Matchmaking: {e}")
            return

    # 4. Scelta Mazzo
    print(f"🎴 [{username}] Scelta mazzo...")
    try:
        # Se collection non è attiva/mockata, questo fallirà se il codice cerca deck veri
        # Assumiamo che select_deck gestisca errori o che collection funzioni
        res = requests.post(f"{GATEWAY_URL}/game/deck/{game_id}", json={"deck_slot": deck_slot}, headers=headers, verify=False)
        if res.status_code != 200:
            print(f"⚠️ [{username}] Errore mazzo: {res.text}. Continuo se possibile...")
    except Exception as e:
        print(f"⚠️ [{username}] Exception mazzo: {e}")

    time.sleep(1)

    # 5. Game Loop
    while True:
        try:
            hand_resp = requests.get(f"{GATEWAY_URL}/game/hand/{game_id}", headers=headers, verify=False)
            hand = hand_resp.json()
            
            # Controllo fine partita
            state_resp = requests.get(f"{GATEWAY_URL}/game/state/{game_id}", headers=headers, verify=False)
            state = state_resp.json()
            if state.get("winner"):
                print(f"🏆 [{username}] FINE: Vince {state['winner']}")
                break

            if not hand or len(hand) == 0:
                print(f"[{username}] Mano vuota, attendo...")
                time.sleep(2)
                continue

            # Gioca una carta a caso dalla mano
            card = random.choice(hand)
            print(f"⚔️ [{username}] Gioca {card['value']} {card['suit']}")
            play_resp = requests.post(f"{GATEWAY_URL}/game/play/{game_id}", json={"card": card}, headers=headers, verify=False)
            
            if play_resp.json().get("status") == "finished":
                print(f"🏁 [{username}] Partita finita dopo mossa.")
                break
            
            time.sleep(1.5)

        except Exception as e:
            print(f"❌ [{username}] Errore loop gioco: {e}")
            break

if __name__ == "__main__":
    u1, p1 = generate_random_user()
    u2, p2 = generate_random_user()

    t1 = threading.Thread(target=player_routine, args=(u1, p1, 1))
    t2 = threading.Thread(target=player_routine, args=(u2, p2, 2))

    t1.start()
    time.sleep(2) # Ritardo per far entrare il primo in attesa
    t2.start()

    t1.join()
    t2.join()
    print("Test completato.")