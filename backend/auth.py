from fastapi import APIRouter, HTTPException, status, Depends, Response, Request, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
import re
import os
import jwt
import logging
from datetime import datetime, timezone
from backend.client import supabase

# Environment variables
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
# SUPABASE_URL and KEY are handled in backend.client
ENV = os.getenv("FLASK_ENV", "development") # Keeping compat with user snippet

router = APIRouter(prefix="/api")

# --- Utilities ---

_email_re = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def is_valid_email(email: str) -> bool:
    return bool(email and _email_re.match(email))

# --- Pydantic Models ---

class UserRegister(BaseModel):
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

# --- Dependencies ---

async def get_current_user(request: Request, authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """
    Validate Supabase JWT (from Authorization header or sb-access-token cookie)
    and return user claims dict.
    """
    token = None
    
    # Debug logging
    logging.info(f"Headers: {request.headers}")
    logging.info(f"Cookies: {request.cookies}")

    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
    else:
        token = request.cookies.get("sb-access-token")

    if not token:
        logging.warning("No token found in Authorization header or cookies")
        raise HTTPException(status_code=401, detail="Missing token")

    if not SUPABASE_JWT_SECRET:
        logging.warning("SUPABASE_JWT_SECRET not set; cannot verify token")
        raise HTTPException(status_code=500, detail="Server misconfiguration")

    try:
        # Verify token
        payload = jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"], audience="authenticated")
        user_id = payload.get("sub")
        email = payload.get("email")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        
        # Construct user dict similar to user's snippet
        return {"id": user_id, "email": email, **payload}

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        logging.exception("Token verification failed")
        raise HTTPException(status_code=401, detail="Invalid token")

# --- Routes ---

@router.post("/register")
async def register(user: UserRegister):
    email = user.email.strip().lower()
    password = user.password

    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    try:
        # Assuming backend.client.supabase is initialized with appropriate key (anon)
        response = supabase.auth.sign_up({"email": email, "password": password})
        
        if response.user and response.user.id:
             return {"id": str(response.user.id), "email": response.user.email}
        else:
             # This case might happen if email confirmation is required and implicit return is different
             # or if upstream error not raised.
             if response.user:
                  return {"id": str(response.user.id), "email": response.user.email}
             raise HTTPException(status_code=500, detail="Supabase did not return user id")

    except Exception as e:
        # Check for specific error messages if possible, strict string matching on Exception might be fragile
        # but following user snippet logic:
        err_str = str(e)
        if "already been registered" in err_str:
            raise HTTPException(status_code=409, detail="A user with this email address has already been registered")
        logging.exception("Supabase admin user creation failed")
        raise HTTPException(status_code=502, detail=f"Upstream error: {err_str}")

@router.post("/login")
async def login(user: UserLogin, response: Response):
    email = user.email.strip().lower()
    password = user.password

    try:
        auth_response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid credentials: {str(e)}")

    if not auth_response.session:
        raise HTTPException(status_code=500, detail="No session returned")

    access_token = auth_response.session.access_token
    refresh_token = auth_response.session.refresh_token
    
    secure_flag = ENV == "production"
    
    # Set HttpOnly cookies
    response.set_cookie(
        key="sb-access-token", 
        value=access_token, 
        httponly=True, 
        secure=secure_flag, 
        samesite="lax", 
        max_age=3600 # 1 hour
    )
    if refresh_token:
        response.set_cookie(
            key="sb-refresh-token", 
            value=refresh_token, 
            httponly=True, 
            secure=secure_flag, 
            samesite="lax", 
            max_age=604800 # 7 days
        )

    return {"msg": "ok", "user": {"id": auth_response.user.id, "email": auth_response.user.email}}

@router.post("/refresh")
async def refresh(request: Request, response: Response):
    refresh_token = request.cookies.get("sb-refresh-token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    try:
        # Note: supabase-py client handles session refreshing usually via methods that wrap calls,
        # or explicit refresh_session.
        auth_response = supabase.auth.refresh_session(refresh_token)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Refresh failed: {str(e)}")

    if not auth_response.session:
        raise HTTPException(status_code=500, detail="No session returned")

    access_token = auth_response.session.access_token
    new_refresh_token = auth_response.session.refresh_token

    secure_flag = ENV == "production"

    response.set_cookie(
        key="sb-access-token",
        value=access_token,
        httponly=True,
        secure=secure_flag,
        samesite="lax",
        max_age=3600
    )
    if new_refresh_token:
        response.set_cookie(
            key="sb-refresh-token",
            value=new_refresh_token,
            httponly=True,
            secure=secure_flag,
            samesite="lax",
            max_age=604800
        )
    
    return {"msg": "ok"}

@router.get("/me")
async def me(user: Dict[str, Any] = Depends(get_current_user)):
    return {
        "id": user.get("id"),
        "email": user.get("email"),
        "user_metadata": user.get("user_metadata", {})
    }

@router.post("/logout")
async def logout(response: Response, user: Dict[str, Any] = Depends(get_current_user)):
    # Clear cookies
    response.delete_cookie("sb-access-token")
    response.delete_cookie("sb-refresh-token")
    
    # Ideally we should also sign out from Supabase to invalidate the session on server side
    try:
        supabase.auth.sign_out() 
    except:
        pass # Ignore errors during sign out
        
    return {"msg": "ok"}

@router.post("/google_oauth")
async def google_oauth():
    try:
        # The user snippet returns jsonify({"url": resp.url})
        # supabase-py sign_in_with_oauth returns `OAuthResponse` which has `url`.
        resp = supabase.auth.sign_in_with_oauth({"provider": "google"})
        if hasattr(resp, 'url') and resp.url:
             return {"url": resp.url}
        # Fallback if the response structure is different (older versions returned dict sometimes)
        return {"url": resp.url}
    except Exception as e:
        logging.exception("Google OAuth failed")
        raise HTTPException(status_code=500, detail=f"OAuth error: {str(e)}")