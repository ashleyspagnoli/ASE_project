# user_editor_service.py (AGGIORNATO CON SANITIZZAZIONE)

from fastapi import Depends, HTTPException, status, FastAPI
# 🟢 AGGIUNTA: field_validator per Pydantic V2 (o 'validator' se usi V1)
from pydantic import BaseModel, Field, field_validator 
from typing import Optional
import requests
from os import environ
from fastapi.security import OAuth2PasswordBearer
import bleach # 🟢 AGGIUNTA: Libreria per sanitizzazione

# =================================================================
# FUNZIONE DI UTILITÀ PER SANITIZZAZIONE
# =================================================================
def sanitize_text(text: str) -> str:
    """
    Rimuove tag HTML potenzialmente pericolosi e spazi bianchi superflui.
    """
    if not text:
        return text
    # Rimuove tutti i tag HTML (tags=[]) e fa strip degli spazi
    clean_text = bleach.clean(text, tags=[], strip=True)
    return clean_text.strip()

# =================================================================

class UserInDB(BaseModel):
    """Schema interno che rappresenta l'utente recuperato dal DB."""
    id: str = Field(alias="_id")
    username: str = Field(alias="username")


AUTH_SERVICE_BASE_URL = environ.get("AUTH_SERVICE_URL", "https://user-manager:5000") 
AUTH_SERVICE_CERT_PATH = "/run/secrets/user_manager_cert"


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="https://localhost:5004/token") 

def get_raw_token(token: str = Depends(oauth2_scheme)) -> str:
    return token

def get_current_user(token: str = Depends(oauth2_scheme)) -> UserInDB:
    """
    Verifica la validità del token JWT chiamando il Microservizio di Autenticazione 
    """
    
    internal_endpoint = f"{AUTH_SERVICE_BASE_URL}/users/validate-token"
    print(f"Calling Auth Service at {internal_endpoint} to validate token.")
    print(f"Using token: {token}")
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(internal_endpoint, headers=headers, verify=AUTH_SERVICE_CERT_PATH)
        print(f"Auth Service response status: {response.status_code}")  
        response.raise_for_status() 

        user_data = response.json()
        
        print(f"User data received from Auth Service: {user_data}")
        print(user_data) 
        return (user_data) 

    except requests.exceptions.HTTPError as e:
        if response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials (Token invalid or expired)",
                headers={"WWW-Authenticate": "Bearer"},
            )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail=f"Auth Service error: {e.response.text}"
        )
    except requests.exceptions.ConnectionError as e:
        print(f"DEBUG SSL ERROR: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail="Cannot connect to Auth Service"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Internal error processing user data: {e}"
        )

# =================================================================
# 1. MODELLI PYDANTIC CON SANITIZZAZIONE
# =================================================================

class UsernameUpdate(BaseModel):
    new_username: str = Field(..., min_length=1)

    # 🟢 AGGIUNTA SANITIZZAZIONE: Pulisce lo username da HTML e spazi
    @field_validator('new_username')
    @classmethod
    def sanitize_username(cls, v):
        return sanitize_text(v)

class PasswordUpdate(BaseModel):
    old_password: str = Field(..., description="Password attuale per verifica")
    new_password: str = Field(..., min_length=3)
    
    # ⚠️ NOTA BENE: Le password NON vanno sanitizzate con bleach perché caratteri 
    # speciali (come <, >, &) sono validi in una password sicura.
    

class UpdateEmail(BaseModel):
    old_email: str = Field(..., min_length=1)
    new_email: str = Field(..., min_length=1)

    # 🟢 AGGIUNTA SANITIZZAZIONE: Pulisce le email
    @field_validator('old_email', 'new_email')
    @classmethod
    def sanitize_email(cls, v):
        return sanitize_text(v)

# =================================================================
# 2. INIZIALIZZAZIONE FASTAPI E ENDPOINT DI MODIFICA
# =================================================================

app = FastAPI(
    title="User Editor Microservice", 
    description="Handles changes in user attributes via internal API.",
    version="1.0.0"
)

# Funzione helper per l'aggiornamento interno

class UserUpdateInternal(BaseModel):
    """Payload interno per aggiornare solo i campi necessari."""
    username: Optional[str] = None
    old_email: Optional[str] = None
    new_email: Optional[str] = None
    new_password: Optional[str] = None 
    old_password: Optional[str] = None 


