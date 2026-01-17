import logging
import os
import re
from typing import Any, Dict, Optional


from dotenv import load_dotenv
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.client import supabase

load_dotenv()

# Environment variables
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
if not SUPABASE_JWT_SECRET:
    logging.warning("SUPABASE_JWT_SECRET is not set. JWT verification will rely on Supabase API.")

# SUPABASE_URL and KEY are handled in backend.client
ENV = os.getenv("ENV", "development") # Keeping compat with user snippet

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
    logging.debug("Checking for authentication token")
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
    else:
        token = request.cookies.get("sb-access-token")

    if not token:
        logging.warning("No token found in Authorization header or cookies")
        raise HTTPException(status_code=401, detail="Missing token")

    try:
        # Verify token using Supabase Auth API
        # This ensures the token is valid, not revoked, and fresh
        user_response = supabase.auth.get_user(token)
        user = user_response.user
        
        if not user:
             raise HTTPException(status_code=401, detail="Invalid token")

        # Construct user dict
        return {
            "id": user.id, 
            "email": user.email, 
            "user_metadata": user.user_metadata,
            # Add other necessary fields if needed by downstream
        }

    except Exception as e:
        logging.error(f"Token verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")

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
async def login(user: UserLogin):
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
    response=JSONResponse({"message": "Login successful"})
    access_token = auth_response.session.access_token
    refresh_token = auth_response.session.refresh_token
    
    secure_flag = ENV == "production"
    # SameSite must be None for cross-site cookie access (like OAuth), but None requires Secure.
    samesite_val = "none" if secure_flag else "lax"
    
    # Set HttpOnly cookies
    response.set_cookie(
        key="sb-access-token", 
        value=access_token, 
        httponly=True, 
        secure=secure_flag, 
        samesite=samesite_val, 
        max_age=3600, # 1 hour
        path="/"
    )
    if refresh_token:
        response.set_cookie(
            key="sb-refresh-token", 
            value=refresh_token, 
            httponly=True, 
            secure=secure_flag, 
            samesite=samesite_val, 
            max_age=604800, # 7 days
            path="/"
        )
        
    if not auth_response.user:
        raise HTTPException(status_code=500, detail="No user returned")
        
    return response
    
@router.post("/refresh")
async def refresh(request: Request):
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
        
    response = JSONResponse({"message": "Refresh successful"})
    access_token = auth_response.session.access_token
    new_refresh_token = auth_response.session.refresh_token

    secure_flag = ENV == "production"
    samesite_val = "none" if secure_flag else "lax"

    response.set_cookie(
        key="sb-access-token",
        value=access_token,
        httponly=True,
        secure=secure_flag,
        samesite=samesite_val,
        max_age=3600,
        path="/"
    )
    if new_refresh_token:
        response.set_cookie(
            key="sb-refresh-token",
            value=new_refresh_token,
            httponly=True,
            secure=secure_flag,
            samesite=samesite_val,
            max_age=604800,
            path="/"
            )
    return response
    
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
        if hasattr(resp, 'url'):
             return {"url": resp.url}
        raise HTTPException(status_code=500, detail="OAuth response missing URL")
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Google OAuth failed")
        raise HTTPException(status_code=500, detail="OAuth initialization failed") from e