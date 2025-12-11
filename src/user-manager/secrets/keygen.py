import secrets
import base64

# Genera 32 byte di casualità crittograficamente sicura
secure_bytes = secrets.token_bytes(32)

# Codifica in Base64 per facilità d'uso nel file di configurazione
# (Molti sistemi, come JWT, preferiscono le chiavi Base64)
secure_key_base64 = base64.urlsafe_b64encode(secure_bytes).decode()

print("La tua chiave JWT sicura (32 byte / 256 bit in Base64):")
print(secure_key_base64)