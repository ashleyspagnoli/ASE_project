import utilities as utils
import app as main_app

# Mock di InsertOneResult
class MockInsertOneResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id

# Mock di DeleteResult
class MockDeleteResult:
    def __init__(self, deleted_count):
        self.deleted_count = deleted_count

# Mock del token validator
def mock_token_validator():
    return "test-user-123", "testUser"

# Mock della collection MongoDB
class MockCollection:
    def __init__(self):
        self.data = {}
        self.counter = 0
    
    def find(self, query):
        """Simula find() di MongoDB"""
        results = []
        for doc in self.data.values():
            if self._match_query(doc, query):
                results.append(doc.copy())
        return results
    
    def find_one(self, query):
        """Simula find_one() di MongoDB"""
        for doc in self.data.values():
            if self._match_query(doc, query):
                return doc.copy()
        return None
    
    def insert_one(self, doc):
        """Simula insert_one() di MongoDB"""
        self.counter += 1
        doc_id = f"mock_id_{self.counter}"
        doc['_id'] = doc_id
        self.data[doc_id] = doc.copy()
        
        return MockInsertOneResult(inserted_id=doc_id)
    
    def delete_one(self, query):
        """Simula delete_one() di MongoDB"""
        for doc_key, doc in list(self.data.items()):
            if self._match_query(doc, query):
                del self.data[doc_key]
                return MockDeleteResult(deleted_count=1)
        return MockDeleteResult(deleted_count=0)
    
    def _match_query(self, doc, query):
        """Helper per verificare se un documento corrisponde alla query"""
        for key, value in query.items():
            if doc.get(key) != value:
                return False
        return True

# Crea l'istanza del mock
mock_collection = MockCollection()

# Funzione che restituisce il mock
def mock_db_conn():
    return mock_collection

# Imposta i mock
utils.mock_token_validator = mock_token_validator
main_app.mock_db_conn = mock_db_conn

# Configura l'app per i test
flask_app = main_app.app