import requests
import json
from config import USERNAMES_BY_IDS_URL, USER_MANAGER_CERT, USER_MANAGER_URL

# Helper to get usernames for a list of UUIDs in one request
mock_get_usernames_by_ids = None
def get_usernames_by_ids(user_ids):
    """
    Fetch usernames for a list of user IDs via the user-manager endpoint
    GET /utenti/usernames-by-ids?id_list=<id>&id_list=<id2> ...
    """
    if mock_get_usernames_by_ids:
        return mock_get_usernames_by_ids(user_ids)

    try:
        # requests will serialize list params as repeated query params
        resp = requests.get(
            USERNAMES_BY_IDS_URL,
            params={'id_list': user_ids},
            timeout=5,
            verify=USER_MANAGER_CERT
        )
        if resp.status_code == 200:
            return resp.json() or []
        else:
            print(f"Error: usernames-by-ids returned {resp.status_code}: {resp.text}", flush=True)
            return []
    except requests.exceptions.ConnectionError as e:
        print(f"Warning: Could not connect to user-manager at {USERNAMES_BY_IDS_URL}. {e}", flush=True)
        return []
    except Exception as e:
        print(f"Warning: Error fetching usernames for ids {user_ids}. {e}", flush=True)
        return []

def associate_usernames_to_ids(user_ids):
    """
    Gets usernames using the get_username_by_ids function
    Returns a dict {id: username}
    """
    if not user_ids:
        return {}
    # Turn input into list
    user_ids = list(user_ids)

    data = get_usernames_by_ids(user_ids)

    mapping = {item.get('id'): item.get('username') for item in data if isinstance(item, dict)}
    # Ensure all ids present in mapping
    for uid in user_ids:
        mapping.setdefault(uid, "Unknown user")
    return mapping


# User Token Validation
mock_validate_user_token = None
def validate_user_token(token_header: str):
    """
    Contacts the user-manager (via HTTPS) to validate a JWT token.
    Returns (user_uuid, username) if the token is valid.
    Raises ValueError if the token is invalid or the service does not respond.
    """

    if not token_header:
        raise ValueError("Missing 'Authorization' header.")
    
    if mock_validate_user_token:
        return mock_validate_user_token(token_header)
    
    # The token_header is "Bearer eyJ...". We need to extract only the token "eyJ..."
    try:
        token_type, token = token_header.split(" ")
        if token_type.lower() != "bearer":
            raise ValueError("Invalid token type, 'Bearer' required.")
    except Exception:
        raise ValueError("Invalid 'Authorization' header format. Use 'Bearer <token>'.")

    # This is the endpoint defined in the user-manager
    validate_url = f"{USER_MANAGER_URL}/users/validate-token"

    try:
        # Sends the GET request with the token in the Authorization header
        response = requests.get(
            validate_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
            verify=USER_MANAGER_CERT  # <-- SSL certificate verification
        )

        # If user-manager responds with 401, 403, 404, etc., raise an error
        response.raise_for_status()

        user_data = response.json()

        # The /users/validate-token endpoint returns 'id' and 'username'
        user_uuid = user_data.get("id")
        username = user_data.get("username")

        if not user_uuid:
            raise ValueError("Incomplete user data from validation service")

        print(f"Token successfully validated for user: {user_uuid}", flush=True)
        return user_uuid, username

    except requests.RequestException as e:
        # Connection error or 4xx/5xx response from user service
        error_detail = f"Unable to validate user. Connection error to {validate_url}."
        if e.response:
            try:
                # Try to read 'detail' from the FastAPI error
                error_detail = e.response.json().get('detail', 'Unknown error from User-Manager')
            except json.JSONDecodeError:
                error_detail = e.response.text

        print(f"Token validation ERROR: {error_detail}")
        # Raises a ValueError that the controller (routes.py) will convert to 401
        raise ValueError(f"User Service: {error_detail}")
