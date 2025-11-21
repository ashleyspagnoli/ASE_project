# ASE Card Game Project

This project is a multi-service card game platform for two players, featuring authentication, deck building, game engine, and history tracking. All services are containerized and orchestrated via Docker Compose.

## 🛠 Prerequisites
- Docker & Docker Compose
- (Optional) Python 3.10+ for local development

## 🚀 Quick Start (Recommended)

1. **Clone the repository**
   ```sh
   git clone https://github.com/ashleyspagnoli/ASE_project.git
   cd ASE_project_/src
   ```

2. **Build and start all services**
   ```sh
   docker compose up --build
   ```
   This will start:
   - user-manager (authentication)
   - collection (deck management)
   - game-engine (game logic)
   - game-history (match history)

3. **Access the services**
   - User Manager: https://localhost:5004
   - Collection: http://localhost:5003
   - Game Engine: http://localhost:5001
   - Game History: http://localhost:5002

## ⚙️ Environment Variables
Each service can be configured via environment variables. See the respective `Dockerfile` and `requirements.txt` for details.

## 🧪 Testing the Workflow
Use the provided Postman collection `game_workflow.postman_collection.json` for a complete game simulation:
- Register users
- Login and get JWTs
- Create decks
- Play a match

## 📝 Useful Endpoints
- **User Registration/Login:** `/users/register`, `/users/login`
- **Token Validation:** `/users/validate-token?token_str=<JWT>`
- **Deck Management:** `/collection/decks`
- **Game Engine:** `/game/connect`, `/game/matchmake`, `/game/deck/{game_id}`, `/game/play/{game_id}`
- **Game State:** `/game/state/{game_id}`

## 📚 Game Rules
See `Game_Rules.md` for detailed rules and examples.

## 🧹 Stopping and Cleaning Up
To stop all services:
```sh
docker compose down
```

---

For any issues, check the logs of each service container or ask for help!
