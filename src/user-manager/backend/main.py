# backend/main.py

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from pymongo import MongoClient
from os import environ
from bson import ObjectId
from datetime import datetime, timedelta
from typing import Optional, List 
import secrets # Importato per la generazione sicura del token

# Librerie JWT e Hashing
from jose import JWTError, jwt
from passlib.context import CryptContext

# --- CONFIGURAZIONE DATABASE E SICUREZZA ---

# DB Name deve corrispondere a MONGO_INITDB_DATABASE nel docker-compose.yml
DB_NAME = "user_auth_db" 

# URI di default con credenziali di test per esecuzione locale
# Aggiunto 'authSource=admin' per forzare PyMongo a usare il database 'admin'
# (dove l'utente root 'user_admin' è stato creato) per l'autenticazione.
DEFAULT_MONGO_URI = f"mongodb://user_admin:secure_password_user@localhost:27017/{DB_NAME}?authSource=admin"

# Legge l'URI dall'ambiente (se definito in docker-compose.yml)
MONGO_URI = environ.get("MONGO_URI", DEFAULT_MONGO_URI) 

# Configurazione JWT (letto dalle variabili d'ambiente)
SECRET_KEY = environ.get("SECRET_KEY", "chiave_di_default_molto_debole")
ALGORITHM = environ.get("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
RESET_TOKEN_EXPIRE_MINUTES = 60 # Scadenza del token di reset (1 ora)
VERIFICATION_TOKEN_EXPIRE_MINUTES = 120 # Scadenza del token di verifica (2 ore) # NUOVO

# Inizializzazione della connessione al DB
try:
    # PyMongo gestisce l'autenticazione tramite l'URI se presente
    client = MongoClient(MONGO_URI)
    # Se l'URI non specifica un DB, usiamo il DB_NAME definito
    db = client.get_database(DB_NAME) 
    
    # Notare: Questa collection 'elementi' è un residuo, in un'architettura 
    # a microservizi andrebbe solo nel servizio 'items-service'
    ITEMS_COLLECTION = db["elementi"] 
    USERS_COLLECTION = db["utenti"] # Collection principale per questo servizio
    
    # Test della connessione leggendo un documento fittizio
    client.server_info() 

    print(f"Connesso con successo al DB: {DB_NAME}")
except Exception as e:
    print(f"ERRORE CRITICO di connessione a MongoDB: {e}")
    # Solleviamo un errore che interrompe l'app se la connessione fallisce
    raise ConnectionError(f"Impossibile connettersi a MongoDB: {e}")

# Contesto per l'hashing delle password
# *** CAMBIATO DA BCRYPT A ARGON2 PER MAGGIORE COMPATIBILITÀ E SICUREZZA ***
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Inizializzazione dell'app FastAPI
app = FastAPI(
    # Titolo aggiornato per riflettere il ruolo di microservizio
    title="Microservizio Gestione Utenti (Auth)",
    description="Gestisce la registrazione, il login e la generazione di token JWT.",
)

# --- MODELLI PYDANTIC ---

class Item(BaseModel):
    id: Optional[str] = None
    nome: str
    valore: int

class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str
    email: str # CAMPO AGGIUNTO: Necessario per la verifica

class UserInDB(UserBase):
    # ATTENZIONE: email è ora un campo OBBLIGATORIO nel DB/modello.
    hashed_password: str
    email: str 
    is_verified: Optional[bool] = False # Default a False
    role: Optional[str] = "user" # Default a 'user'

class UserOut(UserBase):
    # NUOVO MODELLO: Usato per l'output dell'endpoint admin
    id: Optional[str] = None
    email: str
    is_verified: bool
    role: str
    # ATTENZIONE: Questo campo ESISTE nel DB ma viene ESPOSTO qui per l'admin.
    hashed_password: str
    
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class PasswordResetRequest(BaseModel):
    username: str

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

class EmailVerification(BaseModel): # NUOVO MODELLO
    token: str

# --- FUNZIONI DI SICUREZZA (PASSWORD HASHING) ---

def verify_password(plain_password, hashed_password):
    """Verifica se la password in chiaro corrisponde all'hash memorizzato."""
    # Argon2 gestisce tutte le lunghezze standard
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    """
    Restituisce l'hash Argon2 di una password in chiaro.
    Argon2 non ha la limitazione di 72 byte di Bcrypt.
    """
    return pwd_context.hash(password)

# --- FUNZIONI JWT (TOKEN GENERATION E DECODING) ---

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
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
    """
    Ottiene l'utente dal database.
    CORREZIONE: Passa tutti i campi necessari a UserInDB, inclusi i fallback.
    """
    user_doc = USERS_COLLECTION.find_one({"username": username})
    if user_doc:
        # Assicurati che tutti i campi obbligatori di UserInDB siano presenti,
        # usando un fallback se l'utente è stato creato prima delle modifiche dello schema.
        return UserInDB(
            username=user_doc['username'], 
            email=user_doc.get('email', f"{user_doc['username']}@fallback.com"), # FALLBACK RAFFORZATO
            hashed_password=user_doc['hashed_password'],
            is_verified=user_doc.get('is_verified', False), 
            role=user_doc.get('role', 'user')
        )
    return None

def authenticate_user(username: str, password: str):
    """Autentica l'utente tramite username e password."""
    user = get_user(username)
    if not user:
        return False
    
    # NUOVO CONTROLLO: Verifica che l'utente sia verificato via email
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account non verificato. Controlla la tua email."
        )
    
    if not verify_password(password, user.hashed_password):
        return False
    return user

