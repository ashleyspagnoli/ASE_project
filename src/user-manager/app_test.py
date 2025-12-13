import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import HTTPException, status
from bson import ObjectId
from datetime import datetime, timedelta
from passlib.context import CryptContext
import hashlib

# Importa il tuo modulo principale (Auth MS)
# Assumi che il codice fornito sia in 'main.py' nella directory 'user-manager'
import main 

# Crea un client di test per l'applicazione FastAPI
client = TestClient(main.app)

# Dati Mock per tutti i test
MOCK_OBJECT_ID = "60a1b2c3d4e5f6a7b8c9d0e1"
MOCK_USER_CLEARTEXT = "testuser"
MOCK_EMAIL_CLEARTEXT = "test@example.com"
MOCK_PASSWORD_PLAINTEXT = "securepass123"
MOCK_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0dXNlciIsImlkIjoiNjBhMWIyYzNkNGU1ZjZhN2I4YzlkMGUxIiwiaXNzIjoic2VydmVyIn0.S9Fw9ZtG_i8k4q7Q6T7L3d5J7M1O8Y3K9N5H0vA9X3E"

# Dati che useremo per simulare il record nel DB (già hash/encrypted)
MOCK_USER_DB_DATA = {
    "_id": ObjectId(MOCK_OBJECT_ID),
    "username": "encrypted_testuser",
    "email": "encrypted_test@example.com",
    "hashed_password": "hashed_password_mock",
    "hashed_username": "hashed_testuser",
    "hashed_email": "hashed_test@example.com",
}

# Oggetto UserInDB (dopo decrypt/mapping)
MOCK_USER_IN_DB = main.UserInDB(
    id=MOCK_OBJECT_ID,
    username=MOCK_USER_CLEARTEXT,
    email=MOCK_EMAIL_CLEARTEXT,
    hashed_password=MOCK_USER_DB_DATA["hashed_password"],
    hashed_username=MOCK_USER_DB_DATA["hashed_username"],
    hashed_email=MOCK_USER_DB_DATA["hashed_email"],
)

# --- FIXTURES PER IL MOCKING DEL DATABASE ---


import pytest
from unittest.mock import patch, MagicMock
from cryptography.fernet import Fernet # O la tua libreria di crittografia
# Devi importare le funzioni reali (qui assumiamo che vengano da main.crypto)
import main
from main import hash_search_key, get_password_hash, verify_password, SECRET_KEY 
# Assumi che le funzioni encrypt/decrypt siano qui per semplicità
from crypto import encrypt_data, decrypt_data 

# Dati di test
TEST_DATA = "data_to_be_encrypted"
TEST_PASSWORD = "PasswordSicura123"

# --- Test Crittografia (Necessita della SECRET_KEY) ---

@pytest.fixture(scope="module", autouse=True)

def mock_secret_key():
    """Garantisce che la chiave segreta sia caricata per i test di crittografia reali."""
    # Simula una chiave segreta valida (ad esempio, una chiave Fernet)
    test_key = Fernet.generate_key().decode()
    with patch('main.SECRET_KEY', test_key):
         yield

def test_encryption_decryption_integrity(mock_secret_key):
    """Verifica che la decrittografia ripristini i dati originali."""
    
    encrypted = encrypt_data(TEST_DATA)
    decrypted = decrypt_data(encrypted)
    
    # Asserzioni
    assert encrypted != TEST_DATA, "I dati non sono stati cifrati (dovrebbero essere diversi)."
    assert decrypted == TEST_DATA, "La decrittografia non ha funzionato correttamente."


# --- Test Hashing ---

def test_hash_search_key_consistency():
    """Verifica che l'hashing sia coerente e insensibile alle maiuscole/minuscole."""
    
    hash1 = hash_search_key("TestUser@example.com")
    hash2 = hash_search_key("testuser@example.com")
    
    # Asserzioni
    assert hash1 == hash2, "L'hashing di ricerca deve essere insensibile alle maiuscole/minuscole."
    assert len(hash1) == 64, "L'hash SHA-256 deve avere una lunghezza di 64 caratteri."

# --- Test Password Hashing ---

def test_password_hashing_verification():
    """Verifica che l'hashing Argon2 funzioni e che la verifica sia corretta."""
    
    hashed_pass = get_password_hash(TEST_PASSWORD)
    
    # Asserzioni
    assert hashed_pass != TEST_PASSWORD, "La password non è stata hashata."
    assert verify_password(TEST_PASSWORD, hashed_pass), "La verifica della password deve riuscire."
    assert not verify_password("wrong_password", hashed_pass), "La verifica deve fallire con password errata."


