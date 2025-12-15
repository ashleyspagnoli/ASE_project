from fastapi import FastAPI, HTTPException, Depends, status, Query
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
# 🟢 AGGIUNTA: field_validator per la validazione
from pydantic import BaseModel, Field, field_validator 
from pymongo import MongoClient
from os import environ
from bson import ObjectId
from datetime import datetime, timedelta
from typing import Optional, List 
from fastapi import Header

# 🟢 AGGIUNTA: Libreria per pulizia input
import bleach 

# --- MODIFICA: Sostituzione python-jose con PyJWT ---
import jwt 
from jwt import PyJWTError # Base exception di PyJWT
# ----------------------------------------------------

from crypto import encrypt_data, decrypt_data, load_secret_key

from fastapi.middleware.cors import CORSMiddleware

# Hashing Libraries
from passlib.context import CryptContext
import hashlib
from app_test import MockClient

# =================================================================
# 🟢 AGGIUNTA: FUNZIONE DI UTILITÀ PER SANITIZZAZIONE
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


def hash_search_key(data: str) -> str:
    """Generates a SHA-256 hash of the lowercase input string for consistent searching."""
    return hashlib.sha256(data.lower().encode('utf-8')).hexdigest()

# --- CONFIGURATION: DATABASE AND SECURITY ---


# DB configuration (read from environment or use default)
DB_NAME = "user_auth_db" 
DEFAULT_MONGO_URI = f"mongodb://user-db:27017/{DB_NAME}"
MONGO_URI = environ.get("MONGO_URI", DEFAULT_MONGO_URI)

# JWT Configuration (read from environment)
FAKE_SECRET_KEY = load_secret_key("fake-key-jwt.txt", default="default_secret_key_weak") 
SECRET_KEY = load_secret_key("/run/secrets/jwt_secret_key", default=FAKE_SECRET_KEY)
ALGORITHM = environ.get("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
HTTPS_ENABLED = environ.get("HTTPS_ENABLED", "True").lower() == "true" 


# Database Connection Initialization

MOCKMONGO = environ.get("MOCKMONGO", "False").lower()
if MOCKMONGO == "false":
    try:
        print("Connecting to MongoDB...", flush=True)
        print(f"Using MONGO_URI: {MONGO_URI}", flush=True)  
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)

        db = client.get_database(DB_NAME) 
        ITEMS_COLLECTION = db["elementi"] 
        USERS_COLLECTION = db["utenti"] 
        client.server_info() 
        print(f"Successfully connected to DB: {DB_NAME}")
    except Exception as e:
        print(f"CRITICAL MongoDB connection error: {e}")
        raise ConnectionError(f"Cannot connect to MongoDB: {e}")
    
else: 
    print("WARNING: Running in MOCKMONGO mode (Database mocked).", flush=True)
    client = MockClient() 
    db = client.get_database(DB_NAME) 
    USERS_COLLECTION = db["utenti"] 
    client.server_info() 
    print(f"Using Mock MongoDB Collection for DB: {DB_NAME}")

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

    # 🟢 AGGIUNTA: Sanitizzazione Username su tutti i modelli che ereditano
    @field_validator('username')
    @classmethod
    def sanitize_username(cls, v):
        return sanitize_text(v)

class UserInDB(UserBase):
    """Internal schema for user data manipulation at the database level."""
    hashed_password: str
    email: str 
    id: Optional[str] = None
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
    if "sub" not in to_encode and "username" in to_encode:
        to_encode["sub"] = to_encode["username"]    
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_user(username: str):
    """Retrieves user data from MongoDB based on username."""
    # Nota: anche se username è sporco in input, il sanitizer lo pulisce prima di arrivare qui
    print(f"Fetching user from DB: {username}")
    user_doc = USERS_COLLECTION.find_one({"username": username})
    print(f"User document fetched: {user_doc}")
    if user_doc:
        return UserInDB(
            username=user_doc['username'],
            id=str(user_doc['_id']),
            email=decrypt_data(user_doc['email']),
            hashed_password=user_doc['hashed_password'],
            hashed_email=user_doc['hashed_email'],
        )
    return None

def authenticate_user(username: str, password: str):
    """Authenticates user credentials and checks verification status."""
    user = get_user(username)
    print("User fetched for authentication:")
    print(user)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def verify_internal_token(authorization: str = Header(..., alias="Authorization")):
    """Dipendenza FastAPI per validare il token JWT Service-to-Service (S2S)."""
    
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

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except PyJWTError as e:
        print(f"Internal Token Error: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal service token.")
    
    user = get_user(payload.get("sub"))
    return user 

