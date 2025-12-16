# ASE Card Game Project

A multi-service card game platform for two players, featuring authentication, deck building, game engine, and history tracking. All services are containerized and orchestrated via Docker Compose.

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Running the Client](#running-the-client)
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
- **Node.js & Newman** (for running tests via CLI: `npm install -g newman`)
- **Postman** (optional, for manual testing)
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

### 3. Stop Services
```bash
docker compose down
```

## 🖥️ Client

The project includes a Python-based Command Line Interface (CLI) client located in the `/client` directory. This client serves as the frontend for the game, communicating with the backend services via the API Gateway. It uses the `rich` and `questionary` libraries to provide an interactive terminal experience.

To run the client using Docker, execute the following command (Linux):
```bash
cd client/
docker build -t ase-client . --no-cache
docker run -it --rm \
  --add-host=host.docker.internal:host-gateway \
  -e API_GATEWAY_URL="https://host.docker.internal:8443/" \
  -e GATEWAY_CERT_PATH="./gateway_cert.pem" \
  ase-client
```
Ensure that the backend services are running before starting the client.

## 🧪 Running Tests

### Unit Tests

Unit tests verify individual microservice functionality in isolation using mocked dependencies.
They are executed using `newman` (Postman CLI) against the test containers.

#### Collection Service Unit Tests
```bash
# 1. Build and run the test container
cd src
docker build -f collection/Dockerfile_test -t collection-test .
docker run -d -p 5000:5000 --name collection-test collection-test

# 2. Run the tests
newman run ../docs/tests/collection_ut.postman_collection.json --insecure

# 3. Cleanup
docker stop collection-test
docker rm collection-test
```

#### Game History Unit Tests
```bash
# 1. Build and run the test container
cd src
docker build -f game_history/Dockerfile_test -t history-test .
docker run -d -p 5000:5000 --name history-test history-test

# 2. Run the tests
newman run ../docs/tests/game_history_ut.postman_collection.json --insecure

# 3. Cleanup
docker stop history-test
docker rm history-test
```

#### User Manager Unit Tests
```bash
# 1. Build and run the test container
cd src
docker build -f user-manager/Dockerfile_test -t user-manager-test .
docker run -d -p 5004:5000 --name user-manager-test user-manager-test

# 2. Run the tests
newman run ../docs/tests/user_manager_ut.postman_collection.json --insecure

# 3. Cleanup
docker stop user-manager-test
docker rm user-manager-test
```

### Integration Tests

Integration tests verify the complete workflow across all microservices.

#### Prerequisites

Ensure all services are running:
```bash
cd src
docker compose up --build -d
```

#### Running Integration Tests
```bash
# From the project root directory:
newman run docs/tests/integration.postman_collection.json --insecure
```

The integration test suite covers:
- **IT-001**: Complete Game Workflow - Happy Path
- **IT-002**: Authentication & Authorization Tests
- **IT-003**: Deck Validation Tests
- **IT-004**: Game History & Leaderboard Tests
- **IT-005**: Cross-Service Data Consistency Tests
- **IT-007**: Error Handling & Edge Cases
- **IT-008**: User Editor Integration
- **IT-009**: Complete Game Playthrough
- **IT-010**: Complete Game Until Winner
- **IT-011**: Leaderboard and Statistics

#### Quick Integration Test with Python Script

Alternatively, run a complete game simulation:
```bash
# From the project root directory:
python docs/tests/test_match.py
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
docker compose up --build -d

# 2. Start Locust (from project root)
locust -f docs/locustfile.py

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


## 👥 Contributors
Federico Fornaciari, Filippo Morelli, Marco Pernisco, Ashley Spagnoli