# Mock di tutte le interazioni con le collezioni (USO PRINCIPALE)
@pytest.fixture
def mock_users_collection(mocker):
    """Mocka la collezione MongoDB USERS_COLLECTION."""
    # Sostituisce l'oggetto USERS_COLLECTION con un MagicMock che simula i metodi di PyMongo
    return mocker.patch('main.USERS_COLLECTION')

# Mock delle funzioni critiche di crittografia/hashing
@pytest.fixture(autouse=True) # Esegue automaticamente per tutti i test
def mock_crypto(mocker):
    """Mocka le funzioni di hashing e crittografia."""
    # Crittografia
    mocker.patch('main.encrypt_data', return_value="encrypted_value")
    mocker.patch('main.decrypt_data', side_effect=lambda x: MOCK_USER_CLEARTEXT if x == MOCK_USER_DB_DATA["username"] else MOCK_EMAIL_CLEARTEXT)
    
    # Hashing
    mocker.patch('main.hash_search_key', return_value="hashed_value")
    mocker.patch('main.get_password_hash', return_value="new_hashed_password")
    mocker.patch('main.verify_password', return_value=True) # Assume che la password sia corretta
    
    # JWT
    mocker.patch('main.create_access_token', return_value="mock_jwt_token")


# --- TEST DELLE FUNZIONI DI SICUREZZA E DI SUPPORTO ---

def test_get_user_found(mock_users_collection, mocker):
    """Testa la ricerca di un utente esistente nel DB."""
    
    # Configura il mock per ritornare il record DB fittizio
    mock_users_collection.find_one.return_value = MOCK_USER_DB_DATA
    
    # Mocka la decrittografia per ritornare i valori in chiaro
    mocker.patch('main.decrypt_data', side_effect=lambda x: MOCK_USER_CLEARTEXT if 'user' in x else MOCK_EMAIL_CLEARTEXT)
    mocker.patch('main.hash_search_key', return_value=MOCK_USER_DB_DATA["hashed_username"])

    user = main.get_user(MOCK_USER_CLEARTEXT)
    
    # Asserzioni
    assert user is not None
    assert user.username == MOCK_USER_CLEARTEXT
    assert user.id == MOCK_OBJECT_ID
    mock_users_collection.find_one.assert_called_once_with({"hashed_username": MOCK_USER_DB_DATA["hashed_username"]})


def test_get_user_not_found(mock_users_collection):
    """Testa la ricerca di un utente non esistente."""
    mock_users_collection.find_one.return_value = None
    user = main.get_user("nonexistent_user")
    assert user is None

# --- TEST DEGLI ENDPOINT DI AUTENTICAZIONE E REGISTRAZIONE ---
# --- REGISTRAZIONE TESTS -------------
# Mocka la dipendenza di PyMongo che è un blocco top-level
@patch('main.USERS_COLLECTION', new_callable=MagicMock)
def test_register_user_success(mock_users_collection, mocker):
    """Testa la registrazione di un nuovo utente con successo."""
    
    # Configura find_one per ritornare None (nessun duplicato)
    mock_users_collection.find_one.return_value = None
    
    new_user_data = main.UserCreate(
        username=MOCK_USER_CLEARTEXT, 
        password=MOCK_PASSWORD_PLAINTEXT, 
        email=MOCK_EMAIL_CLEARTEXT
    )
    
    response = client.post("/users/register", json=new_user_data.model_dump())
    
    # Asserzioni
    assert response.status_code == 201
    assert response.json()["username"] == MOCK_USER_CLEARTEXT
    
    # Verifica che sia stata chiamata insert_one
    mock_users_collection.insert_one.assert_called_once()
    
    # Verifica il controllo dei duplicati
    assert mock_users_collection.find_one.call_count == 3 

@patch('main.USERS_COLLECTION', new_callable=MagicMock)
def test_register_user_duplicate_username(mock_users_collection):
    """Testa il fallimento della registrazione per username duplicato."""
    
    # Configura find_one per ritornare un record (duplicato trovato)
    mock_users_collection.find_one.return_value = MOCK_USER_DB_DATA
    
    new_user_data = main.UserCreate(
        username=MOCK_USER_CLEARTEXT, 
        password=MOCK_PASSWORD_PLAINTEXT, 
        email=MOCK_EMAIL_CLEARTEXT
    )
    
    response = client.post("/users/register", json=new_user_data.model_dump())
    
    # Asserzioni
    assert response.status_code == 400
    assert "Username already registered" in response.json()["detail"]

# LOGIN TESTS-------------

@patch('main.authenticate_user', return_value=MOCK_USER_IN_DB)
def test_login_for_access_token_success(mock_auth):
    """Testa l'endpoint OAuth2 standard (usato da Swagger)."""
    
    response = client.post(
        "/token", 
        # I dati devono essere passati come form-data per OAuth2PasswordRequestForm
        data={"username": MOCK_USER_CLEARTEXT, "password": MOCK_PASSWORD_PLAINTEXT}
    )
    
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"] == "mock_jwt_token"

# testa il fallimento del login
@patch('main.authenticate_user', return_value=None)
def test_login_for_access_token_failure(mock_auth):
    """Testa il fallimento del login con credenziali errate."""
    
    response = client.post(
        "/token", 
        data={"username": MOCK_USER_CLEARTEXT, "password": "wrong_password"}
    )
    
    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]

# --- TEST DEGLI ENDPOINT INTERNI (S2S) ---

@patch('main.get_user_from_local_token', return_value=MOCK_USER_IN_DB)
def test_validate_token_internal_success(mock_get_user):
    """Testa l'endpoint che convalida il token e ritorna i dati utente per i servizi."""
    
    # Viene chiamato da un altro servizio che usa il token JWT
    response = client.get(
        "/users/validate-token", 
        # Necessario l'header per OAuth2PasswordBearer
        headers={"Authorization": f"Bearer {MOCK_TOKEN}"} 
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == MOCK_OBJECT_ID
    assert data["username"] == MOCK_USER_CLEARTEXT


@patch('main.USERS_COLLECTION', new_callable=MagicMock)
def test_get_usernames_by_ids_success(mock_users_collection, mocker):
    """Testa il recupero di username da una lista di ID (Query Parameter)."""

    mock_users_collection.find.return_value = [
        {"_id": ObjectId(MOCK_OBJECT_ID), "username": "encrypted_testuser_1"},
        {"_id": ObjectId("60a1b2c3d4e5f6a7b8c9d0e2"), "username": "encrypted_testuser_2"},
    ]
    
    # Mock della decrittografia
    mocker.patch('main.decrypt_data', side_effect=["testuser_1", "testuser_2"])
    
    response = client.get(
        "/users/usernames-by-ids", 
        params={"id_list": [MOCK_OBJECT_ID, "60a1b2c3d4e5f6a7b8c9d0e2"]}
    )
    
    assert response.status_code == 200
    assert len(response.json()) == 2
    assert response.json()[0]["username"] == "testuser_1" # Controlla che la decrittografia sia avvenuta

# --- TEST AGGIORNAMENTO UTENTE INTERNO (ENDPOINT CRITICO) ---

@patch('main.USERS_COLLECTION', new_callable=MagicMock)
@patch('main.verify_internal_token', return_value=True) # Bypass token S2S
@patch('main.get_current_user', return_value=MOCK_USER_IN_DB) # Utente autorizzato
def test_update_user_username_success(mock_get_user, mock_internal_token, mock_users_collection):
    """Testa l'aggiornamento solo dell'username."""

    # Dati DB iniziali (per current_record)
    mock_users_collection.find_one.return_value = MOCK_USER_DB_DATA
    
    # Configurazione per check duplicati (deve ritornare None la seconda volta)
    mock_users_collection.find_one.side_effect = [
        MOCK_USER_DB_DATA, # Prima chiamata: trova l'utente attuale
        None,             # Seconda chiamata: check duplicati per il nuovo username (successo)
    ]
    
    # Mock della risposta update_one
    mock_users_collection.update_one.return_value = MagicMock(modified_count=1)

    payload = main.UserUpdateInternal(username="new_username_cleartext")
    
    response = client.post(
        "/internal/update-user", 
        json=payload.model_dump(),
        headers={"Authorization": "Bearer internal_service_token"} 
    )
    
    assert response.status_code == 200
    assert "updated successfully" in response.json()["message"]
    mock_users_collection.update_one.assert_called_once()
    
    # Verifica che i campi crittografati e hashati siano stati usati nell'aggiornamento
    # Si aspetta che i valori siano quelli mockati: "encrypted_value" e "hashed_value"
    update_call_args = mock_users_collection.update_one.call_args[0][1]["$set"]
    assert update_call_args["username"] == "encrypted_value"
    assert update_call_args["hashed_username"] == "hashed_value"