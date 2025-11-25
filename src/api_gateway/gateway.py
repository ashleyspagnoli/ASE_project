

import httpx
from fastapi import Request, Response, HTTPException, status
import os

# Definisci questo client globale per riutilizzare la connessione:
http_client = httpx.AsyncClient(verify=False, timeout=10.0) 




async def simple_forward(request: Request, service_url: str):
    """
    Inoltra una Request in ingresso a un Target Service interno.
    
    Args:
        request: L'oggetto Request in ingresso da FastAPI.
        service_url: L'URL base interno del servizio di destinazione (es. http://game_service:8000).
    """
    
    # 1. Determina l'URL di destinazione interno completo
    path_with_query = request.url.path + ("?" + str(request.url.query) if request.url.query else "")
    target_url = service_url + path_with_query
    
    # 2. Copia gli header
    headers = dict(request.headers)
    
    # ⚠️ Premura di sicurezza: Rimuovi l'header 'host' per evitare problemi di routing interno
    headers.pop('host', None)
    
    # 3. Legge il corpo della richiesta come bytes
    #    Questo gestisce sia JSON che Form Data in modo neutrale.
    body = await request.body() 

    # 4. Inoltra la richiesta
    try:
        response = await http_client.request(
            request.method,
            target_url,
            headers=headers,
            # content passa il body letto come bytes
            content=body, 
        )
        
        # 5. Restituisce la risposta al client esterno
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=response.headers
        )
        
    except httpx.RequestError:
        # Gestisce errori di rete (es. il servizio interno è giù)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Servizio di destinazione ({service_url}) non raggiungibile."
        )
# Esempio di utilizzo in un endpoint FastAPI:
#


@app.api_route("/games/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_to_game_service(request: Request, full_path: str):
    GAME_SERVICE_URL = os.getenv("GAME_SERVICE_URL", "http://game_service:8000")
    return await simple_forward(request, GAME_SERVICE_URL)