"""
Authentication and Role-Based Access Control (RBAC) utilities.
Supports Administrator, Storekeeper, and Viewer roles.
"""

import hmac
import hashlib
import json
import base64
import time
from typing import Optional, List
from fastapi import HTTPException, Security, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.database import get_connection, verify_password

SECRET_KEY = "chemstore_jwt_secret_key_2026_super_secure"
security = HTTPBearer(auto_error=False)

def create_access_token(user_id: int, username: str, role: str, full_name: str) -> str:
    """Creates a base64 HMAC-signed session token containing user payload."""
    payload = {
        "uid": user_id,
        "sub": username,
        "role": role,
        "name": full_name,
        "exp": int(time.time()) + 86400 * 7 # 7 days
    }
    payload_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    encoded_payload = base64.urlsafe_b64encode(payload_bytes).decode('utf-8').rstrip('=')
    
    signature = hmac.new(SECRET_KEY.encode('utf-8'), encoded_payload.encode('utf-8'), hashlib.sha256).hexdigest()
    return f"{encoded_payload}.{signature}"

def decode_access_token(token: str) -> Optional[dict]:
    """Validates token HMAC signature and expiration."""
    try:
        parts = token.split('.')
        if len(parts) != 2:
            return None
        encoded_payload, signature = parts
        expected_sig = hmac.new(SECRET_KEY.encode('utf-8'), encoded_payload.encode('utf-8'), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            return None
        
        # Pad payload if needed
        pad_len = 4 - (len(encoded_payload) % 4)
        if pad_len != 4:
            encoded_payload += '=' * pad_len
        payload_bytes = base64.urlsafe_b64decode(encoded_payload)
        payload = json.loads(payload_bytes.decode('utf-8'))
        
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None

def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Security(security)):
    """Dependency that returns the current authenticated user dict."""
    if not credentials:
        # Fallback to default Storekeeper for seamless desktop usage if header is missing,
        # but check database for real user
        conn = get_connection()
        user = conn.execute("SELECT id, username, full_name, email, role, is_active FROM users WHERE role = 'Storekeeper' LIMIT 1").fetchone()
        conn.close()
        if user:
            return dict(user)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials"
        )
    
    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    conn = get_connection()
    user = conn.execute("SELECT id, username, full_name, email, role, is_active FROM users WHERE id = ?", (payload["uid"],)).fetchone()
    conn.close()
    
    if not user or not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is deactivated or not found"
        )
    return dict(user)

def require_roles(allowed_roles: List[str]):
    """Returns a dependency function verifying the user has one of the allowed roles."""
    def role_checker(current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Requires one of roles: {', '.join(allowed_roles)}. Your role is {current_user['role']}."
            )
        return current_user
    return role_checker
