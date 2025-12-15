import collection, users, game_engine, history, usereditor
from fastapi import FastAPI


app = FastAPI(
    title="Api Gateway Client Side", 
    description="Handles user registration, JWT login, and core user data management.",
    version="1.0.0"
)

# User manager routes
app.include_router(users.router, prefix="/users")
# Game Engine routes
app.include_router(game_engine.router, prefix="/game", tags=["Game"])
# History routes
app.include_router(history.router, prefix="/history", tags=["History"])
# Collection routes
app.include_router(collection.router, prefix="/collection", tags=["Collection"])
# User editor routes
app.include_router(usereditor.router, prefix="/userseditor", tags=["User Editing"])
