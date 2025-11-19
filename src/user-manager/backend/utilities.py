from fastapi import Depends, Header, HTTPException, status
import httpx 

AUTH_SERVICE_URL = "https://user-manager:5004" 


async def get_current_user_from_auth_service(
    token_str: str 
):
    """
    Function to get current user info from Auth Service using the provided JWT token.
    """

    async with httpx.AsyncClient(verify=False) as client:
        try:
            # L'endpoint /validate-token si aspetta il token come query parameter
            response = await client.get(
                f"{AUTH_SERVICE_URL}/users/validate-token?token_str={token_str}"
            )
            
            # 2. Gestione degli errori
            if response.status_code == status.HTTP_401_UNAUTHORIZED:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalid or expired.")
            
            if response.status_code != status.HTTP_200_OK:
                # Gestisce 403, 404 o altri errori interni
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication service error.")
                
            # 3. Restituisci i dati utente validati (ID e Username)
            return response.json()
            
        except httpx.RequestError:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Auth Service is unavailable.")
        
