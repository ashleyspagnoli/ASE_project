# --- MODELLI PYDANTIC ---


from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from pymongo import MongoClient
from os import environ
from bson import ObjectId
from datetime import datetime, timedelta
from typing import Annotated

# Librerie JWT e Hashing
from jose import JWTError, jwt
from passlib.context import CryptContext
class Item(BaseModel):

    id: str | None = None
    nome: str
    valore: int

class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str

class UserInDB(UserBase):
    hashed_password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None

# --- FUNZIONI DI SICUREZZA (PASSWORD HASHING) ---

def verify_password(plain_password, hashed_password):
    """Verifica se la password in chiaro corrisponde all'hash memorizzato."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    """Restituisce l'hash bcrypt di una password in chiaro."""
    return pwd_context.hash(password)

# --- FUNZIONI JWT (TOKEN GENERATION E DECODING) ---

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    """Crea un token JWT."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# --- FUNZIONI DI AUTENTICAZIONE UTENTE ---

def get_user(username: str):
    """Ottiene l'utente dal database."""
    user_doc = USERS_COLLECTION.find_one({"username": username})
    if user_doc:
        # Crea un modello UserInDB (l'ID non serve qui)
        return UserInDB(username=user_doc['username'], hashed_password=user_doc['hashed_password'])
    return None

def authenticate_user(username: str, password: str):
    """Autentica l'utente tramite username e password."""
    user = get_user(username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    """Decodifica e convalida il token JWT."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenziali non valide",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Decodifica il token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
        
    user = get_user(token_data.username)
    if user is None:
        raise credentials_exception
    return user