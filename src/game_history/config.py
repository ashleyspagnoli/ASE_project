import os

PAGE_SIZE = 10
# --- User Service ---
USER_MANAGER_URL = os.environ.get('USER_MANAGER_URL', 'https://user-manager:5000')
USERNAMES_BY_IDS_URL = f'{USER_MANAGER_URL}/users/usernames-by-ids'
USER_MANAGER_CERT = os.environ.get('USER_MANAGER_CERT', '/run/secrets/user_manager_cert')

# --- RabbitMQ broker ---
RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "rabbitmq")

# --- MongoDB ---
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://db-history:27017/")