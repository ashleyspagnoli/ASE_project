import httpx
from pathlib import Path
import ssl
import os
import time

DEFAULT_URL = "https://localhost:8443"
API_GATEWAY_URL = os.getenv("API_GATEWAY_URL", DEFAULT_URL)



class UserState:
    """Contiene lo stato globale dell'utente loggato."""
    def __init__(self):
        self.token = None
        self.username = None

class ApiResult:
    def __init__(self, success: bool, message: str):
        self.success = success
        self.message = message

def get_ssl_context(cert_path):
    """
    Crea un contesto SSL che verifica che il certificato sia quello fornito,
    MA ignora il fatto che il nome host sia 'localhost' invece di 'api-gateway'.
    """
    if not cert_path:
        # Se non trovi il certificato, ritorna False (disabilita SSL - sconsigliato ma fallback)
        return False
        
    # Crea un contesto SSL di default che usa il tuo certificato come Authority
    ssl_context = ssl.create_default_context(cafile=cert_path)
    
    # 🔴 IL TRUCCO È QUI: Disabilitiamo il controllo del nome host
    # Questo permette di chiamare https://localhost:8443 anche se il cert è per 'api-gateway'
    ssl_context.check_hostname = False 
    
    # Assicuriamo che però il certificato sia valido (firmato correttamente)
    ssl_context.verify_mode = ssl.CERT_REQUIRED
    
    return ssl_context


current_dir = Path(__file__).resolve().parent # Risultato: /app/client_app

# 2. Risali alla cartella padre (la root del progetto)
project_root = current_dir.parent # Risultato: /app
# PERCORSO CERTIFICATO
# In Docker lo copieremo in una cartella specifica
DEFAULT_CERT_PATH = project_root / "gateway_cert.pem"
GATEWAY_CERT_PATH = os.getenv("GATEWAY_CERT_PATH", DEFAULT_CERT_PATH)

# 3. Costruisci il percorso del certificato

print(f"Using API Gateway cert at: {GATEWAY_CERT_PATH}")
time.sleep(1) # Pausa per vedere il messaggio

SSL_CONTEXT = get_ssl_context(GATEWAY_CERT_PATH)

# --- FUNZIONI DI SERVIZIO ---

async def api_login(username, password,CURRENT_USER_STATE: UserState):
    async with httpx.AsyncClient(verify=SSL_CONTEXT) as client:
        try:
            login_url = f"{API_GATEWAY_URL}/users/login"
            body = {"username": username, "password": password}
            
            response = await client.post(
                login_url,
                json=body,
            )
            
            response.raise_for_status() 
            data = response.json()
            CURRENT_USER_STATE.token = data.get("token")
            CURRENT_USER_STATE.username = username
            return ApiResult(success=True, message="Login successful")
    
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                return ApiResult(success=False, message="Username o password errati.") 
            # Qui rilanciamo gli errori generici del servizio

        except httpx.RequestError:
            return ApiResult(success=False, message="Servizio di autenticazione non raggiungibile.")
    

async def api_register(username, password, email,CURRENT_USER_STATE: UserState):
    # Logica di registrazione: OK
    async with httpx.AsyncClient(verify=SSL_CONTEXT) as client:
        try:
            register_url = f"{API_GATEWAY_URL}/users/register"
            body = {"username": username, "password": password, "email": email}
            
            response = await client.post(register_url, json=body)
            response.raise_for_status() 
            
            return ApiResult(success=True, message="Registration successful. Please login to continue.")

        except httpx.HTTPStatusError as e:
            # Cattura errori 400 (utente/email già registrato)
            if e.response.status_code == 400:
                detail = e.response.json().get('detail', "Errore di registrazione sconosciuto.")
                return ApiResult(success=False, message=detail)
            
        except httpx.RequestError:
            return ApiResult(success=False, message="Servizio di autenticazione non raggiungibile.")

# api_validate_token è ora api_validate_token_internal

async def api_view_data(CURRENT_USER_STATE: UserState):
    token = CURRENT_USER_STATE.token # Lettura dal globale
    
    async with httpx.AsyncClient(verify=SSL_CONTEXT) as client:
        try:
            collection_url = f"{API_GATEWAY_URL}/usereditor/view-data"
            headers = {"Authorization": f"Bearer {token}"}
            
            response = await client.get(
                collection_url,
                headers=headers,
            )
            
            response.raise_for_status() 
            data = response.json()
            print(data)
            return data  # Ritorna i dati dell'utente
    
        except httpx.HTTPStatusError as e:
            # Qui rilanciamo gli errori generici del servizio
            return None
            
        except httpx.RequestError:
            return None
        


