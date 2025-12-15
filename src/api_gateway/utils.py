import httpx
import ssl
import os
from fastapi import Request, HTTPException, status
from fastapi.responses import Response
from urllib.parse import urlparse

SERVICE_CERTS = {
    "user-manager": "/run/secrets/user_manager_cert",
    "game_history": "/run/secrets/history_cert",
    "collection": "/run/secrets/collection_cert",
    "game_engine": "/run/secrets/game_engine_cert",
    "user-editor": "/run/secrets/user_editor_cert",
}

# ❌ RIMUOVI O COMMENTA IL CLIENT GLOBALE
# http_client = httpx.AsyncClient(timeout=10.0) 

async def forward_request(request: Request, internal_url: str, body_data: dict = None, is_json: bool = True) -> Response:
    headers = dict(request.headers)
    headers.pop('host', None)
    headers.pop('content-length', None)

    parsed_url = urlparse(internal_url)
    hostname = parsed_url.hostname
    cert_path = SERVICE_CERTS.get(hostname)

    # 1. Determina la strategia di verifica SSL
    verify_option = False # Default (insicuro)

    if cert_path and os.path.exists(cert_path):
        try:
            ssl_context = ssl.create_default_context(cafile=cert_path)
            # ssl_context.check_hostname = False # Decommenta se hai problemi di Hostname Mismatch
            verify_option = ssl_context
            print(f"Using SSL Context with cert: {cert_path}")
        except Exception as e:
            print(f"Error loading cert {cert_path}: {e}")
            verify_option = False 
    elif cert_path:
        print(f"⚠️ Certificate path configured but file missing: {cert_path}")

    # 2. Prepara i kwargs (SENZA 'verify' e SENZA 'timeout', li mettiamo nel Client)
    request_kwargs = {
        "method": request.method,
        "url": internal_url,
        "headers": headers,
        "params": request.query_params,
    }

    # 3. Gestione Body
    if body_data is not None:
        if is_json:
            request_kwargs['json'] = body_data
        else:
            request_kwargs['data'] = body_data
    else:
        request_kwargs['content'] = None

    # 4. ESECUZIONE RICHIESTA
    # Creiamo un client "usa e getta" configurato specificamente per QUESTO certificato
    try:
        async with httpx.AsyncClient(verify=verify_option, timeout=10.0) as client:
            response = await client.request(**request_kwargs)
            
        # Controllo errori HTTP (4xx, 5xx del servizio target)
        response.raise_for_status()
        
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=response.headers
        )

    # Gestione errori di connessione / SSL
    except httpx.ConnectError as e:
         print(f"❌ Connection/SSL Error contacting {internal_url}: {e}")
         raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"SSL Handshake failed or host unreachable: {str(e)}"
        )
    except httpx.HTTPStatusError as e:
        # Se il microservizio risponde con un errore (es. 400 o 500), lo inoltriamo
        return Response(
            content=e.response.content,
            status_code=e.response.status_code,
            headers=e.response.headers
        )
    except httpx.RequestError as e:
        # Altri errori generici di httpx
        print(f"Generic Request Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Target service not reachable"
        )