# backend/main.py

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field # Importato Field per i commenti esplicativi
from pymongo import MongoClient
from os import environ
from bson import ObjectId
from datetime import datetime, timedelta
from typing import Optional, List 
import secrets 

# Librerie JWT e Hashing
from jose import JWTError, jwt
from passlib.context import CryptContext

# --- CONFIGURAZIONE DATABASE E SICUREZZA OMITTED FOR BREVITY ---

# DB Name deve corrispondere a MONGO_INITDB_DATABASE nel docker-compose.yml
DB_NAME = "user_auth_db" 

# URI di default con credenziali di test per esecuzione locale
DEFAULT_MONGO_URI = f"mongodb://user_admin:secure_password_user@localhost:27017/{DB_NAME}?authSource=admin"

# Legge l'URI dall'ambiente
MONGO_URI = environ.get("MONGO_URI", DEFAULT_MONGO_URI) 

# Configurazione JWT (letto dalle variabili d'ambiente)
SECRET_KEY = environ.get("SECRET_KEY", "chiave_di_default_molto_debole")
ALGORITHM = environ.get("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
RESET_TOKEN_EXPIRE_MINUTES = 60 
VERIFICATION_TOKEN_EXPIRE_MINUTES = 120 

# Inizializzazione della connessione al DB OMITTED FOR BREVITY

try:
    client = MongoClient(MONGO_URI)
    db = client.get_database(DB_NAME) 
    
    ITEMS_COLLECTION = db["elementi"] 
    USERS_COLLECTION = db["utenti"] 
    
    client.server_info() 

    print(f"Connesso con successo al DB: {DB_NAME}")
except Exception as e:
    print(f"ERRORE CRITICO di connessione a MongoDB: {e}")
    raise ConnectionError(f"Impossibile connettersi a MongoDB: {e}")

# Contesto per l'hashing delle password
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Inizializzazione dell'app FastAPI
app = FastAPI(
    title="Microservizio Utenti e Autenticazione (Auth)", 
    description="Questo servizio gestisce la **registrazione**, il **login** (JWT), la **verifica email**, il **reset della password** e le operazioni protette (CRUD su elementi).",
    version="1.0.0"
)

# --- MODELLI PYDANTIC (Commentati per OpenAPI) ---

class Item(BaseModel):
    """Schema per la gestione di un elemento generico."""
    # Aggiunge un esempio e una descrizione al campo ID per la documentazione
    id: Optional[str] = Field(None, description="L'ID univoco di MongoDB dell'elemento.")
    nome: str = Field(..., description="Il nome descrittivo dell'elemento.")
    valore: int = Field(..., description="Un valore numerico associato all'elemento.")

class UsernameList(BaseModel):
    usernames: List[str] = Field(..., description="Lista di nomi utente.")

class UserIdList(BaseModel):
    user_ids: List[str] = Field(..., description="Lista di ID utente.")

class UserBase(BaseModel):
    """Schema base contenente solo il nome utente."""
    username: str = Field(..., description="Nome utente univoco.")

class UserCreate(UserBase):
    """Schema usato per la registrazione di un nuovo utente."""
    password: str = Field(..., description="La password in chiaro fornita dall'utente.")
    email: str = Field(..., description="L'indirizzo email dell'utente (usato per la verifica).")

class UserLogin(UserBase):
    """Schema usato per il login dell'utente."""
    password: str = Field(..., description="La password in chiaro fornita dall'utente.")

class UserInDB(UserBase):
    """Schema interno usato per la manipolazione dei dati utente a livello di database."""
    hashed_password: str
    email: str 
    is_verified: Optional[bool] = False
    role: Optional[str] = "user"
    id: Optional[str] = None

class UserOut(UserBase):
    """Schema per l'output di informazioni utente, specialmente per gli amministratori."""
    id: Optional[str] = Field(None, description="ID univoco dell'utente nel database.")
    email: str
    is_verified: bool = Field(..., description="Stato di verifica dell'account via email.")
    role: str = Field(..., description="Ruolo dell'utente (e.g., 'user', 'admin').")
    hashed_password: str = Field(..., description="L'hash della password (visibile solo agli admin).")
    
class UserOutPublic(BaseModel):
    """Schema per l'output pubblico delle informazioni utente."""
    # Aggiunto id per completezza
    id: str = Field(..., description="ID univoco dell'utente.") 
    username: str = Field(..., description="Nome utente.")

class Token(BaseModel):
    """Schema di risposta per il login e la generazione del token."""
    access_token: str = Field(..., description="Il token JWT di accesso.")
    token_type: str = Field("bearer", description="Tipo di schema di autenticazione (Bearer).")

class TokenData(BaseModel):
    """Schema interno per i dati decodificati dal token JWT."""
    username: Optional[str] = None

class PasswordResetRequest(BaseModel):
    """Richiesta per avviare il processo di reset della password."""
    username: str

class PasswordResetConfirm(BaseModel):
    """Conferma del reset della password con token e nuova password."""
    token: str = Field(..., description="Token univoco ricevuto via email per il reset.")
    new_password: str = Field(..., description="La nuova password in chiaro.")

class EmailVerification(BaseModel): 
    """Conferma della verifica dell'email tramite token."""
    token: str = Field(..., description="Token univoco ricevuto via email per la verifica.")

# --- FUNZIONI DI SICUREZZA E AUTENTICAZIONE OMITTED FOR BREVITY ---

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

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

def authenticate_user(username: str, password: str):
    user = get_user(username)
    if not user:
        return False
    
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account non verificato. Controlla la tua email."
        )
    
    if not verify_password(password, user.hashed_password):
        return False
    return user

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenziali non valide",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # In get_current_user:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")  # <--- CERCA "sub"!
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
        
    user = get_user(token_data.username)
    if user is None:
        raise credentials_exception
        
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account non verificato. Token non utilizzabile."
        )
        
    return user