async def api_change_password(old_password, new_password,CURRENT_USER_STATE: UserState): #ENDPOINT IMPLEMENTATO FUNZIONANTE
    token = CURRENT_USER_STATE.token # Lettura dal globale
    
    async with httpx.AsyncClient(verify=SSL_CONTEXT) as client:
        try:
            change_url = f"{API_GATEWAY_URL}/usereditor/change-password"
            headers = {"Authorization": f"Bearer {token}"}
            body = {"old_password": old_password, "new_password": new_password}
            
            response = await client.patch(
                change_url,
                headers=headers,
                json=body,
            )
            
            response.raise_for_status() 
            
            # Se la password cambia, il token vecchio è INVALIDO.
            # Rimuoviamo il token per forzare il re-login.

            
            CURRENT_USER_STATE.token = None
            CURRENT_USER_STATE.username = None
            return ApiResult(success=True, message="Password changed! Please login again.") # Forza re-login manuale dal main loop

            
        except httpx.HTTPStatusError as e:
            # Gestione errore 401 (vecchia password sbagliata) o 422 (validazione)
            detail = e.response.json().get('detail', "Errore sconosciuto.")
            if e.response.status_code == 401:
                return ApiResult(success=False, message="Vecchia password non valida.")
            elif e.response.status_code == 422:
                return ApiResult(success=False, message="La nuova password non soddisfa i requisiti di sicurezza.")
            else:
                return ApiResult(success=False, message=f"Errore {e.response.status_code}: {detail}")
            
        except httpx.RequestError:
            return ApiResult(success=False, message="Servizio di autenticazione non raggiungibile.")

async def api_change_email(old_email,new_email,CURRENT_USER_STATE: UserState):
    # ORA C'È DA IMPLEMENTARE BENE LE API PER CAMBIO EMAIL E USERNAME
    token = CURRENT_USER_STATE.token # Lettura dal globale
    
    async with httpx.AsyncClient(verify=SSL_CONTEXT) as client:
        try:
            change_url = f"{API_GATEWAY_URL}/usereditor/change-email"
            headers = {"Authorization": f"Bearer {token}"}
            body = {"old_email": old_email, "new_email": new_email}
            
            response = await client.patch(
                change_url,
                headers=headers,
                json=body,
            )
            
            response.raise_for_status() 

            CURRENT_USER_STATE.token = None
            CURRENT_USER_STATE.username = None
            return ApiResult(success=True, message="Mail changed! Please login again.") # Forza re-login manuale dal main loop

            
        except httpx.HTTPStatusError as e:
            # Gestione errore 401 (vecchia password sbagliata) o 422 (validazione)
            detail = e.response.json().get('detail', "Errore sconosciuto.")
            if e.response.status_code == 401:
                return ApiResult(success=False, message="Vecchia email non valida.")
            elif e.response.status_code == 422:
                return ApiResult(success=False, message="La nuova email non soddisfa i requisiti di sicurezza.")
            else:
                return ApiResult(success=False, message=f"Errore {e.response.status_code}: {detail}")
            
        except httpx.RequestError:
            return ApiResult(success=False, message="Servizio di autenticazione non raggiungibile.")

async def api_change_username(new_username,CURRENT_USER_STATE: UserState):
    # ORA C'È DA IMPLEMENTARE BENE LE API PER CAMBIO EMAIL E USERNAME
    token = CURRENT_USER_STATE.token # Lettura dal globale
    
    async with httpx.AsyncClient(verify=SSL_CONTEXT) as client:
        try:
            change_url = f"{API_GATEWAY_URL}/usereditor/change-username"
            headers = {"Authorization": f"Bearer {token}"}
            body = {"new_username": new_username}
            
            response = await client.patch(
                change_url,
                headers=headers,
                json=body,
            )
            
            response.raise_for_status() 

            CURRENT_USER_STATE.token = None
            CURRENT_USER_STATE.username = None  
            return ApiResult(success=True, message="Username changed! Please login again.") 

            
        except httpx.HTTPStatusError as e:
            error_detail = e.response.json().get('detail', "Errore sconosciuto.")
            # Gestione errore 401 (vecchia password sbagliata) o 422 (validazione)
            detail = e.response.json().get('detail', "Errore sconosciuto.")
            if e.response.status_code == 401:
                return ApiResult(success=False, message="Vecchio username non valido.")
            elif e.response.status_code == 422:
                # 🟢 MODIFICA QUI: Non stampare un messaggio fisso, ma mostra cosa dice il server
                print(f"DEBUG VALIDAZIONE: {error_detail}") 
                # Spesso error_detail è una lista di errori Pydantic
                return ApiResult(success=False, message=f"Errore validazione dati: {error_detail}")
            else:
                return ApiResult(success=False, message=f"Errore {e.response.status_code}: {detail}")
            
        except httpx.RequestError:
            return ApiResult(success=False, message="Servizio di autenticazione non raggiungibile.")
