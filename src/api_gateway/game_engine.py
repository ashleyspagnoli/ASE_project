from fastapi import APIRouter, Request
from utils import forward_request


GAME_URL = 'http://game_engine:5000'  # URL interno del microservizio Game Engine

router = APIRouter()

# Matchmaking
@router.post("/match/join")
async def game_join(request: Request):
    URL = GAME_URL + '/match/join'
    return await forward_request(request, URL, body_data=None)

@router.get("/match/status")
async def game_status(request: Request):
    URL = GAME_URL + '/match/status'
    return await forward_request(request, URL, body_data=None)

# Gameplay
@router.post("/deck/{game_id}")
async def game_deck(game_id: str, request: Request):
    URL = f"{GAME_URL}/deck/{game_id}"
    return await forward_request(request, URL, body_data=await request.json(), is_json=True)

@router.get("/hand/{game_id}")
async def game_hand(game_id: str, request: Request):
    URL = f"{GAME_URL}/hand/{game_id}"
    return await forward_request(request, URL, body_data=None)

@router.post("/play/{game_id}")
async def game_play(game_id: str, request: Request):
    URL = f"{GAME_URL}/play/{game_id}"
    return await forward_request(request, URL, body_data=await request.json(), is_json=True)

@router.get("/state/{game_id}")
async def game_state(game_id: str, request: Request):
    URL = f"{GAME_URL}/state/{game_id}"
    return await forward_request(request, URL, body_data=None)