# Sintassi di tipizzazione aggiornata per Python < 3.9
async def get_current_user(token: str = Depends(oauth2_scheme)):
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
        
    # NUOVO CONTROLLO: Verifica che l'utente sia verificato via email
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account non verificato. Token non utilizzabile."
        )
        
    return user

# --- FUNZIONI DI SUPPORTO PER TOKEN ---

def generate_verification_token(username: str) -> str:
    """Genera un token di verifica sicuro e lo memorizza nel DB con scadenza."""
    token = secrets.token_hex(32)
    expiry = datetime.utcnow() + timedelta(minutes=VERIFICATION_TOKEN_EXPIRE_MINUTES)

    USERS_COLLECTION.update_one(
        {"username": username},
        {"$set": {
            "verification_token": token,
            "verification_token_expiry": expiry
        }}
    )
    return token

def generate_reset_token(username: str) -> str:
    """Genera un token di reset sicuro e lo memorizza nel DB con scadenza."""
    # Genera un token alfanumerico sicuro di 32 byte (circa 64 caratteri esadecimali)
    token = secrets.token_hex(32)
    expiry = datetime.utcnow() + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)

    # Aggiorna il documento utente con il token e la scadenza
    USERS_COLLECTION.update_one(
        {"username": username},
        {"$set": {
            "reset_token": token,
            "reset_token_expiry": expiry
        }}
    )
    return token

# --- ENDPOINT DI AUTENTICAZIONE E UTENTI ---

@app.post("/utenti/registrati", status_code=status.HTTP_201_CREATED)
def register_user(user_in: UserCreate):
    """
    Registra un nuovo utente e avvia il processo di verifica email.
    """
    # 1. Controllo unicita' username
    if get_user(user_in.username):
        raise HTTPException(status_code=400, detail="Username già registrato")
        
    # 2. Controllo unicita' email
    if USERS_COLLECTION.find_one({"email": user_in.email}):
        raise HTTPException(status_code=400, detail="Email già registrata")
        
    # Chiama la funzione di hashing (ora usa Argon2)
    hashed_password = get_password_hash(user_in.password)
    
    # LOGICA DI INSERIMENTO POTENZIATA
    user_data = {
        "username": user_in.username,
        "email": user_in.email, 
        "hashed_password": hashed_password,
        "is_verified": False, # Inizia come NON verificato
        # Assegna il ruolo 'admin' se l'username è 'admin' (solo per test/simulazione)
        "role": "admin" if user_in.username == "admin" else "user" 
    }
    
    # Inserimento iniziale
    USERS_COLLECTION.insert_one(user_data)
    
    # 3. Generazione e invio (simulato) del token di verifica
    verification_token = generate_verification_token(user_in.username)
    
    # SIMULAZIONE EMAIL:
    print(f"Token di verifica generato per {user_in.email}: {verification_token}") # Log for testing
    
    return {
        "message": "Registrazione avvenuta. Controlla la tua email per il link di verifica.", 
        "username": user_in.username,
        # ATTENZIONE: Rimuovere questo campo in produzione! Espone il token!
        "token_for_testing_only": verification_token 
    }

