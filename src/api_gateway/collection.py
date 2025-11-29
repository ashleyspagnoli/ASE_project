from fastapi import APIRouter, Request
from utils import forward_request

COLLECTION_URL = 'http://collection:5000'

router = APIRouter()

@router.get('/collection/cards', tags=['Collection'])
async def get_collection(request: Request):
    URL = COLLECTION_URL + '/collection/cards'
    return await forward_request(request, URL, body_data=None)

@router.get('/collection/cards/{card_id}', tags=['Collection'])
async def get_card(card_id: str, request: Request):
    URL = COLLECTION_URL + f'/collection/cards/{card_id}'
    return await forward_request(request, URL, body_data=None)

@router.get('/collection/decks', tags=['Collection'])
async def get_decks(request: Request):
    URL = COLLECTION_URL + '/collection/decks'
    return await forward_request(request, URL, body_data=None)

@router.post('/collection/decks', tags=['Collection'])
async def create_deck(request: Request):
    URL = COLLECTION_URL + '/collection/decks'
    body = await request.json()
    return await forward_request(request, URL, body_data=body, is_json=True)

@router.delete('/collection/decks/{deck_id}', tags=['Collection'])
async def delete_deck(deck_id: str, request: Request):
    URL = COLLECTION_URL + f'/collection/decks/{deck_id}'
    return await forward_request(request, URL, body_data=None)