
from fastapi import FastAPI, HTTPException, Depends, status, Query
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from pymongo import MongoClient
from os import environ
from bson import ObjectId
from datetime import datetime, timedelta
from typing import Optional, List 
from fastapi import Header
from jose.exceptions import JWTError as PyJWTError

from crypto import encrypt_data, decrypt_data, load_secret_key

from fastapi.middleware.cors import CORSMiddleware
# JWT and Hashing Libraries
from jose import JWTError, jwt
from passlib.context import CryptContext
import hashlib
import pytest
def hash_search_key(data: str) -> str:
    """Generates a SHA-256 hash of the lowercase input string for consistent searching.
     This helps in avoiding storing plain text sensitive data while allowing lookups like email and username.
     """
    return hashlib.sha256(data.lower().encode('utf-8')).hexdigest()

# --- CONFIGURATION: DATABASE AND SECURITY ---


# DB configuration (read from environment or use default)
DB_NAME = "user_auth_db" 
DEFAULT_MONGO_URI = f"mongodb://user_admin:secure_password_user@localhost:27017/{DB_NAME}?authSource=admin"
MONGO_URI = environ.get("MONGO_URI", DEFAULT_MONGO_URI) 


# JWT Configuration (read from environment)
SECRET_KEY = load_secret_key("/run/secrets/jwt_secret_key", default="default_secret_key_weak")
ALGORITHM = environ.get("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", 30)) 


# Database Connection Initialization
try:
    client = MongoClient(MONGO_URI)
    db = client.get_database(DB_NAME) 
    ITEMS_COLLECTION = db["elementi"] 
    USERS_COLLECTION = db["utenti"] 
    client.server_info() 
    print(f"Successfully connected to DB: {DB_NAME}")
except Exception as e:
    print(f"CRITICAL MongoDB connection error: {e}")
    raise ConnectionError(f"Cannot connect to MongoDB: {e}")


# Context for password hashing
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")



# FastAPI App Initialization
app = FastAPI(
    title="User Authentication Microservice (Auth)", 
    description="Handles user registration, JWT login, and core user data management.",
    version="1.0.0"
)


# ---------------------------------------------------- PYDANTIC DATA MODELS ---------------------------------------

class UserBase(BaseModel):
    """Base schema containing only the username."""
    username: str = Field(..., description="Unique username.")

class UserInDB(UserBase):
    """Internal schema for user data manipulation at the database level."""
    hashed_password: str
    email: str 
    id: Optional[str] = None
    hashed_username: str
    hashed_email: str

class UsernameMapping(BaseModel):
    """Schema for public user information."""
    id: str = Field(..., description="Unique user ID.") 
    username: str = Field(..., description="Username.")

class Token(BaseModel):
    """Response schema for login and token generation."""
    access_token: str = Field(..., description="The JWT access token.")
    token_type: str = Field("bearer", description="Token type (Bearer).")

class TokenData(BaseModel):
    """Internal schema for decoded JWT data."""
    username: Optional[str] = None

# --- INTERNAL SERVICE MODELS ---

class UserIdMapping(BaseModel):
    """Mapping schema: Username to ID."""
    username: str = Field(..., description="Username.")
    id: str = Field(..., description="Unique user ID (ObjectId).")


# ------------------------------------------------ SECURITY FUNCTIONS (PASSWORD HASHING & JWT) ------------------------------


#--- PASSWORD HASHING AND VERIFICATION ---

def get_password_hash(password):
    """Returns the Argon2 hash of a plain password."""
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    """Verifies a plain password against the stored hash."""
    return pwd_context.verify(plain_password, hashed_password)


#--- JWT TOKEN CREATION AND USER RETRIEVAL ---

def create_access_token(data: dict):
    """Creates a JWT token, ensuring 'sub' and 'exp' claims are included."""
    to_encode = data.copy()
    # Ensure 'sub' claim exists (standard JWT practice used by get_current_user)
    if "sub" not in to_encode and "username" in to_encode:
        to_encode["sub"] = to_encode["username"]    
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_user(username: str):
    """Retrieves user data from MongoDB based on username."""
    hashed_username=hash_search_key(username)
    user_doc = USERS_COLLECTION.find_one({"hashed_username": hashed_username})
    if user_doc:
        return UserInDB(
            id=str(user_doc['_id']),
            username=decrypt_data(user_doc['username']), 
            email=decrypt_data(user_doc['email']),
            hashed_password=user_doc['hashed_password'],
            hashed_username=user_doc['hashed_username'],
            hashed_email=user_doc['hashed_email'],
        )
    return None

