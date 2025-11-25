import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from typing import Dict, Any

# ⚠️ Indirizzo del tuo Servizio Auth (cruciale in Docker/Kubernetes)
AUTH_SERVICE_URL = "https://localhost:5004"

# 1. Schema per estrarre il token dall'header Authorization: Bearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{AUTH_SERVICE_URL}/token") 

async def get_validated_user_data(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    """
    Estrae il token dall'header del client e lo invia al Servizio Auth per la validazione.
    """
    validation_url = f"{AUTH_SERVICE_URL}/users/validate-token"
    
    async with httpx.AsyncClient() as client:
        try:
            # 2. Chiama l'endpoint di validazione del tuo Servizio Auth
            response = await client.get(
                validation_url,
                headers={"Authorization": f"Bearer {token}"}
            )
            
            # 3. Solleva un'eccezione se l'Auth Service ha risposto con 4xx o 5xx
            response.raise_for_status() 
            
            # 4. Restituisce i dati validati (ID e username)
            return response.json() 

        except httpx.HTTPStatusError as e:
            # Se l'Auth Service dice che il token è cattivo (401/403), lo riproponiamo al client
            if e.response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token JWT non valido o scaduto.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            # Gestisce altri errori restituiti dal Servizio Auth
            raise HTTPException(status_code=500, detail=f"Errore Servizio Auth: {e.response.json().get('detail', 'Sconosciuto')}")
            
        except httpx.RequestError:
            # Errore di connessione: il tuo Servizio Auth è giù
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Servizio di autenticazione non raggiungibile."
            )