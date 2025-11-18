# backend/main.py

from fastapi import FastAPI, HTTPException, Depends, status, Query
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from pymongo import MongoClient
from os import environ
from bson import ObjectId
from datetime import datetime, timedelta
from typing import Optional, List 

# JWT and Hashing Libraries
from jose import JWTError, jwt
from passlib.context import CryptContext

# --- CONFIGURATION: DATABASE AND SECURITY ---

# DB configuration (read from environment or use default)
DB_NAME = "user_auth_db" 
DEFAULT_MONGO_URI = f"mongodb://user_admin:secure_password_user@localhost:27017/{DB_NAME}?authSource=admin"
MONGO_URI = environ.get("MONGO_URI", DEFAULT_MONGO_URI) 

# JWT Configuration (read from environment)
SECRET_KEY = environ.get("SECRET_KEY", "default_secret_key_weak")
ALGORITHM = environ.get("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
RESET_TOKEN_EXPIRE_MINUTES = 60 
VERIFICATION_TOKEN_EXPIRE_MINUTES = 120 

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
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# FastAPI App Initialization
app = FastAPI(
    title="User Authentication Microservice (Auth)", 
    description="Handles user registration, JWT login, and core user data management.",
    version="1.0.0"
)

# --- PYDANTIC DATA MODELS ---

class Item(BaseModel):
    """Schema for a generic item (used for testing protected endpoints)."""
    id: Optional[str] = Field(None, description="The unique MongoDB ID of the item.")
    nome: str = Field(..., description="The descriptive name of the item.")
    valore: int = Field(..., description="A numerical value associated with the item.")

class UserBase(BaseModel):
    """Base schema containing only the username."""
    username: str = Field(..., description="Unique username.")

class UserLogin(UserBase):
    """Schema for user login credentials."""
    password: str = Field(..., description="The plain text password provided by the user.")

class UserCreate(UserLogin):
    """Schema for new user registration."""
    email: str = Field(..., description="The user's email address.")

class UserInDB(UserBase):
    """Internal schema for user data manipulation at the database level."""
    hashed_password: str
    email: str 
    is_verified: Optional[bool] = False
    role: Optional[str] = "user"
    id: Optional[str] = None

class UserOut(UserBase):
    """Schema for detailed user output, primarily for admin use."""
    id: Optional[str] = Field(None, description="Unique database ID.")
    email: str
    is_verified: bool = Field(..., description="Email verification status.")
    role: str = Field(..., description="User role (e.g., 'user', 'admin').")
    hashed_password: str = Field(..., description="Password hash (admin view only).")
    
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


# --- SECURITY FUNCTIONS (PASSWORD HASHING & JWT) ---

def verify_password(plain_password, hashed_password):
    """Verifies a plain password against the stored hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    """Returns the Argon2 hash of a plain password."""
    return pwd_context.hash(password)

def create_access_token(data: dict):
    """Creates a JWT token, ensuring 'sub' and 'exp' claims are included."""
    to_encode = data.copy()
    
    # Ensure 'sub' claim exists (standard JWT practice used by get_current_user)
    if "sub" not in to_encode and "username" in to_encode:
        to_encode["sub"] = to_encode["username"]
        
    # Set expiration time
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_user(username: str):
    """Retrieves user data from MongoDB based on username."""
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
    """Authenticates user credentials and checks verification status."""
    user = get_user(username)
    if not user:
        return False
    
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account not verified. Check your email."
        )
    
    if not verify_password(password, user.hashed_password):
        return False
    return user

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Decodes and validates the JWT token, returning the UserInDB object."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
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
        
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account not verified. Token unusable."
        )
        
    return user

# --- ENDPOINTS: AUTHENTICATION AND USERS ---

@app.post(
    "/utenti/registrati", 
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
        
    if USERS_COLLECTION.find_one({"email": user_in.email}):
        raise HTTPException(status_code=400, detail="Email already registered")
        
    hashed_password = get_password_hash(user_in.password)
    
    user_data = {
        "username": user_in.username,
        "email": user_in.email, 
        "hashed_password": hashed_password,
        "is_verified": True, 
        "role": "admin" if user_in.username == "admin" else "user" 
    }
    
    result = USERS_COLLECTION.insert_one(user_data)
    userid = str(result.inserted_id)
    
    return {
        "message": "Registration successful.", 
        "username": user_in.username,
        # Token is provided for testing convenience; REMOVE IN PRODUCTION
        "token_for_testing_only": create_access_token(data={"username": user_in.username, "id": userid})
    }

@app.post(
    "/login", 
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

@app.post(
    "/utenti/validate-token", 
    response_model=UsernameMapping,
    tags=["Internal Services"],
    summary="[INTERNAL] Validate a JWT token and return user data."
)
def validate_token(token_data: Token):
    """
    Used by other microservices to validate a JWT and retrieve the user's ID and username.
    """
    token_str = token_data.access_token

    try:
        # 1. Decode and verify the token using the SECRET_KEY
        payload = jwt.decode(token_str, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("username")
        
        if username is None:
            # Fallback check if token was created using the standard 'sub' claim
            username = payload.get("sub")
            if username is None:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token does not contain a valid user identifier ('username' or 'sub').")
        
    except JWTError:
        # Catches JWTError (invalid signature, expiry, etc.)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired JWT token.")
        
    # 2. Retrieve user from DB for additional verification
    user = get_user(username)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User associated with token not found.")
    
    if not user.is_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account not verified.")
        
    # 3. Return the requested data to the client service
    return UsernameMapping(
        # Use the ID stored in the token payload (if present) or retrieved from DB
        id=payload.get("id") if payload.get("id") else user.id,
        username=user.username,
    )

# --- ENDPOINTS: INTERNAL ID/USERNAME RESOLUTION ---

@app.get(
    "/utenti/usernames-by-ids", 
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
    "/utenti/ids-by-usernames", 
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

@app.get(
    "/utenti/dev-all-users", 
    response_model=List[UserOut],
    tags=["Administration (Debug)"],
    summary="[DEBUG] Get all users (including password hash)"
)
def get_all_users_for_devs():
    """
    WARNING: Unprotected debug/admin endpoint. Returns ALL user data. Must be removed in production!
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
    tags=["Administration (Protected)"],
    summary="[ADMIN] Delete all non-admin users"
)
def clear_all_users_except_admin(current_user: UserInDB = Depends(get_current_user)):
    """
    WARNING: Destructive endpoint. Deletes all accounts whose role is NOT 'admin'.
    Requires a valid JWT with 'admin' role.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only administrators can perform this operation."
        )

    try:
        result = USERS_COLLECTION.delete_many({"role": {"$ne": "admin"}})
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error during deletion: {e}")

    return {
        "message": f"Successfully deleted {result.deleted_count} users.",
        "deleted_count": result.deleted_count
    }

@app.get(
    "/utenti/admin-all-users", 
    response_model=List[UserOut],
    tags=["Administration (Protected)"],
    summary="[ADMIN] Get all users (including password hash) with protection"
)
def get_all_users_for_admin(current_user: UserInDB = Depends(get_current_user)):
    """
    Returns all user data, including sensitive fields. 
    Requires a valid JWT with 'admin' role.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only administrators can view all users."
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

