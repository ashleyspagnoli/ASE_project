from fastapi import APIRouter, Request
from utils import forward_request

HISTORY_URL = 'http://game_history:5000'

router = APIRouter()

@router.post('/addmatch', tags=['History'])
async def history_add_match(request: Request):
    URL = HISTORY_URL + '/addmatch'
    body = await request.json()
    return await forward_request(request, URL, body_data=body, is_json=True)

@router.get('/matches', tags=['History'])
async def history_matches(request: Request):
    URL = HISTORY_URL + '/matches'
    return await forward_request(request, URL, body_data=None)

@router.get('/leaderboard', tags=['History'])
async def history_leaderboard(request: Request):
    URL = HISTORY_URL + '/leaderboard'
    return await forward_request(request, URL, body_data=None)
