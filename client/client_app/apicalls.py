import httpx
from pathlib import Path
import ssl

API_GATEWAY_URL = "https://localhost:8443"

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

# 3. Costruisci il percorso del certificato
GATEWAY_CERT_PATH = project_root / "gateway_cert.pem"

print(f"Using API Gateway cert at: {GATEWAY_CERT_PATH}")

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
            collection_url = f"{API_GATEWAY_URL}/usereditor/view-userdata"
            headers = {"Authorization": f"Bearer {token}"}
            
            response = await client.get(
                collection_url,
                headers=headers,
            )
            
            response.raise_for_status() 
            data = response.json()
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
            change_url = f"{API_GATEWAY_URL}/users/modify/change-password"
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
            change_url = f"{API_GATEWAY_URL}/users/modify/change-email"
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
            change_url = f"{API_GATEWAY_URL}/users/modify/change-username"
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
            # Gestione errore 401 (vecchia password sbagliata) o 422 (validazione)
            detail = e.response.json().get('detail', "Errore sconosciuto.")
            if e.response.status_code == 401:
                return ApiResult(success=False, message="Vecchio username non valido.")
            elif e.response.status_code == 422:
                return ApiResult(success=False, message="Il nuovo username non soddisfa i requisiti di sicurezza.")
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

        
