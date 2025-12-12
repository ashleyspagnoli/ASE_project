import requests
import json
from config import USERNAMES_BY_IDS_URL, USER_MANAGER_CERT, USER_MANAGER_URL

# Helper to get usernames for a list of UUIDs in one request
mock_usernames_by_ids = None
def get_usernames_by_ids(user_ids):
    """
    Fetch usernames for a list of user IDs via the user-manager endpoint
    GET /utenti/usernames-by-ids?id_list=<id>&id_list=<id2> ...
    Returns a dict {id: username}
    """
    if not user_ids:
        return {}
    # Turn input into list
    user_ids = list(user_ids)
    
    if mock_usernames_by_ids:
        data = mock_usernames_by_ids(user_ids)
    else:
        try:
            # requests will serialize list params as repeated query params
            resp = requests.get(
                USERNAMES_BY_IDS_URL,
                params={'id_list': user_ids},
                timeout=3,
                verify=USER_MANAGER_CERT
            )
            if resp.status_code == 200:
                data = resp.json() or []
            else:
                print(f"Error: usernames-by-ids returned {resp.status_code}: {resp.text}", flush=True)
                data = []
        except requests.exceptions.ConnectionError as e:
            print(f"Warning: Could not connect to user-manager at {USERNAMES_BY_IDS_URL}. {e}", flush=True)
            data = []
        except Exception as e:
            print(f"Warning: Error fetching usernames for ids {user_ids}. {e}", flush=True)
            data = []

    mapping = {item.get('id'): item.get('username') for item in data if isinstance(item, dict)}
    # Ensure all ids present in mapping
    for uid in user_ids:
        mapping.setdefault(uid, "Unknown user")
    return mapping

# ------------------------------------------------------------
# 🔐 User Token Validation
#------------------------------------------------------------
mock_user_validator = None
def validate_user_token(token_header: str):
    """
    Contatta l'user-manager (in HTTPS) per validare un token JWT.
    
    Ignora la verifica del certificato SSL (verify=False) per permettere
    la comunicazione tra container con certificati auto-firmati.

    Restituisce (user_uuid, username) se il token è valido.
    Solleva ValueError se il token non è valido o il servizio non risponde.
    """
    if not token_header:
        raise ValueError("Header 'Authorization' mancante.")

    if mock_user_validator:
        return mock_user_validator(token_header)
    
    # Il token_header è "Bearer eyJ...". Dobbiamo estrarre solo il token "eyJ..."
    try:
        token_type, token = token_header.split(" ")
        if token_type.lower() != "bearer":
            raise ValueError("Tipo di token non valido, richiesto 'Bearer'.")
    except Exception:
        raise ValueError("Formato 'Authorization' header non valido. Usare 'Bearer <token>'.")

    # Questo è l'endpoint che hai definito nel tuo user-manager
    validate_url = f"{USER_MANAGER_URL}/users/validate-token"

    try:
        # Invia la richiesta GET con il token come query parameter
        response = requests.get(
            validate_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
            verify=USER_MANAGER_CERT  # <-- verifica del certificato SSL
        )

        # Se l'user-manager risponde 401, 403, 404, ecc., solleva un errore
        response.raise_for_status()

        user_data = response.json()

        # L'endpoint /users/validate-token restituisce 'id' e 'username'
        user_uuid = user_data.get("id")
        username = user_data.get("username")

        if not user_uuid:
            raise ValueError("Dati utente incompleti dal servizio di validazione")

        print(f"Token validato con successo per l'utente: {user_uuid}", flush=True)
        return user_uuid, username

    except requests.RequestException as e:
        # Errore di connessione o risposta 4xx/5xx dal servizio utenti
        error_detail = f"Impossibile validare l'utente. Errore di connessione a {validate_url}."
        if e.response:
            try:
                # Prova a leggere il 'detail' dall'errore FastAPI
                error_detail = e.response.json().get('detail', 'Errore sconosciuto da User-Manager')
            except json.JSONDecodeError:
                error_detail = e.response.text

        print(f"ERRORE validazione token: {error_detail}")
        # Solleva un ValueError che il controller (routes.py) convertirà in 401
        raise ValueError(f"Servizio Utenti: {error_detail}")
