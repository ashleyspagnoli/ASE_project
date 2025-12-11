from flask import request, jsonify
from functools import wraps
import requests
import os

USER_MANAGER_URL = os.environ.get('USER_MANAGER_URL', 'https://user-manager:5000')

def validate_user_token(token_header: str):
    """
    Valida il token JWT chiamando il microservizio user-manager.
    Restituisce (user_uuid, username) se valido, solleva eccezione altrimenti.
    """
    if not token_header:
        raise ValueError("Header Authorization mancante.")
    
    try:
        token_type, token = token_header.split(" ")
        if token_type.lower() != "bearer":
            raise ValueError("Token non Bearer")
    except:
        raise ValueError("Formato header Authorization invalido. Usa 'Bearer <token>'")

    validate_url = f"{USER_MANAGER_URL}/users/validate-token"
    
    try:
        response = requests.get(
            validate_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
            verify=False
        )
        response.raise_for_status()
        user_data = response.json()
        return user_data["id"], user_data["username"]
    
    except requests.RequestException as e:
        print(f"Errore validazione token: {e}")
        raise ValueError("Token non valido o servizio utenti irraggiungibile")

mock_token_validator = None
def require_auth(f):
    """
    Decorator per proteggere le route Flask.
    Estrae il token dall'header Authorization e lo valida.
    Inietta user_id e username come parametri alla funzione decorata.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        
        if mock_token_validator:
            user_id, username = mock_token_validator()
            return f(user_id=user_id, username=username, *args, **kwargs)
        
        auth_header = request.headers.get('Authorization')
        
        try:
            user_id, username = validate_user_token(auth_header)
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 401
        
        # Inietta user_id e username nella funzione
        return f(user_id=user_id, username=username, *args, **kwargs)
    
    return decorated_function