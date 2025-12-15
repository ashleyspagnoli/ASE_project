from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from typing import Optional
from utils import forward_request

USER_URL = 'https://user-manager:5000'

router = APIRouter()

# --- Pydantic Models ---
class UserLogin(BaseModel):
    username: str = Field(..., example="user123")
    password: str = Field(..., example="strongpassword")

class UserRegister(BaseModel):
    username: str = Field(..., example="newuser")
    password: str = Field(..., min_length=3, example="newstrongpassword")
    email: Optional[str] = Field(None, example="aseproject@unipi.it")

# --- Routes ---
# Note: We remove "/users" from the path because we will add it as a prefix in main.py

@router.post("/login", tags=["Auth"])
async def proxy_json_login(user_data: UserLogin, request: Request):
    URL = USER_URL + '/users/login'
    body = await request.json()
    return await forward_request(request, URL, body_data=user_data.model_dump(), is_json=True)

@router.post("/register", tags=["Authentication and Users"])
async def proxy_register(user_data: UserRegister, request: Request):
    URL = USER_URL + '/users/register' 
    return await forward_request(request, URL, body_data=user_data.model_dump(), is_json=True)

@router.post("/token", tags=["Authentication and Users"])
async def proxy_token(request: Request):
    URL = USER_URL + '/users/token' 
    form_data = await request.form()
    return await forward_request(request, URL, body_data=dict(form_data), is_json=False)

