import os

PAGE_SIZE = 10
# --- User Service ---
USER_MANAGER_URL = os.environ.get('USER_MANAGER_URL', 'https://user-manager:5000')
USERNAMES_BY_IDS_URL = f'{USER_MANAGER_URL}/users/usernames-by-ids'
USER_MANAGER_CERT = os.environ.get('USER_MANAGER_CERT', '/run/secrets/user_manager_cert')

# --- RabbitMQ broker (SSL always enabled) ---
RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.environ.get("RABBITMQ_PORT", "5671"))
RABBITMQ_USER = os.environ.get("RABBITMQ_USER", "rabbitmq_user")
RABBITMQ_PASSWORD = os.environ.get("RABBITMQ_PASSWORD", "rabbitmq_password")
RABBITMQ_CERT_PATH = "/run/secrets/rabbitmq_cert"

# --- MongoDB ---
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://db-history:27017/")