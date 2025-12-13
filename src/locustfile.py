from locust import HttpUser, task, between, SequentialTaskSet
import random
import json
import urllib3

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class UserBehavior(SequentialTaskSet):
    """Sequential task set simulating a complete user journey"""
    
    def on_start(self):
        """Initialize user session data"""
        self.token = None
        self.username = f"loadtest_user_{random.randint(10000, 99999)}"
        self.password = "TestPass123!"
        self.game_id = None
        self.deck_slot = 1
        self.hand = []
        
    @task
    def register_user(self):
        """Register a new user"""
        response = self.client.post(
            "/users/register",
            json={
                "username": self.username,
                "password": self.password,
                "email": f"{self.username}@loadtest.com"
            },
            verify=False,
            name="POST /users/register",
            catch_response=True
        )
        
        if response.status_code == 201:
             response.success()
        elif response.status_code == 400: # Username already exists → acceptable
            response.success()
        else:
            response.failure(f"Unexpected status {response.status_code}")
    
    @task
    def login_user(self):
        """Login and obtain JWT token"""
        response = self.client.post(
            "/users/login",
            json={
                "username": self.username,
                "password": self.password
            },
            verify=False,
            name="POST /users/login"
        )
        
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("token")
            print(f"✓ User {self.username} logged in")
        else:
            print(f"✗ Login failed for {self.username}: {response.status_code}")
            self.interrupt()  # Stop this user's tasks
    
    @task
    def get_all_cards(self):
        """Retrieve all available cards"""
        if not self.token:
            return
            
        response = self.client.get(
            "/collection/cards",
            headers={"Authorization": f"Bearer {self.token}"},
            verify=False,
            name="GET /collection/cards"
        )
        
        if response.status_code == 200:
            print(f"✓ Retrieved cards collection")
    
    @task
    def create_deck(self):
        """Create a new deck"""
        if not self.token:
            return
        
        # Valid deck: 2 cards per suit, max 15 points per suit
        cards = [
            "hA", "h5",  # hearts: 7+5=12
            "d5", "dK",  # diamonds: 5+13=18 -> Need to fix
            "c7", "c8",  # clubs: 7+8=15
            "sA", "s5"   # spades: 7+5=12
        ]
        
        # Fix diamonds to be valid (max 15 points)
        cards = [
            "hA", "h5",  # hearts: 7+5=12
            "d5", "d8",  # diamonds: 5+8=13
            "c7", "c8",  # clubs: 7+8=15
            "sA", "s5"   # spades: 7+5=12
        ]
        
        response = self.client.post(
            "/collection/decks",
            headers={"Authorization": f"Bearer {self.token}"},
            json={
                "deckSlot": self.deck_slot,
                "deckName": f"Test Deck {self.deck_slot}",
                "cards": cards
            },
            verify=False,
            name="POST /collection/decks"
        )
        
        if response.status_code == 201:
            print(f"✓ Created deck in slot {self.deck_slot}")
    
    @task
    def get_user_decks(self):
        """Retrieve user's decks"""
        if not self.token:
            return
            
        response = self.client.get(
            "/collection/decks",
            headers={"Authorization": f"Bearer {self.token}"},
            verify=False,
            name="GET /collection/decks"
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Retrieved {data.get('total', 0)} decks")
    
    @task
    def join_matchmaking(self):
        """Join matchmaking queue"""
        if not self.token:
            return
            
        response = self.client.post(
            "/game/match/join",
            headers={"Authorization": f"Bearer {self.token}"},
            verify=False,
            name="POST /game/match/join"
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "matched":
                self.game_id = data.get("game_id")
                print(f"✓ Matched! Game ID: {self.game_id}")
            else:
                print(f"⏳ Waiting for opponent...")
    
    @task
    def check_matchmaking_status(self):
        """Check matchmaking status"""
        if not self.token or self.game_id:
            return
            
        response = self.client.get(
            "/game/match/status",
            headers={"Authorization": f"Bearer {self.token}"},
            verify=False,
            name="GET /game/match/status"
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "matched":
                self.game_id = data.get("game_id")
                print(f"✓ Match found! Game ID: {self.game_id}")
    
    @task
    def select_deck_for_game(self):
        """Select deck for the game"""
        if not self.token or not self.game_id:
            return
            
        response = self.client.post(
            f"/game/deck/{self.game_id}",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"deck_slot": self.deck_slot},
            verify=False,
            name="POST /game/deck/{game_id}"
        )
        
        if response.status_code == 200:
            print(f"✓ Deck selected for game")
    
    @task
    def get_hand(self):
        """Get current hand"""
        if not self.token or not self.game_id:
            return
            
        response = self.client.get(
            f"/game/hand/{self.game_id}",
            headers={"Authorization": f"Bearer {self.token}"},
            verify=False,
            name="GET /game/hand/{game_id}"
        )
        
        if response.status_code == 200:
            self.hand = response.json()
            print(f"✓ Hand retrieved: {len(self.hand)} cards")
    
    @task
    def play_card(self):
        """Play a random card from hand"""
        if not self.token or not self.game_id or not self.hand:
            return
            
        card = random.choice(self.hand)
        
        response = self.client.post(
            f"/game/play/{self.game_id}",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"card": card},
            verify=False,
            name="POST /game/play/{game_id}"
        )
        
        if response.status_code == 200:
            data = response.json()
            status = data.get("status")
            print(f"✓ Card played: {card}, Status: {status}")
            
            if status == "finished":
                print(f"🏁 Game finished! Winner: {data.get('match_winner')}")
                self.game_id = None  # Reset for next game
    
    @task
    def get_game_state(self):
        """Get current game state"""
        if not self.token or not self.game_id:
            return
            
        response = self.client.get(
            f"/game/state/{self.game_id}",
            headers={"Authorization": f"Bearer {self.token}"},
            verify=False,
            name="GET /game/state/{game_id}"
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Game state: Turn {data.get('turn_number')}")
    
    @task
    def get_match_history(self):
        """Retrieve match history"""
        if not self.token:
            return
            
        response = self.client.get(
            "/history/matches?page=0",
            headers={"Authorization": f"Bearer {self.token}"},
            verify=False,
            name="GET /history/matches"
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Retrieved match history: {len(data)} matches")
    
    @task
    def get_leaderboard(self):
        """Retrieve leaderboard"""
        response = self.client.get(
            "/history/leaderboard?page=0",
            verify=False,
            name="GET /history/leaderboard"
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Retrieved leaderboard: {len(data)} entries")


class QuickUser(HttpUser):
    """Simulates quick users (fast registration, minimal interaction)"""
    tasks = [UserBehavior]
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    
    # Disable SSL verification for self-signed certificates
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client.verify = False
        # Suppress only the InsecureRequestWarning
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class NormalUser(HttpUser):
    """Simulates normal users (balanced interaction)"""
    tasks = [UserBehavior]
    wait_time = between(3, 7)  # Wait 3-7 seconds between tasks
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client.verify = False
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class SlowUser(HttpUser):
    """Simulates slow users (thoughtful gameplay)"""
    tasks = [UserBehavior]
    wait_time = between(5, 15)  # Wait 5-15 seconds between tasks
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client.verify = False
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# Realistic workflow tasks with proper weights
class RealisticUserWorkflow(SequentialTaskSet):
    """More realistic user behavior with weighted task distribution"""
    
    def on_start(self):
        self.token = None
        self.username = f"user_{random.randint(10000, 99999)}"
        self.password = "Pass123!"
        self.game_id = None
        
        # Register and login
        self._register_and_login()
    
    def _register_and_login(self):
        """Helper to register and login"""
        # Try registration (ignora il risultato, tanto faremo login)
        self.client.post(
            "/users/register",
            json={
                "username": self.username,
                "password": self.password,
                "email": f"{self.username}@test.com"
            },
            verify=False
        )
        
        # Login (funziona sia per nuovi utenti che esistenti)
        login_response = self.client.post(
            "/users/login",
            json={
                "username": self.username,
                "password": self.password
            },
            verify=False
        )
        
        if login_response.status_code == 200:
            self.token = login_response.json().get("token")
    
    @task(10)  # High weight - users check cards often
    def browse_cards(self):
        """Browse card collection"""
        if not self.token:
            return
        
        self.client.get(
            "/collection/cards",
            headers={"Authorization": f"Bearer {self.token}"},
            verify=False,
            name="Browse Cards"
        )
    
    @task(3)  # Medium weight - deck management
    def manage_decks(self):
        """View and create decks"""
        if not self.token:
            return
        
        # View existing decks
        self.client.get(
            "/collection/decks",
            headers={"Authorization": f"Bearer {self.token}"},
            verify=False,
            name="View Decks"
        )
        
        # Sometimes create a new deck
        if random.random() < 0.3:  # 30% chance
            cards = ["hA", "h5", "d5", "d8", "c7", "c8", "sA", "s5"]
            self.client.post(
                "/collection/decks",
                headers={"Authorization": f"Bearer {self.token}"},
                json={
                    "deckSlot": random.randint(1, 5),
                    "deckName": f"Deck {random.randint(1, 100)}",
                    "cards": cards
                },
                verify=False,
                name="Create Deck"
            )
    
    @task(5) 
    def play_game(self):
        """Join and play a game"""
        if not self.token:
            return
        
        # Join matchmaking
        match_response = self.client.post(
            "/game/match/join",
            headers={"Authorization": f"Bearer {self.token}"},
            verify=False,
            name="Join Matchmaking"
        )
        
        if match_response.status_code == 200:
            data = match_response.json()
            if data.get("status") == "matched":
                self.game_id = data.get("game_id")
                self._play_match()
    
    def _play_match(self):
        """Play a complete match"""
        if not self.game_id:
            return
        
        # Select deck
        response = self.client.post(
            f"/game/deck/{self.game_id}",
            headers=headers,
            json={"deck_slot": 1},
            verify=False,
            name="Select Deck",
            catch_response=True
        )

        if response.status_code == 200:
            response.success()
        elif response.status_code == 401: # Not my turn
            response.success()
            return
        else:
            response.failure(
                f"Unexpected Select Deck status {response.status_code}"
            )
            return
        
        # Play some turns
        for _ in range(random.randint(3, 8)):
            # Get hand
            hand_response = self.client.get(
                f"/game/hand/{self.game_id}",
                headers={"Authorization": f"Bearer {self.token}"},
                verify=False,
                name="Get Hand"
            )
            
            if hand_response.status_code == 200:
                hand = hand_response.json()
                if hand:
                    # Play random card
                    card = random.choice(hand)
                    response = self.client.post(
                        f"/game/play/{self.game_id}",
                        headers=headers,
                        json={"card": card},
                        verify=False,
                        name="Play Card",
                        catch_response=True
                    )

                    if response.status_code == 200:
                        response.success()
                        status = play_response.json().get("status")
                        if status == "finished":
                            break
                    elif response.status_code == 401: # Not my turn
                        response.success()
                    else:
                        response.failure(
                            f"Unexpected Play Card status {response.status_code}"
                        )
    
    @task(2)  # Lower weight - checking stats
    def check_history(self):
        """Check match history and leaderboard"""
        if not self.token:
            return
        
        self.client.get(
            "/history/matches?page=0",
            headers={"Authorization": f"Bearer {self.token}"},
            verify=False,
            name="Check History"
        )
        
        self.client.get(
            "/history/leaderboard?page=0",
            verify=False,
            name="Check Leaderboard"
        )


class RealisticUser(HttpUser):
    """User with realistic behavior patterns"""
    tasks = [RealisticUserWorkflow]
    wait_time = between(2, 8)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client.verify = False
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    
# Usage:
# 1) If you don't have locust installed
#   1.1) Create the venv if you don't have it yet: python -m venv proj_env
#   1.2) Activate the venv: 

#   1.3) Install locust: pip install locust
# 2) Run locust: locust
# 3) Browse to http://localhost:8089 and run the test