# --- DEPENDENCY: GET CURRENT USER FROM JWT TOKEN ---

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    first_error = exc.errors()[0]
    loc = first_error.get("loc")
    
    if 'min_length' in str(first_error):
        field_name = loc[-1] 
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, 
            content={
                "detail": f"Il campo '{field_name}' non può essere vuoto o troppo corto. Riprova."
            },
        )
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
    allow_origins=origins,             
    allow_credentials=True,            
    allow_methods=["*"],               
    allow_headers=["*"],               
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
        username: str = payload.get("sub") 
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except PyJWTError: 
        raise credentials_exception
        
    user = get_user(token_data.username)
    if user is None:
        raise credentials_exception
        
    return user


@app.post("/token", response_model=Token, tags=["Authentication and Users"], summary="OAuth2 Standard Token Exchange")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    # 🟢 NOTA: OAuth2PasswordRequestForm non è un modello Pydantic standard,
    # quindi è difficile applicare il validatore direttamente qui.
    # Tuttavia, chiamando authenticate_user, useremo get_user che cerca nel DB.
    # Se l'input ha caratteri sporchi (HTML), get_user(username_sporco) non troverà nulla nel DB
    # (perché nel DB salviamo pulito), quindi il login fallirà correttamente.
    
    print(f"Authenticating user: {form_data.username}")
    print(f"Password provided: {form_data.password}")
    user = authenticate_user(form_data.username, form_data.password)
    
    if not user:
         raise HTTPException(
             status_code=status.HTTP_401_UNAUTHORIZED,
             detail="Invalid username or password",
             headers={"WWW-Authenticate": "Bearer"},
         )
    
    access_token = create_access_token(
        data={"username": user.username, "id": user.id}
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


#--- ENDPOINTS: USER REGISTRATION AND LOGIN ---
class UsernameEmail(UserBase):
    """Schema for username and email health check."""
    email: str = Field(..., description="The user's email address.")

    # 🟢 AGGIUNTA: Validazione Email (Username è ereditato da UserBase)
    @field_validator('email')
    @classmethod
    def sanitize_email(cls, v):
        return sanitize_text(v)

@app.get(
    "/users/my-username-my-email", 
    status_code=status.HTTP_200_OK,
    response_model=UsernameEmail,
    tags=["My Information"],
    summary="Service Health Check"
)
def get_my_username_my_email(current_user: UserInDB = Depends(get_current_user)):
    """
    Health check endpoint that returns the username and email of the authenticated user.
    """
    print(f"Health check for user: {current_user.email}")
    return UsernameEmail(username=current_user.username, email=current_user.email)  


class UserLogin(UserBase):
    """Schema for user login credentials."""
    password: str = Field(..., description="The plain text password provided by the user.")
    # ⚠️ Password NON viene sanitizzata. Username viene sanitizzato perché eredita da UserBase.

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
    password: str = Field(..., min_length=3, description="The plain text password for the new user.") 
    email: str = Field(..., description="The user's email address.")
    
    # 🟢 AGGIUNTA: Validazione Email (Username ereditato)
    @field_validator('email')
    @classmethod
    def sanitize_email(cls, v):
        return sanitize_text(v)

@app.post(
    "/users/register", 
    status_code=status.HTTP_201_CREATED,
    tags=["Authentication and Users"],
    summary="Register a new user"
)

def register_user(user_in: UserCreate, ):
    """
    Registers a new user.
    """
    print("Registering new user:")
    print(user_in) # Qui user_in ha già username e email puliti grazie ai validatori
    
    if get_user(user_in.username):
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_password = get_password_hash(user_in.password)
    hashed_email=hash_search_key(user_in.email)

    if USERS_COLLECTION.find_one({"username": user_in.username}):
        raise HTTPException(status_code=400, detail="Username already registered")

    if USERS_COLLECTION.find_one({"hashed_email": hashed_email}):
        raise HTTPException(status_code=400, detail="Email already registered")

    user_data = {
        "username": user_in.username,
        "email": encrypt_data(user_in.email), 
        "hashed_password": hashed_password,
        "hashed_email": hashed_email,
    }
    print(user_data)

    USERS_COLLECTION.insert_one(user_data)
    
    return {
        "message": "Registration successful.", 
        "username": user_in.username,
    }

def get_user_from_local_token(token: str = Depends(oauth2_scheme)) -> UserInDB:
    """Dipendenza LOCALE che decodifica il JWT e recupera l'utente dal DB."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials locally.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        identifier: str = payload.get("username")
        if identifier is None:
            raise credentials_exception
            
    except PyJWTError:
        raise credentials_exception
        
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
    id_list: List[str] = Query(..., description="List of user IDs (repeated in query: ?id_list=ID1&id_list=ID2)"),
):
    if not id_list:
        return []

    object_ids = []
    
    for id_str in id_list:
        try:
            object_ids.append(ObjectId(id_str))
        except Exception:
            print(f"WARNING: Invalid ObjectId format received and ignored: {id_str}")
            continue

    if not object_ids:
        return []
        
    users = USERS_COLLECTION.find(
        {"_id": {"$in": object_ids}},
        {"username": 1} 
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
    username_list: List[str] = Query(..., description="List of usernames (repeated in query: ?username_list=user1&username_list=user2)"),
):
    if not username_list:
        return []

    users = USERS_COLLECTION.find(
        {"username": {"$in": username_list}},
        {"username": 1} 
    )
    
    results = []
    for user_doc in users:
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
    users_list: List[UserInDB] = []
    
    for user_doc in USERS_COLLECTION.find():
        users_list.append(UserInDB(
            id=str(user_doc["_id"]),
            username=(user_doc["username"]),
            email=decrypt_data(user_doc["email"]),
            hashed_password=user_doc["hashed_password"],
            hashed_email=user_doc["hashed_email"],   
        ))
        
    return users_list



class UserUpdateInternal(BaseModel):
    """Payload interno per aggiornare solo i campi necessari."""
    username: Optional[str] = None
    old_email: Optional[str] = None
    new_email: Optional[str] = None
    new_password: Optional[str] = None 
    old_password: Optional[str] = None 

    # 🟢 AGGIUNTA: Validazione campi
    @field_validator('username', 'old_email', 'new_email')
    @classmethod
    def sanitize_input(cls, v):
        return sanitize_text(v)

# =================================================================
# 3. LOGICA CENTRALIZZATA DI AGGIORNAMENTO DB
# =================================================================

@app.post("/internal/update-username", status_code=status.HTTP_200_OK, tags=["Internal DB Access"], dependencies=[Depends(verify_internal_token)])
def update_username_in_db(update_data: UserUpdateInternal, currentuser:UserInDB=Depends(get_current_user)):
    user_id = currentuser.id
    print(f"Updating user with ID: {user_id}")
    try:
        user_object_id = ObjectId(user_id)
    except:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID format.")

    current_record = USERS_COLLECTION.find_one({"_id": user_object_id})
    if not current_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        
    update_fields = {}
    
    if update_data.username:
        if USERS_COLLECTION.find_one({"username": update_data.username}):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken.")
            
        update_fields["username"] = update_data.username
        
    if not update_fields:
        return {"message": "Nessun campo da aggiornare."}
        
    result = USERS_COLLECTION.update_one(
        {"_id": user_object_id},
        {"$set": update_fields}
    )
    
    if result.modified_count == 1:
        return {"message": "User attributes updated successfully."}
    else:
        return {"message": "User record was not modified (data was already the same or concurrent update occurred)."}
        

@app.post("/internal/update-email", status_code=status.HTTP_200_OK, tags=["Internal DB Access"], dependencies=[Depends(verify_internal_token)])
def update_email_in_db(update_data: UserUpdateInternal, currentuser:UserInDB=Depends(get_current_user)):
    user_id = currentuser.id
    try:
        user_object_id = ObjectId(user_id)
    except:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID format.")

    current_record = USERS_COLLECTION.find_one({"_id": user_object_id})

    if not current_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        
    update_fields = {}
    hashed_new_email = hash_search_key(update_data.new_email)
    if decrypt_data(current_record["email"]) != update_data.old_email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Old email does not match current email.")
    
    if USERS_COLLECTION.find_one({"hashed_email": hashed_new_email}):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered.")
    
    encrypted_new_email = encrypt_data(update_data.new_email)
    update_fields["email"] = encrypted_new_email
    update_fields["hashed_email"] = hashed_new_email

    result = USERS_COLLECTION.update_one(
        {"_id": user_object_id},
        {"$set": update_fields}
    )
    
    if result.modified_count == 1:
        return {"message": "User attributes updated successfully."}
    else:
        return {"message": "User record was not modified (data was already the same or concurrent update occurred)."}
    


@app.post("/internal/update-password", status_code=status.HTTP_200_OK, tags=["Internal DB Access"], dependencies=[Depends(verify_internal_token)])
def update_password_in_db(update_data: UserUpdateInternal, currentuser:UserInDB=Depends(get_current_user)):
    user_id = currentuser.id
    print(f"Updating user with ID: {user_id}")
    try:
        user_object_id = ObjectId(user_id)
    except:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID format.")

    current_record = USERS_COLLECTION.find_one({"_id": user_object_id})
    if not current_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        
    update_fields = {}
    
    if update_data.new_password:

        if not verify_password(update_data.old_password, current_record["hashed_password"]):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Old password is incorrect.")
        
        update_fields["hashed_password"] = get_password_hash(update_data.new_password)
        
    if not update_fields:
        return {"message": "Nessun campo da aggiornare."}
        
    result = USERS_COLLECTION.update_one(
        {"_id": user_object_id},
        {"$set": update_fields}
    )
    
    if result.modified_count == 1:
        return {"message": "User attributes updated successfully."}
    else:
        return {"message": "User record was not modified (data was already the same or concurrent update occurred)."}