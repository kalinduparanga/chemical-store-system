"""
Chemical Usage Router.
Handles usage transactions for TMTD, Zinc Oxide, Lauric Acid, DAHP, and Ammonia.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any
from app.models import UsageRequest
from app.auth import get_current_user, require_roles
from app.services.stock_service import StockService
from app.database import get_connection

router = APIRouter(prefix="/api/usage", tags=["Usage"])

@router.post("", dependencies=[Depends(require_roles(["Administrator", "Storekeeper"]))])
def record_usage(req: UsageRequest, current_user: dict = Depends(get_current_user)):
    return StockService.record_usage(req.dict(), current_user["full_name"])

@router.get("")
def list_usage():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            u.id, u.date, u.time, c.name as chemical_name, c.code as chemical_code,
            b.batch_number, b.expiry_date, l.name as storage_location_name,
            u.quantity_used, u.unit, u.purpose, u.supplier_customer_name,
            u.reference_number, u.remarks, u.operator_name, u.is_reversed, u.created_at
        FROM usage_transactions u
        JOIN chemicals c ON u.chemical_id = c.id
        JOIN batches b ON u.batch_id = b.id
        JOIN storage_locations l ON u.storage_location_id = l.id
        ORDER BY u.date DESC, u.time DESC, u.id DESC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows
