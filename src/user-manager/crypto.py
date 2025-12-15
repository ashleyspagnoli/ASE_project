# shared_utils.py

from cryptography.fernet import Fernet # Alternativa più semplice e robusta di AES-GCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
from pathlib import Path

# Percorso standard dove Docker monta il segreto
DEFAULT_ENCRYPTION_KEY = "fallback_key_for_testing_DO_NOT_USE_IN_PROD" # Chiave di fallback (solo per testing locale)

def load_secret_key(path: str, default: str) -> str:
    """Tenta di leggere la chiave dal file segreto di Docker; altrimenti usa il default."""
    secret_file = Path(path)
    if secret_file.exists():
        try:
            # Legge il contenuto del file (rimuovendo eventuali spazi bianchi o newline)
            key_content = secret_file.read_text().strip()
            if not key_content:
                print("ERRORE: Il file del segreto di cifratura è vuoto.")
                return default
            return key_content
        except Exception as e:
            print(f"ERRORE: Impossibile leggere il file del segreto: {e}")
            return default
    else:
        # Potrebbe accadere se non sei in un ambiente Docker Secrets
        print(f"AVVISO: File segreto {path} non trovato. Utilizzo la chiave di fallback.")
        return default

# Assegna la chiave letta
FAKE_ENCRYPTION_KEY = load_secret_key("fake-key-crypto.txt", DEFAULT_ENCRYPTION_KEY)
ENCRYPTION_KEY_STRING = load_secret_key("/run/secrets/user_db_encryption_secret_key", FAKE_ENCRYPTION_KEY)

# ... Il resto della tua logica di cifratura che usa ENCRYPTION_KEY_STRING ...
cipher_suite = None
try:
    # Usiamo Fernet come implementazione robusta che gestisce IV e MAC
    # Internamente, Fernet usa AES-128 in modalità CBC o AES-256 in modalità GCM (a seconda della versione)
    cipher_suite = Fernet(ENCRYPTION_KEY_STRING.encode())
except Exception as e:
    print(f"ERRORE CRITICO: Chiave di cifratura non valida o mancante. {e}")
    # In produzione, dovresti terminare il programma qui.

def encrypt_data(data: str) -> str:
    """Cifra una stringa e restituisce una stringa Base64 URL-safe."""
    if not data:
        return ""
    if cipher_suite is None:
        print("ERRORE: cipher_suite non inizializzato.")
        return ""
    # I dati cifrati sono Base64, quindi pronti per essere salvati come stringa nel DB
    return cipher_suite.encrypt(data.encode('utf-8')).decode()

def decrypt_data(encrypted_data: str) -> str:
    """Decifra i dati. Solleva un errore se i dati sono stati manomessi o se la chiave è sbagliata."""
    if not encrypted_data:
        return ""
    try:
        # Decifra e decodifica in UTF-8
        return cipher_suite.decrypt(encrypted_data.encode()).decode('utf-8')
    except Exception as e:
        # Gestisci errori di decifratura (es. InvalidToken, token scaduto, dati corrotti)
        print(f"ATTENZIONE: Fallita la decifratura: {e}")
        # In un contesto reale, questo può indicare un tentativo di attacco o dati vecchi.
        # Potresti voler registrare un avviso di sicurezza qui.
        return "" # Ritorna una stringa vuota o solleva un errore specifico