from fastapi import Depends, Header, HTTPException, status
import httpx
from pydantic import BaseModel

AUTH_SERVICE_URL = "https://user-manager:5004" 

class UserValidationResponse(BaseModel):
    id: str
    username: str


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
        


async def login(
    username: str,
    password: str
):
    """
    Function to authenticate user via Auth Service using username and password.
    """

    async with httpx.AsyncClient(verify=False) as client:
        try:
            response = await client.post(
                f"{AUTH_SERVICE_URL}/users/login",
                json={"username": username, "password": password}
            )
            
            if response.status_code == status.HTTP_401_UNAUTHORIZED:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password.")
            
            if response.status_code != status.HTTP_200_OK:
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Authentication service error.")

            token_str = response.json().get("access_token")    
            return token_str
            
        except httpx.RequestError:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Auth Service is unavailable.")
        


async def register_user(
    username: str,
    email: str,
    password: str
):
    """
    Function to register a new user via Auth Service.
    """

    async with httpx.AsyncClient(verify=False) as client:
        try:
            response = await client.post(
                f"{AUTH_SERVICE_URL}/users/register",
                json={"username": username, "email": email, "password": password}
            )
            
            if response.status_code == status.HTTP_400_BAD_REQUEST:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username or email already exists.")
            
            if response.status_code != status.HTTP_201_CREATED:
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Authentication service error.")
            token_str = response.json().get("access_token")
            return token_str
            
        except httpx.RequestError:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Auth Service is unavailable.")