def authenticate_user(username: str, password: str):
    """Authenticates user credentials and checks verification status."""
    user = get_user(username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def verify_internal_token(authorization: str = Header(..., alias="Authorization")):
    """
    Dipendenza FastAPI per validare il token JWT Service-to-Service (S2S).
    Verifica che il chiamante sia un servizio interno autorizzato (Microservizio Editor).
    """
    
    # 1. Parsing dell'Header: Atteso formato "Bearer [token]"
    if not authorization or ' ' not in authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Authorization header missing or invalid format."
        )
        
    try:
        scheme, token = authorization.split(' ', 1)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization scheme.")
        
    if scheme.lower() != 'bearer':
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication scheme (Expected Bearer).")

    # 2. Decodifica e Validazione
    try:
        # Usa la chiave segreta specifica per i servizi interni
        payload=jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
    except PyJWTError as e:
        # Cattura errori di firma non valida, token scaduto, ecc.
        print(f"Internal Token Error: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal service token.")
    
    # Se il token è valido e autorizzato, la funzione ritorna senza sollevare eccezioni.
    
    user = get_user(payload.get("sub"))
    return user 

# --- DEPENDENCY: GET CURRENT USER FROM JWT TOKEN ---

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Ottieni la prima riga di errore
    first_error = exc.errors()[0]
    loc = first_error.get("loc")
    
    # Controlla se l'errore è un problema di lunghezza di un campo specifico
    if 'min_length' in str(first_error):
        field_name = loc[-1] # Prende il nome del campo (es. 'old_email')
        
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, # Usa 400 invece di 422 per errore chiaro
            content={
                "detail": f"Il campo '{field_name}' non può essere vuoto o troppo corto. Riprova."
            },
        )
    
    # Per tutti gli altri errori, restituisce il default 422
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
    )

# --- ENDPOINTS: AUTHENTICATION AND USERS ---

# OAuth2 Standard Token Endpoint (For Swagger UI and standard clients)

origins = [
    "https://localhost:5005",
    "https://localhost:5004",]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,             # Specifica le origini autorizzate
    allow_credentials=True,            # Consente i cookie (non cruciale qui, ma buona pratica)
    allow_methods=["*"],               # Consente tutti i metodi (GET, POST, OPTIONS, ecc.)
    allow_headers=["*"],               # Consente tutti gli header (incluso 'Authorization' o 'Content-Type')
)


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_current_user(token: str = Depends(oauth2_scheme)):
    """Decodes and validates the JWT token, returning the UserInDB object."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # Look for the 'sub' claim (standard JWT subject)
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



@app.post("/token", response_model=Token, tags=["Authentication and Users"], summary="OAuth2 Standard Token Exchange")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Standard OAuth2 endpoint to exchange username and password (form-data) for a JWT token.
    This endpoint is used by the global 'Authorize' button in Swagger UI.
    """
    # 1. Autentica l'utente usando i dati del Form Data
    user = authenticate_user(form_data.username, form_data.password)
    
    if not user:
         raise HTTPException(
             status_code=status.HTTP_401_UNAUTHORIZED,
             detail="Invalid username or password",
             headers={"WWW-Authenticate": "Bearer"},
         )
    
    # 2. Crea il token con i dati dell'utente
    access_token = create_access_token(
        data={"username": user.username, "id": user.id}
    )
    
    # 3. Restituisce il token
    return {"access_token": access_token, "token_type": "bearer"}


#--- ENDPOINTS: USER REGISTRATION AND LOGIN ---




class UserLogin(UserBase):
    """Schema for user login credentials."""
    password: str = Field(..., description="The plain text password provided by the user.")

@app.post(
    "/users/login", 
    status_code=status.HTTP_200_OK,
    tags=["Authentication and Users"],
    summary="Simplified JSON Login and JWT generation"
)
def simple_login(user_credentials: UserLogin):
    """
    Authenticates user credentials provided in JSON format and returns a JWT token.
    """
    try:
        user = authenticate_user(user_credentials.username, user_credentials.password)
    except HTTPException as e:
        raise e
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    
    access_token = create_access_token(
        data={"username": user.username, "id": user.id}
    )

    return {
        "message": "Login successful", 
        "token": access_token,
        "token_type": "bearer"
    }





class UserCreate(UserBase):
    """Schema for new user registration."""
    password: str = Field(..., min_length=3, description="The plain text password for the new user.") # FAI CONTROLLI SUALLA SICREZZA DELLA PASSWORD
    email: str = Field(..., description="The user's email address.")
    
