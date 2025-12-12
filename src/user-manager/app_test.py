# tests/test_manager.py
import pytest
from unittest.mock import patch
from mongomock import MongoClient as MockMongoClient

# Sostituiamo il MongoClient di PyMongo con la versione Mock
@pytest.fixture(scope="module", autouse=True)
def mock_mongo_client():
    # Sostituisci la classe MongoClient nel modulo principale
    with patch('main.MongoClient', MockMongoClient):
        # Ritorna il controllo a Pytest per eseguire i test
        yield

def test_create_user_in_mock_db():
    """Testa la creazione di un utente usando il DB in memoria."""

    # Poiché MongoClient è mockato, main.client ora punta a un MongoMock client.
    # Devi pulire lo stato del DB tra i test se non usi una fixture di sessione.

    # Esegui le funzioni che usano USERS_COLLECTION
    user_data = {"username": "test", "password": "hash"}
    main.USERS_COLLECTION.insert_one(user_data)

    # Asserzioni
    assert main.USERS_COLLECTION.find_one({"username": "test"}) is not None