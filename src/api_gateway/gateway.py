import json
import httpx
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List 
from requests.exceptions import HTTPError # Mantieni solo per la cattura dell'errore (anche se non usata con httpx)



# --- CONFIGURAZIONE GLOBALE (Riferimento) ---
ALLOWED_AUTH_OPS = ['login', 'register', 'validate-token']
USER_URL = 'https://user-manager:5000' # URL interno del microservizio
USER_CERT = '/app/cert.pem'
# Client HTTPX globale per efficienza (Assumi che sia definito globalmente)
http_client = httpx.AsyncClient(verify=False, timeout=10.0) 
# ---

# Rimuovi response_model=UserOut per gli endpoint di autenticazione, 
# poiché restituiscono un Token o un Messaggio, non l'oggetto User completo.

app = FastAPI(
    title="Api Gateway Client Side", 
    description="Handles user registration, JWT login, and core user data management.",
    version="1.0.0"
)

# Aggiungi questa funzione all'inizio del tuo file, dopo la configurazione globale

# Funzione di forwarding riprogettata (sostituisci l'implementazione precedente)

async def forward_request(request: Request, internal_url: str, body_data: dict = None) -> Response:
    """
    Funzione generica per inoltrare la richiesta.
    Accetta il body esplicito (body_data) se la rotta lo richiede (POST/PATCH).
    """
    
    # 1. Prepara e pulisce gli header
    headers = dict(request.headers)
    headers.pop('host', None)
    headers.pop('content-length', None) # Cruciale per evitare Too little data

    # 2. Imposta i parametri della richiesta httpx
    request_kwargs = {
        "method": request.method,
        "url": internal_url,
        "headers": headers,
        "params": request.query_params,
        "timeout": 10.0
    }
    
    # 3. Aggiunge il body: usa 'json=body_data' se fornito (per rotte POST/PATCH)
    if body_data is not None:
        request_kwargs['json'] = body_data
    else:
        # Se non c'è body_data (rotte GET/DELETE) o se vogliamo inoltrare body raw
        # (in questo caso non necessario, ma utile per coprire tutti i casi)
        request_kwargs['content'] = None 
    

    # 4. Inoltra la richiesta (usando il client globale)
    try:
        response = await http_client.request(**request_kwargs)
        
        response.raise_for_status() 
        
        # 5. Restituisce la risposta HTTP
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=response.headers
        )

    except httpx.HTTPStatusError as e:
        # 6. Propagazione degli errori
        return Response(
            content=e.response.content,
            status_code=e.response.status_code,
            headers=e.response.headers
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Target service not reachable at {internal_url}"
        )
#-- Authentication Endpoints Proxies --#


class UserLogin(BaseModel):
    username: str = Field(..., example="user123")
    password: str = Field(..., example="strongpassword")
    

# --- Authentication Endpoints Proxies (Riscritto) ---

# Usiamo la funzione di forwarding e il modello Pydantic solo per la documentazione
@app.post("/users/login", tags=["Authentication and Users"])
async def proxy_login(user_data: UserLogin, request: Request):
    """Proxy per l'autenticazione tramite JSON."""
    URL = USER_URL + '/users/login' 
    
    # Inoltra la richiesta originale (inclusi i dati JSON già presenti nel body stream)
    return await forward_request(request, URL, body_data=user_data.dict())

class UserRegister(BaseModel):
    username: str = Field(..., example="newuser")
    password: str = Field(..., min_length=3, example="newstrongpassword")
    email: Optional[str] = Field(None, example="aseproject@unipi.it")

@app.post("/users/register", tags=["Authentication and Users"])
async def proxy_register(user_data: UserRegister, request: Request):
    """Proxy per la registrazione."""
    URL = USER_URL + '/users/register' 

    return await forward_request(request, URL, body_data=user_data.dict())

# --- Endpoint GET e PATCH (Riscritto) ---

@app.get("/users/validate-token", tags=["Authentication and Users"])
async def proxy_validate_token(request: Request):
    """Proxy per la validazione del token JWT."""
    URL = USER_URL + '/users/validate-token' 
    
    # Inoltra la richiesta GET (senza body)
    return await forward_request(request, URL, body_data=None)


@app.patch("/users/modify/change-username", tags=["User Editing"])
async def proxy_change_username(request: Request):
    """Proxy per la modifica del username."""
    URL = USER_URL + '/users/modify/change-username' 
    
    # Inoltra la richiesta PATCH (con body)
    return await forward_request(request, URL, body_data=await request.json())

@app.patch("/users/modify/change-password", tags=["User Editing"])
async def proxy_change_password(request: Request):
    """Proxy per la modifica della password."""
    URL = USER_URL + '/users/modify/change-password' 
    
    # Inoltra la richiesta PATCH (con body)
    return await forward_request(request, URL, body_data=await request.json())

@app.patch("/users/modify/change-email", tags=["User Editing"])
async def proxy_change_email(request: Request):
    """Proxy per la modifica dell'email."""
    URL = USER_URL + '/users/modify/change-email' 
    
    # Inoltra la richiesta PATCH (con body)
    return await forward_request(request, URL, body_data=await request.json())

# --- Internal Service Endpoints Proxies (Riscritto) ---