@app.post(
    "/users/register", 
    status_code=status.HTTP_201_CREATED,
    tags=["Authentication and Users"],
    summary="Register a new user"
)

def register_user(user_in: UserCreate):
    """
    Registers a new user and grants the 'admin' role if the username is 'admin'.
    """
    if get_user(user_in.username):
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_password = get_password_hash(user_in.password)
    hashed_username=hash_search_key(user_in.username)
    hashed_email=hash_search_key(user_in.email)

    if USERS_COLLECTION.find_one({"hashed_username": hashed_username}):
        raise HTTPException(status_code=400, detail="Username already registered")

    if USERS_COLLECTION.find_one({"hashed_email": hashed_email}):
        raise HTTPException(status_code=400, detail="Email already registered")

    user_data = {
        "username": encrypt_data(user_in.username),
        "email": encrypt_data(user_in.email), 
        "hashed_password": hashed_password,
        "hashed_username": hashed_username,
        "hashed_email": hashed_email,
    }
    print(user_data)

    USERS_COLLECTION.insert_one(user_data)
    
    return {
        "message": "Registration successful.", 
        "username": user_in.username,
    }

def get_user_from_local_token(token: str = Depends(oauth2_scheme)) -> UserInDB:
    """
    Dipendenza L O C A L E che decodifica il JWT e recupera l'utente dal DB.
    NON FA CHIAMATE HTTP.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials locally.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # Assumiamo che l'identificatore sia nel campo 'username' o 'sub'
        identifier: str = payload.get("username")
        if identifier is None:
            raise credentials_exception
            
    except PyJWTError:
        raise credentials_exception
        
    # La funzione get_user(identifier) cerca l'utente cifrato nel DB e lo decripta
    user = get_user(identifier) 
    
    if user is None:
        raise credentials_exception
        
    return user



@app.get(
    "/users/validate-token", 
    response_model=UsernameMapping,
    tags=["Internal Services"],
    summary="[INTERNAL] Validate a JWT token and return user data."
)
def validate_token(current_user: UserInDB = Depends(get_user_from_local_token)):
    """
    Used by other microservices to validate a JWT and retrieve the user's ID and username.
    """
    print(f"Validating token for user: {current_user.username}")
    return UsernameMapping(id=current_user.id, username=current_user.username)

# --- ENDPOINTS: INTERNAL ID/USERNAME RESOLUTION ---

@app.get(
    "/users/usernames-by-ids", 
    response_model=List[UsernameMapping],
    tags=["Internal Services"],
    summary="[INTERNAL] Get usernames from a list of user IDs."
)

def get_usernames_by_ids(
    # Standard FastAPI way to handle multiple query parameters
    id_list: List[str] = Query(..., description="List of user IDs (repeated in query: ?id_list=ID1&id_list=ID2)")
):
    
    """
    Returns a list of usernames mapped to their corresponding user IDs.
    """
    if not id_list:
        return []

    try:
        # Validate and convert string IDs to MongoDB ObjectIds
        object_ids = [ObjectId(id_str) for id_str in id_list]
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, 
                            detail="One or more provided User IDs are invalid (ObjectId).")
        
    # Query MongoDB for users whose _id is in the list
    users = USERS_COLLECTION.find(
        {"_id": {"$in": object_ids}},
        {"username": 1} # Project only the username and _id (default)
    )
    
    results = []
    for user_doc in users:
        results.append(UsernameMapping(
            id=str(user_doc["_id"]), 
            username=user_doc["username"] 
        ))
    return results

@app.get(
    "/users/ids-by-usernames", 
    response_model=List[UserIdMapping],
    tags=["Internal Services"],
    summary="[INTERNAL] Get user IDs from a list of usernames."
)
def get_ids_by_usernames(
    # Standard FastAPI way to handle multiple query parameters
    username_list: List[str] = Query(..., description="List of usernames (repeated in query: ?username_list=user1&username_list=user2)")
):
    """
    Returns a list of user IDs mapped to their corresponding usernames.
    """
    if not username_list:
        return []

    # Query MongoDB for users whose username is in the list
    users = USERS_COLLECTION.find(
        {"username": {"$in": username_list}},
        {"username": 1} 
    )
    
    results = []
    for user_doc in users:
        # Check if _id is present (should always be if user exists)
        user_id = user_doc.get("_id") 
        if user_id:
            results.append(UserIdMapping(
                username=user_doc.get("username", "UNKNOWN"),
                id=str(user_id) 
            ))
    return results


# --- ENDPOINTS: ADMIN AND PROTECTED ACCESS ---

@app.delete(
    "/devs/admin-clear-users", 
    status_code=status.HTTP_200_OK,
    tags=["Administration (Protected)"],
    summary="[ADMIN] Delete all non-admin users"
)
def clear_all_users_except_admin():
    """
    WARNING: Destructive endpoint. Deletes all accounts which username is not 'momo'.
    """
    try:
        result = USERS_COLLECTION.delete_many({"username": {"$ne": "admin"}})
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error during deletion: {e}")

    return {
        "message": f"Successfully deleted {result.deleted_count} users.",
        "deleted_count": result.deleted_count
    }

@app.get(
    "/devs/admin-all-users", 
    response_model=List[UserInDB],
    tags=["Administration (Protected)"],
    summary="[ADMIN] Get all users (including password hash) with protection",
)
def get_all_users_for_admin():
    """
    Returns all user data, including sensitive fields. 
    Requires a valid JWT with 'admin' role.
    """
    

    users_list: List[UserInDB] = []
    
    for user_doc in USERS_COLLECTION.find():
        users_list.append(UserInDB(
            id=str(user_doc["_id"]),
            username=decrypt_data(user_doc["username"]),
            email=decrypt_data(user_doc["email"]),
            hashed_password=user_doc["hashed_password"],
            hashed_username=user_doc["hashed_username"],
            hashed_email=user_doc["hashed_email"],   
        ))
        
    return users_list



class UserUpdateInternal(BaseModel):
    """Payload interno per aggiornare solo i campi necessari.
    L'ID è essenziale per trovare l'elemento da aggiornare."""
    username: Optional[str] = None
    old_email: Optional[str] = None
    new_email: Optional[str] = None
    new_password: Optional[str] = None # Solo se la password cambia
    old_password: Optional[str] = None # Solo se la password cambia

# =================================================================
# 3. LOGICA CENTRALIZZATA DI AGGIORNAMENTO DB
# =================================================================

@app.post("/internal/update-user", status_code=status.HTTP_200_OK, tags=["Internal DB Access"], dependencies=[Depends(verify_internal_token)])
def update_user_in_db(update_data: UserUpdateInternal, currentuser:UserInDB=Depends(get_current_user)):
    """
    Endpoint interno che gestisce l'aggiornamento, la crittografia/hashing,
    e il salvataggio dei dati utente.
    """
    user_id = currentuser.id
    print(f"Updating user with ID: {user_id}")
    # 1. Trova l'utente attuale per ottenere i dati esistenti e l'ObjectId
    try:
        user_object_id = ObjectId(user_id)
    except:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID format.")

    current_record = USERS_COLLECTION.find_one({"_id": user_object_id})
    if not current_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        
    # 2. Prepara il dizionario con gli aggiornamenti
    update_fields = {}
    
    # --- Gestione Username ---
    if update_data.username:
        encrypted_new_username = encrypt_data(update_data.username)
        hashed_new_username = hash_search_key(update_data.username)
        # Check duplicati (importante)
        if USERS_COLLECTION.find_one({"hashed_username": hashed_new_username}):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken.")
            
        update_fields["username"] = encrypted_new_username
        update_fields["hashed_username"] = hashed_new_username
        
    # --- Gestione Email ---
    if update_data.new_email:
        encrypted_new_email = encrypt_data(update_data.new_email)
        hashed_new_email = hash_search_key(update_data.new_email)
        #Check vecchia email
        if decrypt_data(current_record["email"]) != update_data.old_email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Old email does not match current email.")
        # Check duplicati
        if USERS_COLLECTION.find_one({"hashed_email": hashed_new_email}):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered.")
            
        update_fields["email"] = encrypted_new_email
        update_fields["hashed_email"] = hashed_new_email
        
    # --- Gestione Password ---
    if update_data.new_password:

        if not verify_password(update_data.old_password, current_record["hashed_password"]):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Old password is incorrect.")
        
        update_fields["hashed_password"] = get_password_hash(update_data.new_password)
        
    if not update_fields:
        return {"message": "Nessun campo da aggiornare."}
        
    # 3. Esegue l'aggiornamento
    result = USERS_COLLECTION.update_one(
        {"_id": user_object_id},
        {"$set": update_fields}
    )
    
    if result.modified_count == 1:
        return {"message": "User attributes updated successfully."}
    else:
        # Questo può accadere se, ad esempio, i dati sono identici
        return {"message": "User record was not modified (data was already the same or concurrent update occurred)."}