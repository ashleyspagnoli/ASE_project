from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from typing import Optional
from utils import forward_request

USER_URL = 'https://user-editor:5000'

router = APIRouter()

# --- Pydantic Models ---

class UserModifyUsername(BaseModel):
    new_username: str = Field(..., example="updateduser")

class UserModifyPassword(BaseModel):
    old_password: str = Field(..., example="oldpassword")
    new_password: str = Field(..., min_length=3, example="newstrongpassword")

class UserModifyEmail(BaseModel):
    old_email: str = Field(..., example="aseproject@unipi.it")
    new_email: str = Field(..., example="aseproject2@unipi.it")   
# --- Routes ---
# Note: We remove "/users" from the path because we will add it as a prefix in main.py


@router.patch("/change-username", tags=["User Editing"])
async def proxy_change_username(data:UserModifyUsername,request: Request):
    URL = USER_URL + '/change-username' 
    return await forward_request(request, URL, body_data=data.model_dump())

@router.patch("/change-password", tags=["User Editing"])
async def proxy_change_password(data:UserModifyPassword,request: Request):
    URL = USER_URL + '/change-password' 
    return await forward_request(request, URL, body_data=data.model_dump())

@router.patch("/change-email", tags=["User Editing"])
async def proxy_change_email(data:UserModifyEmail,request: Request):
    URL = USER_URL + '/change-email' 
    return await forward_request(request, URL, body_data=data.model_dump())

@router.get("/view-data", tags=["User Editing"])
async def proxy_get_username_email(request: Request):
    URL = USER_URL + '/view-data' 
    return await forward_request(request, URL, is_json=False)