# --- ENDPOINTS: PROTECTED OPERATIONS (Requires JWT) ---

@app.post(
    "/elementi/", 
    response_model=Item, 
    status_code=status.HTTP_201_CREATED,
    tags=["Protected Operations (Items)"],
    summary="Create a new item"
)
def crea_elemento(item: Item, current_user: UserInDB = Depends(get_current_user)):
    """
    Creates a new item associated with the authenticated user.
    Requires a valid JWT.
    """
    nuovo_elemento = item.model_dump(exclude_unset=True, exclude={'id'})
    nuovo_elemento['owner'] = current_user.username 

    try:
        risultato = ITEMS_COLLECTION.insert_one(nuovo_elemento)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"MongoDB insertion error: {e}")
    
    item.id = str(risultato.inserted_id)
    return item

@app.get(
    "/elementi/", 
    response_model=List[Item],
    tags=["Protected Operations (Items)"],
    summary="Get all items for the current user"
)
def ottieni_tutti_gli_elementi(current_user: UserInDB = Depends(get_current_user)):
    """
    Returns a list of all items created by the current user.
    Requires a valid JWT.
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
    tags=["Protected Operations (Items)"],
    summary="Get an item by ID"
)
def ottieni_elemento_per_id(item_id: str):
    """
    Returns a specific item by its MongoDB ObjectId.
    NOTE: This endpoint is NOT protected by JWT.
    """
    try:
        elemento = ITEMS_COLLECTION.find_one({"_id": ObjectId(item_id)})
        
        if elemento:
            return Item(
                id=str(elemento['_id']),
                nome=elemento['nome'],
                valore=elemento['valore']
            )
            
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
        
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ID format")