def _call_auth_service_update(payload: UserUpdateInternal, token: str):
    """Invia la richiesta di aggiornamento al Microservizio Auth."""
    
    headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            }


    if payload.username:
        url=f"{AUTH_SERVICE_BASE_URL}/internal/update-username"
        print("Username da cambiare")
    if payload.new_password:
        url=f"{AUTH_SERVICE_BASE_URL}/internal/update-password"
        print("Password da cambiare")
    if payload.new_email:
        url=f"{AUTH_SERVICE_BASE_URL}/internal/update-email"
        print("Email da cambiare")
        
    try:
        response = requests.post(
            url,
            json=payload.model_dump(exclude_none=True),
            headers=headers,
            verify=AUTH_SERVICE_CERT_PATH
            
        )
        response.raise_for_status() 
        print("Dopo richiesta")
        print(response.json())
        return response.json()
    except requests.exceptions.HTTPError as e:
        if response.status_code == status.HTTP_400_BAD_REQUEST:
            detail = response.json().get("detail", "Dato non valido (es. username/email già in uso).")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
        
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail=f"Errore di comunicazione con il servizio Auth: {e}"
        )
    except requests.exceptions.ConnectionError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail="Impossibile connettersi al servizio Auth."
        )


### Modifica Username
@app.patch(
    "/change-username",
    status_code=status.HTTP_200_OK,
    tags=["User Editor"],
    summary="Change username"
)
def change_username(
    update_data: UsernameUpdate,
    current_user: UserInDB = Depends(get_current_user),
    token: str = Depends(get_raw_token),
):
    print("Ciao")
    print(current_user)
    old_username_clear = current_user["username"]
    new_username_clear = update_data.new_username
    
    if old_username_clear == new_username_clear:
        return {"message": "Il nuovo username è identico a quello attuale."}
    
    payload=UserUpdateInternal(
        username=new_username_clear
    )
    
    _call_auth_service_update(
        payload=payload,
        token=token
    )
    
    return {
        "message": "Username changed successfully. Please use the new token for future requests.",
        "old_username": old_username_clear,
        "new_username": new_username_clear,
    }


### Modifica Password
@app.patch(
    "/change-password",
    status_code=status.HTTP_200_OK,
    tags=["User Editor"],
    summary="Change user password"
)
def change_password(
        update_data: PasswordUpdate,
        current_user: UserInDB = Depends(get_current_user),
        token: str = Depends(get_raw_token)
        ):
        
        old_password = update_data.old_password
        new_password = update_data.new_password
        
        payload=UserUpdateInternal(
            new_password=new_password,
            old_password=old_password
        )
        _call_auth_service_update(
            payload=payload,
            token=token
        )
        
        return {"message": "Password changed successfully."}


### Modifica Email
@app.patch(
    "/change-email",
    status_code=status.HTTP_200_OK,
    tags=["User Editor"],
    summary="Change user email"
)
def change_password(
        update_data: UpdateEmail,
        current_user: UserInDB = Depends(get_current_user),
        token: str = Depends(get_raw_token)
        ):

        old_email = update_data.old_email
        new_email = update_data.new_email

        payload=UserUpdateInternal(
            old_email=old_email,
            new_email=new_email
        )
        _call_auth_service_update(
            payload=payload,
            token=token
        )
        
        return {"message": "Email changed successfully."}

### Modifica Email
@app.get(
    "/view-data",
    status_code=status.HTTP_200_OK,
    tags=["User Editor"],
    summary="See user email and username"
)
def view_data(
    current_user: UserInDB = Depends(get_current_user),
    token: str = Depends(get_raw_token)
    ):
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            }

        try:
            url=f"{AUTH_SERVICE_BASE_URL}/users/my-username-my-email"
            response = requests.get(
                url,
                headers=headers,
                verify=AUTH_SERVICE_CERT_PATH
            )
            response.raise_for_status() 

        except requests.exceptions.HTTPError as e:
            if response.status_code == status.HTTP_400_BAD_REQUEST:
                detail = response.json().get("detail", "Dato non valido (es. username/email già in uso).")
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
            
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
                detail=f"Errore di comunicazione con il servizio Auth: {e}"
            )
        
        return {
            "username": current_user["username"],
            "email": response.json().get("email")
        }