# --- ENDPOINT DI AUTENTICAZIONE E UTENTI (Raggruppati con Tags) ---
@app.get(
    "/getidfromusernamelist", 
    status_code=status.HTTP_200_OK,
    tags=["Autenticazione e Utenti"],
    summary="Da l'id dallo username"
)
def idfromusername(user_credentials: UsernameList):
    """
    Endpoint per ottenere gli ID utente dati una lista di nomi utente.
    Restituisce una mappatura di username a ID.
    """
    result = {}
    for username in user_credentials.usernames:
        user = get_user(username)
        if user:
            result[username] = user.id
        else:
            result[username] = None
    return result

@app.get(
    "/getusernamefromidlist/{user_id}",
    status_code=status.HTTP_200_OK,
    tags=["Autenticazione e Utenti"],
    summary="Da lo username dall'id"
)
def usernamefromid(user_ids: UserIdList):
    """
    Endpoint per ottenere i nomi utente dati una lista di ID utente.
    Restituisce una mappatura di ID a username.
    """
    result = {}
    for user_id in user_ids.user_ids:
        user_doc = USERS_COLLECTION.find_one({"_id": ObjectId(user_id)})
        if user_doc:
            result[user_id] = user_doc["username"]
        else:
            result[user_id] = None
    return result

@app.post(
    "/utenti/registrati", 
    status_code=status.HTTP_201_CREATED,
    tags=["Autenticazione e Utenti"], # Tag per raggruppare nella documentazione
    summary="Registrazione di un nuovo utente" # Titolo più conciso
)
def register_user(user_in: UserCreate):
    """
    Registra un nuovo utente nel sistema. 
    
    L'utente viene creato con `is_verified: False`. Viene generato e simulato l'invio 
    di un token di verifica all'email per l'attivazione dell'account.
    
    **ATTENZIONE**: Se l'username è 'admin', il ruolo viene assegnato a 'admin' per scopi di test.
    """
    # 1. Controllo unicita' username
    if get_user(user_in.username):
        raise HTTPException(status_code=400, detail="Username già registrato")
        
    # 2. Controllo unicita' email
    if USERS_COLLECTION.find_one({"email": user_in.email}):
        raise HTTPException(status_code=400, detail="Email già registrata")
        
    hashed_password = get_password_hash(user_in.password)
    
    user_data = {
        "username": user_in.username,
        "email": user_in.email, 
        "hashed_password": hashed_password,
        "is_verified": True, 
        "role": "admin" if user_in.username == "admin" else "user" 
    }
    
    USERS_COLLECTION.insert_one(user_data)
    userid= str(user_data.get("_id"))
    
    
    return {
        "message": "Registrazione avvenuta. Controlla la tua email per il link di verifica.", 
        "username": user_in.username,
        "token_for_testing_only": create_access_token(data={"username": user_in.username, "id": userid})
    }



