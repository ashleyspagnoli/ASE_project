# mock_mongo.py

from bson import ObjectId
from typing import Dict, Any, List, Optional
from unittest.mock import MagicMock


# --- Classi per simulare i risultati di PyMongo ---

class MockInsertOneResult:
    """Simula il risultato di collection.insert_one()."""
    def __init__(self, inserted_id: ObjectId):
        self.inserted_id = inserted_id

class MockUpdateResult:
    """Simula il risultato di collection.update_one()."""
    def __init__(self, modified_count: int):
        self.modified_count = modified_count
    
    # Utile per usare il mock direttamente dove è atteso un oggetto risultato
    def __call__(self):
        return self

class MockDeleteResult:
    """Simula il risultato di collection.delete_many()."""
    def __init__(self, deleted_count: int):
        self.deleted_count = deleted_count
    
    def __call__(self):
        return self

# --- Classe Principale per simulare la Collezione MongoDB ---

class MockCollection:
    """Simula una singola collezione MongoDB (es. USERS_COLLECTION)."""
    
    def __init__(self, name: str):
        self.name = name
        # Il dizionario in-memory che memorizza i documenti
        self.data: Dict[str, Dict[str, Any]] = {}
        self._current_id_counter = 0

    def _match_query(self, doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
        """Helper che implementa la logica di base del matching delle query."""
        
        for key, value in query.items():
            doc_value = doc.get(key)
            
            # Gestione della query per ObjectId (_id)
            if key == '_id':
                # Convertiamo entrambi in stringa per un confronto robusto nel mock
                if str(doc_value) != str(value):
                    return False
            
            # Gestione degli operatori di query
            elif isinstance(value, dict):
                # Operatore $ne (Not Equal)
                if '$ne' in value:
                    if doc_value == value['$ne']:
                        return False
                # Operatore $in (In List)
                elif '$in' in value:
                    if doc_value not in value['$in']:
                        return False
                # Aggiungi altri operatori ($gt, $lt, ecc.) se necessario
            
            # Matching diretto (es. {"username": "test"})
            elif doc_value != value:
                return False
                
        return True

    # Aggiungi questo metodo alla tua classe MockCollection


# ... (I tuoi metodi esistenti come find, insert_one, ecc.) ...

    def find_one(self, query: Optional[Dict[str, Any]] = None, projection: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Simula collection.find_one().
        Restituisce il primo documento che corrisponde alla query, o None.
        """
        if query is None:
            query = {}
        
        # 1. Utilizza il tuo metodo _match_query (o find) per trovare le corrispondenze
        # Per semplicità e coerenza, replichiamo la logica di find, 
        # ma fermandoci al primo match.
        
        for doc in self.data.values():
            if self._match_query(doc, query):
                # Trovato il primo match, lo restituiamo immediatamente
                
                # [Opzionale] Potresti applicare la 'projection' qui, 
                # ma per i mock di base, restituire il doc completo va bene.
                return doc.copy()
                
        # Se il loop finisce senza trovare corrispondenze
        return None

# Il tuo metodo find() dovrebbe rimanere come prima, se restituisce una lista/cursore
# def find(self, query: Dict[str, Any] = None, projection: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
#     # ...

    def find(self, query: Dict[str, Any] = None, projection: Optional[Dict[str, Any]] = None):
        """Simula collection.find(), restituendo una lista di documenti (simula un cursore)."""
        
        # 🟢 Correzione: Se la query è None (chiamata senza argomenti), usa {}
        if query is None:
            query = {}
            
        results = []
        for doc in self.data.values():
            if self._match_query(doc, query):
                results.append(doc.copy())
        return results

    def insert_one(self, doc: Dict[str, Any]) -> MockInsertOneResult:
        """Simula collection.insert_one()."""
        
        if '_id' not in doc:
            new_id = ObjectId()
            doc['_id'] = new_id
        else:
            new_id = doc['_id']
        
        self.data[str(new_id)] = doc.copy()
        return MockInsertOneResult(inserted_id=new_id)

    def update_one(self, query: Dict[str, Any], update: Dict[str, Any]) -> MockUpdateResult:
        """Simula collection.update_one(). Supporta solo $set."""
        
        modified_count = 0
        
        for doc_key, doc in self.data.items():
            if self._match_query(doc, query):
                
                # Applica solo l'operatore $set per semplicità
                if '$set' in update:
                    self.data[doc_key].update(update['$set'])
                    modified_count += 1
                
                # MongoDB si ferma al primo match per update_one
                return MockUpdateResult(modified_count=modified_count)

        return MockUpdateResult(modified_count=0)
    
    def delete_many(self, query: Dict[str, Any]) -> MockDeleteResult:
        """Simula collection.delete_many()."""
        deleted_count = 0
        keys_to_delete = []
        
        # Identifica le chiavi da eliminare
        for doc_key, doc in self.data.items():
            if self._match_query(doc, query):
                keys_to_delete.append(doc_key)
        
        # Elimina i documenti
        for key in keys_to_delete:
            del self.data[key]
            deleted_count += 1
            
        return MockDeleteResult(deleted_count=deleted_count)
        
    def reset_data(self):
        """Svuota la collezione per un nuovo test."""
        self.data = {}
        self._current_id_counter = 0

# --- Classe per simulare il Database MongoDB ---

class MockDatabase:
    """Simula un database MongoDB (db = client.get_database(DB_NAME))."""
    
    def __init__(self, name: str):
        self.name = name
        # Dizionario per memorizzare le istanze delle collezioni (mockate)
        self._collections: Dict[str, MockCollection] = {}

    def __getitem__(self, collection_name: str) -> MockCollection:
        """Permette l'accesso come db['collection_name']."""
        if collection_name not in self._collections:
            # Crea e memorizza l'istanza se non esiste
            self._collections[collection_name] = MockCollection(collection_name)
        return self._collections[collection_name]
    
    def reset_all_collections(self):
        """Svuota i dati in tutte le collezioni create."""
        for collection in self._collections.values():
            collection.reset_data()

# --- Classe per simulare il MongoClient ---

class MockClient:
    """Simula il MongoClient (client = MongoClient(URI))."""
    
    def __init__(self):
        self._databases: Dict[str, MockDatabase] = {}
        # Usiamo un MagicMock per simulare il client stesso
        self.admin = MagicMock() 

    def get_database(self, db_name: str) -> MockDatabase:
        """Simula client.get_database(DB_NAME)."""
        if db_name not in self._databases:
            self._databases[db_name] = MockDatabase(db_name)
        return self._databases[db_name]

    def server_info(self):
        """Simula client.server_info() (il controllo di connessione)."""
        # Ritorna un valore atteso per simulare il successo della connessione
        return {"version": "5.0.0", "ok": 1}
    
    def close(self):
        """Simula client.close()."""
        pass

# --- FUNZIONE UTILITY PER IL TUO MAIN.PY ---

def get_mock_client() -> MockClient:
    """Restituisce un'istanza singleton (o quasi) del MockClient."""
    # Se devi mantenere lo stato tra i moduli, usa una variabile globale qui
    return MockClient()

# --- Esempio di Uso (Non parte del modulo, solo per testare la classe) ---
if __name__ == '__main__':
    client_mock = get_mock_client()
    db_mock = client_mock.get_database("test_db")
    utenti_col = db_mock["utenti"]
    
    # 1. Test Inserimento
    res = utenti_col.insert_one({"username": "mario", "età": 30})
    print(f"Inserito ID: {res.inserted_id}")
    
    # 2. Test Ricerca
    user = utenti_col.find_one({"username": "mario"})
    print(f"Trovato: {user}")
    
    # 3. Test Aggiornamento
    update_res = utenti_col.update_one({"username": "mario"}, {"$set": {"età": 31}})
    print(f"Modificati: {update_res.modified_count}")
    print(f"Dopo update: {utenti_col.find_one({'username': 'mario'})}")
    
    # 4. Test Eliminazione
    delete_res = utenti_col.delete_many({"età": 31})
    print(f"Eliminati: {delete_res.deleted_count}")
    print(f"Dopo delete: {utenti_col.find_one({'username': 'mario'})}")