@app.post("/utenti/verifica-email", status_code=status.HTTP_200_OK)
def verify_email_confirmation(data: EmailVerification):
    """
    Endpoint che verifica il token e attiva l'account.
    """
    # 1. Trova l'utente tramite il token e verifica che non sia scaduto
    user_doc = USERS_COLLECTION.find_one({
        "verification_token": data.token,
        # Il token deve essere maggiore del tempo attuale
        "verification_token_expiry": {"$gt": datetime.utcnow()} 
    })
    
    if not user_doc:
        raise HTTPException(status_code=400, detail="Token di verifica non valido o scaduto.")

    # 2. Aggiorna lo stato di verifica e consuma il token
    USERS_COLLECTION.update_one(
        {"_id": user_doc["_id"]},
        {"$set": {"is_verified": True},
         # Rimuovi i campi del token per invalidarlo dopo l'uso
         "$unset": {"verification_token": "", "verification_token_expiry": ""}}
    )
    
    return {"message": "Email verificata con successo. Il tuo account è ora attivo."}


@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Endpoint di login standard (OAuth2): genera un token JWT se le credenziali sono valide.
    """
    user = authenticate_user(form_data.username, form_data.password)
    # authenticate_user gestisce già l'eccezione in caso di credenziali non valide o account non verificato
    if not user:
         # Se l'errore non è stato sollevato (caso di credenziali non valide) solleva qui l'eccezione standard
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
    try:
        user = authenticate_user(user_credentials.username, user_credentials.password)
    except HTTPException as e:
        # Cattura l'errore 403 (Account non verificato) sollevato da authenticate_user
        raise e
    
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

@app.post("/utenti/richiesta-reset-password", status_code=status.HTTP_200_OK)
def request_password_reset(request: PasswordResetRequest):
    """
    Endpoint per richiedere il reset della password. 
    Genera un token e (in un'implementazione reale) lo invierebbe via email.
    """
    user_doc = USERS_COLLECTION.find_one({"username": request.username})
    
    if not user_doc:
        # Non sollevare un 404 per evitare l'enumerazione degli utenti.
        # Restituisce sempre un messaggio di successo, anche se l'utente non esiste.
        return {"message": "Se l'utente esiste, una mail per il reset della password è stata inviata."}
    
    # 1. Genera e memorizza il token
    reset_token = generate_reset_token(request.username)
    
    # 2. SIMULAZIONE EMAIL: 
    
    print(f"Token generato per {request.username}: {reset_token}") # Log for testing
    
    return {
        "message": "Se l'utente esiste, una mail per il reset della password è stata inviata.",
        # ATTENZIONE: Rimuovere questo campo in produzione! Espone il token!
        "token_for_testing_only": reset_token 
    }

@app.post("/utenti/reimposta-password", status_code=status.HTTP_200_OK)
def confirm_password_reset(data: PasswordResetConfirm):
    """
    Endpoint per confermare il reset della password usando il token.
    """
    # 1. Trova l'utente tramite il token e verifica che non sia scaduto
    # Cerca il token che non sia scaduto e sia presente
    user_doc = USERS_COLLECTION.find_one({
        "reset_token": data.token,
        "reset_token_expiry": {"$gt": datetime.utcnow()} # Il token deve essere maggiore del tempo attuale
    })
    
    if not user_doc:
        # Ritorna un errore generico per non dare indizi su token esistenti ma scaduti
        raise HTTPException(status_code=400, detail="Token di reset non valido o scaduto.")

    # 2. Hash della nuova password
    new_hashed_password = get_password_hash(data.new_password)
    
    # 3. Aggiorna la password e rimuovi i campi del token (consuma il token)
    USERS_COLLECTION.update_one(
        {"_id": user_doc["_id"]},
        {"$set": {"hashed_password": new_hashed_password},
         "$unset": {"reset_token": "", "reset_token_expiry": ""}}
    )
    
    return {"message": "Password reimpostata con successo. Esegui il login con la nuova password."}

# --- NUOVO ENDPOINT DI AMMINISTRAZIONE ---

@app.get("/utenti/admin-all-users", response_model=List[UserOut])
def get_all_users_for_admin(current_user: UserInDB = Depends(get_current_user)):
    """
    [ATTENZIONE: ENDPOINT DI DEBUG/AMMINISTRAZIONE]
    Restituisce tutti gli utenti nel DB, inclusi hash della password, email e token.
    Accessibile solo agli utenti con role='admin'.
    """
    # Controllo del ruolo: Solo l'utente con role='admin' può accedere
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accesso negato. Solo gli amministratori possono visualizzare tutti gli utenti."
        )

    users_list: List[UserOut] = []
    
    # Itera su tutti i documenti nella collection USERS_COLLECTION
    for user_doc in USERS_COLLECTION.find():
        # Costruisce l'oggetto UserOut, esponendo tutte le informazioni sensibili
        users_list.append(UserOut(
            id=str(user_doc["_id"]),
            username=user_doc["username"],
            email=user_doc.get("email", "EMAIL_MISSING"), # Usa un fallback chiaro
            is_verified=user_doc.get("is_verified", False),
            role=user_doc.get("role", "user"),
            hashed_password=user_doc.get("hashed_password", "HASH_MISSING")
        ))
        
    return users_list


@app.delete("/utenti/admin-clear-users", status_code=status.HTTP_200_OK)
def clear_all_users_except_admin(current_user: UserInDB = Depends(get_current_user)):
    """
    [ATTENZIONE: ENDPOINT DISTRUTTIVO]
    Cancella tutti gli utenti nel DB il cui ruolo NON è 'admin'.
    Accessibile solo agli utenti con role='admin'.
    """
    # 1. Controllo del ruolo
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accesso negato. Solo gli amministratori possono eseguire questa operazione."
        )

    # 2. Cancellazione di tutti gli utenti il cui ruolo NON è 'admin'
    try:
        # Usa l'operatore $ne (not equal) di MongoDB per escludere i documenti con role: "admin"
        result = USERS_COLLECTION.delete_many({"role": {"$ne": "admin"}})
    except Exception as e:
        # Gestisce errori del database
        raise HTTPException(status_code=500, detail=f"Errore durante la cancellazione degli utenti: {e}")

    # 3. Restituisce il conteggio degli utenti cancellati
    return {
        "message": f"Cancellati con successo {result.deleted_count} utenti. L'utente admin ('{current_user.username}') e gli altri admin non sono stati rimossi.",
        "deleted_count": result.deleted_count
    }





# --- ENDPOINT PROTETTI (Richiedono JWT) ---

# Sintassi di tipizzazione aggiornata per Python < 3.9
@app.post("/elementi/", response_model=Item, status_code=201)
def crea_elemento(item: Item, current_user: UserInDB = Depends(get_current_user)):
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

@app.get("/elementi/", response_model=List[Item])
def ottieni_tutti_gli_elementi(current_user: UserInDB = Depends(get_current_user)):
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

# L'endpoint GET per ID e la logica di errore rimangono utili e non richiedono l'utente per questa implementazione base
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