@app.post(
    "/login", 
    status_code=status.HTTP_200_OK,
    tags=["Autenticazione e Utenti"],
    summary="Login semplificato (JSON) e generazione JWT"
)
def simple_login(user_credentials: UserLogin):
    """
    Endpoint di login alternativo che accetta le credenziali in formato JSON. 
    
    Restituisce un messaggio di successo e il token in caso di autenticazione riuscita.
    """
    try:
        user = authenticate_user(user_credentials.username, user_credentials.password)
    except HTTPException as e:
        raise e
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nome utente o password non validi",
        )
    
    access_token = create_access_token(
        data={"username": user.username, "id": user.id}
    )

    return {
        "message": "Login avvenuto con successo", 
        "token": access_token,
        "token_type": "bearer"
    }





# Nel backend/main.py del tuo user-manager:

class UserInternalOut(BaseModel): # Nuovo schema per i servizi interni
    id: str = Field(..., description="ID univoco dell'utente.")
    username: str = Field(..., description="Nome utente.")

@app.post(
    "/utenti/validate-token", 
    response_model=UserInternalOut,
    tags=["Servizi Interni"],
    summary="[INTERNAL] Convalida un token JWT e restituisce i dati utente."
)
def validate_token(token_data: Token):
    """
    Endpoint utilizzato da altri microservizi per inviare un token JWT 
    e ottenere l'ID e il ruolo dell'utente se il token è valido.
    """
    token_str = token_data.access_token

    try:
        # 1. Decodifica e verifica del token con la SECRET_KEY
        payload = jwt.decode(token_str, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("username")
        
        if username is None:
            raise HTTPException(status_code=401, detail="Token non contiene un 'username' valido.")
        
    except JWTError:
        # Cattura JWTError (firma non valida, scadenza, ecc.)
        raise HTTPException(status_code=401, detail="Token JWT non valido o scaduto.")
        
    # 2. Recupero utente dal DB per verifica aggiuntiva
    user = get_user(username)
    if user is None:
        raise HTTPException(status_code=404, detail="Utente associato al token non trovato.")
    
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Account non verificato.")
        
    # 3. Restituisce i dati richiesti al Client Service
    return UserInternalOut(
        id=payload.get("id"),
        username=user.username,
    )



# --- ENDPOINT DI DEBUG E AMMINISTRAZIONE (Raggruppati con Tags) ---

@app.get(
    "/utenti/dev-all-users", 
    response_model=List[UserOut],
    tags=["Amministrazione (Debug)"], # Nuovo tag per debug/amministrazione
    summary="[DEBUG] Ottieni tutti gli utenti (incluso hash password)"
)
def get_all_users_for_devs():
    """
    **ATTENZIONE**: Endpoint di **debug/amministrazione** non protetto. 
    Restituisce **tutti** i dati utente, inclusi gli hash delle password. 
    Da rimuovere in produzione!
    """
    users_list: List[UserOut] = []
    
    for user_doc in USERS_COLLECTION.find():
        users_list.append(UserOut(
            id=str(user_doc["_id"]),
            username=user_doc["username"],
            email=user_doc.get("email", "EMAIL_MISSING"),
            is_verified=user_doc.get("is_verified", False),
            role=user_doc.get("role", "user"),
            hashed_password=user_doc.get("hashed_password", "HASH_MISSING")
        ))
        
    return users_list

@app.delete(
    "/utenti/admin-clear-users", 
    status_code=status.HTTP_200_OK,
    tags=["Amministrazione (Protetto)"], # Nuovo tag per operazioni admin protette
    summary="[ADMIN] Cancella tutti gli utenti non-admin"
)
def clear_all_users_except_admin(current_user: UserInDB = Depends(get_current_user)):
    """
    **ATTENZIONE**: Endpoint distruttivo. 
    Cancella dal database **tutti** gli account il cui ruolo **NON** è 'admin'. 
    
    **Richiede** un token JWT valido con ruolo `admin`.
    """
    # 1. Controllo del ruolo
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accesso negato. Solo gli amministratori possono eseguire questa operazione."
        )

    # 2. Cancellazione di tutti gli utenti il cui ruolo NON è 'admin'
    try:
        result = USERS_COLLECTION.delete_many({"role": {"$ne": "admin"}})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante la cancellazione degli utenti: {e}")

    return {
        "message": f"Cancellati con successo {result.deleted_count} utenti. L'utente admin ('{current_user.username}') e gli altri admin non sono stati rimossi.",
        "deleted_count": result.deleted_count
    }

