import os

GAME_HISTORY_URL = os.environ.get("GAME_HISTORY_URL", "https://game_history:5000/addmatch")
COLLECTION_URL = os.environ.get("COLLECTION_URL", "https://collection:5000/collection")
USER_MANAGER_URL = os.environ.get("USER_MANAGER_URL", "https://user_manager:5000")
USER_MANAGER_CERT = os.environ.get('USER_MANAGER_CERT', '/run/secrets/user_manager_cert')
COLLECTION_CERT = os.environ.get('COLLECTION_CERT', '/run/secrets/collection_cert')
HISTORY_CERT = os.environ.get('HISTORY_CERT', '/run/secrets/history_cert')
RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.environ.get("RABBITMQ_PORT", "5671"))
RABBITMQ_USER = os.environ.get("RABBITMQ_USER", "rabbitmq_user")
RABBITMQ_PASSWORD = os.environ.get("RABBITMQ_PASSWORD", "rabbitmq_password")
RABBITMQ_CERT_PATH = "/run/secrets/rabbitmq_cert"