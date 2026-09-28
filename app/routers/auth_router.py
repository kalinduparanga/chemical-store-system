"""
Authentication and User Management Router.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any
from app.database import get_connection, verify_password, hash_password
from app.models import LoginRequest, UserResponse, CreateUserRequest
from app.auth import create_access_token, get_current_user, require_roles

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

@router.post("/login")
def login(req: LoginRequest):
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (req.username,)).fetchone()
    conn.close()

    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated"
        )

    token = create_access_token(user["id"], user["username"], user["role"], user["full_name"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "full_name": user["full_name"],
            "email": user["email"],
            "role": user["role"]
        }
    }

@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return current_user

@router.get("/users", dependencies=[Depends(require_roles(["Administrator"]))])
def list_users():
    conn = get_connection()
    users = conn.execute("SELECT id, username, full_name, email, role, is_active, created_at FROM users ORDER BY id").fetchall()
    conn.close()
    return [dict(u) for u in users]

@router.post("/users", dependencies=[Depends(require_roles(["Administrator"]))])
def create_user(req: CreateUserRequest):
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO users (username, password_hash, full_name, email, role, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (req.username, hash_password(req.password), req.full_name, req.email, req.role))
        conn.commit()
        return {"message": f"User '{req.username}' created successfully as {req.role}"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail="Username already exists or database error")
    finally:
        conn.close()
