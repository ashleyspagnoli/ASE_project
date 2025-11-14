# Librerie JWT e Hashing
from jose import JWTError, jwt

SECRET_KEY= "GUERRA_ASE_SECRET_KEY"
ALGORITHM= "HS256"


def get_id_from_token(token: str) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("id")
        if user_id is None:
            return "Wrong token"
        return user_id
    except JWTError:
        return "Wrong key"
    
def get_username_from_token(token: str) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("username")
        if user_id is None:
            return "Wrong token"
        return user_id
    except JWTError:
        return "Wrong key"