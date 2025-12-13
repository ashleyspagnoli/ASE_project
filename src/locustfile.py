from locust import HttpUser, task, between, SequentialTaskSet
import random
import urllib3

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

        self._register()
        self._login()
        self._ensure_deck()

    # -----------------------
    # Auth
    # -----------------------

    def _register(self):
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
        ) as response:
            if response.status_code in (201, 400):  # 400 = user already exists
                response.success()
            else:
                response.failure(f"Register failed ({response.status_code})")

    def _login(self):
        with self.client.post(
            "/users/login",
            json={
                "username": self.username,
                "password": self.password,
            },
            verify=False,
            name="/users/login",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                self.token = response.json().get("token")
                response.success()
            else:
                response.failure(f"Login failed ({response.status_code})")
                self.interrupt()

    # -----------------------
    # Deck setup
    # -----------------------

    def _ensure_deck(self):
        headers = {"Authorization": f"Bearer {self.token}"}

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
        ) as response:
            if response.status_code == 201:
                response.success()
            else:
                response.failure(f"Deck creation failed ({response.status_code})")

    # -----------------------
    # Matchmaking
    # -----------------------

    @task
    def play_match(self):
        if not self.token:
            return

        headers = {"Authorization": f"Bearer {self.token}"}

        # Join matchmaking
        with self.client.post(
            "/game/match/join",
            headers=headers,
            verify=False,
            name="/game/match/join",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure("Failed to join matchmaking")
                return

            data = response.json()
            response.success()

            if data.get("status") != "matched":
                return

            self.game_id = data.get("game_id")

        self._select_deck()
        self._play_turns()

    # -----------------------
    # Deck selection
    # -----------------------

    def _select_deck(self):
        headers = {"Authorization": f"Bearer {self.token}"}

        with self.client.post(
            f"/game/deck/{self.game_id}",
            headers=headers,
            json={"deck_slot": self.deck_slot},
            verify=False,
            name="/game/deck",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 401:  # Not my turn
                response.success()
            else:
                response.failure(
                    f"Unexpected Select Deck status {response.status_code}"
                )

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

        self.client.get(
            "/history/matches?page=0",
            headers=headers,
            verify=False,
            name="/history/matches",
        )

        self.client.get(
            "/history/leaderboard?page=0",
            verify=False,
            name="/history/leaderboard",
        )


# ===========================
# User types
# ===========================

class QuickUser(HttpUser):
    tasks = [GameUserFlow]
    wait_time = between(1, 3)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client.verify = False


class NormalUser(HttpUser):
    tasks = [GameUserFlow]
    wait_time = between(3, 7)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client.verify = False


class SlowUser(HttpUser):
    tasks = [GameUserFlow]
    wait_time = between(5, 15)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client.verify = False


# ===========================
# Usage
# ===========================

# 1) If you don't have locust installed
#   1.1) Create the venv if you don't have it yet: python -m venv proj_env
#   1.2) Activate the venv: 

#   1.3) Install locust: pip install locust
# 2) Run locust: locust
# 3) Browse to http://localhost:8089 and run the test