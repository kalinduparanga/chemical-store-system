"""
Settings and Audit Logs Router.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any, Optional
from app.models import UpdateSettingRequest
from app.auth import get_current_user, require_roles
from app.database import get_connection

router = APIRouter(prefix="/api/settings", tags=["Settings"])

@router.get("")
def list_settings():
    conn = get_connection()
    settings = conn.execute("SELECT key, value, description, updated_at FROM system_settings ORDER BY key").fetchall()
    conn.close()
    return [dict(s) for s in settings]

@router.post("", dependencies=[Depends(require_roles(["Administrator"]))])
def update_setting(req: UpdateSettingRequest, current_user: dict = Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE system_settings 
        SET value = ?, updated_at = CURRENT_TIMESTAMP
        WHERE key = ?
    """, (req.value, req.key))
    if cursor.rowcount == 0:
        cursor.execute("INSERT INTO system_settings (key, value) VALUES (?, ?)", (req.key, req.value))
    
    cursor.execute("""
        INSERT INTO audit_logs (user_name, action, transaction_type, record_id, details)
        VALUES (?, 'Settings Update', 'Setting', ?, ?)
    """, (current_user["full_name"], req.key, f"Updated setting '{req.key}' to '{req.value}'"))

    conn.commit()
    conn.close()
    return {"message": f"Setting '{req.key}' updated successfully"}

@router.get("/audit-logs", dependencies=[Depends(require_roles(["Administrator", "Storekeeper", "Viewer"]))])
def list_audit_logs(limit: int = 100):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, user_name, action, transaction_type, record_id, details, created_at
        FROM audit_logs
        ORDER BY id DESC LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows
