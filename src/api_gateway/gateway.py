import users
import game_engine
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
