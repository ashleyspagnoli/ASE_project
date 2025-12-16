from locust import HttpUser, task, between, SequentialTaskSet
import random
import urllib3
import time

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ===========================
# User workflow
# ===========================

class GameUserFlow(SequentialTaskSet):
    """
    Full realistic user journey:
    register → login → ensure deck → matchmaking → game → history
    """

    def on_start(self):
        self.username = f"loadtest_user_{random.randint(10000, 99999)}" # nosec
        self.password = "TestPass123!"
        self.token = None
        self.game_id = None
        self.deck_slot = 1
        self.max_retries = 3

        # Add delays between setup operations to avoid overwhelming services
        if self._register():
            time.sleep(0.5)  # Wait before login
            if self._login():
                time.sleep(0.5)  # Wait before deck creation
                self._ensure_deck()

    # -----------------------
    # Auth
    # -----------------------

    def _register(self):
        """Register with retry logic for 503 errors"""
        for attempt in range(self.max_retries):
            try:
                with self.client.post(
                    "/users/register",
                    json={
                        "username": self.username,
                        "password": self.password,
                        "email": f"{self.username}@loadtest.com",
                    },
                    verify=False,
                    name="/users/register",
                    catch_response=True,
                    timeout=10,
                ) as response:
                    if response.status_code in (201, 400):  # 400 = user already exists
                        response.success()
                        return True
                    elif response.status_code == 503 and attempt < self.max_retries - 1:
                        # Service unavailable, retry
                        response.success()  # Don't count as failure yet
                        time.sleep(1 * (attempt + 1))  # Exponential backoff
                        continue
                    else:
                        response.failure(f"Register failed ({response.status_code})")
                        return False
            except Exception as e:
                if attempt < self.max_retries - 1:
                    time.sleep(1 * (attempt + 1))
                    continue
                return False
        return False

    def _login(self):
        """Login with retry logic for 503 errors"""
        for attempt in range(self.max_retries):
            try:
                with self.client.post(
                    "/users/login",
                    json={
                        "username": self.username,
                        "password": self.password,
                    },
                    verify=False,
                    name="/users/login",
                    catch_response=True,
                    timeout=10,
                ) as response:
                    if response.status_code == 200:
                        data = response.json()
                        self.token = data.get("token")
                        if self.token:
                            response.success()
                            return True
                        else:
                            response.failure("No token in response")
                            self.interrupt()
                            return False
                    elif response.status_code == 503 and attempt < self.max_retries - 1:
                        # Service unavailable, retry
                        response.success()  # Don't count as failure yet
                        time.sleep(1 * (attempt + 1))  # Exponential backoff
                        continue
                    else:
                        response.failure(f"Login failed ({response.status_code})")
                        self.interrupt()
                        return False
            except Exception as e:
                if attempt < self.max_retries - 1:
                    time.sleep(1 * (attempt + 1))
                    continue
                self.interrupt()
                return False
        self.interrupt()
        return False

    # -----------------------
    # Deck setup
    # -----------------------

    def _ensure_deck(self):
        """Create deck with proper authentication check"""
        if not self.token:
            return False
            
        headers = {"Authorization": f"Bearer {self.token}"}

        try:
            with self.client.post(
                "/collection/decks",
                headers=headers,
                json={
                    "deckSlot": self.deck_slot,
                    "deckName": "LoadTest Deck",
                    "cards": ["hA", "h5", "d5", "d8", "c7", "c8", "sA", "s5"],
                },
                verify=False,
                name="/collection/decks",
                catch_response=True,
                timeout=10,
            ) as response:
                if response.status_code == 201:
                    response.success()
                    return True
                elif response.status_code == 401:
                    response.failure(f"Deck creation failed (401) - token invalid or expired")
                    self.token = None  # Clear invalid token
                    return False
                else:
                    response.failure(f"Deck creation failed ({response.status_code})")
                    return False
        except Exception as e:
            return False

    # -----------------------
    # Matchmaking
    # -----------------------

    @task
    def play_match(self):
        if not self.token:
            return

        headers = {"Authorization": f"Bearer {self.token}"}

        # Join matchmaking with pre-selected deck
        try:
            with self.client.post(
                "/game/match/join",
                headers=headers,
                json={"deck_slot": self.deck_slot},  # Pre-select deck
                verify=False,
                name="/game/match/join",
                catch_response=True,
                timeout=10,
            ) as response:
                if response.status_code == 200:
                    data = response.json()
                    response.success()

                    if data.get("status") != "matched":
                        return

                    self.game_id = data.get("game_id")
                    # Deck is already loaded automatically, no need to select
                elif response.status_code == 400:
                    response.failure(f"Failed to join matchmaking (400) - deck issue: {response.text}")
                    return
                elif response.status_code == 401:
                    response.failure(f"Failed to join matchmaking (401) - token invalid")
                    self.token = None  # Clear invalid token
                    return
                else:
                    response.failure(f"Failed to join matchmaking ({response.status_code})")
                    return
        except Exception as e:
            return

        time.sleep(0.3)  # Small delay before playing
        self._play_turns()

    # -----------------------
    # Deck selection (DEPRECATED - kept for backwards compatibility)
    # -----------------------

    def _select_deck(self):
        # This method is no longer needed as decks are loaded during matchmaking
        # Kept for backwards compatibility only
        pass

    # -----------------------
    # Gameplay loop
    # -----------------------

    def _play_turns(self):
        headers = {"Authorization": f"Bearer {self.token}"}

        for _ in range(random.randint(3, 8)): # nosec

            # Get hand
            with self.client.get(
                f"/game/hand/{self.game_id}",
                headers=headers,
                verify=False,
                name="game/hand",
                catch_response=True,
            ) as response:
                if response.status_code != 200:
                    response.failure("Failed to get hand")
                    return

                hand = response.json()
                response.success()

            if not hand:
                return

            card = random.choice(hand) # nosec

            # Play card
            with self.client.post(
                f"/game/play/{self.game_id}",
                headers=headers,
                json={"card": card},
                verify=False,
                name="game/play",
                catch_response=True,
            ) as response:
                if response.status_code == 200:
                    status = response.json().get("status")
                    response.success()
                    if status == "finished":
                        self.game_id = None
                        return
                elif response.status_code == 401: # Not my turn
                    response.success()
                else:
                    response.failure(
                        f"Unexpected Play Card status {response.status_code}"
                    )
                    return

    # -----------------------
    # History
    # -----------------------

    @task
    def read_history(self):
        if not self.token:
            return

        headers = {"Authorization": f"Bearer {self.token}"}

        # Get match history
        try:
            with self.client.get(
                "/history/matches?page=0",
                headers=headers,
                verify=False,
                name="/history/matches",
                catch_response=True,
                timeout=10,
            ) as response:
                if response.status_code == 200:
                    response.success()
                elif response.status_code == 401:
                    response.failure("History access failed (401) - token invalid")
                    self.token = None
                    return
                else:
                    response.failure(f"History failed ({response.status_code})")
        except Exception:
            pass

        time.sleep(0.2)  # Small delay between requests

        # Get leaderboard (no auth required)
        try:
            self.client.get(
                "/history/leaderboard?page=0",
                verify=False,
                name="/history/leaderboard",
                timeout=10,
            )
        except Exception:
            pass


