# ASE Card Game Project

A multi-service card game platform for two players, featuring authentication, deck building, game engine, and history tracking. All services are containerized and orchestrated via Docker Compose.

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Running Tests](#running-tests)
  - [Unit Tests](#unit-tests)
  - [Integration Tests](#integration-tests)
  - [Performance Tests](#performance-tests)
- [Service Documentation](#service-documentation)
- [Game Rules](#game-rules)
- [Useful Commands](#useful-commands)
- [Troubleshooting](#troubleshooting)

## 🛠 Prerequisites

- **Docker**
- **Docker Compose**
- **Postman** (for running tests)
- **Locust** (for performance tests)

## 🚀 Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/ashleyspagnoli/ASE_project.git
cd ASE_project/src
```

### 2. Start All Services
```bash
docker compose up --build
```

This will start all microservices, accessible through the **API Gateway** on https://localhost:8443

### 4. Stop Services
```bash
docker compose down
```

## 🧪 Running Tests

### Unit Tests

Unit tests verify individual microservice functionality in isolation using mocked dependencies.

#### Collection Service Unit Tests
```bash
# 1. Build and run the test container
cd src
docker build -f collection/Dockerfile_test -t collection-test .
docker run -d -p 5006:5000 --name collection-test collection-test

# 2. Import and run the Postman collection
# Open Postman and import: docs/tests/collection_ut.postman_collection.json
# Run the entire collection

# 3. Cleanup
docker stop collection-test-container
docker rm collection-test-container
```

#### Game History Unit Tests
```bash
# 1. Build and run the test container
cd src
docker build -f game_history/Dockerfile_test -t history-test .
docker run -d -p 5007:5000 --name history-test history-test

# 2. Import and run the Postman collection
# Open Postman and import: docs/tests/game_history_ut.postman_collection.json
# Set base URL to: http://localhost:5007
# Run the entire collection

# 3. Cleanup
docker stop history-test-container
docker rm history-test-container
```

#### User Manager Unit Tests
```bash
# 1. Build and run the test container
cd src
docker build -f user-manager/Dockerfile_test -t user-manager-test .
docker run -d -p 5007:5000 --name user-manager-test user-manager-test

# 2. Import and run the Postman collection
# Open Postman and import: docs/tests/user_manager_ut.postman_collection.json
# Set base URL to: http://localhost:5004
# Run the entire collection

# 3. Cleanup
docker user-manager-test
docker rm user-manager-test
```

### Integration Tests

Integration tests verify the complete workflow across all microservices.

#### Prerequisites

Ensure all services are running:
```bash
cd src
docker compose up --build
```

#### Running Integration Tests
```bash
# 1. Import the integration test collection
# Open Postman and import: tests/integration.postman_collection.json

# 2. Verify environment variables are set correctly:
#    - gateway_url: https://localhost:8443
#    - User credentials will be auto-generated

# 3. Run the entire collection or specific test suites:
#    - IT-001: Complete Game Workflow - Happy Path
#    - IT-002: Authentication & Authorization Tests
#    - IT-003: Deck Validation Tests
#    - IT-004: Game History & Leaderboard Tests
#    - IT-005: Cross-Service Data Consistency Tests
#    - IT-007: Error Handling & Edge Cases

# Note: Some tests depend on previous tests in the sequence.
# Run tests in order for best results.
```

#### Quick Integration Test with Python Script

Alternatively, run a complete game simulation:
```bash
cd src
python test_match.py
```

This script will:
- Register two random users
- Create decks for both
- Match them together
- Play a complete game
- Display comprehensive game statistics

### Performance Tests

Performance tests use Locust to simulate multiple concurrent users and measure system behavior under load.

#### Setup
```bash
# Install Locust if not already installed
pip install locust
```

#### Running Performance Tests
```bash
# 1. Ensure all services are running
cd src
docker compose up -d

# 2. Start Locust
cd docs
locust

# 3. Open browser to http://localhost:8089

# 4. Configure the test:
#    - Number of users (e.g., 50)
#    - Spawn rate (e.g., 4 users/second)
#    - Host: https://localhost:8443

# 5. Click "Start"
```

#### Performance Test Scenarios

The performance test simulates realistic user behavior:

1. **User Registration** - Creates new user accounts
2. **Authentication** - Login and JWT token generation
3. **Deck Creation** - Valid deck building
4. **Matchmaking** - Queue joining and matching
5. **Gameplay** - Complete game sessions
6. **History Access** - Match history and leaderboard queries

## 📚 Service Documentation

Each microservice its own API documentation:

- **API Gateway**: See `docs/openapi.yml`
- **User Manager**: See `src/user-manager/openapi.yml`
- **Collection**: See `src/collection/openapi.yml`
- **Game Engine**: See `src/game_engine/static/openapi.yml`
- **Game History**: See `src/game_history/openapi.yml`

### Key Endpoints

#### Authentication
- `POST /users/register` - Register new user
- `POST /users/login` - Login and get JWT
- `POST /token` - OAuth2 token exchange

#### Collection Management
- `GET /collection/cards` - Get all available cards
- `GET /collection/cards/{card_id}` - Get card details
- `POST /collection/decks` - Create a new deck
- `GET /collection/decks` - Get user's decks
- `DELETE /collection/decks/{deck_id}` - Delete a deck

#### Game Engine
- `POST /game/match/join` - Join matchmaking queue
- `GET /game/match/status` - Check matchmaking status
- `POST /game/deck/{game_id}` - Select deck for game
- `GET /game/hand/{game_id}` - Get current hand
- `POST /game/play/{game_id}` - Play a card
- `GET /game/state/{game_id}` - Get game state

#### Game History
- `GET /history/matches` - Get match history (paginated)
- `GET /history/leaderboard` - Get global leaderboard (paginated)

## 🎮 Game Rules

See **`Game_Rules.md`** for complete game rules including:
- Deck building constraints
- Card values and hierarchy
- Suit priority
- Win conditions
- Example gameplay

## 👥 Contributors
Federico Fornaciari, Filippo Morelli, Marco Pernisco, Ashley Spagnoli

---

For detailed information about game rules, see `Game_Rules.md`.  
For detailed informations about the entire project, see `docs/main.tex`. 