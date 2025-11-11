# backend/main.py

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

# --- CONFIGURAZIONE DATABASE E SICUREZZA ---

# Legge l'URI dall'ambiente (definito in docker-compose.yml)
MONGO_URI = environ.get("MONGO_URI", "mongodb://localhost:27017/") 
DB_NAME = "user_data_db" 

# Configurazione JWT (letto dalle variabili d'ambiente)
SECRET_KEY = environ.get("SECRET_KEY", "chiave_di_default_molto_debole")
ALGORITHM = environ.get("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

# Inizializzazione della connessione al DB
try:
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    ITEMS_COLLECTION = db["elementi"] 
    USERS_COLLECTION = db["utenti"] # NUOVA COLLECTION PER GLI UTENTI
    
    print(f"Connesso con successo al DB: {DB_NAME}")
except Exception as e:
    print(f"ERRORE CRITICO di connessione a MongoDB: {e}")
    raise ConnectionError(f"Impossibile connettersi a MongoDB: {e}")

# Contesto per l'hashing delle password
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Inizializzazione dell'app FastAPI
app = FastAPI(
    title="API Backend per Elementi",
    description="Gestisce l'inserimento e la lettura di elementi nel database MongoDB.",
)

# --- MODELLI PYDANTIC ---

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

# --- ENDPOINT DI AUTENTICAZIONE E UTENTI ---

@app.post("/utenti/registrati", status_code=status.HTTP_201_CREATED)
def register_user(user_in: UserCreate):
    """
    Registra un nuovo utente.
    """
    if get_user(user_in.username):
        raise HTTPException(status_code=400, detail="Username già registrato")
        
    hashed_password = get_password_hash(user_in.password)
    
    user_data = {
        "username": user_in.username,
        "hashed_password": hashed_password
    }
    USERS_COLLECTION.insert_one(user_data)
    
    return {"message": "Utente registrato con successo", "username": user_in.username}

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    """
    Endpoint di login standard (OAuth2): genera un token JWT se le credenziali sono valide.
    """
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nome utente o password non validi",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Crea il token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/login", status_code=status.HTTP_200_OK)
def simple_login(user_credentials: UserCreate):
    """
    Endpoint di login semplificato: verifica le credenziali. 
    Restituisce un messaggio di successo e il token in caso di autenticazione riuscita.
    """
    user = authenticate_user(user_credentials.username, user_credentials.password)
    if not user:
        # Solleva 401 Unauthorized se le credenziali non sono valide
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nome utente o password non validi",
        )
    
    # Se l'autenticazione riesce, genera il token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    # Restituisce un messaggio di successo e il token
    return {
        "message": "Login avvenuto con successo", 
        "token": access_token,
        "token_type": "bearer"
    }


# --- ENDPOINT PROTETTI (Richiedono JWT) ---

# Aggiungiamo la dipendenza 'get_current_user' per proteggere l'endpoint.
@app.post("/elementi/", response_model=Item, status_code=201)
def crea_elemento(item: Item, current_user: Annotated[UserInDB, Depends(get_current_user)]):
    """
    Crea un nuovo elemento e lo inserisce nella collection 'elementi'.
    (Richiede un token JWT valido)
    """
    # Converte il modello Pydantic in un dizionario per l'inserimento
    nuovo_elemento = item.model_dump(exclude_unset=True, exclude={'id'})
    
    # Aggiunge l'utente che ha creato l'elemento (buona pratica di audit)
    nuovo_elemento['owner'] = current_user.username 

    try:
        risultato = ITEMS_COLLECTION.insert_one(nuovo_elemento)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore di inserimento in MongoDB: {e}")
    
    item.id = str(risultato.inserted_id)
    return item

@app.get("/elementi/", response_model=list[Item])
def ottieni_tutti_gli_elementi(current_user: Annotated[UserInDB, Depends(get_current_user)]):
    """
    Restituisce una lista di tutti gli elementi creati dall'utente corrente.
    (Richiede un token JWT valido)
    """
    items = []
    # Filtra solo gli elementi creati dall'utente corrente
    for elemento in ITEMS_COLLECTION.find({"owner": current_user.username}): 
        items.append(Item(
            id=str(elemento['_id']),
            nome=elemento['nome'],
            valore=elemento['valore']
        ))
        
    return items

# L'endpoint GET per ID e la sua logica di errore rimangono utili e non richiedono l'utente per questa implementazione base
@app.get("/elementi/{item_id}", response_model=Item)
def ottieni_elemento_per_id(item_id: str):
    """
    Restituisce un elemento specifico tramite il suo ID (ObjectId) di MongoDB.
    """
    try:
        elemento = ITEMS_COLLECTION.find_one({"_id": ObjectId(item_id)})
        
        if elemento:
            return Item(
                id=str(elemento['_id']),
                nome=elemento['nome'],
                valore=elemento['valore']
            )
            
        raise HTTPException(status_code=404, detail="Elemento non trovato")
        
    except Exception:
        raise HTTPException(status_code=400, detail="ID non valido")