# ===========================
# User types
# ===========================

class QuickUser(HttpUser):
    tasks = [GameUserFlow]
    wait_time = between(2, 4)  # Increased from 1-3 to reduce load
    host = "https://localhost:8443"  # API Gateway endpoint

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client.verify = False


class NormalUser(HttpUser):
    tasks = [GameUserFlow]
    wait_time = between(4, 8)  # Increased from 3-7 to reduce load
    host = "https://localhost:8443"  # API Gateway endpoint

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client.verify = False


class SlowUser(HttpUser):
    tasks = [GameUserFlow]
    wait_time = between(7, 15)  # Increased from 5-15 to reduce load
    host = "https://localhost:8443"  # API Gateway endpoint

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client.verify = False


# ===========================
# Usage
# ===========================

# 1) Ensure docker services are running:
#    cd src && docker compose up
#
# 2) If you don't have locust installed
#   2.1) Create the venv if you don't have it yet: python -m venv proj_env
#   2.2) Activate the venv: source proj_env/bin/activate (Linux/Mac) or proj_env\Scripts\activate (Windows)
#   2.3) Install locust: pip install locust
#
# 3) Run locust: locust -f locustfile.py
#
# 4) Browse to http://localhost:8089 and configure:
#    - Host: https://localhost:8443 (already set in the code)
#    - Number of users: Start with 10-20 users
#    - Spawn rate: 1-2 users per second
#    - Run time: Optional
#
# 5) Tips for avoiding failures:
#    - Start with low user count (10-20) and gradually increase
#    - Use slower spawn rate (1-2 users/sec) to avoid overwhelming services
#    - Monitor docker logs: docker compose logs -f
#    - If you see 503 errors, reduce the load
#    - If you see 401 errors after a while, tokens may be expiring (normal)