# --- LEADERBOARD ---
async def api_get_leaderboard(page:int, CURRENT_USER_STATE: UserState):
    token = CURRENT_USER_STATE.token # Lettura dal globale
    
    async with httpx.AsyncClient(verify=SSL_CONTEXT) as client:
        try:
            leaderboard_url = f"{API_GATEWAY_URL}/history/leaderboard"
            headers = {"Authorization": f"Bearer {token}"}
            
            response = await client.get(
                leaderboard_url,
                headers=headers,
                params={"page": page}
            )
            
            response.raise_for_status() 
            data = response.json()
            return data  # Ritorna i dati della leaderboard
    
        except httpx.HTTPStatusError as e:
            # Qui rilanciamo gli errori generici del servizio
            return None
            
        except httpx.RequestError:
            return None
        
# In client_app/apicalls.py

async def api_get_match_history(state: UserState):
    """Recupera lo storico delle partite dell'utente."""
    # Assumiamo che l'endpoint sia /history/matches
    url = f"{API_GATEWAY_URL}/history/matches" 
    token = state.token
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(verify=SSL_CONTEXT) as client:
        try:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                # Ci aspettiamo una lista di match es:
                # [{'opponent': 'Pippo', 'result': 'WIN', 'score': '10-2', 'date': '2023-10-10'}, ...]
                return response.json()
            return []
        except Exception:
            return []
        

# --- CARD COLLECTION ---
async def api_get_card_collection(CURRENT_USER_STATE: UserState):
    token = CURRENT_USER_STATE.token # Lettura dal globale
    
    async with httpx.AsyncClient(verify=SSL_CONTEXT) as client:
        try:
            collection_url = f"{API_GATEWAY_URL}/collection/cards"
            headers = {"Authorization": f"Bearer {token}"}
            
            response = await client.get(
                collection_url,
                headers=headers,
            )
            
            response.raise_for_status() 
            data = response.json()
            return data  # Ritorna i dati della card collection
    
        except httpx.HTTPStatusError as e:
            # Qui rilanciamo gli errori generici del servizio
            return None
            
        except httpx.RequestError:
            return None
        
async def api_get_deck_collection(CURRENT_USER_STATE: UserState):
    token = CURRENT_USER_STATE.token # Lettura dal globale
    
    async with httpx.AsyncClient(verify=SSL_CONTEXT) as client:
        try:
            collection_url = f"{API_GATEWAY_URL}/collection/decks"
            headers = {"Authorization": f"Bearer {token}"}
            
            response = await client.get(
                collection_url,
                headers=headers,
            )
            
            response.raise_for_status() 
            data = response.json()
            return data  # Ritorna i dati della deck collection
    
        except httpx.HTTPStatusError as e:
            # Qui rilanciamo gli errori generici del servizio
            return None
            
        except httpx.RequestError:
            return None
        
async def api_create_deck(deck:list,deck_slot:int,deck_name:str,CURRENT_USER_STATE: UserState):
    token = CURRENT_USER_STATE.token # Lettura dal globale

    async with httpx.AsyncClient(verify=SSL_CONTEXT) as client:
        try:
            create_url = f"{API_GATEWAY_URL}/collection/decks"
            headers = {"Authorization": f"Bearer {token}"}
            body = {"cards": deck,
                    "deckSlot": int(deck_slot),
                    "deckName": deck_name}
            print(body)
            response = await client.post(
                create_url,
                headers=headers,
                json=body,
            )
            
            response.raise_for_status() 
            data = response.json()
            print(data)
            return ApiResult(success=True, message="Deck created successfully.")
    
        except httpx.HTTPStatusError as e:
            # Qui rilanciamo gli errori generici del servizio
            detail = e.response.json().get('detail', "Errore sconosciuto.")
            return ApiResult(success=False, message=f"Errore {e.response.status_code}: {detail}")
            
        except httpx.RequestError:
            return ApiResult(success=False, message="Servizio di gestione collezione non raggiungibile.")
        
# In client_app/apicalls.py