@app.get(
    "/utenti/admin-all-users", 
    response_model=List[UserOut],
    tags=["Amministrazione (Protetto)"],
    summary="[ADMIN] Ottieni tutti gli utenti (incluso hash password) con protezione"
)
def get_all_users_for_admin(current_user: UserInDB = Depends(get_current_user)):
    """
    Restituisce tutti gli utenti nel DB, inclusi i dati sensibili. 
    
    **Richiede** un token JWT valido con ruolo `admin`.
    """
    # Controllo del ruolo
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accesso negato. Solo gli amministratori possono visualizzare tutti gli utenti."
        )

    users_list: List[UserOut] = []
    
    for user_doc in USERS_COLLECTION.find():
        users_list.append(UserOut(
            id=str(user_doc["_id"]),
            username=user_doc["username"],
            email=user_doc.get("email", "EMAIL_MISSING"), 
            is_verified=user_doc.get("is_verified", False),
            role=user_doc.get("role", "user"),
            hashed_password=user_doc.get("hashed_password", "HASH_MISSING")
        ))
        
    return users_list

# --- ENDPOINT PROTETTI (Richiedono JWT) (Raggruppati con Tags) ---

@app.post(
    "/elementi/", 
    response_model=Item, 
    status_code=201,
    tags=["Operazioni Protette (Elementi)"], # Tag per operazioni CRUD protette
    summary="Crea un nuovo elemento"
)
def crea_elemento(item: Item, current_user: UserInDB = Depends(get_current_user)):
    """
    Crea un nuovo elemento nel database e lo associa all'utente autenticato.
    
    **Richiede** un token JWT valido.
    """
    nuovo_elemento = item.model_dump(exclude_unset=True, exclude={'id'})
    nuovo_elemento['owner'] = current_user.username 

    try:
        risultato = ITEMS_COLLECTION.insert_one(nuovo_elemento)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore di inserimento in MongoDB: {e}")
    
    item.id = str(risultato.inserted_id)
    return item

@app.get(
    "/elementi/", 
    response_model=List[Item],
    tags=["Operazioni Protette (Elementi)"],
    summary="Ottieni tutti gli elementi dell'utente corrente"
)
def ottieni_tutti_gli_elementi(current_user: UserInDB = Depends(get_current_user)):
    """
    Restituisce una lista di tutti gli elementi **creati dall'utente corrente**.
    
    **Richiede** un token JWT valido.
    """
    items = []
    for elemento in ITEMS_COLLECTION.find({"owner": current_user.username}): 
        items.append(Item(
            id=str(elemento['_id']),
            nome=elemento['nome'],
            valore=elemento['valore']
        ))
        
    return items

@app.get(
    "/elementi/{item_id}", 
    response_model=Item,
    tags=["Operazioni Protette (Elementi)"],
    summary="Ottieni un elemento per ID"
)
def ottieni_elemento_per_id(item_id: str):
    """
    Restituisce un elemento specifico tramite il suo ID (ObjectId) di MongoDB.
    
    **Nota**: Questo endpoint non è protetto da token, ma la gestione della proprietà 
    dovrebbe essere implementata per prevenire l'accesso non autorizzato ai dati.
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