# profile/main.py

from fastapi import FastAPI, HTTPException, Depends, status, Body
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field
from pymongo import MongoClient
from os import environ
from datetime import datetime, timedelta
from typing import Optional
from passlib.context import CryptContext
from jose import JWTError, jwt

# --- CONFIGURAZIONE E SICUREZZA (COPIA DAL SERVIZIO AUTH) ---

DB_NAME = "user_auth_db" 
MONGO_URI = environ.get("MONGO_URI", 
    f"mongodb://user_admin:secure_password_user@localhost:27017/{DB_NAME}?authSource=admin"
) 
SECRET_KEY = environ.get("SECRET_KEY", "chiave_di_default_molto_debole")
ALGORITHM = environ.get("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

# Connessione DB
try:
    client = MongoClient(MONGO_URI)
    db = client.get_database(DB_NAME) 
    USERS_COLLECTION = db["utenti"] 
    client.server_info() 
    print(f"Connesso (Profile Manager) al DB: {DB_NAME}")
except Exception as e:
    print(f"ERRORE CRITICO di connessione a MongoDB: {e}")
    raise ConnectionError(f"Impossibile connettersi a MongoDB: {e}")

# Contesto per l'hashing (deve essere identico al servizio Auth)
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- MODELLI DI DATI (Adattati) ---

class UserInDB(BaseModel):
    # Questi campi sono minimi per l'autenticazione/autorizzazione
    username: str
    email: str 
    hashed_password: str
    is_verified: Optional[bool] = False
    role: Optional[str] = "user"
    id: Optional[str] = None

class UserUpdate(BaseModel):
    """Schema per l'aggiornamento parziale del profilo."""
    # Rendi tutti i campi opzionali (PATCH)
    username: Optional[str] = Field(None, description="Nuovo nome utente.")
    email: Optional[str] = Field(None, description="Nuovo indirizzo email.")
    current_password: Optional[str] = Field(None, description="Password attuale (richiesta se si aggiorna la password).")
    new_password: Optional[str] = Field(None, description="Nuova password da impostare.")

class StatusMessage(BaseModel):
    message: str

# --- FUNZIONI DI SICUREZZA (Adattate) ---

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)
    
def get_user(username: str):
    user_doc = USERS_COLLECTION.find_one({"username": username})
    if user_doc:
        return UserInDB(
            id=str(user_doc['_id']),
            username=user_doc['username'], 
            email=user_doc.get('email', f"{user_doc['username']}@fallback.com"), 
            hashed_password=user_doc['hashed_password'],
            is_verified=user_doc.get('is_verified', False), 
            role=user_doc.get('role', 'user')
        )
    return None
    
# Funzione per l'estrazione dell'utente corrente (Copia dal servizio Auth)
async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenziali non valide",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub") or payload.get("username") # Supporta sia 'sub' che 'username'
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    user = get_user(username)
    if user is None:
        raise credentials_exception
    # Non controlliamo is_verified qui se vogliamo permettere il cambio password/username anche se non verificato
    return user

# --- INIZIALIZZAZIONE FASTAPI ---

app = FastAPI(
    title="Microservizio Gestione Profilo Utente",
    description="Gestisce l'aggiornamento del profilo utente (password, username, email).",
    version="1.0.0"
)

# --- ENDPOINT DI AGGIORNAMENTO PROFILO ---

@app.patch(
    "/profilo/aggiorna", 
    response_model=StatusMessage,
    tags=["Gestione Profilo"],
    summary="Aggiorna username, email e/o password dell'utente corrente"
)
async def update_user_profile(
    updates: UserUpdate, 
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Permette all'utente corrente di aggiornare i propri dati.
    
    Richiede: Un token JWT valido.
    Logica:
    - Se si cambia la password, `current_password` e `new_password` sono obbligatori e la password attuale deve essere verificata.
    - Se si cambia l'username o l'email, la nuova risorsa deve essere univoca.
    """
    update_fields = {}

    # 1. LOGICA DI CAMBIO PASSWORD
    if updates.new_password:
        if not updates.current_password:
             raise HTTPException(status_code=400, detail="Per cambiare la password, è richiesta la password attuale.")

        # Verifica che la password attuale sia corretta
        if not verify_password(updates.current_password, current_user.hashed_password):
            raise HTTPException(status_code=401, detail="Password attuale non valida.")
            
        # Genera hash della nuova password
        update_fields["hashed_password"] = get_password_hash(updates.new_password)

    # 2. LOGICA DI CAMBIO USERNAME
    if updates.username and updates.username != current_user.username:
        # Verifica l'unicità del nuovo username
        if USERS_COLLECTION.find_one({"username": updates.username}):
            raise HTTPException(status_code=400, detail="Il nuovo username è già in uso.")
        update_fields["username"] = updates.username

    # 3. LOGICA DI CAMBIO EMAIL
    if updates.email and updates.email != current_user.email:
        # Verifica l'unicità della nuova email
        if USERS_COLLECTION.find_one({"email": updates.email}):
            raise HTTPException(status_code=400, detail="La nuova email è già in uso.")
        update_fields["email"] = updates.email
        # NOTA: In un'implementazione reale, l'utente dovrebbe essere reimpostato a is_verified=False

    if not update_fields:
        return StatusMessage(message="Nessun campo valido fornito per l'aggiornamento.")

    # 4. Esecuzione dell'aggiornamento nel DB
    try:
        # Usa l'ID utente per garantire l'aggiornamento del record corretto
        result = USERS_COLLECTION.update_one(
            {"username": current_user.username}, # Filtro sicuro tramite username del token
            {"$set": update_fields}
        )
    except Exception as e:
         raise HTTPException(status_code=500, detail=f"Errore DB durante l'aggiornamento: {e}")

    if result.modified_count == 0:
         # Può succedere se l'aggiornamento non cambia i dati, ma è un buon controllo
         return StatusMessage(message="Profilo aggiornato con successo (nessuna modifica effettiva dei dati).")
         
    return StatusMessage(message="Profilo aggiornato con successo. Potrebbe essere necessario effettuare nuovamente il login.")