async def api_delete_deck(deck_id, CURRENT_USER_STATE: UserState):
    token = CURRENT_USER_STATE.token
    # Assicurati di usare il contesto SSL corretto come discusso prima

    async with httpx.AsyncClient(verify=SSL_CONTEXT) as client:
        try:
            url = f"{API_GATEWAY_URL}/collection/decks/{deck_id}"
            headers = {"Authorization": f"Bearer {token}"}
            
            response = await client.delete(url, headers=headers)
            
            # Gestione errori HTTP (es. 404 o 403)
            if response.status_code == 200 or response.status_code == 204:
                return {"success": True} # O response.json() se il server ritorna JSON
            else:
                return {"success": False, "detail": response.text}

        except Exception as e:
            print(f"Errore delete: {e}")
            return {"success": False}

async def api_get_card_image(card_id, CURRENT_USER_STATE):
    token = CURRENT_USER_STATE.token
    # Usa il tuo SSL context getter


    async with httpx.AsyncClient(verify=SSL_CONTEXT) as client:
        try:
            # Assumo che l'endpoint sia questo
            url = f"{API_GATEWAY_URL}/collection/cards/{card_id}/image"
            headers = {"Authorization": f"Bearer {token}"}
            
            # Nota: Non ci aspettiamo JSON, ma dati binari
            response = await client.get(url, headers=headers)
            
            if response.status_code == 200:
                # Ritorniamo i bytes grezzi dell'immagine
                return response.content
            else:
                return None
        except Exception as e:
            print(f"Errore recupero immagine: {e}")
            return None
        

# In client_app/apicalls.py

async def api_join_matchmaking(deck_slot: int, CURRENT_USER_STATE):
    """Richiede di unirsi alla coda con un deck specifico."""
    url = f"{API_GATEWAY_URL}/game/match/join" # Adatta l'endpoint al tuo backend
    token = CURRENT_USER_STATE.token
 
    
    headers = {"Authorization": f"Bearer {token}"}
    body = {"deck_slot": deck_slot}

    async with httpx.AsyncClient(verify=SSL_CONTEXT) as client:
        try:
            response = await client.post(url, json=body, headers=headers)
            
            if response.status_code == 200 or response.status_code == 201:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "detail": response.text}
        except Exception as e:
            return {"success": False, "detail": str(e)}
        

async def api_get_match_status(CURRENT_USER_STATE: UserState):
    """Controlla lo stato attuale del matchmaking."""
    url = f"{API_GATEWAY_URL}/game/match/status" # Adatta l'endpoint
    token = CURRENT_USER_STATE.token

    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(verify=SSL_CONTEXT) as client:
        try:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                return response.json() # Ci aspettiamo { "status": "searching"|"started", "game_id": ... }
            return None
        except:
            return None
        
async def api_get_hand(game_id: str, CURRENT_USER_STATE: UserState):
    """Recupera le carte in mano al giocatore."""
    url = f"{API_GATEWAY_URL}/game/hand/{game_id}"
    token = CURRENT_USER_STATE.token
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(verify=SSL_CONTEXT) as client:
        try:
            response = await client.get(url, headers=headers)
            
            if response.status_code == 200:
                # 🟢 CORREZIONE: La risposta è GIÀ la lista, non usare .get()
                data = response.json()
                if isinstance(data, list):
                    return data
                # Fallback nel caso il formato cambiasse in futuro
                return data.get('hand', [])
            
            return [] # Ritorna lista vuota se status != 200 per evitare crash
            
        except Exception as e:
            print(f"Errore get hand: {e}")
            return [] # Ritorna lista vuota in caso di eccezione per evitare TypeError

async def api_get_game_state(game_id: str, CURRENT_USER_STATE: UserState):
    """Recupera lo stato completo della partita."""
    url = f"{API_GATEWAY_URL}/game/state/{game_id}"
    token = CURRENT_USER_STATE.token
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(verify=SSL_CONTEXT) as client:
        try:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception:
            return None

async def api_play_card(game_id: str, card_payload: dict, CURRENT_USER_STATE: UserState):
    """Gioca una carta e ritorna il JSON completo con lo status."""
    url = f"{API_GATEWAY_URL}/game/play/{game_id}"
    token = CURRENT_USER_STATE.token
    headers = {"Authorization": f"Bearer {token}"}
    
    body = {"card": card_payload}

    async with httpx.AsyncClient(verify=SSL_CONTEXT) as client:
        try:
            response = await client.post(url, json=body, headers=headers)
            # Ritorniamo il json grezzo se 200, altrimenti gestiamo l'errore
            if response.status_code == 200:
                return response.json() 
            else:
                return {"status": "error", "message": response.text}
        except Exception as e:
            return {"status": "error", "message": str(e)}