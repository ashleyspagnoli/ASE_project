import httpx
from fastapi import Request, HTTPException, status
from fastapi.responses import Response
from urllib.parse import urlparse

# Mapping of service hostnames to their certificate paths
SERVICE_CERTS = {
    "user-manager": "/run/secrets/user_manager_cert",
    "game_history": "/run/secrets/history_cert",
    "collection": "/run/secrets/collection_cert",
    "game_engine": "/run/secrets/game_engine_cert"
}

# Initialize the global client
# Note: In production, consider using a lifespan event in main.py to close this client cleanly
http_client = httpx.AsyncClient(timeout=10.0) 

async def forward_request(request: Request, internal_url: str, body_data: dict = None, is_json: bool = True) -> Response:
    """
    Funzione generica per inoltrare la richiesta.
    Accetta il body esplicito (body_data) se la rotta lo richiede (POST/PATCH).
    """
    
    # 1. Prepara e pulisce gli header
    headers = dict(request.headers)
    headers.pop('host', None)
    headers.pop('content-length', None) 

    # Determine the certificate to use based on the hostname
    parsed_url = urlparse(internal_url)
    hostname = parsed_url.hostname
    cert_path = SERVICE_CERTS.get(hostname)
    
    # Use the specific certificate if available, otherwise disable verification
    verify_ssl = cert_path if cert_path else False

    # 2. Imposta i parametri della richiesta httpx
    print(f"Forwarding request to {internal_url} with SSL verify: {verify_ssl}")
    request_kwargs = {
        "method": request.method,
        "url": internal_url,
        "headers": headers,
        "params": request.query_params,
        "timeout": 10.0,
    }
    
    # 3. Aggiunge il body
    if body_data is not None:
        if is_json:
            request_kwargs['json'] = body_data  
        else:
            request_kwargs['data'] = body_data 
    else:
        request_kwargs['content'] = None
    

    # 4. Inoltra la richiesta
    try:
        async with httpx.AsyncClient(verify=verify_ssl) as client:
            response = await client.request(**request_kwargs)
        response.raise_for_status() 
        
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=response.headers
        )

    except httpx.HTTPStatusError as e:
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